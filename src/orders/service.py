"""Business logic for orders: detail, list, cancel requests, backoffice cancel/refund."""

import os
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

from repository import OrderRepository
from schemas import BackofficeCancelInput, CancelRequestInput


ORDER_COMPLETED_STATUSES = ("approved", "completed")
CUSTOMER_CANCEL_DAYS = 7


class OrderService:
    def __init__(self) -> None:
        self.repo = OrderRepository()
        self._mp_token = os.environ.get("MP_ACCESS_TOKEN")

    def get_order_detail(self, order_id: str, user_id: str) -> dict[str, Any]:
        """Full order detail for customer (must be own order)."""
        order = self.repo.get_order_with_items(order_id, user_id=user_id)
        if not order:
            raise Exception("Pedido não encontrado")
        refunds = self.repo.list_refund_requests_by_order(order_id)
        order["refund_requests"] = refunds
        return order

    def list_orders_by_customer(self, user_id: str, page: int = 1, limit: int = 20) -> dict[str, Any]:
        """Simplified list of orders by customer."""
        return self.repo.list_orders_by_user(user_id, page=page, limit=limit)

    def list_all_orders_for_admin(self, admin_user_id: str, page: int = 1, limit: int = 20) -> dict[str, Any]:
        """List all orders; only allowed when requester has role 'admin'."""
        role = self.repo.get_profile_role(admin_user_id)
        if role != "admin":
            raise PermissionError("Apenas usuários com role admin podem listar todos os pedidos")
        return self.repo.list_all_orders(page=page, limit=limit)

    def _order_completed_at(self, order: dict[str, Any]) -> Optional[datetime]:
        """Order is completed when status is approved/completed; use updated_at or created_at."""
        if order.get("status") not in ORDER_COMPLETED_STATUSES:
            return None
        raw = order.get("updated_at") or order.get("created_at")
        if not raw:
            return None
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                return None
        return raw

    def request_cancel_or_refund(self, order_id: str, user_id: str, payload: CancelRequestInput) -> dict[str, Any]:
        """
        Customer request: cancel/refund total or partial (by item), only within 7 days of completion.
        Creates a refund_request row (customer, pending); backoffice processes later.
        """
        order = self.repo.get_order_with_items(order_id, user_id=user_id)
        if not order:
            raise Exception("Pedido não encontrado")
        completed_at = self._order_completed_at(order)
        if not completed_at:
            raise Exception("Pedido ainda não está concluído; cancelamento disponível após conclusão")
        cutoff = datetime.now(timezone.utc) - timedelta(days=CUSTOMER_CANCEL_DAYS)
        if completed_at < cutoff:
            raise Exception(
                f"Solicitação de cancelamento/reembolso permitida apenas até 7 dias após a conclusão do pedido"
            )
        if payload.total:
            amount = float(order.get("total_amount", 0))
            item_ids: list[str] = []
        else:
            items = self.repo.get_order_items_by_ids(order_id, payload.order_item_ids or [])
            if len(items) != len(payload.order_item_ids or []):
                raise Exception("Um ou mais itens não pertencem a este pedido")
            amount = sum(float(i.get("price_at_purchase") or i.get("price", 0)) * int(i.get("quantity", 0)) for i in items)
            item_ids = [str(i["id"]) for i in items]
        ref = self.repo.insert_refund_request(
            order_id=order_id,
            request_type="customer",
            amount=amount,
            order_item_ids=item_ids if item_ids else None,
        )
        return {
            "message": "Solicitação de cancelamento/reembolso registrada",
            "refund_request_id": ref["id"],
            "order_id": order_id,
            "amount": amount,
            "status": "pending",
        }

    def _generate_voucher_code(self, length: int = 5) -> str:
        """5 alphanumeric uppercase."""
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

    def _ensure_unique_voucher_code(self) -> str:
        for _ in range(20):
            code = self._generate_voucher_code()
            if not self.repo.get_voucher_by_code(code):
                return code
        raise Exception("Não foi possível gerar código de voucher único")

    def create_voucher(self, amount: float, order_id: Optional[str] = None, valid_days: int = 365) -> dict[str, Any]:
        """Generate voucher: 5-char code, amount, validity. Used by backoffice for refund as voucher."""
        code = self._ensure_unique_voucher_code()
        valid_until = (datetime.now(timezone.utc) + timedelta(days=valid_days)).isoformat()
        v = self.repo.create_voucher(code=code, amount=amount, order_id=order_id, valid_until=valid_until)
        return {
            "id": v["id"],
            "code": v["code"],
            "amount": float(v["amount"]),
            "order_id": v.get("order_id"),
            "created_at": v.get("created_at"),
            "valid_until": v.get("valid_until"),
        }

    def _refund_mercadopago(self, mp_payment_id: str, amount: Optional[float], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/payments/{id}/refunds. Amount optional = full refund."""
        url = f"https://api.mercadopago.com/v1/payments/{mp_payment_id}/refunds"
        headers = {
            "Authorization": f"Bearer {self._mp_token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": idempotency_key,
        }
        body = {} if amount is None else {"amount": round(amount, 2)}
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        if resp.status_code not in (200, 201):
            err = resp.json() if resp.text else {}
            msg = err.get("message", resp.text or "Erro Mercado Pago")
            raise Exception(f"Reembolso MP: {msg}")
        return resp.json()

    def backoffice_cancel_and_refund(
        self,
        order_id: str,
        payload: BackofficeCancelInput,
    ) -> dict[str, Any]:
        """
        Backoffice: cancel items (or full order), trigger MP refund or issue voucher.
        - full_cancel: mark order as cancelled; refund total via MP or voucher.
        - cancel_item_ids: partial refund for those items; optionally set order status if all cancelled.
        """
        order = self.repo.get_order_with_items(order_id, user_id=None)
        if not order:
            raise Exception("Pedido não encontrado")
        mp_payment_id = order.get("mp_payment_id")
        items = order.get("items") or []
        if payload.full_cancel:
            amount = float(order.get("total_amount", 0))
            item_ids = [str(i["id"]) for i in items]
        else:
            cancel_ids = payload.cancel_item_ids or []
            if not cancel_ids:
                raise ValueError("Informe cancel_item_ids ou full_cancel=true")
            selected = self.repo.get_order_items_by_ids(order_id, cancel_ids)
            if len(selected) != len(cancel_ids):
                raise Exception("Um ou mais itens não pertencem a este pedido")
            amount = sum(
                float(i.get("price_at_purchase") or i.get("price", 0)) * int(i.get("quantity", 0)) for i in selected
            )
            item_ids = [str(i["id"]) for i in selected]
        ref = self.repo.insert_refund_request(
            order_id=order_id,
            request_type="backoffice",
            amount=amount,
            order_item_ids=item_ids,
        )
        refund_id = ref["id"]
        if payload.refund_method == "mp":
            if not mp_payment_id:
                raise Exception("Pedido sem mp_payment_id; reembolso MP não disponível")
            if not self._mp_token:
                raise Exception("MP_ACCESS_TOKEN não configurado")
            idem = str(uuid.uuid4())
            mp_resp = self._refund_mercadopago(mp_payment_id, amount, idem)
            self.repo.update_refund_request(
                refund_id, status="refunded", refund_method="mp", mp_refund_id=str(mp_resp.get("id", ""))
            )
            result_refund = {"mp_refund_id": mp_resp.get("id"), "status": "refunded"}
        else:
            voucher = self.create_voucher(amount=amount, order_id=order_id)
            self.repo.update_refund_request(
                refund_id, status="refunded", refund_method="voucher", voucher_id=voucher["id"]
            )
            result_refund = {"voucher": voucher, "status": "refunded"}
        if payload.full_cancel:
            self.repo.update_order_status(order_id, "cancelled")
        return {
            "message": "Cancelamento e reembolso processados",
            "order_id": order_id,
            "refund_request_id": refund_id,
            "amount": amount,
            **result_refund,
        }
