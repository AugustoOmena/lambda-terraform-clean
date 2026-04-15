"""
Envio transacional via SMTP (Twilio / SendGrid compatível).

Variáveis de ambiente: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Optional


def _smtp_config() -> tuple[str, int, str, str]:
    host = (os.environ.get("SMTP_HOST") or "").strip()
    port_raw = (os.environ.get("SMTP_PORT") or "587").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASS") or "").strip()
    if not host or not user or not password:
        raise ValueError("SMTP_HOST, SMTP_USER e SMTP_PASS são obrigatórios para envio de e-mail")
    try:
        port = int(port_raw)
    except ValueError as e:
        raise ValueError("SMTP_PORT deve ser um inteiro") from e
    return host, port, user, password


def send_shipped_notification(
    to_email: str,
    *,
    order_id: str,
    tracking_url: Optional[str],
    tracking_code: Optional[str],
) -> None:
    """Notifica o cliente que o pedido foi postado e inclui link de rastreamento Melhor Envio."""
    host, port, user, password = _smtp_config()
    subject = "Seu pedido foi enviado"
    lines = [
        "Olá,",
        "",
        "Seu pedido foi postado e está a caminho.",
        f"Pedido: {order_id}",
    ]
    if tracking_code:
        lines.append(f"Código de rastreamento: {tracking_code}")
    if tracking_url:
        lines.append(f"Rastrear envio: {tracking_url}")
    lines.extend(["", "Obrigado pela compra."])
    body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
