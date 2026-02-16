from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

class Identification(BaseModel):
    type: str = Field(default="CPF", description="Tipo de documento")
    number: str = Field(..., description="Número do documento")

    @field_validator('number')
    @classmethod
    def clean_number(cls, v: str) -> str:
        """Remove caracteres não-numéricos do número do documento."""
        return ''.join(filter(str.isdigit, v))

# NOVO: Classe de Endereço
class Address(BaseModel):
    zip_code: str
    street_name: str
    street_number: str
    neighborhood: str
    city: str
    federal_unit: str
    complement: Optional[str] = Field(None, max_length=30, description="Complemento (até 30 caracteres)")

class Payer(BaseModel):
    email: str
    first_name: Optional[str] = Field(default="Cliente", description="Nome enviado pelo checkout")
    last_name: Optional[str] = Field(default="Desconhecido", description="Sobrenome enviado pelo checkout")
    identification: Identification
    address: Optional[Address] = None

    @model_validator(mode="after")
    def normalize_payer_name(self):
        """Garante valores não vazios para MP quando o checkout envia first_name/last_name separados."""
        updates = {}
        if not (self.first_name and str(self.first_name).strip()):
            updates["first_name"] = "Cliente"
        if not (self.last_name and str(self.last_name).strip()):
            updates["last_name"] = "Desconhecido"
        return self.model_copy(update=updates) if updates else self

class Item(BaseModel):
    id: int
    name: str
    price: float
    quantity: int
    image: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = "Único"

def _normalize_cep(v: str) -> str:
    digits = "".join(c for c in str(v).strip() if c.isdigit())
    if len(digits) != 8:
        raise ValueError("CEP deve conter 8 dígitos")
    return digits


class PaymentInput(BaseModel):
    token: Optional[str] = None
    transaction_amount: float
    payment_method_id: str
    installments: int = 1
    issuer_id: Optional[str] = None
    payer: Payer
    user_id: str
    items: List[Item]
    frete: float = Field(..., ge=0, description="Valor do frete em R$ (validado na API Melhor Envio)")
    frete_service: str = Field(..., min_length=1, description="Identificador do serviço escolhido (retornado em opcoes[].service no GET /frete)")
    cep: str = Field(..., description="CEP de destino, 8 dígitos")

    @field_validator("cep", mode="before")
    @classmethod
    def validate_cep(cls, v: str) -> str:
        return _normalize_cep(v)