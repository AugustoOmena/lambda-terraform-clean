import json
import pytest
from unittest.mock import patch, MagicMock

from src.shared.melhor_envio import (
    MelhorEnvioAPIError,
    get_quote,
    _parse_response,
    _parse_quote_option,
)


class TestParseQuoteOption:
    """Parsing de um item da resposta da API."""

    def test_extracts_name_price_days(self) -> None:
        entry = {"name": "Correios PAC", "price": 25.90, "delivery_time": 8}
        out = _parse_quote_option(entry)
        assert out["transportadora"] == "Correios PAC"
        assert out["preco"] == 25.90
        assert out["prazo_entrega_dias"] == 8

    def test_uses_custom_price_when_present(self) -> None:
        entry = {"name": "PAC", "price": 20.00, "custom_price": 22.50}
        out = _parse_quote_option(entry)
        assert out["preco"] == 22.50

    def test_company_name_fallback(self) -> None:
        entry = {"company": {"name": "Jadlog"}, "price": 31.00}
        out = _parse_quote_option(entry)
        assert out["transportadora"] == "Jadlog"
        assert out["preco"] == 31.00

    def test_returns_none_when_no_price(self) -> None:
        assert _parse_quote_option({"name": "X"}) is None
        assert _parse_quote_option({}) is None


class TestParseResponse:
    """Parsing da resposta completa da API (list ou dict)."""

    def test_list_of_options(self) -> None:
        body = [
            {"name": "A", "price": 10.0},
            {"name": "B", "price": 20.0},
        ]
        out = _parse_response(body)
        assert len(out) == 2
        assert out[0]["transportadora"] == "A" and out[0]["preco"] == 10.0
        assert out[1]["transportadora"] == "B" and out[1]["preco"] == 20.0

    def test_packages_wrapper(self) -> None:
        body = {
            "id": 1,
            "packages": [
                {"options": [{"name": "PAC", "price": 15.0}]},
            ],
        }
        out = _parse_response(body)
        assert len(out) == 1
        assert out[0]["transportadora"] == "PAC" and out[0]["preco"] == 15.0

    def test_empty_list_for_unknown_structure(self) -> None:
        assert _parse_response({"other": 1}) == []


class TestGetQuote:
    """Chamada HTTP à API (mock de urllib)."""

    @pytest.fixture(autouse=True)
    def env_vars(self):
        with patch.dict(
            "os.environ",
            {"MELHOR_ENVIO_TOKEN": "fake-token", "CEP_ORIGEM": "59082000"},
            clear=False,
        ):
            yield

    def test_builds_payload_and_returns_parsed_options(self, env_vars) -> None:
        api_response = [
            {"name": "Correios PAC", "price": 25.90, "delivery_time": 8},
        ]
        with patch("src.shared.melhor_envio.urllib.request.urlopen") as mock_open:
            resp = MagicMock()
            resp.status = 200
            resp.read.return_value = json.dumps(api_response).encode("utf-8")
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = resp

            result = get_quote("01310100", [{"width": 11, "height": 17, "length": 11, "weight": 0.3, "quantity": 1}])

            assert len(result) == 1
            assert result[0]["preco"] == 25.90
            mock_open.assert_called_once()
            call_args = mock_open.call_args[0][0]
            assert call_args.data is not None
            payload = json.loads(call_args.data.decode("utf-8"))
            assert payload["from"]["postal_code"] == "59082000"
            assert payload["to"]["postal_code"] == "01310100"
            assert len(payload["products"]) == 1
            assert payload["products"][0]["weight"] == 0.3

    def test_raises_on_http_error(self, env_vars) -> None:
        import urllib.error
        with patch("src.shared.melhor_envio.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = urllib.error.HTTPError(
                "http://x", 500, "Error", {}, None
            )
            with pytest.raises(MelhorEnvioAPIError) as exc_info:
                get_quote("01310100", [{"width": 11, "height": 17, "length": 11, "weight": 0.3, "quantity": 1}])
            assert "500" in str(exc_info.value)

    def test_raises_on_timeout(self, env_vars) -> None:
        import urllib.error
        with patch("src.shared.melhor_envio.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = TimeoutError("timed out")
            with pytest.raises(MelhorEnvioAPIError) as exc_info:
                get_quote("01310100", [{"width": 11, "height": 17, "length": 11, "weight": 0.3, "quantity": 1}])
            assert "Timeout" in str(exc_info.value)

    def test_raises_when_token_missing(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(MelhorEnvioAPIError) as exc_info:
                get_quote("01310100", [{"width": 11, "height": 17, "length": 11, "weight": 0.3, "quantity": 1}])
            assert "MELHOR_ENVIO_TOKEN" in str(exc_info.value) or "obrigatória" in str(exc_info.value)
