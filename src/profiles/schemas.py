from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime


class Profile(BaseModel):
    """Modelo de perfil de usuário (saída da API)."""
    id: str
    email: Optional[str] = None
    role: str = "user"
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileFilter(BaseModel):
    """Modelo para validar query parameters de listagem."""
    page: int = Field(default=1, ge=1, description="Página atual (1-indexed)")
    limit: int = Field(default=10, ge=1, le=100, description="Itens por página")
    email: Optional[str] = Field(default=None, description="Filtro parcial por email (ilike)")
    role: Optional[Literal["admin", "user"]] = Field(default=None, description="Filtro exato por role")
    sort: Optional[Literal["newest", "role_asc", "role_desc"]] = Field(
        default="newest",
        description="Ordenação: newest (created_at desc), role_asc, role_desc"
    )

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: Optional[str]) -> Optional[str]:
        """Remove espaços extras do email."""
        return v.strip() if v else None


class ProfileUpdate(BaseModel):
    """Modelo para atualização de perfil (PUT)."""
    id: str = Field(..., description="UUID do perfil a atualizar")
    email: Optional[str] = Field(None, description="Novo email (opcional)")
    role: Optional[Literal["admin", "user"]] = Field(None, description="Nova role (opcional)")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Valida formato básico de email."""
        if v:
            v = v.strip()
            if "@" not in v or "." not in v:
                raise ValueError("Email inválido")
        return v


class ProfileDelete(BaseModel):
    """Modelo para remoção de perfil (DELETE)."""
    id: str = Field(..., description="UUID do perfil a remover")
