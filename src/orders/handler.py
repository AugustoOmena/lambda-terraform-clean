"""
Handler for orders microservice.

Routes:
- GET /pedidos/{order_id}?user_id=...  Customer: full order detail
- GET /pedidos?user_id=...&page=&limit=  Customer: simplified list; Backoffice (X-Backoffice: true): list all if user role admin
- POST /pedidos/{order_id}/solicitar-cancelamento  Customer: cancel/refund request (7 days)
- PUT /pedidos/{order_id}  Backoffice: editar status (body {"status": "shipped"}) ou cancel/reembolso (header X-Backoffice: true)
"""

import json
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import parse
from aws_lambda_powertools.utilities.typing import LambdaContext

from shared.responses import http_response
from schemas import BackofficeCancelInput, CancelRequestInput, OrderStatusUpdate
from service import OrderService

logger = Logger(service="orders")


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    if method == "OPTIONS":
        return http_response(200, {})

    try:
        service = OrderService()
        order_id = (path_params.get("proxy") or path_params.get("order_id") or "").split("/")[0]
        if order_id and "/" in (path_params.get("proxy") or ""):
            order_id = (path_params.get("proxy") or "").split("/")[0]
        user_id = query_params.get("user_id") or (event.get("body") and _body_json(event).get("user_id"))

        if method == "GET":
            if order_id:
                if not user_id:
                    return http_response(400, {"error": "user_id obrigatório para ver detalhe do pedido"})
                result = service.get_order_detail(order_id, user_id)
                return http_response(200, result)
            page = int(query_params.get("page", 1))
            limit = int(query_params.get("limit", 20))
            is_backoffice = (
                (event.get("headers") or {}).get("x-backoffice", "").lower() == "true"
                or (event.get("headers") or {}).get("X-Backoffice", "").lower() == "true"
            )
            if is_backoffice and user_id:
                try:
                    result = service.list_all_orders_for_admin(user_id, page=page, limit=limit)
                except PermissionError as e:
                    return http_response(403, {"error": str(e)})
                return http_response(200, result)
            if not user_id:
                return http_response(400, {"error": "user_id obrigatório para listar pedidos"})
            result = service.list_orders_by_customer(user_id, page=page, limit=limit)
            return http_response(200, result)

        if method == "POST" and order_id:
            path_proxy = path_params.get("proxy") or ""
            if "solicitar-cancelamento" in path_proxy or event.get("rawPath", "").endswith("solicitar-cancelamento"):
                if not user_id:
                    return http_response(400, {"error": "user_id obrigatório"})
                body = _body_json(event)
                payload = parse(event=body, model=CancelRequestInput)
                result = service.request_cancel_or_refund(order_id, user_id, payload)
                return http_response(201, result)
            return http_response(404, {"error": "Rota não encontrada"})

        if method == "PUT" and order_id:
            is_backoffice = (
                (event.get("headers") or {}).get("x-backoffice", "").lower() == "true"
                or (event.get("headers") or {}).get("X-Backoffice", "").lower() == "true"
            )
            if not is_backoffice:
                return http_response(403, {"error": "Acesso restrito ao backoffice"})
            body = _body_json(event)
            if "status" in body and "refund_method" not in body:
                payload = parse(event=body, model=OrderStatusUpdate)
                result = service.update_order_status(order_id, payload.status)
                return http_response(200, result)
            if "refund_method" in body and body.get("refund_method") is not None:
                payload = parse(event=body, model=BackofficeCancelInput)
                result = service.backoffice_cancel_and_refund(order_id, payload)
                return http_response(200, result)
            return http_response(400, {"error": "Envie {\"status\": \"...\"} para editar status ou payload de cancelamento/reembolso (refund_method, etc.)"})

        return http_response(405, {"error": "Método não permitido"})

    except ValueError as e:
        logger.warning(f"Validação: {e!s}")
        return http_response(400, {"error": "Dados inválidos", "details": str(e)})
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
