import json
import pytest
from unittest.mock import patch, MagicMock

from handler import lambda_handler


def _event(
    method: str,
    path_params: dict | None = None,
    query_params: dict | None = None,
    body=None,
    raw_path: str | None = None,
) -> dict:
    e = {
        "requestContext": {"http": {"method": method}},
        "pathParameters": path_params,
        "queryStringParameters": query_params,
    }
    if body is not None:
        e["body"] = body
    if raw_path is not None:
        e["rawPath"] = raw_path
    return e


def _context():
    return MagicMock()


@pytest.fixture
def mock_service():
    with patch("handler.ProductService") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


class TestHandlerGetListagem:
    """GET /produtos — listagem: queryStringParameters passados para service.list_products."""

    def test_listagem_passes_page_limit_and_filters_to_list_products(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.list_products.return_value = {"data": [], "meta": {"total": 0, "page": 2, "limit": 5, "nextPage": None}}

        event = _event(
            "GET",
            path_params={},
            query_params={"page": "2", "limit": "5"},
        )
        resp = lambda_handler(event, _context())

        mock_service.list_products.assert_called_once()
        call = mock_service.list_products.call_args
        assert call[0][0] == 2
        assert call[0][1] == 5
        filters = call[0][2]
        assert filters["sort"] == "newest"
        assert filters.get("name") is None
        assert filters.get("category") is None
        assert resp["statusCode"] == 200

    def test_listagem_passes_all_query_filters_to_list_products(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.list_products.return_value = {"data": [], "meta": {"total": 0}}

        event = _event(
            "GET",
            path_params={},
            query_params={
                "page": "1",
                "limit": "20",
                "name": "camiseta",
                "category": "Roupas",
                "min_price": "10",
                "max_price": "100",
                "sort": "oldest",
                "size": "M",
            },
        )
        lambda_handler(event, _context())

        call = mock_service.list_products.call_args
        assert call[0][0] == 1
        assert call[0][1] == 20
        filters = call[0][2]
        assert filters["name"] == "camiseta"
        assert filters["category"] == "Roupas"
        assert filters["min_price"] == "10"
        assert filters["max_price"] == "100"
        assert filters["sort"] == "oldest"
        assert filters["size"] == "M"

    def test_listagem_uses_search_as_name_fallback(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.list_products.return_value = {"data": [], "meta": {}}

        event = _event(
            "GET",
            path_params={},
            query_params={"search": "terno"},
        )
        lambda_handler(event, _context())

        filters = mock_service.list_products.call_args[0][2]
        assert filters["name"] == "terno"


class TestHandlerGetById:
    """GET /produtos/{id} — ID vindo de pathParameters.proxy ou pathParameters.id."""

    def test_get_by_id_from_path_parameters_proxy(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.get_product.return_value = {"id": 456, "name": "Prod"}

        event = _event("GET", path_params={"proxy": "456"}, query_params=None)
        resp = lambda_handler(event, _context())

        mock_service.get_product.assert_called_once_with(456)
        assert resp["statusCode"] == 200

    def test_get_by_id_from_path_parameters_id(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.get_product.return_value = {"id": 789, "name": "Outro"}

        event = _event("GET", path_params={"id": "789"}, query_params=None)
        resp = lambda_handler(event, _context())

        mock_service.get_product.assert_called_once_with(789)
        assert resp["statusCode"] == 200


class TestHandlerGetExportar:
    """GET /produtos/exportar — proxy='exportar' e Content-Type text/csv."""

    def test_exportar_proxy_returns_text_csv_and_calls_export(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.export_products_csv.return_value = "ID,Nome\n1,Test"

        event = _event("GET", path_params={"proxy": "exportar"}, query_params=None)
        resp = lambda_handler(event, _context())

        mock_service.export_products_csv.assert_called_once()
        assert resp["statusCode"] == 200
        assert "text/csv" in resp["headers"]["Content-Type"]
        assert resp["body"] == "ID,Nome\n1,Test"


class TestHandlerOptions:
    """OPTIONS — 200 e corpo vazio."""

    def test_options_returns_200_and_empty_body(
        self, mock_service: MagicMock
    ) -> None:
        event = _event("OPTIONS", path_params=None, query_params=None)
        resp = lambda_handler(event, _context())

        assert resp["statusCode"] == 200
        assert resp["body"] == "{}"
        mock_service.list_products.assert_not_called()
        mock_service.get_product.assert_not_called()
        mock_service.export_products_csv.assert_not_called()


class TestHandlerPost:
    """POST /produtos — create; validação do body via parse."""

    def test_post_success_returns_201(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.create_product.return_value = {"id": 1, "name": "Camiseta", "price": 29.90}

        event = _event("POST", body='{"name": "Camiseta", "price": 29.90}')
        resp = lambda_handler(event, _context())

        assert resp["statusCode"] == 201
        mock_service.create_product.assert_called_once()
        body = json.loads(resp["body"])
        assert body["id"] == 1 and body["name"] == "Camiseta"

    def test_post_parse_fails_returns_500(
        self, mock_service: MagicMock
    ) -> None:
        with patch("handler.parse", side_effect=ValueError("body inválido")):
            event = _event("POST", body='{"invalid": true}')
            resp = lambda_handler(event, _context())

        assert resp["statusCode"] == 500
        out = json.loads(resp["body"])
        assert "error" in out
        assert "inválido" in out["error"]
        mock_service.create_product.assert_not_called()


class TestHandlerPut:
    """PUT /produtos — atualização; extração de ID da URL ou do body."""

    def test_put_id_from_url_success(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.update_product.return_value = {"id": 123, "name": "Atualizado"}

        event = _event(
            "PUT",
            path_params={"id": "123"},
            body='{"name": "Atualizado"}',
        )
        resp = lambda_handler(event, _context())

        assert resp["statusCode"] == 200
        mock_service.update_product.assert_called_once()
        assert mock_service.update_product.call_args[0][0] == 123

    def test_put_id_from_body_fallback_success(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.update_product.return_value = {"id": 456, "name": "Novo"}

        event = _event(
            "PUT",
            path_params={},
            body='{"id": 456, "name": "Novo"}',
        )
        resp = lambda_handler(event, _context())

        assert resp["statusCode"] == 200
        mock_service.update_product.assert_called_once()
        assert mock_service.update_product.call_args[0][0] == 456

    def test_put_no_id_returns_400(
        self, mock_service: MagicMock
    ) -> None:
        event = _event(
            "PUT",
            path_params={},
            body='{"name": "Sem ID"}',
        )
        resp = lambda_handler(event, _context())

        assert resp["statusCode"] == 400
        out = json.loads(resp["body"])
        assert "error" in out and "ID obrigatório" in out["error"]
        mock_service.update_product.assert_not_called()


class TestHandlerDelete:
    """DELETE /produtos — extração de ID da URL ou do rawPath."""

    def test_delete_id_from_url_success(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.delete_product.return_value = None

        event = _event("DELETE", path_params={"id": "777"})
        resp = lambda_handler(event, _context())

        assert resp["statusCode"] == 204
        mock_service.delete_product.assert_called_once_with(777)

    def test_delete_id_from_raw_path_fallback_success(
        self, mock_service: MagicMock
    ) -> None:
        mock_service.delete_product.return_value = None

        event = _event("DELETE", path_params={}, raw_path="/produtos/888")
        resp = lambda_handler(event, _context())

        assert resp["statusCode"] == 204
        mock_service.delete_product.assert_called_once_with(888)

    def test_delete_no_id_returns_400(
        self, mock_service: MagicMock
    ) -> None:
        event = _event("DELETE", path_params={}, raw_path="/produtos")
        resp = lambda_handler(event, _context())

        assert resp["statusCode"] == 400
        out = json.loads(resp["body"])
        assert "error" in out and "ID obrigatório" in out["error"]
        mock_service.delete_product.assert_not_called()
