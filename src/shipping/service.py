"""
Freight quote service: integrates with Melhor Envio API for shipping calculation.

All CEPs are quoted via the external API; no local rules or region conditionals.
"""

from aws_lambda_powertools import Logger

from shared.melhor_envio import MelhorEnvioAPIError, get_quote
from schemas import FreightQuoteInput

__all__ = ["MelhorEnvioAPIError", "quote_freight"]

logger = Logger(service="shipping")


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
            "width": item.width,
            "height": item.height,
            "length": item.length,
            "weight": item.weight,
            "quantity": item.quantity,
            "insurance_value": item.insurance_value,
        }
        for i, item in enumerate(payload_input.itens, start=1)
    ]
    return get_quote(payload_input.cep_destino, products)
