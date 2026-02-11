"""Repository for fulfillment: database access for orders shipping data."""

from shared.database import get_supabase_client


class FulfillmentRepository:
    def __init__(self):
        self.db = get_supabase_client()

    def get_order_for_shipment(self, order_id: str) -> dict | None:
        """
        Busca pedido com dados necessários para criar etiqueta.
        Retorna order com payer (endereço), items, total_amount.
        """
        result = self.db.table("orders").select("*").eq("id", order_id).execute()
        if not result.data:
            return None
        order = result.data[0]

        items_result = self.db.table("order_items").select("*").eq("order_id", order_id).execute()
        order["items"] = items_result.data or []

        return order

    def update_melhor_envio_order_id(self, order_id: str, me_order_id: str) -> None:
        """Salva o ID do pedido no Melhor Envio."""
        self.db.table("orders").update({
            "melhor_envio_order_id": me_order_id,
        }).eq("id", order_id).execute()

    def update_tracking(
        self,
        order_id: str,
        tracking_code: str,
        shipping_service: str | None = None,
        status: str | None = None,
    ) -> None:
        """Atualiza código de rastreio e status do pedido."""
        update_data: dict = {"tracking_code": tracking_code}
        if shipping_service:
            update_data["shipping_service"] = shipping_service
        if status:
            update_data["status"] = status
        self.db.table("orders").update(update_data).eq("id", order_id).execute()

    def get_order_by_melhor_envio_id(self, me_order_id: str) -> dict | None:
        """Busca pedido pelo ID do Melhor Envio (para webhook)."""
        result = self.db.table("orders").select("*").eq("melhor_envio_order_id", me_order_id).execute()
        return result.data[0] if result.data else None

    def update_order_status(self, order_id: str, status: str) -> None:
        """Atualiza apenas o status do pedido."""
        self.db.table("orders").update({"status": status}).eq("id", order_id).execute()
