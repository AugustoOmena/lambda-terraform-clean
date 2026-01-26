from decimal import Decimal
from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List, Dict


class ProductInput(BaseModel):
    
    # name TEXT NOT NULL
    name: str
    
    # price NUMERIC (nullable no banco, mas obrigatório na criação)
    price: Decimal = Field(..., gt=0, decimal_places=2)
    
    # description TEXT (nullable)
    description: Optional[str] = None
    
    # category TEXT (nullable)
    category: Optional[str] = None
    
    # quantity INTEGER DEFAULT 0
    quantity: int = 0
    
    # size TEXT (nullable)
    size: Optional[str] = None
    
    # image TEXT (nullable)
    image: Optional[str] = None
    
    # images TEXT[] DEFAULT '{}'
    images: List[str] = []
    
    # stock JSONB DEFAULT '{}'
    stock: Dict[str, int] = {}
    
    # is_featured BOOLEAN DEFAULT false
    is_featured: Optional[bool] = None
    
    # Serializa Decimal como float no JSON para compatibilidade com Frontend
    @field_serializer('price', when_used='json')
    def serialize_price(self, value: Decimal) -> float:
        return float(value)


class ProductUpdate(BaseModel):
    
    # Todos os campos opcionais em Update (PATCH semântico)
    name: Optional[str] = None
    
    # AJUSTE: float -> Decimal para precisão monetária
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    
    description: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[int] = None
    size: Optional[str] = None
    image: Optional[str] = None
    images: Optional[List[str]] = None
    stock: Optional[Dict[str, int]] = None
    is_featured: Optional[bool] = None
    
    # Serializa Decimal como float no JSON para compatibilidade com Frontend
    @field_serializer('price', when_used='json')
    def serialize_price(self, value: Optional[Decimal]) -> Optional[float]:
        return float(value) if value is not None else None