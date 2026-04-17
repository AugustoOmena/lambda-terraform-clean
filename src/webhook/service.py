"""Processamento de eventos de webhook Melhor Envio (status de etiqueta)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any, Optional

from aws_lambda_powertools import Logger

from shared.email_service import send_shipped_notification

from me_webhook_repository import WebhookRepository
from me_webhook_schemas import MelhorEnvioWebhookPayload

logger = Logger(service="webhook")


def verify_me_signature(raw_body: bytes, signature_header: Optional[str], secret: str) -> bool:
    """Valida ``X-ME-Signature``: HMAC-SHA256 do corpo em Base64 (documentação Melhor Envio)."""
    if not signature_header or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected_b64 = base64.b64encode(expected).decode("ascii")
    try:
        return hmac.compare_digest(expected_b64.strip(), signature_header.strip())
    except Exception:
        return False


def _header_ci(headers: dict[str, Any], name: str) -> Optional[str]:
    if not headers:
        return None
    lower = {k.lower(): v for k, v in headers.items() if isinstance(k, str)}
    return lower.get(name.lower())


class WebhookService:
    def __init__(self) -> None:
        self.repo = WebhookRepository()

    def process_request(self, raw_body: bytes, headers: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        secret = (os.environ.get("MELHOR_ENVIO_CLIENT_SECRET") or "").strip()
        sig = _header_ci(headers, "x-me-signature")
        if not verify_me_signature(raw_body, sig, secret):
            logger.warning("Assinatura de webhook inválida ou ausente")
            return 401, {"error": "Invalid signature"}

        try:
            body_obj = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return 400, {"error": "Invalid JSON"}

        try:
            payload = MelhorEnvioWebhookPayload.model_validate(body_obj)
        except Exception as e:
            logger.warning("Payload inválido", extra={"err": str(e)})
            return 400, {"error": "Invalid payload"}

        data_parsed = payload.parsed_data()
        me_id = (data_parsed.id or "").strip()
        if not me_id:
            return 400, {"error": "Missing data.id"}

        event = (payload.event or "").strip()
        order = self.repo.get_order_by_melhor_envio_id(me_id)
        if not order:
            logger.info(
                "Pedido não encontrado para melhor_envio_order_id; ignorando",
                extra={"melhor_envio_order_id": me_id, "event": event},
            )
            return 200, {"ok": True, "ignored": True, "reason": "order_not_found"}

        order_id = str(order["id"])
        if event == "order.released":
            self.repo.update_order_delivery_status(order_id, "in_process")
            return 200, {"ok": True, "order_id": order_id, "event": event}

        if event == "order.posted":
            tracking_code = data_parsed.tracking
            shipping_service = None
            raw = payload.data.get("service") or payload.data.get("service_id")
            if raw is not None:
                shipping_service = str(raw)
            self.repo.update_order_shipped(
                order_id,
                tracking_code=tracking_code,
                shipping_service=shipping_service,
            )
            user_id = order.get("user_id")
            email: Optional[str] = None
            if user_id:
                email = self.repo.get_profile_email(str(user_id))
            if email:
                try:
                    send_shipped_notification(
                        email,
                        order_id=order_id,
                        tracking_url=data_parsed.tracking_url,
                        tracking_code=tracking_code,
                    )
                except Exception as e:
                    logger.exception(
                        "Falha ao enviar e-mail de envio (pedido já atualizado)",
                        extra={"order_id": order_id, "err": str(e)},
                    )
            return 200, {"ok": True, "order_id": order_id, "event": event}

        if event == "order.delivered":
            self.repo.update_order_delivery_status(order_id, "delivered")
            return 200, {"ok": True, "order_id": order_id, "event": event}

        return 200, {"ok": True, "ignored": True, "event": event}
