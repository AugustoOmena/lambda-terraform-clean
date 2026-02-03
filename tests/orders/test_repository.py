"""Unit tests for orders repository."""

from unittest.mock import MagicMock, patch

import pytest

from src.orders.repository import OrderRepository


@pytest.fixture
def mock_db():
    """Mock Supabase client with chained table/select/order/range/execute."""
    with patch("src.orders.repository.get_supabase_client") as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client


def test_list_all_orders_adds_user_email_from_profiles(mock_db: MagicMock) -> None:
    """list_all_orders fetches profiles by user_id and attaches user_email to each order."""
    orders_res = MagicMock()
    orders_res.data = [
        {"id": "o1", "user_id": "u1", "status": "approved", "total_amount": 100.0},
        {"id": "o2", "user_id": "u2", "status": "pending", "total_amount": 50.0},
    ]
    orders_res.count = 2

    profiles_res = MagicMock()
    profiles_res.data = [
        {"id": "u1", "email": "buyer1@example.com"},
        {"id": "u2", "email": "buyer2@example.com"},
    ]

    def table_side_effect(name: str):
        t = MagicMock()
        if name == "orders":
            chain = MagicMock()
            chain.select.return_value = chain
            chain.order.return_value = chain
            chain.range.return_value = chain
            chain.execute.return_value = orders_res
            t.select.return_value = chain
        else:
            chain = MagicMock()
            chain.select.return_value = chain
            chain.in_.return_value = chain
            chain.execute.return_value = profiles_res
            t.select.return_value = chain
        return t

    mock_db.table.side_effect = table_side_effect

    repo = OrderRepository()
    result = repo.list_all_orders(page=1, limit=20)

    assert result["count"] == 2
    assert len(result["data"]) == 2
    assert result["data"][0]["user_email"] == "buyer1@example.com"
    assert result["data"][1]["user_email"] == "buyer2@example.com"
