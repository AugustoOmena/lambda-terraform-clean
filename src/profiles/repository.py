from shared.database import get_supabase_client
from schemas import ProfileFilter


class ProfileRepository:
    """Repository para operações no banco de dados (tabela profiles)."""
    
    def __init__(self):
        self.db = get_supabase_client()
    
    def list_all(
        self,
        filters: ProfileFilter,
        authorization_header: str | None = None,
        admin_user_id: str | None = None,
    ) -> dict:
        """
        Lista perfis com filtros, paginação e ordenação.
        
        Retorna:
            { "data": [...], "count": N }
        """
        if admin_user_id:
            rpc_result = self._list_all_via_rpc(filters, admin_user_id)
            if rpc_result is not None:
                return rpc_result

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
        count = response.count or 0
        if data:
            return {"data": data, "count": count}

        return {
            "data": data,
            "count": count,  # Total de registros (sem paginação)
        }

    def _list_all_via_rpc(
        self,
        filters: ProfileFilter,
        admin_user_id: str,
    ) -> dict | None:
        try:
            response = self.db.rpc(
                "backoffice_list_profiles",
                {
                    "p_admin_user_id": admin_user_id,
                    "p_page": filters.page,
                    "p_limit": filters.limit,
                    "p_email": filters.email,
                    "p_role": filters.role,
                    "p_sort": filters.sort,
                },
            )
            rows = response.data or []
            total = int(rows[0]["total_count"]) if rows else 0
            data = []
            for row in rows:
                item = dict(row)
                item.pop("total_count", None)
                data.append(item)
            return {"data": data, "count": total}
        except Exception:
            return None
    
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
