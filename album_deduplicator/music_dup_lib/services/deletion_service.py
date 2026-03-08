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
        resolution_states: Optional[Dict[str, str]] = None,
        excluded_folder_ids: Optional[set[str]] = None,
    ) -> DeletePreview:
        items: Dict[str, DeletePreviewItem] = {}
        total_size_mb = 0.0
        auto_selected_count = 0
        manual_selected_count = 0
        excluded = excluded_folder_ids or set()
        for cluster_id, keeper_id in decisions.items():
            if not keeper_id:
                continue
            cluster = clusters.get(cluster_id)
            if cluster is None or keeper_id not in cluster.folder_ids:
                continue
            keeper_album = albums[keeper_id]
            selection_source = (resolution_states or {}).get(cluster_id, cluster.resolution_state)
            for folder_id in cluster.folder_ids:
                if folder_id == keeper_id or folder_id in excluded:
                    continue
                album = albums[folder_id]
                preview_item = DeletePreviewItem(
                    folder_id=folder_id,
                    folder_path=album.path,
                    folder_name=album.name,
                    keeper_folder_id=keeper_id,
                    keeper_folder_name=keeper_album.name,
                    keeper_folder_path=keeper_album.path,
                    cluster_id=cluster_id,
                    estimated_size_mb=album.total_size_mb,
                    selection_source=selection_source,
                )
                items[folder_id] = preview_item
                total_size_mb += album.total_size_mb
                if selection_source == "auto":
                    auto_selected_count += 1
                else:
                    manual_selected_count += 1
        return DeletePreview(
            items=list(items.values()),
            total_size_mb=round(total_size_mb, 2),
            auto_selected_count=auto_selected_count,
            manual_selected_count=manual_selected_count,
        )

    def build_preview_item(
        self,
        cluster: AlbumCluster,
        albums: Dict[str, AlbumSummary],
        folder_id: str,
        keeper_id: str,
        selection_source: str = "user_selected",
    ) -> DeletePreviewItem:
        album = albums[folder_id]
        keeper_album = albums[keeper_id]
        return DeletePreviewItem(
            folder_id=folder_id,
            folder_path=album.path,
            folder_name=album.name,
            keeper_folder_id=keeper_id,
            keeper_folder_name=keeper_album.name,
            keeper_folder_path=keeper_album.path,
            cluster_id=cluster.cluster_id,
            estimated_size_mb=album.total_size_mb,
            selection_source=selection_source,
        )

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
                        size_mb=item.estimated_size_mb,
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
                        size_mb=item.estimated_size_mb,
                    )
                )

        return DeleteExecution(
            moved_count=moved_count,
            failed_count=failed_count,
            total_size_mb=round(sum(result.size_mb for result in results if result.success), 2),
            results=results,
        )
