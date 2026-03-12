"""Handler: disparado por EventBridge (cron diário meia-noite UTC)."""

from aws_lambda_powertools import Logger

from service import CleanupOrphanImagesService

logger = Logger(service="cleanup-orphan-images")


@logger.inject_lambda_context
def lambda_handler(event, context):
    """Executa limpeza de imagens órfãs no bucket product-images."""
    try:
        service = CleanupOrphanImagesService()
        result = service.run()
        logger.info("Cleanup concluído", extra=result)
        return {"statusCode": 200, "body": result}
    except Exception as e:
        logger.exception("Erro na limpeza de imagens órfãs")
        raise
