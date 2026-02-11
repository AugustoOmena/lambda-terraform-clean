"""Schemas for fulfillment microservice."""

from typing import Optional
from pydantic import BaseModel, Field


class CreateShipmentInput(BaseModel):
    """Input para criar etiqueta no carrinho Melhor Envio. Se omitido, usa shipping_service do pedido."""
    service_id: Optional[int] = Field(None, description="ID do serviço Melhor Envio (ex: 1=PAC, 2=SEDEX). Opcional: usa o do pedido.")


class WebhookEvent(BaseModel):
    """Evento recebido do webhook Melhor Envio."""
    event: str = Field(..., description="Tipo do evento (ex: shipment.tracking)")
    data: dict = Field(default_factory=dict, description="Dados do evento")


class ShipmentResponse(BaseModel):
    """Resposta após criar etiqueta."""
    melhor_envio_order_id: str
    message: str


class TrackingResponse(BaseModel):
    """Resposta de consulta de rastreamento."""
    order_id: str
    tracking_code: Optional[str] = None
    status: str
    tracking_events: list[dict] = Field(default_factory=list)
