from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List, Dict, Any


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
    
    # color, material, pattern (VARCHAR 100, opcionais)
    color: Optional[str] = None
    material: Optional[str] = None
    pattern: Optional[str] = None
    
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
    color: Optional[str] = None
    material: Optional[str] = None
    pattern: Optional[str] = None
    
    # Serializa Decimal como float no JSON para compatibilidade com Frontend
    @field_serializer('price', when_used='json')
    def serialize_price(self, value: Optional[Decimal]) -> Optional[float]:
        return float(value) if value is not None else None


def serialize_for_firebase(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts product data from Supabase format to Firebase-compatible format.
    
    Handles:
    - Decimal to float conversion
    - datetime to ISO 8601 string
    - None values removal (Firebase doesn't store nulls efficiently)
    
    Args:
        product_data: Raw product dict from Supabase
        
    Returns:
        Firebase-compatible dict
    """
    firebase_data = {}
    
    for key, value in product_data.items():
        if value is None:
            continue
        
        if isinstance(value, Decimal):
            firebase_data[key] = float(value)
        elif isinstance(value, datetime):
            firebase_data[key] = value.isoformat()
        elif isinstance(value, dict):
            firebase_data[key] = value
        elif isinstance(value, list):
            firebase_data[key] = value
        else:
            firebase_data[key] = value
    
    return firebase_data