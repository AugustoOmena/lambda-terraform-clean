"""
Freight quote service: integrates with Melhor Envio API for shipping calculation.

All CEPs are quoted via the external API; no local rules or region conditionals.
"""

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

from aws_lambda_powertools import Logger

from schemas import FreightQuoteInput

logger = Logger(service="shipping")

# Default sandbox base URL; override with MELHOR_ENVIO_API_URL for production.
DEFAULT_API_BASE = "https://sandbox.melhorenvio.com.br"
CALCULATE_PATH = "/api/v2/me/shipment/calculate"
REQUEST_TIMEOUT_SEC = 15


class MelhorEnvioAPIError(Exception):
    """Raised when the external API returns an error or is unreachable."""

    pass


def _env(key: str, default: str | None = None) -> str:
    value = os.environ.get(key) or default
    if not value and key in ("MELHOR_ENVIO_TOKEN", "CEP_ORIGEM"):
        raise MelhorEnvioAPIError(f"Variável de ambiente obrigatória não definida: {key}")
    return value or ""


def _build_products(itens: list) -> list[dict[str, Any]]:
    """Build Melhor Envio products array from input items (dimensions in cm, weight in kg)."""
    return [
        {
            "id": str(i),
            "width": round(item.width, 2),
            "height": round(item.height, 2),
            "length": round(item.length, 2),
            "weight": round(item.weight, 3),
            "insurance_value": round(item.insurance_value, 2),
            "quantity": item.quantity,
        }
        for i, item in enumerate(itens, start=1)
    ]


def _build_payload(cep_origem: str, cep_destino: str, itens: list) -> dict[str, Any]:
    return {
        "from": {"postal_code": cep_origem},
        "to": {"postal_code": cep_destino},
        "products": _build_products(itens),
        "options": {"receipt": False, "own_hand": False},
    }


def _parse_quote_option(entry: dict[str, Any]) -> dict[str, Any] | None:
    """
    Map a single quote from Melhor Envio response to a clean option.
    API may return name, company.name, custom_price/price, delivery_time (days).
    """
    name = (
        entry.get("name")
        or (entry.get("company") or {}).get("name")
        or entry.get("company_name")
        or "Transportadora"
    )
    value = entry.get("custom_price")
    if value is None or value == "":
        value = entry.get("price")
    if value is None:
        return None
    try:
        price_float = float(value)
    except (TypeError, ValueError):
        return None
    delivery = (
        entry.get("delivery_time")
        or entry.get("delivery_time_min")
        or entry.get("custom_delivery_time")
    )
    try:
        days = int(delivery) if delivery is not None else None
    except (TypeError, ValueError):
        days = None
    return {
        "transportadora": name,
        "preco": round(price_float, 2),
        "prazo_entrega_dias": days,
    }


def _parse_response(body: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract a clean list of quote options from Melhor Envio response.
    Response may be a list or an object with id/packages/data.
    """
    options: list[dict[str, Any]] = []
    if isinstance(body, list):
        for item in body:
            parsed = _parse_quote_option(item if isinstance(item, dict) else {})
            if parsed:
                options.append(parsed)
        return options
    if not isinstance(body, dict):
        return options
    # Common wrappers: id (single), packages (list), data (list)
    for key in ("id", "packages", "data"):
        if key not in body:
            continue
        val = body[key]
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    # Nested packages may have a list inside
                    inner = item.get("options") or item.get("services") or [item]
                    if not isinstance(inner, list):
                        inner = [inner]
                    for opt in inner:
                        parsed = _parse_quote_option(opt if isinstance(opt, dict) else {})
                        if parsed:
                            options.append(parsed)
            return options
        if isinstance(val, dict):
            parsed = _parse_quote_option(val)
            if parsed:
                options.append(parsed)
            return options
    # Top-level as single quote
    parsed = _parse_quote_option(body)
    if parsed:
        options.append(parsed)
    return options


def quote_freight(payload_input: FreightQuoteInput) -> list[dict[str, Any]]:
    """
    Call Melhor Envio calculate API and return a clean list of options.

    Returns:
        List of dicts with keys: transportadora, preco, prazo_entrega_dias.

    Raises:
        MelhorEnvioAPIError: On missing env, connection/timeout or API error.
    """
    base = (os.environ.get("MELHOR_ENVIO_API_URL") or DEFAULT_API_BASE).rstrip("/")
    url = f"{base}{CALCULATE_PATH}"
    token = _env("MELHOR_ENVIO_TOKEN", "")
    cep_origem = _env("CEP_ORIGEM", "")

    body = _build_payload(cep_origem, payload_input.cep_destino, payload_input.itens)
    data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    try:
        with urllib.request.urlopen(
            req, timeout=REQUEST_TIMEOUT_SEC, context=ssl.create_default_context()
        ) as resp:
            if resp.status != 200:
                raw = resp.read().decode("utf-8", errors="replace")
                logger.warning("Melhor Envio API status %s: %s", resp.status, raw[:500])
                raise MelhorEnvioAPIError(f"API retornou status {resp.status}")
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        logger.warning("Melhor Envio HTTP error %s: %s", e.code, raw[:500])
        raise MelhorEnvioAPIError(f"API retornou erro HTTP {e.code}") from e
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, TimeoutError) or (reason and "timed out" in str(reason).lower()):
            raise MelhorEnvioAPIError("Timeout ao conectar na API de frete") from e
        raise MelhorEnvioAPIError("Falha de conexão com a API de frete") from e
    except TimeoutError as e:
        raise MelhorEnvioAPIError("Timeout ao conectar na API de frete") from e
    except OSError as e:
        raise MelhorEnvioAPIError("Falha de conexão com a API de frete") from e

    try:
        parsed_body = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Resposta da API não é JSON válido: %s", raw[:300])
        raise MelhorEnvioAPIError("Resposta inválida da API de frete") from e

    options = _parse_response(parsed_body)
    return options
