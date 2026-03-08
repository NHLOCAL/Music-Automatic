from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable, Optional

from send2trash import send2trash

from .dto import (
    AlbumCluster,
    AlbumSummary,
    DeleteExecution,
    DeleteExecutionItem,
    DeletePreview,
    DeletePreviewItem,
)

logger = logging.getLogger(__name__)


class DeletionService:
    def build_preview(
        self,
        clusters: Dict[str, AlbumCluster],
        albums: Dict[str, AlbumSummary],
        decisions: Dict[str, Optional[str]],
    ) -> DeletePreview:
        items: Dict[str, DeletePreviewItem] = {}
        for cluster_id, keeper_id in decisions.items():
            if not keeper_id:
                continue
            cluster = clusters.get(cluster_id)
            if cluster is None or keeper_id not in cluster.folder_ids:
                continue
            keeper_album = albums[keeper_id]
            for folder_id in cluster.folder_ids:
                if folder_id == keeper_id:
                    continue
                album = albums[folder_id]
                items[folder_id] = DeletePreviewItem(
                    folder_id=folder_id,
                    folder_path=album.path,
                    folder_name=album.name,
                    keeper_folder_id=keeper_id,
                    keeper_folder_name=keeper_album.name,
                    keeper_folder_path=keeper_album.path,
                    cluster_id=cluster_id,
                )
        return DeletePreview(items=list(items.values()))

    def execute(
        self,
        preview: DeletePreview,
        confirmed_folder_ids: Iterable[str],
    ) -> DeleteExecution:
        confirmed = set(confirmed_folder_ids)
        moved_count = 0
        failed_count = 0
        results: list[DeleteExecutionItem] = []

        for item in preview.items:
            if item.folder_id not in confirmed:
                continue
            try:
                if not item.folder_path.exists():
                    failed_count += 1
                    results.append(
                        DeleteExecutionItem(
                            folder_id=item.folder_id,
                            folder_path=item.folder_path,
                            success=False,
                            message="התיקייה לא קיימת.",
                        )
                    )
                    continue
                send2trash(str(item.folder_path))
                moved_count += 1
                results.append(
                    DeleteExecutionItem(
                        folder_id=item.folder_id,
                        folder_path=item.folder_path,
                        success=True,
                        message="הועבר לסל המחזור.",
                    )
                )
            except Exception as exc:
                failed_count += 1
                logger.error("Failed to move folder to recycle bin: %s", item.folder_path, exc_info=True)
                results.append(
                    DeleteExecutionItem(
                        folder_id=item.folder_id,
                        folder_path=item.folder_path,
                        success=False,
                        message=str(exc),
                    )
                )

        return DeleteExecution(
            moved_count=moved_count,
            failed_count=failed_count,
            results=results,
        )

