"""Erros específicos do fluxo de pagamento (Mercado Pago + regras de negócio)."""


class PaymentDeclinedError(Exception):
    """Banco/emissor recusou ou pagamento cancelado; não persistir pedido nem estoque."""

    def __init__(self, mp_response: dict, public_message: str | None = None) -> None:
        self.mp_response = mp_response if isinstance(mp_response, dict) else {}
        msg = (public_message or "").strip() or self._default_message(self.mp_response)
        super().__init__(msg)

    @staticmethod
    def _default_message(mp_response: dict) -> str:
        m = (mp_response.get("message") or "").strip()
        if m:
            return m
        return "Pagamento recusado."


class MercadoPagoAPIError(Exception):
    """HTTP de erro retornado pelo SDK (status além de 200/201)."""

    def __init__(self, message: str, response: dict | None = None) -> None:
        self.response = response if isinstance(response, dict) else {}
        super().__init__(message)
