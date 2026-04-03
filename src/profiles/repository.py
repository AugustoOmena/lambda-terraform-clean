from shared.database import get_supabase_client
from shared.supabase_utils import role_from_auth_user_obj
from schemas import ProfileFilter

# Limite de usuários auth para fallback (evita loop longo em contas grandes).
_AUTH_LIST_MAX_USERS = 5000


class ProfileRepository:
    """Repository para operações no banco de dados (tabela profiles)."""
    
    def __init__(self):
        self.db = get_supabase_client()
    
    def list_all(self, filters: ProfileFilter) -> dict:
        """
        Lista perfis com filtros, paginação e ordenação.
        
        Retorna:
            { "data": [...], "count": N }
        """
        # 1. Inicia query base
        query = self.db.table("profiles").select("*", count="exact")
        
        # 2. Aplica filtros
        if filters.email:
            # Busca parcial case-insensitive
            query = query.ilike("email", f"%{filters.email}%")
        
        if filters.role:
            # Filtro exato por role
            query = query.eq("role", filters.role)
        
        # 3. Aplica ordenação
        sort_mapping = {
            "newest": ("created_at", False),  # (coluna, ascending)
            "role_asc": ("role", True),
            "role_desc": ("role", False),
        }
        
        sort_column, ascending = sort_mapping.get(filters.sort, ("created_at", False))
        # Supabase order: order(column, desc=True/False)
        query = query.order(sort_column, desc=not ascending)
        
        # 4. Aplica paginação usando range
        # Supabase range é 0-indexed e inclusivo: range(0, 9) retorna 10 itens
        start = (filters.page - 1) * filters.limit
        end = start + filters.limit - 1
        query = query.range(start, end)
        
        # 5. Executa
        response = query.execute()
        data = response.data or []
        count = response.count

        if not data and (count is None or count == 0):
            if (not filters.email and not filters.role) or self._profiles_table_has_no_rows():
                fallback = self._list_all_from_auth_admin(filters)
                if fallback is not None:
                    return fallback

        return {
            "data": data,
            "count": count,
        }

    def _profiles_table_has_no_rows(self) -> bool:
        """True se não há linhas visíveis em profiles (tabela vazia ou RLS bloqueou tudo)."""
        try:
            r = self.db.table("profiles").select("id", count="exact").limit(1).execute()
            return (r.count or 0) == 0
        except Exception:
            return False

    def _auth_user_to_row(self, u: object) -> dict:
        """Converte User do GoTrue para o mesmo formato da tabela profiles."""
        uid = getattr(u, "id", None)
        email = getattr(u, "email", None)
        created_at = getattr(u, "created_at", None)
        role = role_from_auth_user_obj(u) or "user"
        return {
            "id": str(uid) if uid is not None else "",
            "email": email,
            "role": role,
            "created_at": created_at,
        }

    def _list_all_from_auth_admin(self, filters: ProfileFilter) -> dict | None:
        """Quando ``profiles`` está vazio (RLS/anon ou dados só em auth), lista via Auth Admin."""
        try:
            all_users: list = []
            page = 1
            page_size = 200
            while len(all_users) < _AUTH_LIST_MAX_USERS:
                batch = self.db.auth.admin.list_users(page=page, per_page=page_size)
                if not batch:
                    break
                all_users.extend(batch)
                if len(batch) < page_size:
                    break
                page += 1
        except Exception:
            return None

        rows = [self._auth_user_to_row(u) for u in all_users]

        if filters.email:
            fe = filters.email.lower()
            rows = [r for r in rows if r.get("email") and fe in (r["email"] or "").lower()]

        if filters.role:
            rows = [r for r in rows if r.get("role") == filters.role]

        if filters.sort == "newest":
            rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        elif filters.sort == "role_asc":
            rows.sort(key=lambda r: (r.get("role") or "").lower())
        elif filters.sort == "role_desc":
            rows.sort(key=lambda r: (r.get("role") or "").lower(), reverse=True)
        else:
            rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)

        total = len(rows)
        start = (filters.page - 1) * filters.limit
        end = start + filters.limit
        page_rows = rows[start:end]

        return {"data": page_rows, "count": total}
    
    def update(self, profile_id: str, data: dict) -> dict:
        """
        Atualiza um perfil.
        
        Args:
            profile_id: UUID do perfil
            data: Dict com campos a atualizar (email, role)
        
        Returns:
            Perfil atualizado
        """
        # Remove campos None para não sobrescrever com null
        clean_data = {k: v for k, v in data.items() if v is not None}
        
        if not clean_data:
            raise ValueError("Nenhum campo para atualizar")
        
        response = self.db.table("profiles").update(clean_data).eq("id", profile_id).execute()
        
        if not response.data:
            raise Exception(f"Perfil {profile_id} não encontrado ou não foi atualizado")
        
        return response.data[0]
    
    def delete(self, profile_id: str) -> bool:
        """
        Remove um perfil.
        
        Args:
            profile_id: UUID do perfil
        
        Returns:
            True se removido com sucesso
        """
        response = self.db.table("profiles").delete().eq("id", profile_id).execute()
        
        if not response.data:
            raise Exception(f"Perfil {profile_id} não encontrado ou não foi removido")
        
        return True
    
    def get_by_id(self, profile_id: str) -> dict:
        """
        Busca um perfil por ID.
        
        Args:
            profile_id: UUID do perfil
        
        Returns:
            Dict com dados do perfil ou None se não encontrado
        """
        response = self.db.table("profiles").select("*").eq("id", profile_id).execute()
        return response.data[0] if response.data else None
