"""Testes da validação de frete no PaymentService (Melhor Envio)."""

import pytest
from unittest.mock import patch, MagicMock

from src.payment.service import PaymentService
from src.payment.schemas import PaymentInput, Payer, Identification, Item
from src.shared.melhor_envio import MelhorEnvioAPIError


@pytest.fixture
def mock_repository():
    with patch("src.payment.service.PaymentRepository") as mock_repo_class:
        mock_instance = MagicMock()
        mock_repo_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_mercadopago():
    with patch("src.payment.service.mercadopago.SDK") as mock_mp:
        yield mock_mp


def _payload(frete: float = 25.90, cep: str = "01310100", frete_service: str = "jadlog_package") -> PaymentInput:
    return PaymentInput(
        transaction_amount=100.00 + frete,  # subtotal 100 + frete
        payment_method_id="pix",
        installments=1,
        payer=Payer(
            email="test@example.com",
            identification=Identification(number="12345678900"),
        ),
        user_id="user-123",
        items=[Item(id=1, name="Produto", price=100.0, quantity=1)],
        frete=frete,
        frete_service=frete_service,
        cep=cep,
    )


OPTION_PAC = {"transportadora": "PAC", "preco": 25.90, "prazo_entrega_dias": 8, "service": "jadlog_package"}
OPTION_JADLOG = {"transportadora": "Jadlog", "preco": 31.00, "prazo_entrega_dias": 5, "service": "jadlog_another"}


class TestPaymentServiceFreightValidation:
    """Frete enviado deve coincidir com cotação Melhor Envio."""

    def test_freight_valid_matches_quote(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock
    ) -> None:
        with patch("src.payment.service.get_quote") as mock_get_quote:
            mock_get_quote.return_value = [OPTION_PAC]
            mock_repository.get_product_price.return_value = {"id": 1, "price": 100.00}
            mock_mp = mock_mercadopago.return_value
            mock_mp.payment.return_value.create.return_value = {
                "status": 201,
                "response": {"id": "mp-1", "status": "approved", "status_detail": "accredited"},
            }
            mock_repository.create_order.return_value = {"id": "order-1"}

            service = PaymentService()
            result = service.process_payment(_payload(frete=25.90))

            assert result is not None
            mock_get_quote.assert_called_once()
            call_cep, call_products = mock_get_quote.call_args[0]
            assert call_cep == "01310100"
            assert len(call_products) == 1
            assert call_products[0]["quantity"] == 1

    def test_freight_valid_within_tolerance(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock
    ) -> None:
        with patch("src.payment.service.get_quote") as mock_get_quote:
            mock_get_quote.return_value = [OPTION_PAC]
            mock_repository.get_product_price.return_value = {"id": 1, "price": 100.00}
            mock_mp = mock_mercadopago.return_value
            mock_mp.payment.return_value.create.return_value = {
                "status": 201,
                "response": {"id": "mp-1", "status": "approved", "status_detail": "accredited"},
            }
            mock_repository.create_order.return_value = {"id": "order-1"}

            service = PaymentService()
            service.process_payment(_payload(frete=25.91))

            mock_repository.create_order.assert_called_once()

    def test_freight_invalid_divergence_raises_value_error(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock
    ) -> None:
        with patch("src.payment.service.get_quote") as mock_get_quote:
            mock_get_quote.return_value = [OPTION_PAC]
            service = PaymentService()
            with pytest.raises(ValueError) as exc_info:
                service.process_payment(_payload(frete=15.00))
            assert "não confere" in str(exc_info.value) or "Recalcule" in str(exc_info.value)
            mock_repository.get_product_price.assert_not_called()

    def test_freight_no_options_raises_value_error(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock
    ) -> None:
        with patch("src.payment.service.get_quote") as mock_get_quote:
            mock_get_quote.return_value = []
            service = PaymentService()
            with pytest.raises(ValueError) as exc_info:
                service.process_payment(_payload())
            assert "nenhuma opção" in str(exc_info.value).lower()

    def test_freight_api_error_raises_melhor_envio_error(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock
    ) -> None:
        with patch("src.payment.service.get_quote") as mock_get_quote:
            mock_get_quote.side_effect = MelhorEnvioAPIError("Timeout ao conectar")
            service = PaymentService()
            with pytest.raises(MelhorEnvioAPIError) as exc_info:
                service.process_payment(_payload())
            assert "Frete" in str(exc_info.value) or "Timeout" in str(exc_info.value)
            mock_repository.get_product_price.assert_not_called()

    def test_freight_matches_chosen_service_option(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock
    ) -> None:
        with patch("src.payment.service.get_quote") as mock_get_quote:
            mock_get_quote.return_value = [OPTION_PAC, OPTION_JADLOG]
            mock_repository.get_product_price.return_value = {"id": 1, "price": 100.00}
            mock_mp = mock_mercadopago.return_value
            mock_mp.payment.return_value.create.return_value = {
                "status": 201,
                "response": {"id": "mp-1", "status": "approved", "status_detail": "accredited"},
            }
            mock_repository.create_order.return_value = {"id": "order-1"}

            service = PaymentService()
            service.process_payment(_payload(frete=31.00, frete_service="jadlog_another"))
            mock_repository.create_order.assert_called_once()

    def test_freight_service_not_found_raises_value_error(
        self, mock_repository: MagicMock, mock_mercadopago: MagicMock
    ) -> None:
        with patch("src.payment.service.get_quote") as mock_get_quote:
            mock_get_quote.return_value = [OPTION_PAC]
            service = PaymentService()
            with pytest.raises(ValueError) as exc_info:
                service.process_payment(_payload(frete=25.90, frete_service="servico_inexistente"))
            assert "não encontrado" in str(exc_info.value) or "Recalcule" in str(exc_info.value)
