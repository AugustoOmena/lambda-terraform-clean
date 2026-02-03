"""Unit tests for orders Lambda handler."""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.orders.handler import lambda_handler


@pytest.fixture
def mock_order_service():
    """Mock OrderService to avoid real DB and business logic."""
    with patch("src.orders.handler.OrderService") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


def _get_event(
    method: str = "GET",
    path_proxy: str = "",
    user_id: str | None = "admin-user-123",
    x_backoffice: str = "true",
) -> dict:
    """Build API Gateway-like event for GET /pedidos (list)."""
    return {
        "requestContext": {"http": {"method": method}},
        "pathParameters": {"proxy": path_proxy} if path_proxy else {},
        "queryStringParameters": {"user_id": user_id} if user_id else None,
        "headers": {"x-backoffice": x_backoffice, "X-Backoffice": x_backoffice},
        "body": None,
    }


def test_get_orders_admin_returns_user_email(mock_order_service: MagicMock) -> None:
    """GET /pedidos with X-Backoffice and user_id returns list with user_email per order."""
    mock_order_service.list_all_orders_for_admin.return_value = {
        "data": [
            {
                "id": "ord-1",
                "user_id": "user-a",
                "user_email": "comprador@example.com",
                "status": "approved",
                "total_amount": 99.90,
                "created_at": "2025-02-01T12:00:00Z",
                "payment_method": "pix",
            },
            {
                "id": "ord-2",
                "user_id": "user-b",
                "user_email": "outro@example.com",
                "status": "pending",
                "total_amount": 50.00,
                "created_at": "2025-02-02T10:00:00Z",
                "payment_method": "credit_card",
            },
        ],
        "count": 2,
    }

    event = _get_event()
    response = lambda_handler(event, MagicMock())

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "data" in body
    assert len(body["data"]) == 2
    assert body["data"][0]["user_email"] == "comprador@example.com"
    assert body["data"][1]["user_email"] == "outro@example.com"
    assert body["count"] == 2
    mock_order_service.list_all_orders_for_admin.assert_called_once()
