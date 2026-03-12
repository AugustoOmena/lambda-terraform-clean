"""Service: lógica de limpeza de imagens órfãs."""

from typing import Dict, Any

from aws_lambda_powertools import Logger
from repository import CleanupOrphanImagesRepository

logger = Logger(service="cleanup-orphan-images")


class CleanupOrphanImagesService:
    """Remove imagens do bucket product-images não referenciadas em nenhum produto."""

    def __init__(self) -> None:
        self.repo = CleanupOrphanImagesRepository()

    def run(self) -> Dict[str, Any]:
        """Executa a limpeza e retorna resumo (deleted_count, errors)."""
        referenced = self.repo.get_referenced_image_paths()
        storage_paths = self.repo.list_storage_paths()
        referenced_basenames = {p.split("/")[-1] for p in referenced if p}
        orphans = [p for p in storage_paths if p.split("/")[-1] not in referenced_basenames]
        if not orphans:
            return {"deleted_count": 0, "orphans_found": 0}
        logger.info("Orphans a deletar", extra={"paths": orphans})
        deleted = self.repo.delete_storage_files(orphans)
        return {"deleted_count": deleted, "orphans_found": len(orphans)}
