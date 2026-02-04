import json
import pytest
from unittest.mock import patch

from src.shipping.handler import lambda_handler


def _event(body: dict | None = None, method: str = "POST") -> dict:
    return {
        "requestContext": {"http": {"method": method}},
        "body": json.dumps(body) if body else None,
    }


class TestShippingHandler:
    """Testes do handler de cotação de frete."""

    def test_options_returns_200(self) -> None:
        resp = lambda_handler(_event(method="OPTIONS"), None)
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"]) == {}

    def test_non_post_returns_405(self) -> None:
        resp = lambda_handler(_event(body={}, method="GET"), None)
        assert resp["statusCode"] == 405
        assert "POST" in json.loads(resp["body"])["error"]

    def test_empty_body_returns_400(self) -> None:
        resp = lambda_handler(_event(body=None), None)
        assert resp["statusCode"] == 400
        body_err = json.loads(resp["body"])["error"]
        assert "cep_destino" in body_err or "itens" in body_err or "obrigatório" in body_err.lower()

    def test_success_returns_opcoes(self) -> None:
        with patch("src.shipping.handler.quote_freight") as mock_quote:
            mock_quote.return_value = [
                {"transportadora": "Correios PAC", "preco": 25.90, "prazo_entrega_dias": 8},
            ]
            body = {
                "cep_destino": "01310100",
                "itens": [{"width": 11, "height": 17, "length": 11, "weight": 0.3}],
            }
            resp = lambda_handler(_event(body=body), None)
            assert resp["statusCode"] == 200
            data = json.loads(resp["body"])
            assert "opcoes" in data
            assert len(data["opcoes"]) == 1
            assert data["opcoes"][0]["preco"] == 25.90
            mock_quote.assert_called_once()

    def test_validation_error_returns_400(self) -> None:
        with patch("src.shipping.handler.parse") as mock_parse:
            mock_parse.side_effect = ValueError("CEP deve conter 8 dígitos")
            body = {"cep_destino": "123", "itens": [{"width": 11, "height": 17, "length": 11, "weight": 0.3}]}
            resp = lambda_handler(_event(body=body), None)
            assert resp["statusCode"] == 400
            assert "details" in json.loads(resp["body"])

    def test_melhor_envio_error_returns_502(self) -> None:
        from src.shipping.service import MelhorEnvioAPIError
        with patch("src.shipping.handler.quote_freight") as mock_quote:
            mock_quote.side_effect = MelhorEnvioAPIError("Falha de conexão")
            body = {"cep_destino": "01310100", "itens": [{"width": 11, "height": 17, "length": 11, "weight": 0.3}]}
            resp = lambda_handler(_event(body=body), None)
            assert resp["statusCode"] == 502
            err = json.loads(resp["body"])["error"]
            assert "Frete" in err or "conexão" in err.lower()

    def test_unexpected_exception_returns_500(self) -> None:
        with patch("src.shipping.handler.quote_freight") as mock_quote:
            mock_quote.side_effect = RuntimeError("Unexpected")
            body = {"cep_destino": "01310100", "itens": [{"width": 11, "height": 17, "length": 11, "weight": 0.3}]}
            resp = lambda_handler(_event(body=body), None)
            assert resp["statusCode"] == 500
            assert "error" in json.loads(resp["body"])
