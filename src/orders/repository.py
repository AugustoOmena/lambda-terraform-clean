"""Repository for orders, order_items, vouchers and order_refunds."""

from datetime import datetime, timezone
from typing import Any, Optional
from shared.database import get_supabase_client


class OrderRepository:
    def __init__(self) -> None:
        self.db = get_supabase_client()

    def get_order_by_id(self, order_id: str, user_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Fetch order by id. If user_id given, RLS enforces ownership."""
        q = self.db.table("orders").select("*").eq("id", order_id)
        if user_id:
            q = q.eq("user_id", user_id)
        res = q.execute()
        return res.data[0] if res.data else None

    def get_order_with_items(self, order_id: str, user_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Fetch order and its items. If user_id given, RLS enforces ownership."""
        order = self.get_order_by_id(order_id, user_id)
        if not order:
            return None
        res = self.db.table("order_items").select("*").eq("order_id", order_id).execute()
        order["items"] = res.data or []
        return order

    def list_orders_by_user(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List orders by user with fields for API contract (id, user_id, status, total_amount, created_at, payment_id, payer)."""
        start = (page - 1) * limit
        end = start + limit - 1
        res = (
            self.db.table("orders")
            .select("id, user_id, status, total_amount, created_at, payment_method, payment_id, payer", count="exact")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(start, end)
            .execute()
        )
        return {"data": res.data or [], "count": res.count or 0}

    def list_all_orders(self, page: int = 1, limit: int = 20) -> dict[str, Any]:
        """List all orders (backoffice admin). Same simplified fields + user_id + user email."""
        start = (page - 1) * limit
        end = start + limit - 1
        res = (
            self.db.table("orders")
            .select("id, user_id, status, total_amount, created_at, payment_method, payment_id, payer", count="exact")
            .order("created_at", desc=True)
            .range(start, end)
            .execute()
        )
        data = res.data or []
        if data:
            user_ids = list({o["user_id"] for o in data if o.get("user_id")})
            if user_ids:
                profiles_res = (
                    self.db.table("profiles").select("id, email").in_("id", user_ids).execute()
                )
                id_to_email = {p["id"]: p.get("email") for p in (profiles_res.data or [])}
                for o in data:
                    o["user_email"] = id_to_email.get(o.get("user_id")) if o.get("user_id") else None
            else:
                for o in data:
                    o["user_email"] = None
        return {"data": data, "count": res.count or 0}

    def get_profile_role(self, user_id: str) -> Optional[str]:
        """Fetch profile role by user_id (for admin check)."""
        res = self.db.table("profiles").select("role").eq("id", user_id).execute()
        return res.data[0].get("role") if res.data else None

    def get_profile_email(self, user_id: str) -> Optional[str]:
        """Fetch profile email by user_id (for order payload)."""
        res = self.db.table("profiles").select("email").eq("id", user_id).execute()
        return res.data[0].get("email") if res.data else None

    def get_order_items_by_ids(self, order_id: str, item_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch order_items by ids belonging to order_id."""
        if not item_ids:
            return []
        res = (
            self.db.table("order_items")
            .select("*")
            .eq("order_id", order_id)
            .in_("id", item_ids)
            .execute()
        )
        return res.data or []

    def get_order_items_all(self, order_id: str) -> list[dict[str, Any]]:
        """Fetch all order_items for an order."""
        res = self.db.table("order_items").select("*").eq("order_id", order_id).execute()
        return res.data or []

    def get_order_items_for_order_ids(self, order_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch all order_items for multiple orders (for list responses)."""
        if not order_ids:
            return []
        res = (
            self.db.table("order_items")
            .select("*")
            .in_("order_id", order_ids)
            .execute()
        )
        return res.data or []

    def insert_refund_request(
        self,
        order_id: str,
        request_type: str,
        amount: float,
        order_item_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Insert a refund request (customer or backoffice)."""
        row = {
            "order_id": order_id,
            "request_type": request_type,
            "status": "pending",
            "amount": amount,
            "order_item_ids": order_item_ids or [],
        }
        res = self.db.table("order_refunds").insert(row).execute()
        if not res.data:
            raise Exception("Falha ao criar solicitação de reembolso")
        return res.data[0]

    def update_refund_request(
        self,
        refund_id: str,
        status: str,
        refund_method: Optional[str] = None,
        mp_refund_id: Optional[str] = None,
        voucher_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update refund request after processing."""
        data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if refund_method is not None:
            data["refund_method"] = refund_method
        if mp_refund_id is not None:
            data["mp_refund_id"] = mp_refund_id
        if voucher_id is not None:
            data["voucher_id"] = voucher_id
        res = self.db.table("order_refunds").update(data).eq("id", refund_id).execute()
        if not res.data:
            raise Exception("Falha ao atualizar solicitação de reembolso")
        return res.data[0]

    def update_order_status(self, order_id: str, status: str) -> dict[str, Any]:
        """Update order status (e.g. cancelled)."""
        res = (
            self.db.table("orders")
            .update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", order_id)
            .execute()
        )
        if not res.data:
            raise Exception("Falha ao atualizar status do pedido")
        return res.data[0]

    def create_voucher(self, code: str, amount: float, order_id: Optional[str], valid_until: str) -> dict[str, Any]:
        """Create a voucher (5-char code, amount, validity)."""
        row = {
            "code": code,
            "amount": amount,
            "order_id": order_id,
            "valid_until": valid_until,
        }
        res = self.db.table("vouchers").insert(row).execute()
        if not res.data:
            raise Exception("Falha ao criar voucher")
        return res.data[0]

    def get_voucher_by_code(self, code: str) -> Optional[dict[str, Any]]:
        """Fetch voucher by code."""
        res = self.db.table("vouchers").select("*").eq("code", code).execute()
        return res.data[0] if res.data else None

    def list_refund_requests_by_order(self, order_id: str) -> list[dict[str, Any]]:
        """List refund requests for an order."""
        res = self.db.table("order_refunds").select("*").eq("order_id", order_id).order("created_at", desc=True).execute()
        return res.data or []
