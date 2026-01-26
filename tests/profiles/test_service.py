import pytest
from unittest.mock import MagicMock, patch
from src.profiles.service import ProfileService
from src.profiles.schemas import ProfileFilter, ProfileUpdate, ProfileDelete


class TestProfileServiceList:
    """Testes unitários para listagem de perfis."""
    
    @patch("src.profiles.service.ProfileRepository")
    def test_list_profiles_calls_repository_with_correct_filters(self, mock_repo_class):
        """Verifica se list_profiles chama repo.list_all com os filtros corretos."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_result = {"data": [], "count": 0}
        mock_repo.list_all.return_value = mock_result
        
        service = ProfileService()
        
        filters = ProfileFilter(
            page=2,
            limit=20,
            email="teste@example.com",
            role="admin",
            sort="role_asc"
        )
        
        result = service.list_profiles(filters)
        
        mock_repo.list_all.assert_called_once_with(filters)
        assert result == mock_result
    
    @patch("src.profiles.service.ProfileRepository")
    def test_list_profiles_with_default_filters(self, mock_repo_class):
        """Verifica listagem com filtros padrão."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_result = {
            "data": [
                {"id": "123", "email": "user1@test.com", "role": "user"},
                {"id": "456", "email": "user2@test.com", "role": "admin"}
            ],
            "count": 2
        }
        mock_repo.list_all.return_value = mock_result
        
        service = ProfileService()
        
        filters = ProfileFilter()
        result = service.list_profiles(filters)
        
        mock_repo.list_all.assert_called_once()
        assert result["count"] == 2
        assert len(result["data"]) == 2


class TestProfileServiceUpdate:
    """Testes unitários para atualização de perfis."""
    
    @patch("src.profiles.service.ProfileRepository")
    def test_update_profile_with_email_only(self, mock_repo_class):
        """Atualiza apenas o email do perfil."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_updated = {"id": "123", "email": "novo@teste.com", "role": "user"}
        mock_repo.update.return_value = mock_updated
        
        service = ProfileService()
        
        payload = ProfileUpdate(id="123", email="novo@teste.com")
        result = service.update_profile(payload)
        
        mock_repo.update.assert_called_once_with("123", {"email": "novo@teste.com"})
        assert result == mock_updated
    
    @patch("src.profiles.service.ProfileRepository")
    def test_update_profile_with_role_only(self, mock_repo_class):
        """Atualiza apenas a role do perfil."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_updated = {"id": "123", "email": "user@test.com", "role": "admin"}
        mock_repo.update.return_value = mock_updated
        
        service = ProfileService()
        
        payload = ProfileUpdate(id="123", role="admin")
        result = service.update_profile(payload)
        
        mock_repo.update.assert_called_once_with("123", {"role": "admin"})
        assert result == mock_updated
    
    @patch("src.profiles.service.ProfileRepository")
    def test_update_profile_with_both_fields(self, mock_repo_class):
        """Atualiza email e role simultaneamente."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_updated = {"id": "123", "email": "novo@admin.com", "role": "admin"}
        mock_repo.update.return_value = mock_updated
        
        service = ProfileService()
        
        payload = ProfileUpdate(id="123", email="novo@admin.com", role="admin")
        result = service.update_profile(payload)
        
        mock_repo.update.assert_called_once_with(
            "123",
            {"email": "novo@admin.com", "role": "admin"}
        )
        assert result == mock_updated
    
    @patch("src.profiles.service.ProfileRepository")
    def test_update_profile_with_no_fields_raises_error(self, mock_repo_class):
        """Deve lançar ValueError quando nenhum campo é fornecido."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        service = ProfileService()
        
        payload = ProfileUpdate(id="123")
        
        with pytest.raises(ValueError) as exc_info:
            service.update_profile(payload)
        
        assert "Informe ao menos um campo para atualizar" in str(exc_info.value)
        mock_repo.update.assert_not_called()


class TestProfileServiceDelete:
    """Testes unitários para remoção de perfis."""
    
    @patch("src.profiles.service.ProfileRepository")
    def test_delete_profile_success(self, mock_repo_class):
        """Remove perfil com sucesso quando encontrado."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_profile = {"id": "123", "email": "user@test.com", "role": "user"}
        mock_repo.get_by_id.return_value = mock_profile
        
        service = ProfileService()
        
        payload = ProfileDelete(id="123")
        result = service.delete_profile(payload)
        
        mock_repo.get_by_id.assert_called_once_with("123")
        mock_repo.delete.assert_called_once_with("123")
        assert result["message"] == "Perfil removido com sucesso"
        assert result["id"] == "123"
    
    @patch("src.profiles.service.ProfileRepository")
    def test_delete_profile_not_found_raises_error(self, mock_repo_class):
        """Deve lançar Exception quando perfil não existe."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_repo.get_by_id.return_value = None
        
        service = ProfileService()
        
        payload = ProfileDelete(id="999")
        
        with pytest.raises(Exception) as exc_info:
            service.delete_profile(payload)
        
        assert "Perfil 999 não encontrado" in str(exc_info.value)
        mock_repo.delete.assert_not_called()
    
    @patch("src.profiles.service.ProfileRepository")
    def test_delete_profile_admin_cannot_delete_self(self, mock_repo_class):
        """Administrador não pode deletar seu próprio perfil."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        admin_profile = {"id": "admin1", "email": "admin@test.com", "role": "admin"}
        
        mock_repo.get_by_id.return_value = admin_profile
        
        service = ProfileService()
        
        payload = ProfileDelete(id="admin1")
        
        with pytest.raises(Exception) as exc_info:
            service.delete_profile(payload, current_user_id="admin1")
        
        assert "Administradores não podem deletar seu próprio perfil" in str(exc_info.value)
        
        assert mock_repo.get_by_id.call_count == 2
        mock_repo.delete.assert_not_called()
    
    @patch("src.profiles.service.ProfileRepository")
    def test_delete_profile_regular_user_can_delete_self(self, mock_repo_class):
        """Usuário comum pode deletar seu próprio perfil."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        user_profile = {"id": "user1", "email": "user@test.com", "role": "user"}
        
        mock_repo.get_by_id.return_value = user_profile
        
        service = ProfileService()
        
        payload = ProfileDelete(id="user1")
        result = service.delete_profile(payload, current_user_id="user1")
        
        assert mock_repo.get_by_id.call_count == 2
        mock_repo.delete.assert_called_once_with("user1")
        assert result["message"] == "Perfil removido com sucesso"
    
    @patch("src.profiles.service.ProfileRepository")
    def test_delete_profile_admin_can_delete_other_users(self, mock_repo_class):
        """Administrador pode deletar outros usuários."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        target_profile = {"id": "user123", "email": "user@test.com", "role": "user"}
        mock_repo.get_by_id.return_value = target_profile
        
        service = ProfileService()
        
        payload = ProfileDelete(id="user123")
        result = service.delete_profile(payload, current_user_id="admin1")
        
        mock_repo.get_by_id.assert_called_once_with("user123")
        mock_repo.delete.assert_called_once_with("user123")
        assert result["id"] == "user123"
    
    @patch("src.profiles.service.ProfileRepository")
    def test_delete_profile_without_current_user_id(self, mock_repo_class):
        """Remove perfil sem validação de current_user_id."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_profile = {"id": "123", "email": "user@test.com", "role": "admin"}
        mock_repo.get_by_id.return_value = mock_profile
        
        service = ProfileService()
        
        payload = ProfileDelete(id="123")
        result = service.delete_profile(payload)
        
        mock_repo.get_by_id.assert_called_once_with("123")
        mock_repo.delete.assert_called_once_with("123")
        assert result["id"] == "123"
