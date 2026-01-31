"""DTOs and validation for orders microservice."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CancelRequestInput(BaseModel):
    """Solicitação de cancelamento/reembolso pelo cliente (total ou por itens)."""
    total: bool = Field(default=False, description="Cancelamento total do pedido")
    order_item_ids: Optional[List[str]] = Field(default=None, description="IDs dos itens para reembolso parcial")

    @model_validator(mode="after")
    def check_partial_or_total(self):
        if self.total and self.order_item_ids:
            raise ValueError("Envie total=true ou order_item_ids, não ambos")
        if not self.total and (not self.order_item_ids or len(self.order_item_ids) == 0):
            raise ValueError("Para reembolso parcial informe order_item_ids")
        return self


class BackofficeCancelInput(BaseModel):
    """Cancelamento/reembolso pelo backoffice: itens e método (MP ou voucher)."""
    cancel_item_ids: Optional[List[str]] = Field(default=None, description="IDs dos order_items a cancelar; vazio = total")
    refund_method: str = Field(..., description="'mp' (reembolso Mercado Pago) ou 'voucher'")
    full_cancel: bool = Field(default=False, description="Cancelamento total do pedido")

    @field_validator("refund_method")
    @classmethod
    def refund_method_value(cls, v: str) -> str:
        if v not in ("mp", "voucher"):
            raise ValueError("refund_method deve ser 'mp' ou 'voucher'")
        return v
