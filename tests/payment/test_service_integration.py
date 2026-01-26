import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock, call

from service import PaymentService
from schemas import PaymentInput, Payer, Identification, Item


@pytest.fixture
def mock_repository():
    """Mock do PaymentRepository para todos os métodos."""
    with patch("service.PaymentRepository") as mock_repo_class:
        mock_instance = MagicMock()
        mock_repo_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_mercadopago():
    """Mock do Mercado Pago SDK."""
    with patch("service.mercadopago") as mock_mp_module:
        # Mock da classe SDK
        mock_sdk_instance = MagicMock()
        mock_mp_module.SDK.return_value = mock_sdk_instance
        
        # Mock do RequestOptions
        mock_mp_module.config.RequestOptions = MagicMock
        
        yield mock_sdk_instance


@pytest.fixture
def valid_pix_payload():
    """Payload válido para pagamento PIX."""
    return PaymentInput(
        transaction_amount=100.00,
        payment_method_id="pix",
        installments=1,
        payer=Payer(
            email="cliente@example.com",
            first_name="João",
            last_name="Silva",
            identification=Identification(type="CPF", number="12345678900")
        ),
        user_id="user-abc-123",
        items=[
            Item(id=1, name="Camiseta", price=50.00, quantity=2, size="M")
        ]
    )


@pytest.fixture
def valid_card_payload():
    """Payload válido para pagamento com Cartão."""
    return PaymentInput(
        token="card_token_abc123",
        transaction_amount=150.00,
        payment_method_id="visa",
        installments=3,
        issuer_id="123",
        payer=Payer(
            email="maria@example.com",
            first_name="Maria",
            last_name="Santos",
            identification=Identification(type="CPF", number="98765432100")
        ),
        user_id="user-xyz-789",
        items=[
            Item(id=2, name="Calça", price=150.00, quantity=1, size="G")
        ]
    )


class TestPaymentServiceIntegration:
    """Testes de integração do PaymentService com Mercado Pago."""

    def test_process_payment_pix_success_with_qr_code(
        self,
        mock_repository: MagicMock,
        mock_mercadopago: MagicMock,
        valid_pix_payload
    ) -> None:
        """
        Cenário: Pagamento PIX bem-sucedido com retorno de QR Code.
        Esperado: Payload correto enviado ao MP, order criada, estoque atualizado.
        """
        # Arrange: Auditoria passa
        mock_repository.get_product_price.return_value = {"id": 1, "price": 50.00}
        
        # Mock retorno do Mercado Pago com QR Code
        mock_payment_method = MagicMock()
        mock_mercadopago.payment.return_value = mock_payment_method
        mock_payment_method.create.return_value = {
            "status": 201,
            "response": {
                "id": "mp-pix-123456",
                "status": "pending",
                "status_detail": "pending_waiting_payment",
                "point_of_interaction": {
                    "transaction_data": {
                        "qr_code": "00020126580014br.gov.bcb.pix...",
                        "qr_code_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
                        "ticket_url": "https://www.mercadopago.com.br/payments/123456/ticket"
                    }
                }
            }
        }
        
        # Mock create_order e update_stock
        mock_repository.create_order.return_value = {"id": "order-db-123"}
        mock_repository.update_stock.return_value = None
        
        # Act
        service = PaymentService()
        result = service.process_payment(valid_pix_payload)
        
        # Assert: Verifica estrutura de resposta
        assert result["id"] == "mp-pix-123456"
        assert result["status"] == "pending"
        assert result["payment_method_id"] == "pix"
        assert "qr_code" in result
        assert "qr_code_base64" in result
        assert "ticket_url" in result
        
        # Verifica que create foi chamado com payload correto
        create_call = mock_payment_method.create.call_args
        payment_data = create_call[0][0]  # Primeiro argumento posicional
        
        assert payment_data["transaction_amount"] == 100.00
        assert payment_data["payment_method_id"] == "pix"
        assert payment_data["installments"] == 1
        assert payment_data["payer"]["email"] == "cliente@example.com"
        assert "token" not in payment_data  # PIX não usa token
        
        # Verifica que order foi criada e estoque atualizado
        mock_repository.create_order.assert_called_once()
        mock_repository.update_stock.assert_called_once_with(valid_pix_payload.items)

    def test_process_payment_card_success_with_token(
        self,
        mock_repository: MagicMock,
        mock_mercadopago: MagicMock,
        valid_card_payload
    ) -> None:
        """
        Cenário: Pagamento com Cartão bem-sucedido.
        Esperado: Payload inclui token, installments e issuer_id.
        """
        # Arrange
        mock_repository.get_product_price.return_value = {"id": 2, "price": 150.00}
        
        mock_payment_method = MagicMock()
        mock_mercadopago.payment.return_value = mock_payment_method
        mock_payment_method.create.return_value = {
            "status": 200,
            "response": {
                "id": "mp-card-789",
                "status": "approved",
                "status_detail": "accredited"
            }
        }
        
        mock_repository.create_order.return_value = {"id": "order-card-456"}
        
        # Act
        service = PaymentService()
        result = service.process_payment(valid_card_payload)
        
        # Assert
        assert result["id"] == "mp-card-789"
        assert result["status"] == "approved"
        assert result["payment_method_id"] == "visa"
        
        # Verifica payload enviado ao MP
        payment_data = mock_payment_method.create.call_args[0][0]
        assert payment_data["token"] == "card_token_abc123"
        assert payment_data["installments"] == 3
        assert payment_data["issuer_id"] == "123"
        assert payment_data["transaction_amount"] == 150.00
        
        # Verifica chamadas subsequentes
        mock_repository.create_order.assert_called_once()
        mock_repository.update_stock.assert_called_once()

    def test_process_payment_boleto_success(
        self,
        mock_repository: MagicMock,
        mock_mercadopago: MagicMock
    ) -> None:
        """
        Cenário: Pagamento com Boleto bancário.
        Esperado: installments=1, retorna ticket_url.
        """
        # Arrange
        boleto_payload = PaymentInput(
            transaction_amount=200.00,
            payment_method_id="bolbradesco",
            installments=1,
            payer=Payer(
                email="pedro@example.com",
                first_name="Pedro",
                last_name="Costa",
                identification=Identification(type="CPF", number="11122233344")
            ),
            user_id="user-boleto-001",
            items=[
                Item(id=3, name="Tênis", price=200.00, quantity=1)
            ]
        )
        
        mock_repository.get_product_price.return_value = {"id": 3, "price": 200.00}
        
        mock_payment_method = MagicMock()
        mock_mercadopago.payment.return_value = mock_payment_method
        mock_payment_method.create.return_value = {
            "status": 201,
            "response": {
                "id": "mp-boleto-999",
                "status": "pending",
                "status_detail": "pending_waiting_payment",
                "transaction_details": {
                    "external_resource_url": "https://www.mercadopago.com.br/payments/999/boleto"
                }
            }
        }
        
        mock_repository.create_order.return_value = {"id": "order-boleto-789"}
        
        # Act
        service = PaymentService()
        result = service.process_payment(boleto_payload)
        
        # Assert
        assert result["id"] == "mp-boleto-999"
        assert result["ticket_url"] == "https://www.mercadopago.com.br/payments/999/boleto"
        
        payment_data = mock_payment_method.create.call_args[0][0]
        assert payment_data["installments"] == 1
        assert "token" not in payment_data

    def test_process_payment_mp_error_400_does_not_create_order(
        self,
        mock_repository: MagicMock,
        mock_mercadopago: MagicMock,
        valid_pix_payload
    ) -> None:
        """
        Cenário: Mercado Pago retorna erro 400 (bad request).
        Esperado: Lança Exception, create_order NÃO é chamado.
        """
        # Arrange
        mock_repository.get_product_price.return_value = {"id": 1, "price": 50.00}
        
        mock_payment_method = MagicMock()
        mock_mercadopago.payment.return_value = mock_payment_method
        mock_payment_method.create.return_value = {
            "status": 400,
            "response": {
                "message": "Bad Request",
                "cause": [
                    {"description": "Invalid parameter: payer.email"}
                ]
            }
        }
        
        # Act & Assert
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(valid_pix_payload)
        
        error_msg = str(exc_info.value)
        assert "Bad Request" in error_msg
        assert "Invalid parameter: payer.email" in error_msg
        
        # Verifica que create_order NÃO foi chamado
        mock_repository.create_order.assert_not_called()
        mock_repository.update_stock.assert_not_called()

    def test_process_payment_mp_error_500_does_not_create_order(
        self,
        mock_repository: MagicMock,
        mock_mercadopago: MagicMock,
        valid_card_payload
    ) -> None:
        """
        Cenário: Mercado Pago retorna erro 500 (internal server error).
        Esperado: Lança Exception genérica, create_order NÃO é chamado.
        """
        # Arrange
        mock_repository.get_product_price.return_value = {"id": 2, "price": 150.00}
        
        mock_payment_method = MagicMock()
        mock_mercadopago.payment.return_value = mock_payment_method
        mock_payment_method.create.return_value = {
            "status": 500,
            "response": {
                "message": "Internal Server Error"
            }
        }
        
        # Act & Assert
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(valid_card_payload)
        
        assert "Internal Server Error" in str(exc_info.value)
        mock_repository.create_order.assert_not_called()
        mock_repository.update_stock.assert_not_called()

    def test_process_payment_card_without_token_raises_exception(
        self,
        mock_repository: MagicMock,
        mock_mercadopago: MagicMock
    ) -> None:
        """
        Cenário: Pagamento com cartão sem fornecer token.
        Esperado: Lança Exception antes de chamar MP.
        """
        # Arrange
        card_payload_no_token = PaymentInput(
            transaction_amount=100.00,
            payment_method_id="visa",
            installments=2,
            payer=Payer(
                email="test@example.com",
                first_name="Test",
                last_name="User",
                identification=Identification(type="CPF", number="12345678900")
            ),
            user_id="user-test",
            items=[
                Item(id=1, name="Produto", price=100.00, quantity=1)
            ]
        )
        
        mock_repository.get_product_price.return_value = {"id": 1, "price": 100.00}
        
        # Act & Assert
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(card_payload_no_token)
        
        assert "Token obrigatório para cartão" in str(exc_info.value)
        
        # MP não deve ser chamado
        mock_mercadopago.payment.assert_not_called()

    def test_process_payment_uses_backend_calculated_amount(
        self,
        mock_repository: MagicMock,
        mock_mercadopago: MagicMock,
        valid_pix_payload
    ) -> None:
        """
        Cenário: Front envia R$ 100, banco calcula R$ 100.50 (dentro da margem).
        Esperado: MP recebe o valor CALCULADO pelo backend (R$ 100.50), não o do front.
        """
        # Arrange: Banco retorna preço ligeiramente diferente (50.25 * 2 = 100.50)
        mock_repository.get_product_price.return_value = {"id": 1, "price": 50.25}
        
        mock_payment_method = MagicMock()
        mock_mercadopago.payment.return_value = mock_payment_method
        mock_payment_method.create.return_value = {
            "status": 201,
            "response": {"id": "mp-123", "status": "pending", "status_detail": "pending"}
        }
        mock_repository.create_order.return_value = {"id": "order-123"}
        
        # Act
        service = PaymentService()
        service.process_payment(valid_pix_payload)
        
        # Assert: MP deve receber 100.50 (valor do backend), não 100.00 (valor do front)
        payment_data = mock_payment_method.create.call_args[0][0]
        assert payment_data["transaction_amount"] == 100.50  # Valor autoritativo do backend

    def test_process_payment_with_address_includes_payer_address(
        self,
        mock_repository: MagicMock,
        mock_mercadopago: MagicMock
    ) -> None:
        """
        Cenário: Payload inclui endereço do pagador.
        Esperado: Endereço é enviado ao MP no formato correto.
        """
        # Arrange
        from schemas import Address
        
        payload_with_address = PaymentInput(
            transaction_amount=50.00,
            payment_method_id="pix",
            payer=Payer(
                email="jose@example.com",
                first_name="José",
                last_name="Oliveira",
                identification=Identification(type="CPF", number="11111111111"),
                address=Address(
                    zip_code="30130-100",
                    street_name="Av. Afonso Pena",
                    street_number="1000",
                    neighborhood="Centro",
                    city="Belo Horizonte",
                    federal_unit="MG"
                )
            ),
            user_id="user-with-address",
            items=[Item(id=1, name="Item", price=50.00, quantity=1)]
        )
        
        mock_repository.get_product_price.return_value = {"id": 1, "price": 50.00}
        
        mock_payment_method = MagicMock()
        mock_mercadopago.payment.return_value = mock_payment_method
        mock_payment_method.create.return_value = {
            "status": 201,
            "response": {"id": "mp-addr-123", "status": "approved", "status_detail": "accredited"}
        }
        mock_repository.create_order.return_value = {"id": "order-addr-456"}
        
        # Act
        service = PaymentService()
        service.process_payment(payload_with_address)
        
        # Assert: Verifica que endereço foi incluído
        payment_data = mock_payment_method.create.call_args[0][0]
        assert "address" in payment_data["payer"]
        assert payment_data["payer"]["address"]["zip_code"] == "30130-100"
        assert payment_data["payer"]["address"]["city"] == "Belo Horizonte"
        assert payment_data["payer"]["address"]["federal_unit"] == "MG"
