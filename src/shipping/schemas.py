"""DTOs and validation for shipping (freight quote) microservice.

Dimensões (width, height, length) em cm devem ser sempre inteiras e arredondadas
para cima (math.ceil) antes de enviar ao Melhor Envio e ao Carrinho — evita
divergência de preços entre cotação e checkout.
"""

import math
from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field, field_validator


def _normalize_cep(v: str) -> str:
    """Strip non-digits and validate length."""
    digits = "".join(c for c in str(v).strip() if c.isdigit())
    if len(digits) != 8:
        raise ValueError("CEP deve conter 8 dígitos")
    return digits


def _dimension_to_int_ceil(v) -> int:
    """Converte dimensão para int; frações são arredondadas para cima (Melhor Envio / Carrinho)."""
    if v is None:
        raise ValueError("Dimensões são obrigatórias")
    if isinstance(v, bool):
        raise ValueError("Valores numéricos inválidos")
    if isinstance(v, int):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError("Valores numéricos inválidos")
    return math.ceil(f)


class ShippingItemInput(BaseModel):
    """Single item for freight quote: dimensions in cm (int, ceil), weight in kg (Decimal, 3 decimals)."""

    width: int = Field(..., gt=0, description="Largura em cm (inteiro; valores fracionários devem ser arredondados para cima antes do envio)")
    height: int = Field(..., gt=0, description="Altura em cm (inteiro; usar math.ceil para frações)")
    length: int = Field(..., gt=0, description="Comprimento em cm (inteiro; usar math.ceil para frações)")
    weight: Decimal = Field(..., gt=0, description="Peso em kg (até 3 casas decimais, padrão Melhor Envio)")
    quantity: int = Field(default=1, ge=1, description="Quantidade")
    insurance_value: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Valor declarado em R$ (opcional); use Decimal para alinhar ao Carrinho",
    )

    @field_validator("width", "height", "length", mode="before")
    @classmethod
    def dimensions_ceil_to_int(cls, v):
        """Garante int; entradas fracionárias viram ceil — alinha payload com Carrinho e API."""
        return _dimension_to_int_ceil(v)

    @field_validator("weight", mode="after")
    @classmethod
    def weight_max_three_decimals(cls, v: Decimal) -> Decimal:
        """Peso em kg com no máximo 3 casas decimais (padrão Melhor Envio)."""
        return v.quantize(Decimal("0.001"))


class FreightQuoteInput(BaseModel):
    """Input for freight quote: destination CEP and list of items."""

    cep_destino: str = Field(..., description="CEP de destino (8 dígitos)")
    itens: List[ShippingItemInput] = Field(..., min_length=1, description="Lista de itens com peso e dimensões")

    @field_validator("cep_destino", mode="before")
    @classmethod
    def validate_cep_destino(cls, v: str) -> str:
        return _normalize_cep(v)
