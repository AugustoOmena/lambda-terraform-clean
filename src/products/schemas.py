from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List, Dict, Any


class ProductVariantInput(BaseModel):
    """Uma variante: cor + tamanho + estoque (e opcionalmente SKU)."""
    color: str
    size: str
    stock_quantity: int = Field(0, ge=0)
    sku: Optional[str] = None


class ProductInput(BaseModel):
    
    name: str
    price: Decimal = Field(..., gt=0, decimal_places=2)
    description: Optional[str] = None
    category: Optional[str] = None
    quantity: int = 0
    size: Optional[str] = None
    image: Optional[str] = None
    images: List[str] = []
    stock: Dict[str, int] = {}
    is_featured: Optional[bool] = None
    material: Optional[str] = None
    pattern: Optional[str] = None
    variants: List[ProductVariantInput] = []

    @field_serializer('price', when_used='json')
    def serialize_price(self, value: Decimal) -> float:
        return float(value)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    description: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[int] = None
    size: Optional[str] = None
    image: Optional[str] = None
    images: Optional[List[str]] = None
    stock: Optional[Dict[str, int]] = None
    is_featured: Optional[bool] = None
    material: Optional[str] = None
    pattern: Optional[str] = None
    variants: Optional[List[ProductVariantInput]] = None

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