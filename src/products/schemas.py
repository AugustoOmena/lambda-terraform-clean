from pydantic import BaseModel, Field
from typing import Optional, List, Dict # <--- ADICIONEI O Dict E O List AQUI

# Se preferir, no Python 3.11 você pode usar list[] e dict[] minúsculos,
# mas vamos manter o import para garantir compatibilidade total com seu Pydantic.

class ProductInput(BaseModel):
    name: str
    price: float = Field(..., gt=0)
    description: Optional[str] = None
    category: Optional[str] = None
    quantity: int = 0
    size: Optional[str] = None 
    image: Optional[str] = None
    images: List[str] = []
    
    # Campo corrigido (agora Dict está importado lá em cima)
    stock: Optional[Dict[str, int]] = {} 

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[int] = None
    size: Optional[str] = None
    image: Optional[str] = None
    images: Optional[List[str]] = None
    
    # Campo corrigido
    stock: Optional[Dict[str, int]] = None