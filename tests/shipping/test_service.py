import pytest
from unittest.mock import patch, MagicMock

from src.shipping.schemas import FreightQuoteInput, ShippingItemInput
from src.shipping.service import quote_freight
from src.shared.melhor_envio import MelhorEnvioAPIError


@pytest.fixture
def valid_quote_payload():
    return FreightQuoteInput(
        cep_destino="01310100",
        itens=[
            ShippingItemInput(width=11, height=17, length=11, weight=0.3),
            ShippingItemInput(width=20, height=15, length=10, weight=0.5, quantity=2),
        ],
    )


class TestQuoteFreight:
    """quote_freight delega para get_quote com products montados a partir do input."""

    def test_returns_options_from_get_quote(self, valid_quote_payload) -> None:
        with patch("src.shipping.service.get_quote") as mock_get_quote:
            mock_get_quote.return_value = [
                {"transportadora": "Correios PAC", "preco": 25.90, "prazo_entrega_dias": 8},
                {"transportadora": "Jadlog", "preco": 31.00, "prazo_entrega_dias": 5},
            ]
            result = quote_freight(valid_quote_payload)
            assert len(result) == 2
            assert result[0]["transportadora"] == "Correios PAC"
            assert result[0]["preco"] == 25.90
            mock_get_quote.assert_called_once()
            call_cep, call_products = mock_get_quote.call_args[0]
            assert call_cep == "01310100"
            assert len(call_products) == 2
            assert call_products[0]["width"] == 11 and call_products[0]["weight"] == 0.3
            assert call_products[1]["quantity"] == 2

    def test_raises_melhor_envio_api_error_on_failure(self, valid_quote_payload) -> None:
        with patch("src.shipping.service.get_quote") as mock_get_quote:
            mock_get_quote.side_effect = MelhorEnvioAPIError("Timeout ao conectar")
            with pytest.raises(MelhorEnvioAPIError) as exc_info:
                quote_freight(valid_quote_payload)
            assert "Timeout" in str(exc_info.value)
