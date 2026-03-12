"""Repository: acesso ao Supabase para produtos e Storage."""

from typing import List, Set

from aws_lambda_powertools import Logger
from shared.database import get_supabase_client

logger = Logger(service="cleanup-orphan-images")


class CleanupOrphanImagesRepository:
    """Consulta produtos e gerencia Storage para limpeza de imagens órfãs."""

    BUCKET = "product-images"

    def __init__(self) -> None:
        self.db = get_supabase_client()

    def get_referenced_image_paths(self) -> Set[str]:
        """Retorna set de paths de imagens referenciadas em products (image e images)."""
        res = self.db.table("products").select("image, images").execute()
        paths: Set[str] = set()
        for row in res.data or []:
            if row.get("image"):
                paths.add(self._normalize_path(row["image"]))
            for img in row.get("images") or []:
                if img:
                    paths.add(self._normalize_path(img))
        return paths

    def _normalize_path(self, value: str) -> str:
        """Extrai o path relativo ao bucket (ex: '1770xxx.jpg') de URL ou path completo."""
        if not value:
            return ""
        if self.BUCKET in value:
            return value.split(f"{self.BUCKET}/")[-1].split("?")[0]
        return value.split("/")[-1].split("?")[0] if "/" in value else value

    def list_storage_paths(self) -> List[str]:
        """Lista paths de arquivos no bucket product-images (raiz e subpastas recursivo)."""
        paths: List[str] = []

        def _list_recursive(prefix: str) -> None:
            items = self.db.storage.from_(self.BUCKET).list(prefix) or []
            for item in items:
                name = item.get("name", "")
                if not name or name == ".emptyFolderPlaceholder":
                    continue
                full_path = f"{prefix}{name}" if prefix else name
                if item.get("id") is not None:
                    paths.append(full_path)
                else:
                    _list_recursive(f"{full_path}/")

        _list_recursive("")
        return paths

    def delete_storage_files(self, paths: List[str]) -> int:
        """Remove arquivos do Storage pelo path. Retorna quantidade deletada com sucesso."""
        if not paths:
            return 0
        deleted = 0
        for path in paths:
            try:
                self.db.storage.from_(self.BUCKET).remove([path])
                deleted += 1
            except Exception as e:
                logger.warning("Falha ao deletar", extra={"path": path, "error": str(e)})
        return deleted
