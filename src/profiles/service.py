from src.profiles.repository import ProfileRepository
from src.profiles.schemas import ProfileFilter, ProfileUpdate, ProfileDelete


class ProfileService:
    """Service com regras de negócio para gerenciamento de perfis."""
    
    def __init__(self):
        self.repo = ProfileRepository()
    
    def list_profiles(self, filters: ProfileFilter) -> dict:
        """
        Lista perfis com filtros e paginação.
        
        Returns:
            { "data": [...], "count": N }
        """
        return self.repo.list_all(filters)
    
    def update_profile(self, payload: ProfileUpdate) -> dict:
        """
        Atualiza um perfil (email e/ou role).
        
        Regras de negócio:
        - Ao menos um campo (email ou role) deve ser fornecido
        """
        # Prepara dados para atualização
        update_data = {}
        if payload.email is not None:
            update_data["email"] = payload.email
        if payload.role is not None:
            update_data["role"] = payload.role
        
        if not update_data:
            raise ValueError("Informe ao menos um campo para atualizar (email ou role)")
        
        # Executa atualização
        updated = self.repo.update(payload.id, update_data)
        return updated
    
    def delete_profile(self, payload: ProfileDelete, current_user_id: str = None) -> dict:
        """
        Remove um perfil.
        
        Regras de negócio:
        - (Opcional) Impede que um admin delete a si mesmo
        
        Args:
            payload: ProfileDelete com id do perfil a remover
            current_user_id: UUID do usuário logado (opcional, para validação)
        """
        # Busca perfil antes de deletar (para validações)
        profile = self.repo.get_by_id(payload.id)
        
        if not profile:
            raise Exception(f"Perfil {payload.id} não encontrado")
        
        # Regra de negócio: Admin não pode deletar a si mesmo
        if current_user_id and payload.id == current_user_id:
            # Verifica se o perfil atual é admin
            current_profile = self.repo.get_by_id(current_user_id)
            if current_profile and current_profile.get("role") == "admin":
                raise Exception("Administradores não podem deletar seu próprio perfil")
        
        # Executa remoção
        self.repo.delete(payload.id)
        
        return {
            "message": "Perfil removido com sucesso",
            "id": payload.id
        }
