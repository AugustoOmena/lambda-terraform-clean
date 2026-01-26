import json
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from shared.responses import http_response
from shared.database import get_supabase_client


class TestHttpResponse:
    """Testes para a função http_response que formata respostas HTTP."""

    def test_http_response_basic_structure(self) -> None:
        """
        Cenário: Chamada simples com status 200 e body básico.
        Esperado: Retorna dict com statusCode, headers CORS e body stringificado.
        """
        # Arrange
        status = 200
        body = {"message": "Success", "data": {"id": 1, "name": "Test"}}
        
        # Act
        response = http_response(status, body)
        
        # Assert
        assert response["statusCode"] == 200
        assert "headers" in response
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert response["headers"]["Access-Control-Allow-Methods"] == "GET, POST, PUT, DELETE, OPTIONS"
        assert response["headers"]["Access-Control-Allow-Headers"] == "Content-Type, Authorization"
        
        # Body deve ser string JSON
        assert isinstance(response["body"], str)
        parsed_body = json.loads(response["body"])
        assert parsed_body["message"] == "Success"
        assert parsed_body["data"]["id"] == 1

    def test_http_response_error_status_codes(self) -> None:
        """
        Cenário: Retornar diferentes códigos de erro (400, 500).
        Esperado: StatusCode correto e body com mensagem de erro.
        """
        # Teste 400
        response_400 = http_response(400, {"error": "Bad Request"})
        assert response_400["statusCode"] == 400
        body_400 = json.loads(response_400["body"])
        assert body_400["error"] == "Bad Request"
        
        # Teste 500
        response_500 = http_response(500, {"error": "Internal Server Error"})
        assert response_500["statusCode"] == 500
        body_500 = json.loads(response_500["body"])
        assert body_500["error"] == "Internal Server Error"

    def test_http_response_serializes_decimal_type(self) -> None:
        """
        Cenário CRÍTICO: Body contém Decimal (usado em preços).
        Esperado: Serializa corretamente usando default=str.
        """
        # Arrange: Dicionário com Decimal (tipo não serializável por padrão)
        body = {
            "product": "Camiseta",
            "price": Decimal("10.50"),
            "discount": Decimal("2.00")
        }
        
        # Act
        response = http_response(200, body)
        
        # Assert: Não deve lançar TypeError
        assert isinstance(response["body"], str)
        
        # Verifica que os valores foram convertidos corretamente
        parsed_body = json.loads(response["body"])
        assert parsed_body["product"] == "Camiseta"
        # Decimal é convertido para string pelo default=str
        assert parsed_body["price"] == "10.50"
        assert parsed_body["discount"] == "2.00"

    def test_http_response_serializes_datetime_type(self) -> None:
        """
        Cenário CRÍTICO: Body contém datetime.
        Esperado: Serializa usando default=str (formato ISO).
        """
        # Arrange
        now = datetime(2026, 1, 25, 14, 30, 0)
        body = {
            "event": "Order Created",
            "created_at": now,
            "timestamp": datetime.now()
        }
        
        # Act
        response = http_response(201, body)
        
        # Assert: Não deve lançar TypeError
        assert isinstance(response["body"], str)
        
        parsed_body = json.loads(response["body"])
        assert parsed_body["event"] == "Order Created"
        # datetime é convertido para string
        assert "2026-01-25" in parsed_body["created_at"]
        assert isinstance(parsed_body["timestamp"], str)

    def test_http_response_serializes_complex_nested_types(self) -> None:
        """
        Cenário CRÍTICO: Body com tipos complexos aninhados (Decimal + datetime).
        Esperado: Serialização completa sem erro (cenário real de pedidos).
        """
        # Arrange: Simula resposta de um pedido com preço e data
        body = {
            "order_id": "order-123",
            "total_amount": Decimal("150.75"),
            "created_at": datetime.now(),
            "items": [
                {
                    "id": 1,
                    "price": Decimal("50.25"),
                    "quantity": 3
                }
            ],
            "metadata": {
                "updated_at": datetime(2026, 1, 25, 10, 0, 0),
                "discount": Decimal("10.00")
            }
        }
        
        # Act
        response = http_response(201, body)
        
        # Assert
        assert response["statusCode"] == 201
        parsed_body = json.loads(response["body"])
        
        assert parsed_body["order_id"] == "order-123"
        assert parsed_body["total_amount"] == "150.75"
        assert isinstance(parsed_body["created_at"], str)
        assert parsed_body["items"][0]["price"] == "50.25"
        assert parsed_body["metadata"]["discount"] == "10.00"

    def test_http_response_empty_body(self) -> None:
        """
        Cenário: Body vazio (usado em OPTIONS).
        Esperado: Retorna body como "{}" (string JSON vazia).
        """
        # Arrange
        body = {}
        
        # Act
        response = http_response(200, body)
        
        # Assert
        assert response["statusCode"] == 200
        assert response["body"] == "{}"


class TestGetSupabaseClient:
    """Testes para a função get_supabase_client (Singleton pattern + config)."""

    def test_get_supabase_client_missing_url_raises_error(self) -> None:
        """
        Cenário: Variável SUPABASE_URL não definida.
        Esperado: Lança ValueError com mensagem sobre ENV VARS.
        """
        # Arrange: Mock ambiente sem SUPABASE_URL
        with patch("shared.database.os.environ.get") as mock_env:
            mock_env.side_effect = lambda key: None if key == "SUPABASE_URL" else "fake-key"
            
            # Reset singleton para forçar nova inicialização
            with patch("shared.database._client", None):
                # Act & Assert
                with pytest.raises(ValueError) as exc_info:
                    get_supabase_client()
                
                assert "Supabase ausentes" in str(exc_info.value)

    def test_get_supabase_client_missing_key_raises_error(self) -> None:
        """
        Cenário: Variável SUPABASE_KEY não definida.
        Esperado: Lança ValueError.
        """
        # Arrange: Mock ambiente sem SUPABASE_KEY
        with patch("shared.database.os.environ.get") as mock_env:
            mock_env.side_effect = lambda key: "fake-url" if key == "SUPABASE_URL" else None
            
            # Reset singleton
            with patch("shared.database._client", None):
                # Act & Assert
                with pytest.raises(ValueError) as exc_info:
                    get_supabase_client()
                
                assert "Supabase ausentes" in str(exc_info.value)

    def test_get_supabase_client_singleton_pattern_caches_instance(self) -> None:
        """
        Cenário CRÍTICO: Chamar get_supabase_client() múltiplas vezes.
        Esperado: create_client é chamado APENAS UMA VEZ (singleton/cache funcionando).
        """
        # Arrange: Mock das variáveis de ambiente
        with patch("shared.database.os.environ.get") as mock_env:
            mock_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://fake-url.supabase.co",
                "SUPABASE_KEY": "fake-key-123"
            }.get(key)
            
            # Mock do create_client
            with patch("shared.database.create_client") as mock_create:
                mock_client_instance = MagicMock()
                mock_create.return_value = mock_client_instance
                
                # Reset singleton antes do teste (CRÍTICO para isolamento)
                import shared.database
                shared.database._client = None
                
                # Act: Chama 3 vezes
                client1 = get_supabase_client()
                client2 = get_supabase_client()
                client3 = get_supabase_client()
                
                # Assert: create_client chamado APENAS 1 vez
                assert mock_create.call_count == 1
                
                # Todas as chamadas retornam a MESMA instância (singleton)
                assert client1 is client2
                assert client2 is client3
                assert client1 is mock_client_instance

    def test_get_supabase_client_success_returns_client(self) -> None:
        """
        Cenário: Configuração correta no ambiente.
        Esperado: Retorna instância do cliente Supabase.
        """
        # Arrange
        with patch("shared.database.os.environ.get") as mock_env:
            mock_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key"
            }.get(key)
            
            with patch("shared.database.create_client") as mock_create:
                mock_client = MagicMock()
                mock_create.return_value = mock_client
                
                # Reset singleton
                import shared.database
                shared.database._client = None
                
                # Act
                client = get_supabase_client()
                
                # Assert
                assert client is not None
                assert client is mock_client
                mock_create.assert_called_once_with(
                    "https://test.supabase.co",
                    "test-key"
                )

    def test_get_supabase_client_env_vars_used_correctly(self) -> None:
        """
        Cenário: Verificar que as variáveis de ambiente corretas são usadas.
        Esperado: create_client recebe SUPABASE_URL e SUPABASE_KEY.
        """
        # Arrange
        expected_url = "https://myproject.supabase.co"
        expected_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake"
        
        with patch("shared.database.os.environ.get") as mock_env:
            def get_env(key):
                if key == "SUPABASE_URL":
                    return expected_url
                elif key == "SUPABASE_KEY":
                    return expected_key
                return None
            
            mock_env.side_effect = get_env
            
            with patch("shared.database.create_client") as mock_create:
                mock_create.return_value = MagicMock()
                
                # Reset singleton
                import shared.database
                shared.database._client = None
                
                # Act
                get_supabase_client()
                
                # Assert: Verifica argumentos passados para create_client
                mock_create.assert_called_once_with(expected_url, expected_key)
                
                # Verifica que os.environ.get foi chamado para ambas as vars
                assert mock_env.call_count >= 2
                mock_env.assert_any_call("SUPABASE_URL")
                mock_env.assert_any_call("SUPABASE_KEY")
