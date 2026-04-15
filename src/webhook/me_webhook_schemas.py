"""DTOs para payload de webhook Melhor Envio."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class MelhorEnvioWebhookData(BaseModel):
    """Campos relevantes do objeto ``data`` no corpo do webhook."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Identificador do pedido no Melhor Envio (UUID)")
    protocol: Optional[str] = None
    status: Optional[str] = None
    tracking: Optional[str] = None
    tracking_url: Optional[str] = None


class MelhorEnvioWebhookPayload(BaseModel):
    """Corpo JSON enviado pelo Melhor Envio (eventos order.*)."""

    model_config = ConfigDict(extra="ignore")

    event: str
    data: dict[str, Any]

    def parsed_data(self) -> MelhorEnvioWebhookData:
        return MelhorEnvioWebhookData.model_validate(self.data)
