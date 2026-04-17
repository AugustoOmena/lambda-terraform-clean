"""Persistência de atualizações de pedido vindas do webhook Melhor Envio."""

from datetime import datetime, timezone
from typing import Any, Optional

from shared.database import get_supabase_client


class WebhookRepository:
    def __init__(self) -> None:
        self.db = get_supabase_client()

    def get_order_by_melhor_envio_id(self, melhor_envio_order_id: str) -> Optional[dict[str, Any]]:
        res = (
            self.db.table("orders")
            .select("id, user_id, payment_status, delivery_status, melhor_envio_order_id")
            .eq("melhor_envio_order_id", melhor_envio_order_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_profile_email(self, user_id: str) -> Optional[str]:
        res = self.db.table("profiles").select("email").eq("id", user_id).limit(1).execute()
        if not res.data:
            return None
        return res.data[0].get("email")

    def update_order_delivery_status(self, order_id: str, delivery_status: str) -> dict[str, Any]:
        res = (
            self.db.table("orders")
            .update({"delivery_status": delivery_status, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", order_id)
            .execute()
        )
        if not res.data:
            raise RuntimeError("Falha ao atualizar status do pedido")
        return res.data[0]

    def update_order_shipped(
        self,
        order_id: str,
        *,
        tracking_code: Optional[str],
        shipping_service: Optional[str],
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "delivery_status": "shipped",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if tracking_code is not None:
            data["tracking_code"] = tracking_code
        if shipping_service is not None:
            data["shipping_service"] = shipping_service
        res = self.db.table("orders").update(data).eq("id", order_id).execute()
        if not res.data:
            raise RuntimeError("Falha ao atualizar pedido (enviado)")
        return res.data[0]
