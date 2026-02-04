"""
Melhor Envio API client: quote calculation (used by shipping and payment modules).

Expects env: MELHOR_ENVIO_TOKEN, CEP_ORIGEM; optional MELHOR_ENVIO_API_URL.
"""

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

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


def _parse_quote_option(entry: dict[str, Any]) -> dict[str, Any] | None:
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
    service_id = (
        entry.get("service")
        or (entry.get("company") or {}).get("id")
        or (entry.get("company") or {}).get("code")
        or entry.get("id")
    )
    service = str(service_id).strip() if service_id is not None else None
    return {
        "transportadora": name,
        "preco": round(price_float, 2),
        "prazo_entrega_dias": days,
        "service": service,
    }


def _parse_response(body: dict[str, Any]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if isinstance(body, list):
        for item in body:
            parsed = _parse_quote_option(item if isinstance(item, dict) else {})
            if parsed:
                options.append(parsed)
        return options
    if not isinstance(body, dict):
        return options
    for key in ("id", "packages", "data"):
        if key not in body:
            continue
        val = body[key]
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
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
    parsed = _parse_quote_option(body)
    if parsed:
        options.append(parsed)
    return options


def get_quote(cep_destino: str, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Call Melhor Envio calculate API.

    Args:
        cep_destino: Destination postal code (8 digits).
        products: List of dicts with width, height, length (cm), weight (kg),
                  quantity, and optional insurance_value (default 0). Optional "id" per product.

    Returns:
        List of dicts with keys: transportadora, preco, prazo_entrega_dias, service (id do serviço Melhor Envio).

    Raises:
        MelhorEnvioAPIError: On missing env, connection/timeout or API error.
    """
    base = (os.environ.get("MELHOR_ENVIO_API_URL") or DEFAULT_API_BASE).rstrip("/")
    url = f"{base}{CALCULATE_PATH}"
    token = _env("MELHOR_ENVIO_TOKEN", "")
    cep_origem = _env("CEP_ORIGEM", "")

    payload_products = []
    for i, p in enumerate(products, start=1):
        payload_products.append({
            "id": str(p.get("id", i)),
            "width": round(float(p["width"]), 2),
            "height": round(float(p["height"]), 2),
            "length": round(float(p["length"]), 2),
            "weight": round(float(p["weight"]), 3),
            "quantity": int(p.get("quantity", 1)),
            "insurance_value": round(float(p.get("insurance_value", 0)), 2),
        })

    body = {
        "from": {"postal_code": cep_origem},
        "to": {"postal_code": cep_destino},
        "products": payload_products,
        "options": {"receipt": False, "own_hand": False},
    }
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
                raise MelhorEnvioAPIError(f"API retornou status {resp.status}")
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
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
        raise MelhorEnvioAPIError("Resposta inválida da API de frete") from e

    return _parse_response(parsed_body)
