import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from src.payment.service import PaymentService
from src.payment.schemas import PaymentInput, Payer, Identification, Item


@pytest.fixture
def mock_repository():
    """Mock do PaymentRepository para isolar testes da auditoria de preços."""
    with patch("src.payment.service.PaymentRepository") as mock_repo_class:
        mock_instance = MagicMock()
        mock_repo_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_mercadopago():
    """Mock do Mercado Pago SDK para focar apenas na auditoria."""
    with patch("src.payment.service.mercadopago.SDK") as mock_mp:
        yield mock_mp


@pytest.fixture
def valid_payment_payload():
    """Payload válido: transaction_amount = subtotal (100) + frete (25.90) = 125.90."""
    return PaymentInput(
        transaction_amount=125.90,  # 50*2 + 25.90
        payment_method_id="pix",
        installments=1,
        payer=Payer(
            email="test@example.com",
            first_name="João",
            last_name="Silva",
            identification=Identification(type="CPF", number="12345678900")
        ),
        user_id="user-123",
        items=[Item(id=1, name="Camiseta", price=50.00, quantity=2)],
        frete=25.90,
        frete_service="jadlog_package",
        cep="01310100",
    )


@pytest.fixture
def mock_get_quote():
    """Mock get_quote para passar na validação de frete (valor 25.90, service jadlog_package)."""
    with patch("src.payment.service.get_quote") as m:
        m.return_value = [{"transportadora": "PAC", "preco": 25.90, "prazo_entrega_dias": 8, "service": "jadlog_package"}]
        yield m


class TestPaymentServiceAudit:
    """Testes focados na regra de Auditoria de Preços do PaymentService."""

    def test_audit_success_price_matches_within_tolerance(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, valid_payment_payload, mock_get_quote
    ) -> None:
        """
        Cenário: Front envia R$ 100.00 e banco retorna preço que resulta em R$ 100.00.
        Esperado: Auditoria passa, fluxo continua (não lança exceção).
        """
        # Arrange: Mock retorna preço do banco que bate com o front
        mock_repository.get_product_price_and_stock.return_value = {"id": 1, "price": 50.00, "stock": {"Único": 100}, "quantity": 100}
        
        # Mock Mercado Pago para não falhar (não é o foco deste teste)
        mock_mp_instance = mock_mercadopago.return_value
        mock_mp_instance.payment.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "mp-123",
                "status": "approved",
                "status_detail": "accredited"
            }
        }
        mock_repository.create_order.return_value = {"id": "order-123"}
        
        # Act: Executa o pagamento
        service = PaymentService()
        result = service.process_payment(valid_payment_payload)
        
        # Assert: Não deve lançar exceção e deve chamar create_order
        assert result is not None
        mock_repository.get_product_price_and_stock.assert_called_once_with(1)
        mock_repository.create_order.assert_called_once()

    def test_audit_success_with_minor_difference_under_1_real(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, mock_get_quote
    ) -> None:
        """
        Cenário: Banco retorna 50.25 (subtotal 100.50); total = 100.50 + 25.90 = 126.40.
        Front envia 126.40. Esperado: Auditoria passa.
        """
        payload = PaymentInput(
            transaction_amount=126.40,
            payment_method_id="pix",
            installments=1,
            payer=Payer(email="t@t.com", identification=Identification(number="12345678900")),
            user_id="user-123",
            items=[Item(id=1, name="Camiseta", price=50.00, quantity=2)],
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310100",
        )
        mock_repository.get_product_price_and_stock.return_value = {"id": 1, "price": 50.25, "stock": {"Único": 100}, "quantity": 100}
        mock_mp_instance = mock_mercadopago.return_value
        mock_mp_instance.payment.return_value.create.return_value = {
            "status": 201,
            "response": {"id": "mp-456", "status": "approved", "status_detail": "accredited"}
        }
        mock_repository.create_order.return_value = {"id": "order-456"}
        service = PaymentService()
        result = service.process_payment(payload)
        assert result is not None
        mock_repository.create_order.assert_called_once()

    def test_audit_failure_divergence_exceeds_tolerance(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, valid_payment_payload, mock_get_quote
    ) -> None:
        """
        Cenário: Front envia R$ 100.00, mas banco calcula R$ 500.00 (diferença > R$ 1.00).
        Esperado: Lança Exception com mensagem de divergência e detalhes dos itens.
        """
        # Arrange: Preço no banco é MUITO maior (R$ 250.00 * 2 = R$ 500.00 subtotal); total esperado = 500 + 25.90
        mock_repository.get_product_price_and_stock.return_value = {"id": 1, "price": 250.00, "stock": {"Único": 100}, "quantity": 100}
        payload_divergente = PaymentInput(
            transaction_amount=125.90,  # front envia subtotal+frete (mas subtotal real do back é 500)
            payment_method_id="pix",
            installments=1,
            payer=Payer(email="t@t.com", identification=Identification(number="12345678900")),
            user_id="user-123",
            items=[Item(id=1, name="Camiseta", price=50.00, quantity=2)],
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310100",
        )
        # Act & Assert: Deve lançar exceção
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(payload_divergente)
        error_msg = str(exc_info.value)
        assert "Divergência" in error_msg
        assert "125.90" in error_msg  # Total do front
        assert "525.90" in error_msg or "525.9" in error_msg  # Back: subtotal 500 + frete 25.90
        assert "ID:1" in error_msg
        assert "PreçoDB:250" in error_msg

    def test_audit_product_not_found_in_database(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, valid_payment_payload, mock_get_quote
    ) -> None:
        """
        Cenário: Front envia produto ID 1, mas repositório retorna None (produto inexistente).
        Esperado: Lança Exception informando que produto não foi encontrado.
        """
        # Arrange: Repository retorna None (produto não existe)
        mock_repository.get_product_price_and_stock.return_value = None
        
        # Act & Assert
        service = PaymentService()
        with pytest.raises(ValueError) as exc_info:
            service.process_payment(valid_payment_payload)
        assert "não encontrado" in str(exc_info.value)

    def test_audit_insufficient_stock_raises_friendly_error(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, mock_get_quote
    ) -> None:
        """Estoque insuficiente deve retornar mensagem amigável (sem cobrar no MP)."""
        mock_repository.get_product_price_and_stock.return_value = {
            "id": 1, "price": 50.00, "stock": {"Único": 2}, "quantity": 2
        }
        payload = PaymentInput(
            transaction_amount=125.90,
            payment_method_id="pix",
            installments=1,
            payer=Payer(email="t@t.com", identification=Identification(number="12345678900")),
            user_id="user-123",
            items=[Item(id=1, name="Chapéu", price=50.00, quantity=7)],
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310100",
        )
        service = PaymentService()
        with pytest.raises(ValueError) as exc_info:
            service.process_payment(payload)
        msg = str(exc_info.value)
        assert "Chapéu" in msg
        assert "fora de estoque" in msg or "não está disponível" in msg
        assert "7" in msg and "2" in msg
        mock_mercadopago.return_value.payment.return_value.create.assert_not_called()

    def test_audit_empty_items_list(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, mock_get_quote
    ) -> None:
        """
        Cenário: Front envia lista de itens vazia.
        Esperado: Lança Exception antes de qualquer cálculo.
        """
        # Arrange: Payload com lista de itens vazia (frete/cep obrigatórios no schema)
        empty_payload = PaymentInput(
            transaction_amount=25.90,  # só frete (sem itens)
            payment_method_id="pix",
            installments=1,
            payer=Payer(
                email="test@example.com",
                first_name="João",
                last_name="Silva",
                identification=Identification(type="CPF", number="12345678900")
            ),
            user_id="user-123",
            items=[],  # LISTA VAZIA
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310100",
        )
        
        # Act & Assert: falha antes (lista vazia)
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(empty_payload)
        error_msg = str(exc_info.value)
        assert "lista de itens vazia" in error_msg
        assert "25.9" in error_msg  # valor que o front enviou
        
        # Repository NÃO deve ser chamado (falha antes)
        mock_repository.get_product_price_and_stock.assert_not_called()

    def test_audit_multiple_items_price_calculation(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, mock_get_quote
    ) -> None:
        """
        Cenário: Múltiplos itens com quantidades diferentes.
        Esperado: Soma correta (item1: R$ 30 x 2 = R$ 60, item2: R$ 20 x 1 = R$ 20, total = R$ 80).
        """
        # Arrange
        # Subtotal 30*2 + 20*1 = 80; total esperado = 80 + 25.90 = 105.90
        payload = PaymentInput(
            transaction_amount=105.90,
            payment_method_id="pix",
            installments=1,
            payer=Payer(
                email="test@example.com",
                first_name="Maria",
                last_name="Santos",
                identification=Identification(type="CPF", number="98765432100")
            ),
            user_id="user-456",
            items=[
                Item(id=1, name="Camiseta", price=30.00, quantity=2),
                Item(id=2, name="Boné", price=20.00, quantity=1),
            ],
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310100",
        )
        
        def get_price_side_effect(product_id):
            prices = {
                1: {"id": 1, "price": 30.00, "stock": {"Único": 100}, "quantity": 100},
                2: {"id": 2, "price": 20.00, "stock": {"Único": 100}, "quantity": 100},
            }
            return prices.get(product_id)
        
        mock_repository.get_product_price_and_stock.side_effect = get_price_side_effect
        
        mock_mp_instance = mock_mercadopago.return_value
        mock_mp_instance.payment.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "mp-789",
                "status": "approved",
                "status_detail": "accredited"
            }
        }
        mock_repository.create_order.return_value = {"id": "order-789"}
        
        # Act
        service = PaymentService()
        result = service.process_payment(payload)
        
        # Assert: Não deve lançar exceção, valores batem
        assert result is not None
        assert mock_repository.get_product_price_and_stock.call_count == 2
        mock_repository.create_order.assert_called_once()

    def test_audit_handles_none_price_from_database(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, valid_payment_payload, mock_get_quote
    ) -> None:
        """
        Cenário: Banco retorna produto mas com price=None.
        Esperado: Código trata como 0.00 (conversão segura linhas 27-28 do service).
        """
        # Arrange: Produto existe mas price é None
        mock_repository.get_product_price_and_stock.return_value = {"id": 1, "price": None, "stock": {"Único": 100}, "quantity": 100}
        
        # Act & Assert: Subtotal 0 (price None), total_esperado = 0 + 25.90 = 25.90; front envia 125.90
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(valid_payment_payload)
        error_msg = str(exc_info.value)
        assert "Divergência" in error_msg
        assert "125.90" in error_msg
        assert "25.90" in error_msg  # total_esperado (0 + frete)
