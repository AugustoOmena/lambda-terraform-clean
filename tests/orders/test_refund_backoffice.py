"""Testes do fluxo de reembolso backoffice (refund_amount + teto mercadoria)."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.orders.schemas import BackofficeCancelInput
from src.orders.service import OrderService, _merchandise_refund_cap, _sum_refunded_merchandise


def test_merchandise_refund_cap_excludes_shipping() -> None:
    order = {"total_amount": 110.0, "shipping_amount": 10.0}
    rem, teto, ja = _merchandise_refund_cap(order, 0.0)
    assert teto == 100.0
    assert ja == 0.0
    assert rem == 100.0


def test_merchandise_refund_cap_null_shipping() -> None:
    order = {"total_amount": 50.0, "shipping_amount": None}
    rem, teto, ja = _merchandise_refund_cap(order, 20.0)
    assert teto == 50.0
    assert ja == 20.0
    assert rem == 30.0


def test_sum_refunded_merchandise_only_refunded_status() -> None:
    refunds = [
        {"amount": 10.0, "status": "refunded"},
        {"amount": 5.0, "status": "pending"},
        {"amount": 3.0, "status": "refunded"},
    ]
    assert _sum_refunded_merchandise(refunds) == 13.0


def test_backoffice_input_refund_amount_mode() -> None:
    p = BackofficeCancelInput(refund_method="mp", refund_amount=25.50)
    assert p.refund_amount == 25.5
    assert p.full_cancel is False


def test_backoffice_input_rejects_refund_amount_with_full_cancel() -> None:
    with pytest.raises(ValidationError):
        BackofficeCancelInput(refund_method="mp", refund_amount=10.0, full_cancel=True)


def test_backoffice_input_requires_mode() -> None:
    with pytest.raises(ValidationError):
        BackofficeCancelInput(refund_method="mp")


@pytest.fixture
def mp_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP_ACCESS_TOKEN", "test-token")


@patch("src.orders.service.OrderRepository")
def test_backoffice_refund_amount_ok(mock_repo_cls: MagicMock, mp_token: None) -> None:
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    svc = OrderService()
    mock_repo.get_order_with_items.return_value = {
        "id": "o1",
        "total_amount": 110.0,
        "shipping_amount": 10.0,
        "mp_payment_id": "mp-99",
        "items": [],
    }
    mock_repo.list_refund_requests_by_order.return_value = []
    mock_repo.insert_refund_request.return_value = {"id": "rf-1"}
    mock_repo.update_refund_request.return_value = {"id": "rf-1", "status": "refunded"}

    with patch.object(OrderService, "_refund_mercadopago", return_value={"id": 777}) as mock_mp:
        out = svc.backoffice_cancel_and_refund(
            "o1",
            BackofficeCancelInput(refund_method="mp", refund_amount=50.0),
        )

    mock_mp.assert_called_once()
    assert out["amount"] == 50.0
    assert out["mp_refund_id"] == 777
    insert_kw = mock_repo.insert_refund_request.call_args.kwargs
    assert insert_kw["order_item_ids"] == []


@patch("src.orders.service.OrderRepository")
def test_backoffice_refund_amount_exceeds_cap(mock_repo_cls: MagicMock, mp_token: None) -> None:
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    svc = OrderService()
    mock_repo.get_order_with_items.return_value = {
        "id": "o1",
        "total_amount": 110.0,
        "shipping_amount": 10.0,
        "mp_payment_id": "mp-99",
        "items": [],
    }
    mock_repo.list_refund_requests_by_order.return_value = []

    with pytest.raises(ValueError, match="Valor acima do permitido"):
        svc.backoffice_cancel_and_refund(
            "o1",
            BackofficeCancelInput(refund_method="mp", refund_amount=100.01),
        )


@patch("src.orders.service.OrderRepository")
def test_backoffice_refund_amount_after_prior_refund(mock_repo_cls: MagicMock, mp_token: None) -> None:
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    svc = OrderService()
    mock_repo.get_order_with_items.return_value = {
        "id": "o1",
        "total_amount": 100.0,
        "shipping_amount": 0.0,
        "mp_payment_id": "mp-99",
        "items": [],
    }
    mock_repo.list_refund_requests_by_order.return_value = [
        {"amount": 40.0, "status": "refunded"},
    ]
    mock_repo.insert_refund_request.return_value = {"id": "rf-2"}
    mock_repo.update_refund_request.return_value = {}

    with patch.object(OrderService, "_refund_mercadopago", return_value={"id": 888}):
        out = svc.backoffice_cancel_and_refund(
            "o1",
            BackofficeCancelInput(refund_method="mp", refund_amount=60.0),
        )
    assert out["amount"] == 60.0


@patch("src.orders.service.OrderRepository")
def test_backoffice_refund_amount_when_pool_exhausted(mock_repo_cls: MagicMock, mp_token: None) -> None:
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    svc = OrderService()
    mock_repo.get_order_with_items.return_value = {
        "id": "o1",
        "total_amount": 50.0,
        "shipping_amount": 0.0,
        "mp_payment_id": "mp-99",
        "items": [],
    }
    mock_repo.list_refund_requests_by_order.return_value = [
        {"amount": 50.0, "status": "refunded"},
    ]
    with pytest.raises(ValueError, match="Valor acima do permitido"):
        svc.backoffice_cancel_and_refund(
            "o1",
            BackofficeCancelInput(refund_method="mp", refund_amount=1.0),
        )
