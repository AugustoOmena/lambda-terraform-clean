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
    """Payload válido de pagamento para usar nos testes (inclui frete e cep)."""
    return PaymentInput(
        transaction_amount=100.00,
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
        cep="01310100",
    )


@pytest.fixture
def mock_get_quote():
    """Mock get_quote para passar na validação de frete (valor 25.90)."""
    with patch("src.payment.service.get_quote") as m:
        m.return_value = [{"transportadora": "PAC", "preco": 25.90, "prazo_entrega_dias": 8}]
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
        mock_repository.get_product_price.return_value = {"id": 1, "price": 50.00}
        
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
        mock_repository.get_product_price.assert_called_once_with(1)
        mock_repository.create_order.assert_called_once()

    def test_audit_success_with_minor_difference_under_1_real(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, valid_payment_payload, mock_get_quote
    ) -> None:
        """
        Cenário: Front envia R$ 100.00, banco calcula R$ 100.50 (diferença < R$ 1.00).
        Esperado: Auditoria passa (margem de tolerância).
        """
        # Arrange: Banco retorna preço ligeiramente diferente
        mock_repository.get_product_price.return_value = {"id": 1, "price": 50.25}
        
        mock_mp_instance = mock_mercadopago.return_value
        mock_mp_instance.payment.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "mp-456",
                "status": "approved",
                "status_detail": "accredited"
            }
        }
        mock_repository.create_order.return_value = {"id": "order-456"}
        
        # Act
        service = PaymentService()
        result = service.process_payment(valid_payment_payload)
        
        # Assert: Não deve lançar exceção
        assert result is not None
        mock_repository.create_order.assert_called_once()

    def test_audit_failure_divergence_exceeds_tolerance(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, valid_payment_payload, mock_get_quote
    ) -> None:
        """
        Cenário: Front envia R$ 100.00, mas banco calcula R$ 500.00 (diferença > R$ 1.00).
        Esperado: Lança Exception com mensagem de divergência e detalhes dos itens.
        """
        # Arrange: Preço no banco é MUITO maior (R$ 250.00 * 2 = R$ 500.00)
        mock_repository.get_product_price.return_value = {"id": 1, "price": 250.00}
        
        # Act & Assert: Deve lançar exceção
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(valid_payment_payload)
        
        # Verifica que a mensagem contém os valores divergentes e detalhes
        error_msg = str(exc_info.value)
        assert "Divergência" in error_msg
        assert "100.00" in error_msg  # Total do front
        assert "500.00" in error_msg or "500.0" in error_msg  # Total calculado pelo back
        assert "ID:1" in error_msg    # Detalhes do item no log
        assert "Qtd:2" in error_msg
        assert "PreçoDB:250" in error_msg  # Aceita 250.0 ou 250.00

    def test_audit_product_not_found_in_database(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, valid_payment_payload, mock_get_quote
    ) -> None:
        """
        Cenário: Front envia produto ID 1, mas repositório retorna None (produto inexistente).
        Esperado: Lança Exception informando que produto não foi encontrado.
        """
        # Arrange: Repository retorna None (produto não existe)
        mock_repository.get_product_price.return_value = None
        
        # Act & Assert
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(valid_payment_payload)
        
        # Verifica mensagem de erro
        error_msg = str(exc_info.value)
        assert "Produto ID 1 não encontrado" in error_msg

    def test_audit_empty_items_list(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, mock_get_quote
    ) -> None:
        """
        Cenário: Front envia lista de itens vazia.
        Esperado: Lança Exception antes de qualquer cálculo.
        """
        # Arrange: Payload com lista de itens vazia (frete/cep obrigatórios no schema)
        empty_payload = PaymentInput(
            transaction_amount=100.00,
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
            cep="01310100",
        )
        
        # Act & Assert
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(empty_payload)
        
        # Verifica mensagem de erro
        error_msg = str(exc_info.value)
        assert "lista de itens vazia" in error_msg
        assert "R$ 100.0" in error_msg  # Deve mencionar o valor que o front enviou
        
        # Repository NÃO deve ser chamado (falha antes)
        mock_repository.get_product_price.assert_not_called()

    def test_audit_multiple_items_price_calculation(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, mock_get_quote
    ) -> None:
        """
        Cenário: Múltiplos itens com quantidades diferentes.
        Esperado: Soma correta (item1: R$ 30 x 2 = R$ 60, item2: R$ 20 x 1 = R$ 20, total = R$ 80).
        """
        # Arrange
        payload = PaymentInput(
            transaction_amount=80.00,
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
            cep="01310100",
        )
        
        # Mock retorna preços diferentes para cada produto
        def get_price_side_effect(product_id):
            prices = {
                1: {"id": 1, "price": 30.00},
                2: {"id": 2, "price": 20.00}
            }
            return prices.get(product_id)
        
        mock_repository.get_product_price.side_effect = get_price_side_effect
        
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
        assert mock_repository.get_product_price.call_count == 2
        mock_repository.create_order.assert_called_once()

    def test_audit_handles_none_price_from_database(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock, valid_payment_payload, mock_get_quote
    ) -> None:
        """
        Cenário: Banco retorna produto mas com price=None.
        Esperado: Código trata como 0.00 (conversão segura linhas 27-28 do service).
        """
        # Arrange: Produto existe mas price é None
        mock_repository.get_product_price.return_value = {"id": 1, "price": None}
        
        # Act & Assert: Vai calcular total como 0.00, divergência com front (100.00)
        service = PaymentService()
        with pytest.raises(Exception) as exc_info:
            service.process_payment(valid_payment_payload)
        
        error_msg = str(exc_info.value)
        assert "Divergência" in error_msg
        # Front: 100.00, Back calcula: 0.00 (None virou 0)
        assert "100.00" in error_msg
        assert "0.00" in error_msg or "PreçoDB:0" in error_msg
