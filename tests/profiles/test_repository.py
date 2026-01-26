import pytest
from unittest.mock import patch, MagicMock

from repository import ProfileRepository
from schemas import ProfileFilter


@pytest.fixture
def mock_supabase_client():
    """Mock do cliente Supabase com estrutura encadeada de métodos."""
    with patch("repository.get_supabase_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        yield mock_client


class TestProfileRepositoryListAll:
    """Testes para o método list_all (query building complexo)."""
    
    def test_list_all_query_building(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Lista perfis com todos os filtros aplicados (email, role, sort, paginação).
        Esperado: Verifica cadeia completa de chamadas Supabase.
        """
        # Arrange: Mock da cadeia completa de métodos do Supabase
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_ilike = MagicMock()
        mock_eq = MagicMock()
        mock_order = MagicMock()
        mock_range = MagicMock()
        mock_execute = MagicMock()
        
        # Configura a cadeia de retornos
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.ilike.return_value = mock_ilike
        mock_ilike.eq.return_value = mock_eq
        mock_eq.order.return_value = mock_order
        mock_order.range.return_value = mock_range
        mock_range.execute.return_value = mock_execute
        
        # Dados mockados de retorno
        mock_execute.data = [
            {"id": "1", "email": "teste1@example.com", "role": "admin"},
            {"id": "2", "email": "teste2@example.com", "role": "admin"}
        ]
        mock_execute.count = 25  # Total sem paginação
        
        # Act
        repo = ProfileRepository()
        filters = ProfileFilter(
            page=2,
            limit=10,
            email="teste",
            role="admin",
            sort="newest"
        )
        result = repo.list_all(filters)
        
        # Assert: Verifica cada chamada da cadeia
        mock_supabase_client.table.assert_called_once_with("profiles")
        mock_table.select.assert_called_once_with("*", count="exact")
        mock_select.ilike.assert_called_once_with("email", "%teste%")
        mock_ilike.eq.assert_called_once_with("role", "admin")
        mock_eq.order.assert_called_once_with("created_at", desc=True)
        
        # Paginação: page=2, limit=10 → start=10, end=19
        mock_order.range.assert_called_once_with(10, 19)
        
        # Verifica resultado
        assert result["data"] == mock_execute.data
        assert result["count"] == 25
    
    def test_list_all_with_minimal_filters(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Lista perfis apenas com filtros padrão (sem email/role).
        Esperado: ilike e eq NÃO devem ser chamados.
        """
        # Arrange
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_range = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        mock_order.range.return_value = mock_range
        mock_range.execute.return_value = mock_execute
        
        mock_execute.data = []
        mock_execute.count = 0
        
        # Act
        repo = ProfileRepository()
        filters = ProfileFilter()  # Valores padrão: page=1, limit=10, sort="newest"
        result = repo.list_all(filters)
        
        # Assert
        mock_table.select.assert_called_once_with("*", count="exact")
        mock_select.order.assert_called_once_with("created_at", desc=True)
        
        # Paginação: page=1, limit=10 → start=0, end=9
        mock_order.range.assert_called_once_with(0, 9)
        
        # Verifica que ilike e eq NÃO foram chamados
        assert not hasattr(mock_select, 'ilike') or mock_select.ilike.call_count == 0
        assert result["count"] == 0
    
    def test_list_all_with_different_sort_options(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Testa diferentes opções de ordenação.
        Esperado: order() é chamado com parâmetros corretos para cada sort.
        """
        # Arrange
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_range = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        mock_order.range.return_value = mock_range
        mock_range.execute.return_value = mock_execute
        
        mock_execute.data = []
        mock_execute.count = 0
        
        repo = ProfileRepository()
        
        # Test 1: sort="role_asc"
        filters_asc = ProfileFilter(sort="role_asc")
        repo.list_all(filters_asc)
        mock_select.order.assert_called_with("role", desc=False)
        
        # Reset mocks
        mock_select.reset_mock()
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        
        # Test 2: sort="role_desc"
        filters_desc = ProfileFilter(sort="role_desc")
        repo.list_all(filters_desc)
        mock_select.order.assert_called_with("role", desc=True)
    
    def test_list_all_with_only_email_filter(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Filtra apenas por email (sem role).
        Esperado: ilike é chamado, eq NÃO é chamado.
        """
        # Arrange
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_ilike = MagicMock()
        mock_order = MagicMock()
        mock_range = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.ilike.return_value = mock_ilike
        mock_ilike.order.return_value = mock_order
        mock_order.range.return_value = mock_range
        mock_range.execute.return_value = mock_execute
        
        mock_execute.data = []
        mock_execute.count = 0
        
        # Act
        repo = ProfileRepository()
        filters = ProfileFilter(email="test@example.com")
        result = repo.list_all(filters)
        
        # Assert
        mock_select.ilike.assert_called_once_with("email", "%test@example.com%")
        # eq não deve ter sido chamado no select ou no ilike
        assert not hasattr(mock_ilike, 'eq') or mock_ilike.eq.call_count == 0
        assert result["count"] == 0


class TestProfileRepositoryUpdate:
    """Testes para o método update."""
    
    def test_update_logic_removes_none_values(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Atualiza perfil com data contendo valores None.
        Esperado: Campos None são removidos antes de enviar ao banco.
        """
        # Arrange
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        
        mock_execute.data = [{"id": "id1", "email": "novo@email.com", "role": "user"}]
        
        # Act
        repo = ProfileRepository()
        result = repo.update("id1", {"email": "novo@email.com", "role": None})
        
        # Assert: update() deve ser chamado APENAS com email (role=None foi removido)
        mock_table.update.assert_called_once_with({"email": "novo@email.com"})
        mock_update.eq.assert_called_once_with("id", "id1")
        assert result["email"] == "novo@email.com"
    
    def test_update_raises_error_when_all_fields_are_none(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Todos os campos são None (não há nada para atualizar).
        Esperado: Lança ValueError antes de tentar atualizar.
        """
        # Arrange
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        
        # Act & Assert
        repo = ProfileRepository()
        with pytest.raises(ValueError) as exc_info:
            repo.update("id1", {"email": None, "role": None})
        
        assert "Nenhum campo para atualizar" in str(exc_info.value)
        # update() não deve ter sido chamado
        mock_table.update.assert_not_called()
    
    def test_update_success_with_multiple_fields(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Atualiza múltiplos campos válidos.
        Esperado: Todos os campos são enviados ao banco.
        """
        # Arrange
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        
        mock_execute.data = [{"id": "id1", "email": "novo@email.com", "role": "admin"}]
        
        # Act
        repo = ProfileRepository()
        result = repo.update("id1", {"email": "novo@email.com", "role": "admin"})
        
        # Assert
        mock_table.update.assert_called_once_with(
            {"email": "novo@email.com", "role": "admin"}
        )
        assert result["role"] == "admin"
    
    def test_update_raises_exception_when_profile_not_found(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Perfil não existe (response.data vazio).
        Esperado: Lança Exception informando que não foi encontrado.
        """
        # Arrange
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        
        mock_execute.data = []  # Perfil não encontrado
        
        # Act & Assert
        repo = ProfileRepository()
        with pytest.raises(Exception) as exc_info:
            repo.update("id999", {"email": "novo@email.com"})
        
        assert "Perfil id999 não encontrado ou não foi atualizado" in str(exc_info.value)


class TestProfileRepositoryGetById:
    """Testes para o método get_by_id."""
    
    def test_get_by_id_found(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Perfil existe no banco.
        Esperado: Retorna dict com dados do perfil.
        """
        # Arrange
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        
        mock_execute.data = [{"id": "123", "email": "user@test.com", "role": "user"}]
        
        # Act
        repo = ProfileRepository()
        result = repo.get_by_id("123")
        
        # Assert
        mock_supabase_client.table.assert_called_once_with("profiles")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("id", "123")
        assert result == {"id": "123", "email": "user@test.com", "role": "user"}
    
    def test_get_by_id_not_found(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Perfil não existe no banco (data vazio).
        Esperado: Retorna None.
        """
        # Arrange
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        
        mock_execute.data = []  # Não encontrado
        
        # Act
        repo = ProfileRepository()
        result = repo.get_by_id("999")
        
        # Assert
        assert result is None
        mock_select.eq.assert_called_once_with("id", "999")


class TestProfileRepositoryDelete:
    """Testes para o método delete."""
    
    def test_delete_success(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Perfil é removido com sucesso.
        Esperado: Retorna True e verifica cadeia de chamadas.
        """
        # Arrange
        mock_table = MagicMock()
        mock_delete = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.delete.return_value = mock_delete
        mock_delete.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        
        mock_execute.data = [{"id": "123"}]  # Confirmação de remoção
        
        # Act
        repo = ProfileRepository()
        result = repo.delete("123")
        
        # Assert
        mock_supabase_client.table.assert_called_once_with("profiles")
        mock_table.delete.assert_called_once()
        mock_delete.eq.assert_called_once_with("id", "123")
        assert result is True
    
    def test_delete_raises_exception_when_profile_not_found(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Perfil não existe (data vazio).
        Esperado: Lança Exception.
        """
        # Arrange
        mock_table = MagicMock()
        mock_delete = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.delete.return_value = mock_delete
        mock_delete.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        
        mock_execute.data = []  # Perfil não encontrado
        
        # Act & Assert
        repo = ProfileRepository()
        with pytest.raises(Exception) as exc_info:
            repo.delete("999")
        
        assert "Perfil 999 não encontrado ou não foi removido" in str(exc_info.value)
