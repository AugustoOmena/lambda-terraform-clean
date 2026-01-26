from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

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

class Payer(BaseModel):
    email: str 
    first_name: Optional[str] = "Cliente"
    last_name: Optional[str] = "Desconhecido"
    identification: Identification
    # NOVO: Endereço opcional
    address: Optional[Address] = None

class Item(BaseModel):
    id: int
    name: str
    price: float
    quantity: int
    image: Optional[str] = None 
    size: Optional[str] = "Único"

class PaymentInput(BaseModel):
    token: Optional[str] = None 
    transaction_amount: float
    payment_method_id: str
    installments: int = 1
    issuer_id: Optional[str] = None
    payer: Payer
    user_id: str
    items: List[Item]