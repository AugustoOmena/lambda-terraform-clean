"""
Freight quote service: integrates with Melhor Envio API for shipping calculation.

All CEPs are quoted via the external API; no local rules or region conditionals.
Products montados com tipos alinhados ao Carrinho: int (cm) nas dimensões,
peso com 3 casas decimais (float no payload JSON da API).
"""

from aws_lambda_powertools import Logger

from shared.melhor_envio import MelhorEnvioAPIError, get_quote
from schemas import FreightQuoteInput

__all__ = ["MelhorEnvioAPIError", "quote_freight"]

logger = Logger(service="shipping")


def _weight_for_api(weight) -> float:
    """Peso em kg com até 3 casas decimais, formato esperado pelo calculate/carrinho."""
    # Decimal nativo do schema já quantizado; float garante JSON serializável idêntico ao round(..., 3) no cliente
    return float(weight)


def quote_freight(payload_input: FreightQuoteInput) -> list[dict]:
    """
    Call Melhor Envio calculate API and return a clean list of options.

    Returns:
        List of dicts with keys: transportadora, preco, prazo_entrega_dias.

    Raises:
        MelhorEnvioAPIError: On missing env, connection/timeout or API error.
    """
    products = [
        {
            "id": str(i),
            "width": int(item.width),
            "height": int(item.height),
            "length": int(item.length),
            "weight": _weight_for_api(item.weight),
            "quantity": int(item.quantity),
            "insurance_value": float(item.insurance_value),
        }
        for i, item in enumerate(payload_input.itens, start=1)
    ]
    return get_quote(payload_input.cep_destino, products)
