from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import parse
from aws_lambda_powertools.utilities.typing import LambdaContext

from shared.responses import http_response
from src.payment.schemas import PaymentInput
from src.payment.service import PaymentService

# Inicializa Logs Profissionais (JSON estruturado)
logger = Logger(service="payment")

@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext):
    # CORS Preflight
    if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
        return http_response(200, {})

    try:
        # 1. Validação Automática (Pydantic)
        # Se faltar campo ou tipo errado, lança erro aqui mesmo
        # O envelope=None significa que estamos pegando direto do body
        if "body" in event:
            event = event["body"] # Ajuste para API Gateway HTTP API v2
            
        payload: PaymentInput = parse(event=event, model=PaymentInput)
        
        logger.info(f"Iniciando pagamento para Order de R$ {payload.transaction_amount}")

        # 2. Execução
        service = PaymentService()
        result = service.process_payment(payload)

        logger.info("Pagamento processado com sucesso")
        return http_response(201, result)

    except ValueError as e:
        # Erros de validação (Pydantic)
        logger.warning(f"Erro de validação: {str(e)}")
        return http_response(400, {"error": "Dados inválidos", "details": str(e)})
        
    except Exception as e:
        # Erros Genéricos
        logger.exception("Erro crítico no processamento")
        return http_response(500, {"error": str(e)})