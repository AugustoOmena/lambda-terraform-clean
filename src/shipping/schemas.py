"""DTOs and validation for shipping (freight quote) microservice."""

from typing import List
from pydantic import BaseModel, Field, field_validator


def _normalize_cep(v: str) -> str:
    """Strip non-digits and validate length."""
    digits = "".join(c for c in str(v).strip() if c.isdigit())
    if len(digits) != 8:
        raise ValueError("CEP deve conter 8 dígitos")
    return digits


class ShippingItemInput(BaseModel):
    """Single item for freight quote: dimensions in cm, weight in kg."""

    width: float = Field(..., gt=0, description="Largura em cm")
    height: float = Field(..., gt=0, description="Altura em cm")
    length: float = Field(..., gt=0, description="Comprimento em cm")
    weight: float = Field(..., gt=0, description="Peso em kg")
    quantity: int = Field(default=1, ge=1, description="Quantidade")
    insurance_value: float = Field(default=0.0, ge=0, description="Valor declarado em R$ (opcional)")

    @field_validator("width", "height", "length", "weight", mode="before")
    @classmethod
    def coerce_float(cls, v):
        if v is None:
            raise ValueError("Dimensão e peso são obrigatórios")
        try:
            return float(v)
        except (TypeError, ValueError):
            raise ValueError("Valores numéricos inválidos")


class FreightQuoteInput(BaseModel):
    """Input for freight quote: destination CEP and list of items."""

    cep_destino: str = Field(..., description="CEP de destino (8 dígitos)")
    itens: List[ShippingItemInput] = Field(..., min_length=1, description="Lista de itens com peso e dimensões")

    @field_validator("cep_destino", mode="before")
    @classmethod
    def validate_cep_destino(cls, v: str) -> str:
        return _normalize_cep(v)
