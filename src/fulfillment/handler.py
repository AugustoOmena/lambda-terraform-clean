"""
Handler for fulfillment microservice: Melhor Envio cart, shipment and webhook.

Routes:
- POST /fulfillment/{order_id}/create-shipment  Backoffice: cria etiqueta no carrinho ME
- POST /fulfillment/webhook  Webhook público: recebe eventos do Melhor Envio
- GET  /fulfillment/{order_id}/tracking  Consulta rastreamento
"""

import json
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import parse
from aws_lambda_powertools.utilities.typing import LambdaContext

from shared.responses import http_response
from shared.melhor_envio import MelhorEnvioAPIError
from schemas import CreateShipmentInput, WebhookEvent
from service import FulfillmentService

logger = Logger(service="fulfillment")


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method")
    path_params = event.get("pathParameters") or {}
    raw_path = event.get("rawPath", "")

    if method == "OPTIONS":
        return http_response(200, {})

    try:
        service = FulfillmentService()

        # POST /fulfillment/webhook
        if method == "POST" and "webhook" in raw_path:
            body = _body_json(event)
            event_type = body.get("event", "")
            data = body.get("data", body)
            result = service.process_webhook(event_type, data)
            return http_response(200, result)

        # Extrai order_id do path
        order_id = path_params.get("proxy") or path_params.get("order_id") or ""
        if "/" in order_id:
            order_id = order_id.split("/")[0]

        # POST /fulfillment/{order_id}/create-shipment
        if method == "POST" and order_id and "create-shipment" in raw_path:
            is_backoffice = _is_backoffice(event)
            if not is_backoffice:
                return http_response(403, {"error": "Acesso restrito ao backoffice"})

            body = _body_json(event)
            payload = parse(event=body, model=CreateShipmentInput)
            result = service.create_shipment(order_id, payload)
            return http_response(201, result)

        # GET /fulfillment/{order_id}/tracking
        if method == "GET" and order_id and "tracking" in raw_path:
            result = service.get_tracking_info(order_id)
            return http_response(200, result)

        return http_response(404, {"error": "Rota não encontrada"})

    except ValueError as e:
        logger.warning(f"Validação: {e!s}")
        return http_response(400, {"error": "Dados inválidos", "details": str(e)})
    except MelhorEnvioAPIError as e:
        logger.warning(f"Melhor Envio API: {e!s}")
        return http_response(502, {"error": str(e)})
    except Exception as e:
        logger.exception("Erro no processamento")
        return http_response(500, {"error": str(e)})


def _body_json(event: dict) -> dict:
    body = event.get("body")
    if body is None:
        return {}
    if isinstance(body, str):
        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError:
            return {}
    return body if isinstance(body, dict) else {}


def _is_backoffice(event: dict) -> bool:
    headers = event.get("headers") or {}
    return (
        headers.get("x-backoffice", "").lower() == "true"
        or headers.get("X-Backoffice", "").lower() == "true"
    )
