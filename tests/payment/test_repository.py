import pytest
from unittest.mock import patch, MagicMock, call

from src.payment.repository import PaymentRepository
from src.payment.schemas import Item


@pytest.fixture
def mock_supabase_client():
    """Mock do cliente Supabase com estrutura encadeada de métodos."""
    with patch("src.payment.repository.get_supabase_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_order_items():
    """Lista de itens para testes de pedidos."""
    return [
        Item(id=1, name="Camiseta", price=50.00, quantity=2, size="M"),
        Item(id=2, name="Calça", price=100.00, quantity=1, size="G")
    ]


class TestPaymentRepositoryGetProductPrice:
    """Testes para o método get_product_price."""

    def test_get_product_price_found(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Produto existe no banco.
        Esperado: Retorna dict com id e price.
        """
        # Arrange: Mock da cadeia de métodos do Supabase
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        mock_execute.data = [{"id": 1, "price": 50.00}]
        
        # Act
        repo = PaymentRepository()
        result = repo.get_product_price(1)
        
        # Assert
        assert result == {"id": 1, "price": 50.00}
        mock_supabase_client.table.assert_called_once_with("products")
        mock_table.select.assert_called_once_with("id, price")
        mock_select.eq.assert_called_once_with("id", 1)

    def test_get_product_price_not_found(self, mock_supabase_client: MagicMock) -> None:
        """
        Cenário: Produto não existe no banco.
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
        mock_execute.data = []  # Produto não encontrado
        
        # Act
        repo = PaymentRepository()
        result = repo.get_product_price(999)
        
        # Assert
        assert result is None


class TestPaymentRepositoryUpdateStock:
    """Testes para o método update_stock (lógica complexa de JSON stock)."""

    def test_update_stock_exact_size_match_reduces_correctly(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Produto tem {"M": 10}, venda de 2 unidades tamanho "M".
        Esperado: stock atualizado para {"M": 8}, quantity=8.
        """
        # Arrange: Mock select (busca produto)
        mock_table_select = MagicMock()
        mock_select = MagicMock()
        mock_eq_select = MagicMock()
        mock_execute_select = MagicMock()
        
        mock_supabase_client.table.return_value = mock_table_select
        mock_table_select.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq_select
        mock_eq_select.execute.return_value = mock_execute_select
        mock_execute_select.data = [
            {"stock": {"M": 10}, "quantity": 10}
        ]
        
        # Mock update (atualiza produto)
        mock_table_update = MagicMock()
        mock_update = MagicMock()
        mock_eq_update = MagicMock()
        mock_execute_update = MagicMock()
        
        # Configura para retornar o mock_table_update quando update for chamado
        # mas preserva o select anterior
        def table_side_effect(table_name):
            if mock_supabase_client.table.call_count <= 1:
                return mock_table_select
            else:
                return mock_table_update
        
        mock_supabase_client.table.side_effect = table_side_effect
        mock_table_update.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq_update
        mock_eq_update.execute.return_value = mock_execute_update
        
        # Act
        repo = PaymentRepository()
        items = [Item(id=1, name="Camiseta", price=50.00, quantity=2, size="M")]
        repo.update_stock(items)
        
        # Assert: Verifica que update foi chamado com valores corretos
        mock_table_update.update.assert_called_once()
        update_data = mock_table_update.update.call_args[0][0]
        
        assert update_data["stock"] == {"M": 8}
        assert update_data["quantity"] == 8
        mock_update.eq.assert_called_once_with("id", 1)

    def test_update_stock_multiple_sizes_calculates_total_correctly(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Produto tem {"P": 5, "M": 10, "G": 3}, venda de 2 "M".
        Esperado: stock={"P": 5, "M": 8, "G": 3}, quantity=16 (5+8+3).
        """
        # Arrange
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        
        # Select (primeira chamada)
        mock_select = MagicMock()
        mock_eq_select = MagicMock()
        mock_execute_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq_select
        mock_eq_select.execute.return_value = mock_execute_select
        mock_execute_select.data = [
            {"stock": {"P": 5, "M": 10, "G": 3}, "quantity": 18}
        ]
        
        # Update (segunda chamada ao table)
        mock_update = MagicMock()
        mock_eq_update = MagicMock()
        mock_execute_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq_update
        mock_eq_update.execute.return_value = mock_execute_update
        
        # Act
        repo = PaymentRepository()
        items = [Item(id=1, name="Camiseta", price=50.00, quantity=2, size="M")]
        repo.update_stock(items)
        
        # Assert
        update_data = mock_table.update.call_args[0][0]
        assert update_data["stock"] == {"P": 5, "M": 8, "G": 3}
        assert update_data["quantity"] == 16

    def test_update_stock_fallback_to_unico_when_size_not_found(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Produto tem {"Único": 5}, item vendido sem tamanho ou tamanho inválido.
        Esperado: Desconta de "Único", stock={"Único": 4}, quantity=4.
        """
        # Arrange
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        
        mock_select = MagicMock()
        mock_eq_select = MagicMock()
        mock_execute_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq_select
        mock_eq_select.execute.return_value = mock_execute_select
        mock_execute_select.data = [
            {"stock": {"Único": 5}, "quantity": 5}
        ]
        
        mock_update = MagicMock()
        mock_eq_update = MagicMock()
        mock_execute_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq_update
        mock_eq_update.execute.return_value = mock_execute_update
        
        # Act: Item sem tamanho (size=None ou não especificado, usa default "Único")
        repo = PaymentRepository()
        items = [Item(id=1, name="Produto Único", price=30.00, quantity=1)]
        repo.update_stock(items)
        
        # Assert
        update_data = mock_table.update.call_args[0][0]
        assert update_data["stock"] == {"Único": 4}
        assert update_data["quantity"] == 4

    def test_update_stock_prevents_negative_stock(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Produto tem {"M": 2}, venda de 5 unidades (overselling).
        Esperado: stock não fica negativo, fica em {"M": 0}, quantity=0.
        """
        # Arrange
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        
        mock_select = MagicMock()
        mock_eq_select = MagicMock()
        mock_execute_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq_select
        mock_eq_select.execute.return_value = mock_execute_select
        mock_execute_select.data = [
            {"stock": {"M": 2}, "quantity": 2}
        ]
        
        mock_update = MagicMock()
        mock_eq_update = MagicMock()
        mock_execute_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq_update
        mock_eq_update.execute.return_value = mock_execute_update
        
        # Act
        repo = PaymentRepository()
        items = [Item(id=1, name="Camiseta", price=50.00, quantity=5, size="M")]
        repo.update_stock(items)
        
        # Assert: Usa max(0, ...) para prevenir negativo
        update_data = mock_table.update.call_args[0][0]
        assert update_data["stock"] == {"M": 0}
        assert update_data["quantity"] == 0

    def test_update_stock_handles_product_not_found_gracefully(
        self, mock_supabase_client: MagicMock, capfd
    ) -> None:
        """
        Cenário: Produto não existe no banco.
        Esperado: Continue sem quebrar (log de erro, mas não lança exceção).
        """
        # Arrange
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        
        mock_select = MagicMock()
        mock_eq_select = MagicMock()
        mock_execute_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq_select
        mock_eq_select.execute.return_value = mock_execute_select
        mock_execute_select.data = []  # Produto não encontrado
        
        # Act: Não deve lançar exceção
        repo = PaymentRepository()
        items = [Item(id=999, name="Inexistente", price=10.00, quantity=1)]
        repo.update_stock(items)
        
        # Assert: update NÃO deve ter sido chamado
        mock_table.update.assert_not_called()


class TestPaymentRepositoryCreateOrder:
    """Testes para o método create_order."""

    def test_create_order_structure_includes_price_and_price_at_purchase(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Criar pedido com itens.
        Esperado: order_items tem TANTO 'price' QUANTO 'price_at_purchase' (compatibilidade).
        """
        # Arrange
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        
        # Mock insert de order
        mock_insert_order = MagicMock()
        mock_execute_order = MagicMock()
        mock_table.insert.return_value = mock_insert_order
        mock_insert_order.execute.return_value = mock_execute_order
        mock_execute_order.data = [{"id": "order-123"}]
        
        # Mock insert de order_items
        mock_insert_items = MagicMock()
        mock_execute_items = MagicMock()
        # Segunda chamada ao insert (para itens)
        mock_table.insert.side_effect = [mock_insert_order, mock_insert_items]
        mock_insert_items.execute.return_value = mock_execute_items
        
        # Payloads simulados
        from src.payment.schemas import PaymentInput, Payer, Identification
        payload = PaymentInput(
            transaction_amount=150.00,
            payment_method_id="pix",
            installments=1,
            payer=Payer(
                email="test@example.com",
                first_name="Test",
                last_name="User",
                identification=Identification(type="CPF", number="12345678900")
            ),
            user_id="user-123",
            items=[
                Item(id=1, name="Produto A", price=50.00, quantity=2, image="img.png"),
                Item(id=2, name="Produto B", price=50.00, quantity=1)
            ],
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310100",
        )
        
        mp_response = {"id": "mp-123", "status": "approved"}
        
        # Act
        repo = PaymentRepository()
        result = repo.create_order(payload, mp_response, 150.00)
        
        # Assert: Verifica estrutura do order
        assert result == {"id": "order-123"}
        
        # Verifica que insert de order foi chamado
        order_insert_call = mock_table.insert.call_args_list[0]
        order_data = order_insert_call[0][0]
        assert order_data["user_id"] == "user-123"
        assert order_data["total_amount"] == 150.00
        assert order_data["mp_payment_id"] == "mp-123"
        
        # Verifica que insert de items foi chamado com ambos os campos
        items_insert_call = mock_table.insert.call_args_list[1]
        items_data = items_insert_call[0][0]
        
        assert len(items_data) == 2
        
        # Item 1
        assert items_data[0]["product_id"] == 1
        assert items_data[0]["quantity"] == 2
        assert items_data[0]["price"] == 50.00  # Campo legado
        assert items_data[0]["price_at_purchase"] == 50.00  # Campo novo
        assert items_data[0]["image_url"] == "img.png"
        
        # Item 2
        assert items_data[1]["product_id"] == 2
        assert items_data[1]["price"] == 50.00
        assert items_data[1]["price_at_purchase"] == 50.00

    def test_create_order_raises_exception_if_order_insert_fails(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Insert do order retorna data vazio (falha).
        Esperado: Lança Exception.
        """
        # Arrange
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = []  # Falha ao salvar
        
        from src.payment.schemas import PaymentInput, Payer, Identification
        payload = PaymentInput(
            transaction_amount=100.00,
            payment_method_id="pix",
            payer=Payer(
                email="test@example.com",
                identification=Identification(number="12345678900")
            ),
            user_id="user-123",
            items=[Item(id=1, name="Produto", price=100.00, quantity=1)],
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310100",
        )
        
        # Act & Assert
        repo = PaymentRepository()
        with pytest.raises(Exception) as exc_info:
            repo.create_order(payload, {"id": "mp-123"}, 100.00)
        
        assert "Falha ao salvar pedido" in str(exc_info.value)

    def test_create_order_handles_empty_items_gracefully(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """
        Cenário: Payload sem itens (items vazio).
        Esperado: Order criada, mas insert de items não é chamado.
        """
        # Arrange
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = [{"id": "order-empty-items"}]
        
        from src.payment.schemas import PaymentInput, Payer, Identification
        payload = PaymentInput(
            transaction_amount=0.00,
            payment_method_id="pix",
            payer=Payer(
                email="test@example.com",
                identification=Identification(number="12345678900")
            ),
            user_id="user-123",
            items=[],  # Lista vazia
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310100",
        )
        
        # Act
        repo = PaymentRepository()
        result = repo.create_order(payload, {"id": "mp-empty"}, 0.00)
        
        # Assert: Order criada, mas items insert só foi chamado 1 vez (para order)
        assert result == {"id": "order-empty-items"}
        assert mock_table.insert.call_count == 1  # Apenas o order, não os items
