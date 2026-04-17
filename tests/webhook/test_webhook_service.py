"""Testes do microserviço webhook (assinatura HMAC e roteamento de eventos)."""

import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest

import webhook_me_service as webhook_service


def _sign(body: bytes, secret: str) -> str:
    dig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(dig).decode("ascii")


@pytest.fixture
def me_secret() -> str:
    return "test-app-secret"


@pytest.fixture(autouse=True)
def env_secret(monkeypatch: pytest.MonkeyPatch, me_secret: str) -> None:
    monkeypatch.setenv("MELHOR_ENVIO_CLIENT_SECRET", me_secret)


@patch("webhook_me_service.WebhookRepository")
def test_signature_invalid_returns_401(
    _mock_repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    me_secret: str,
) -> None:
    body = b'{"event":"order.released","data":{"id":"me-uuid-1"}}'
    status, payload = webhook_service.WebhookService().process_request(
        body,
        {"x-me-signature": "wrong"},
    )
    assert status == 401


@patch("webhook_me_service.WebhookRepository")
def test_order_released_updates_in_process(
    mock_repo_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    me_secret: str,
) -> None:
    repo = mock_repo_cls.return_value
    repo.get_order_by_melhor_envio_id.return_value = {"id": "ord-1", "user_id": "u1"}
    body_dict = {"event": "order.released", "data": {"id": "me-uuid-1"}}
    raw = json.dumps(body_dict).encode("utf-8")
    sig = _sign(raw, me_secret)
    status, payload = webhook_service.WebhookService().process_request(raw, {"x-me-signature": sig})
    assert status == 200
    assert payload.get("ok") is True
    repo.update_order_delivery_status.assert_called_once_with("ord-1", "in_process")


@patch("webhook_me_service.send_shipped_notification")
@patch("webhook_me_service.WebhookRepository")
def test_order_posted_sends_email(
    mock_repo_cls: MagicMock,
    mock_email: MagicMock,
    me_secret: str,
) -> None:
    repo = mock_repo_cls.return_value
    repo.get_order_by_melhor_envio_id.return_value = {"id": "ord-2", "user_id": "u2"}
    repo.get_profile_email.return_value = "buyer@example.com"
    body_dict = {
        "event": "order.posted",
        "data": {
            "id": "me-uuid-2",
            "tracking": "BR123",
            "tracking_url": "https://rastreio.example/track",
        },
    }
    raw = json.dumps(body_dict).encode("utf-8")
    sig = _sign(raw, me_secret)
    status, _ = webhook_service.WebhookService().process_request(raw, {"x-me-signature": sig})
    assert status == 200
    repo.update_order_shipped.assert_called_once()
    mock_email.assert_called_once()
    call_kw = mock_email.call_args.kwargs
    assert call_kw["order_id"] == "ord-2"
    assert call_kw["tracking_code"] == "BR123"


@patch("webhook_me_service.WebhookRepository")
def test_unknown_me_id_returns_200_ignored(mock_repo_cls: MagicMock, me_secret: str) -> None:
    repo = mock_repo_cls.return_value
    repo.get_order_by_melhor_envio_id.return_value = None
    body_dict = {"event": "order.delivered", "data": {"id": "unknown"}}
    raw = json.dumps(body_dict).encode("utf-8")
    sig = _sign(raw, me_secret)
    status, payload = webhook_service.WebhookService().process_request(raw, {"x-me-signature": sig})
    assert status == 200
    assert payload.get("ignored") is True
