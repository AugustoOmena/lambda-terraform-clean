"""
Handler for shipping (freight quote) microservice.

POST body: { "cep_destino": "01310100", "itens": [ { "width": 11, "height": 17, "length": 11, "weight": 0.3 } ] }
Response: { "opcoes": [ { "transportadora": "...", "preco": 25.90, "prazo_entrega_dias": 8, "service": "jadlog_package" } ] }
"""

import json
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import parse
from aws_lambda_powertools.utilities.typing import LambdaContext

from shared.responses import http_response
from schemas import FreightQuoteInput
from service import MelhorEnvioAPIError, quote_freight

logger = Logger(service="shipping")


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method")

    if method == "OPTIONS":
        return http_response(200, {})

    if method != "POST":
        return http_response(405, {"error": "Método não permitido. Use POST."})

    body = _body_json(event)
    if not body:
        return http_response(400, {"error": "Body JSON obrigatório com cep_destino e itens"})

    try:
        payload = parse(event=body, model=FreightQuoteInput)
    except ValueError as e:
        logger.warning("Validação: %s", e)
        return http_response(400, {"error": "Dados inválidos", "details": str(e)})

    try:
        opcoes = quote_freight(payload)
        return http_response(200, {"opcoes": opcoes})
    except MelhorEnvioAPIError as e:
        logger.warning("API frete: %s", e)
        return http_response(502, {"error": str(e)})
    except Exception as e:
        logger.exception("Erro no cálculo de frete")
        return http_response(500, {"error": "Erro interno no cálculo de frete"})


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
