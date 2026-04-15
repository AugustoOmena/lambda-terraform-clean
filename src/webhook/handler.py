"""Lambda HTTP: POST /webhook — notificações Melhor Envio (HMAC + atualização de pedidos)."""

import base64
import json
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from shared.responses import http_response

from service import WebhookService

logger = Logger(service="webhook")


def _raw_body_bytes(event: dict[str, Any]) -> bytes:
    body = event.get("body")
    if body is None:
        return b""
    if event.get("isBase64Encoded"):
        if isinstance(body, str):
            return base64.b64decode(body)
        return b""
    if isinstance(body, str):
        return body.encode("utf-8")
    return json.dumps(body).encode("utf-8")


@logger.inject_lambda_context
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    method = event.get("requestContext", {}).get("http", {}).get("method")
    if method == "OPTIONS":
        return http_response(200, {})

    if method != "POST":
        return http_response(405, {"error": "Method not allowed"})

    raw = _raw_body_bytes(event)
    headers = event.get("headers") or {}
    try:
        status, body = WebhookService().process_request(raw, headers)
        return http_response(status, body)
    except Exception as e:
        logger.exception("Erro ao processar webhook")
        return http_response(500, {"error": str(e)})
