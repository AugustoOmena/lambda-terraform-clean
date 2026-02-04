import pytest
from pydantic import ValidationError

from src.shipping.schemas import FreightQuoteInput, ShippingItemInput


class TestShippingItemInput:
    """Validação de itens de frete (dimensões e peso)."""

    def test_valid_item(self) -> None:
        item = ShippingItemInput(width=11, height=17, length=11, weight=0.3)
        assert item.width == 11
        assert item.weight == 0.3
        assert item.quantity == 1
        assert item.insurance_value == 0.0

    def test_item_quantity_default_one(self) -> None:
        item = ShippingItemInput(width=10, height=10, length=10, weight=0.5, quantity=2)
        assert item.quantity == 2

    def test_item_requires_positive_dimensions(self) -> None:
        with pytest.raises(ValidationError):
            ShippingItemInput(width=0, height=10, length=10, weight=0.5)
        with pytest.raises(ValidationError):
            ShippingItemInput(width=10, height=10, length=10, weight=-0.1)

    def test_item_coerces_numeric_strings(self) -> None:
        item = ShippingItemInput(width="11.5", height=17, length=11, weight="0.3")
        assert item.width == 11.5
        assert item.weight == 0.3


class TestFreightQuoteInput:
    """Validação do payload de cotação (CEP e itens)."""

    def test_valid_quote_input(self) -> None:
        payload = FreightQuoteInput(
            cep_destino="01310100",
            itens=[ShippingItemInput(width=11, height=17, length=11, weight=0.3)],
        )
        assert payload.cep_destino == "01310100"
        assert len(payload.itens) == 1

    def test_cep_normalized_strips_non_digits(self) -> None:
        payload = FreightQuoteInput(cep_destino="01310-100", itens=[ShippingItemInput(width=11, height=17, length=11, weight=0.3)])
        assert payload.cep_destino == "01310100"

    def test_cep_invalid_length_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            FreightQuoteInput(cep_destino="0131010", itens=[ShippingItemInput(width=11, height=17, length=11, weight=0.3)])
        assert "CEP" in str(exc_info.value) or "8" in str(exc_info.value)

    def test_cep_requires_eight_digits(self) -> None:
        with pytest.raises(ValidationError):
            FreightQuoteInput(cep_destino="1234567", itens=[ShippingItemInput(width=11, height=17, length=11, weight=0.3)])
        with pytest.raises(ValidationError):
            FreightQuoteInput(cep_destino="123456789", itens=[ShippingItemInput(width=11, height=17, length=11, weight=0.3)])

    def test_itens_min_length_one(self) -> None:
        with pytest.raises(ValidationError):
            FreightQuoteInput(cep_destino="01310100", itens=[])

    def test_itens_required(self) -> None:
        with pytest.raises(ValidationError):
            FreightQuoteInput(cep_destino="01310100")
