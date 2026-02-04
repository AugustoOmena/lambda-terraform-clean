import json
import pytest
from unittest.mock import patch, MagicMock

from src.payment.handler import lambda_handler


@pytest.fixture
def mock_payment_service():
    """Mock da classe PaymentService para evitar lógica real."""
    with patch("src.payment.handler.PaymentService") as mock_service_class:
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_logger():
    """Mock do Logger para não poluir o terminal."""
    with patch("src.payment.handler.logger") as mock_log:
        yield mock_log


def _create_event(body: dict = None, http_method: str = "POST") -> dict:
    """Helper para criar eventos simulados do API Gateway."""
    return {
        "body": json.dumps(body) if body else None,
        "requestContext": {
            "http": {
                "method": http_method
            }
        },
        "headers": {
            "Content-Type": "application/json"
        }
    }


class TestPaymentLambdaHandler:
    """Testes unitários para a função lambda_handler."""

    def test_handler_success_201_creates_payment(
        self, mock_payment_service: MagicMock, mock_logger: MagicMock
    ) -> None:
        """
        Cenário: Payload válido enviado para processar pagamento.
        Esperado: Retorna statusCode 201 com dados do pagamento.
        """
        # Arrange: Mock do retorno do service
        mock_payment_service.process_payment.return_value = {
            "order_id": "order-123",
            "mp_payment_id": "mp-456",
            "status": "approved",
            "qr_code": "00020101021243650016COM.MERCADOLIBRE..."
        }
        
        # Payload válido simulado
        event = _create_event({
            "transaction_amount": 100.00,
            "payment_method_id": "pix",
            "installments": 1,
            "payer": {
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "identification": {"type": "CPF", "number": "12345678900"}
            },
            "user_id": "user-123",
            "items": [{"id": 1, "name": "Produto Teste", "price": 100.00, "quantity": 1}],
            "frete": 25.90,
            "frete_service": "jadlog_package",
            "cep": "01310100",
        })
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response["statusCode"] == 201
        
        body = json.loads(response["body"])
        assert body["order_id"] == "order-123"
        assert body["mp_payment_id"] == "mp-456"
        assert body["status"] == "approved"
        assert "qr_code" in body
        
        # Verifica que o service foi chamado
        mock_payment_service.process_payment.assert_called_once()

    def test_handler_validation_error_400_missing_required_fields(
        self, mock_payment_service: MagicMock, mock_logger: MagicMock
    ) -> None:
        """
        Cenário: Payload com campos obrigatórios faltando (ValidationError do Pydantic).
        Esperado: Retorna statusCode 400 com mensagem de erro.
        """
        # Arrange: Mock do parse para lançar ValidationError
        with patch("src.payment.handler.parse") as mock_parse:
            from pydantic import ValidationError
            
            # Simula erro de validação do Pydantic
            mock_parse.side_effect = ValueError(
                "1 validation error for PaymentInput\npayer\n  Field required [type=missing, input_value={...}]"
            )
            
            event = _create_event({
                "transaction_amount": 100.00,
                "payment_method_id": "pix"
                # Falta: payer, user_id, items
            })
            
            # Act
            response = lambda_handler(event, None)
            
            # Assert
            assert response["statusCode"] == 400
            
            body = json.loads(response["body"])
            assert "error" in body
            assert body["error"] == "Dados inválidos"
            assert "details" in body
            
            # Service NÃO deve ter sido chamado (erro na validação antes)
            mock_payment_service.process_payment.assert_not_called()

    def test_handler_validation_error_400_invalid_json(
        self, mock_payment_service: MagicMock, mock_logger: MagicMock
    ) -> None:
        """
        Cenário: Body com JSON malformado.
        Esperado: Retorna statusCode 400.
        """
        # Arrange: Mock do parse para simular JSON inválido
        with patch("src.payment.handler.parse") as mock_parse:
            mock_parse.side_effect = ValueError("Invalid JSON format")
            
            event = {
                "body": "{invalid json syntax}",
                "requestContext": {"http": {"method": "POST"}},
                "headers": {"Content-Type": "application/json"}
            }
            
            # Act
            response = lambda_handler(event, None)
            
            # Assert
            assert response["statusCode"] == 400
            body = json.loads(response["body"])
            assert "error" in body
            assert body["error"] == "Dados inválidos"

    def test_handler_internal_error_500_service_exception(
        self, mock_payment_service: MagicMock, mock_logger: MagicMock
    ) -> None:
        """
        Cenário: PaymentService lança exceção genérica (ex: erro do Mercado Pago).
        Esperado: Retorna statusCode 500 com mensagem de erro.
        """
        # Arrange: Mock lançando exceção
        mock_payment_service.process_payment.side_effect = Exception(
            "Erro Mercado Pago: Timeout na comunicação"
        )
        event = _create_event({
            "transaction_amount": 100.00,
            "payment_method_id": "pix",
            "installments": 1,
            "payer": {"email": "test@example.com", "identification": {"number": "12345678900"}},
            "user_id": "user-123",
                "items": [{"id": 1, "name": "Produto", "price": 100.00, "quantity": 1}],
                "frete": 25.90,
                "frete_service": "jadlog_package",
                "cep": "01310100",
            })
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response["statusCode"] == 500
        
        body = json.loads(response["body"])
        assert "error" in body
        assert "Erro Mercado Pago" in str(body["error"])

    def test_handler_cors_options_returns_200_empty(
        self, mock_payment_service: MagicMock, mock_logger: MagicMock
    ) -> None:
        """
        Cenário: Requisição OPTIONS (CORS preflight).
        Esperado: Retorna statusCode 200 com body vazio.
        """
        # Arrange
        event = _create_event(http_method="OPTIONS")
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response["statusCode"] == 200
        
        body = json.loads(response["body"])
        assert body == {}
        
        # Service NÃO deve ser chamado em OPTIONS
        mock_payment_service.process_payment.assert_not_called()

    def test_handler_includes_cors_headers(
        self, mock_payment_service: MagicMock, mock_logger: MagicMock
    ) -> None:
        """
        Cenário: Qualquer resposta do handler.
        Esperado: Deve incluir headers CORS.
        """
        # Arrange
        mock_payment_service.process_payment.return_value = {
            "order_id": "order-123",
            "status": "approved"
        }
        
        event = _create_event({
            "transaction_amount": 100.00,
            "payment_method_id": "pix",
            "installments": 1,
            "payer": {"email": "test@example.com", "identification": {"number": "12345678900"}},
            "user_id": "user-123",
            "items": [{"id": 1, "name": "Produto", "price": 100.00, "quantity": 1}],
            "frete": 25.90,
            "frete_service": "jadlog_package",
            "cep": "01310100",
        })
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert "headers" in response
        assert "Access-Control-Allow-Origin" in response["headers"]
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Methods" in response["headers"]

    def test_handler_pix_payment_returns_qr_code(
        self, mock_payment_service: MagicMock, mock_logger: MagicMock
    ) -> None:
        """
        Cenário: Pagamento PIX bem-sucedido.
        Esperado: Resposta contém campo 'qr_code' e 'qr_code_base64'.
        """
        # Arrange
        mock_payment_service.process_payment.return_value = {
            "order_id": "order-pix-123",
            "mp_payment_id": "mp-pix-456",
            "status": "pending",
            "qr_code": "00020101021243650016COM.MERCADOLIBRE02013063204C3F1",
            "qr_code_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
        }
        
        event = _create_event({
            "transaction_amount": 50.00,
            "payment_method_id": "pix",
            "installments": 1,
            "payer": {"email": "pix@example.com", "identification": {"number": "98765432100"}},
            "user_id": "user-pix",
            "items": [{"id": 2, "name": "Produto PIX", "price": 50.00, "quantity": 1}],
            "frete": 25.90,
            "frete_service": "jadlog_package",
            "cep": "01310100",
        })
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response["statusCode"] == 201
        
        body = json.loads(response["body"])
        assert body["status"] == "pending"
        assert "qr_code" in body
        assert "qr_code_base64" in body
        assert body["qr_code"].startswith("00020101")

    def test_handler_card_payment_success(
        self, mock_payment_service: MagicMock, mock_logger: MagicMock
    ) -> None:
        """
        Cenário: Pagamento com Cartão de Crédito bem-sucedido.
        Esperado: Retorna status 'approved' e detalhes do pagamento.
        """
        # Arrange
        mock_payment_service.process_payment.return_value = {
            "order_id": "order-card-789",
            "mp_payment_id": "mp-card-012",
            "status": "approved",
            "status_detail": "accredited",
            "installments": 3
        }
        
        event = _create_event({
            "transaction_amount": 300.00,
            "payment_method_id": "credit_card",
            "token": "card-token-abc123",
            "installments": 3,
            "payer": {
                "email": "card@example.com",
                "first_name": "Card",
                "last_name": "User",
                "identification": {"number": "11122233344"}
            },
            "user_id": "user-card",
            "items": [{"id": 3, "name": "Produto Caro", "price": 300.00, "quantity": 1}],
            "frete": 25.90,
            "frete_service": "jadlog_package",
            "cep": "01310100",
        })
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response["statusCode"] == 201
        
        body = json.loads(response["body"])
        assert body["status"] == "approved"
        assert body["installments"] == 3

    def test_handler_melhor_envio_error_502(
        self, mock_payment_service: MagicMock, mock_logger: MagicMock
    ) -> None:
        """
        Cenário: PaymentService lança MelhorEnvioAPIError (falha na API de frete).
        Esperado: Retorna statusCode 502.
        """
        from shared.melhor_envio import MelhorEnvioAPIError
        mock_payment_service.process_payment.side_effect = MelhorEnvioAPIError(
            "Timeout ao conectar na API de frete"
        )
        event = _create_event({
            "transaction_amount": 100.00,
            "payment_method_id": "pix",
            "installments": 1,
            "payer": {"email": "a@b.com", "identification": {"number": "12345678900"}},
            "user_id": "user-1",
            "items": [{"id": 1, "name": "P", "price": 100.00, "quantity": 1}],
            "frete": 25.90,
            "frete_service": "jadlog_package",
            "cep": "01310100",
        })
        response = lambda_handler(event, None)
        assert response["statusCode"] == 502
        body = json.loads(response["body"])
        assert "error" in body
        assert "Frete" in body["error"] or "frete" in body["error"] or "Timeout" in body["error"]
