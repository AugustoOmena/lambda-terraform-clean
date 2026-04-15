"""Carrinho Melhor Envio após pagamento: persiste ``melhor_envio_order_id``."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.payment.schemas import Address, Identification, Item, Payer, PaymentInput
from src.payment.service import PaymentService


def _sender_profile() -> str:
    return json.dumps(
        {
            "name": "Loja Teste",
            "phone": "11988887777",
            "email": "loja@test.com",
            "document": "12345678901234",
            "address": {
                "postal_code": "01310100",
                "address": "Av Paulista",
                "number": "1000",
                "complement": "",
                "district": "Bela Vista",
                "city": "São Paulo",
                "state_abbr": "SP",
            },
        }
    )


@pytest.fixture
def payment_payload() -> PaymentInput:
    return PaymentInput(
        transaction_amount=125.90,
        payment_method_id="pix",
        installments=1,
        payer=Payer(
            email="buyer@test.com",
            phone="11977776666",
            identification=Identification(number="12345678900"),
            address=Address(
                zip_code="01310100",
                street_name="Rua X",
                street_number="10",
                neighborhood="Centro",
                city="São Paulo",
                federal_unit="SP",
            ),
        ),
        user_id="user-1",
        items=[Item(id=1, name="Produto", price=100.0, quantity=1)],
        frete=25.90,
        frete_service="3",
        cep="01310100",
    )


class TestMelhorEnvioCartAfterPayment:
    def test_persists_melhor_envio_order_id_on_cart_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
        payment_payload: PaymentInput,
    ) -> None:
        monkeypatch.setenv("ME_SENDER_PROFILE", _sender_profile())
        with patch("src.payment.service.PaymentRepository") as mock_repo_cls:
            with patch("src.payment.service.get_quote") as mock_quote:
                with patch("src.payment.service.add_to_cart") as mock_cart:
                    mock_repo = mock_repo_cls.return_value
                    mock_repo.get_product_price_and_stock.return_value = {
                        "id": 1,
                        "price": 100.00,
                        "stock": {"Único": 100},
                        "quantity": 100,
                    }
                    mock_quote.return_value = [
                        {"transportadora": "PAC", "preco": 25.90, "prazo_entrega_dias": 8, "service": 3},
                    ]
                    mock_cart.return_value = {"id": "me-order-uuid-99"}
                    mock_repo.create_order.return_value = {"id": "db-order-1"}
                    with patch("mercadopago.SDK"):
                        with patch.object(PaymentService, "__init__", lambda self: None):
                            svc = PaymentService.__new__(PaymentService)
                            svc.repo = mock_repo
                            import mercadopago as _mp

                            svc._mp = _mp
                            svc.mp = _mp.SDK(None)
                            svc.mp.payment.return_value.create.return_value = {
                                "status": 201,
                                "response": {
                                    "id": "mp-1",
                                    "status": "approved",
                                    "status_detail": "accredited",
                                },
                            }
                            svc.process_payment(payment_payload)
                    mock_cart.assert_called_once()
                    mock_repo.update_melhor_envio_order_id.assert_called_once_with(
                        "db-order-1",
                        "me-order-uuid-99",
                    )
