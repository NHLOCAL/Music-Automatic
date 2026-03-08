from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from .. import config
from ..models import FolderInfo
from .dto import (
    AlbumCluster,
    AlbumSummary,
    PairAnalysis,
    RecommendationReason,
    stable_id,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, preferred_root: Optional[Path] = None):
        self.preferred_root = preferred_root

    def build_album_summaries(self, folders: Dict[Path, FolderInfo]) -> Dict[str, AlbumSummary]:
        summaries: Dict[str, AlbumSummary] = {}
        for folder_path, folder_info in folders.items():
            folder_id = stable_id("folder", str(folder_path))
            summaries[folder_id] = AlbumSummary(
                folder_id=folder_id,
                path=folder_path,
                name=folder_info.path.name,
                quality_score=folder_info.quality_score,
                avg_bitrate=folder_info.avg_bitrate,
                file_count=len(folder_info.files),
                in_preferred_root=self._is_in_preferred_root(folder_path),
                has_album_art=bool(folder_info.album_art_hash),
                lossless_ratio=folder_info.lossless_ratio,
                lyrics_ratio=folder_info.lyrics_ratio,
            )
        return summaries

    def build_clusters(
        self,
        folders: Dict[Path, FolderInfo],
        pairs: Dict[str, PairAnalysis],
        albums: Dict[str, AlbumSummary],
    ) -> Dict[str, AlbumCluster]:
        graph: Dict[str, Set[str]] = defaultdict(set)
        pair_lookup_by_folder_ids: Dict[frozenset[str], str] = {}
        eligible_pairs = [
            pair
            for pair in pairs.values()
            if pair.is_identical_by_hash or pair.final_score >= config.REVIEW_MIN_SIMILARITY
        ]
        for pair in eligible_pairs:
            graph[pair.folder1_id].add(pair.folder2_id)
            graph[pair.folder2_id].add(pair.folder1_id)
            pair_lookup_by_folder_ids[frozenset({pair.folder1_id, pair.folder2_id})] = pair.pair_id

        clusters: Dict[str, AlbumCluster] = {}
        seen: Set[str] = set()
        for folder_id in sorted(graph):
            if folder_id in seen:
                continue
            component = self._collect_component(folder_id, graph, seen)
            if len(component) < 2:
                continue

            component_pairs = self._component_pairs(component, pair_lookup_by_folder_ids)
            recommended_keeper_id, keeper_reasons, reason_codes, clear_keeper = self._pick_keeper(component, albums)
            all_pairs_safe = all(
                pair.is_identical_by_hash or pair.final_score >= config.SAFE_DELETE_MIN_SIMILARITY
                for pair in (pairs[pair_id] for pair_id in component_pairs)
            )
            keeper_covers_members = self._keeper_covers_members(component, component_pairs, pairs, recommended_keeper_id)

            confidence_bucket = "review"
            if clear_keeper and recommended_keeper_id and all_pairs_safe and keeper_covers_members:
                confidence_bucket = "safe"
                reason_codes.append("cluster_safe")
                keeper_reasons.append(
                    RecommendationReason("cluster_safe", "כל הקשרים בקבוצה עומדים בסף המחיקה הבטוחה.")
                )
            else:
                reason_codes.append("cluster_review")
                keeper_reasons.append(
                    RecommendationReason("cluster_review", "הקבוצה דורשת סקירה לפני מחיקה.")
                )

            cluster_id = stable_id("cluster", "|".join(sorted(component)))
            clusters[cluster_id] = AlbumCluster(
                cluster_id=cluster_id,
                folder_ids=sorted(component),
                pair_ids=sorted(component_pairs),
                recommended_keeper_id=recommended_keeper_id,
                confidence_bucket=confidence_bucket,
                reason_codes=reason_codes,
                reasons=keeper_reasons,
                deletable_folder_ids=[
                    folder_id for folder_id in sorted(component) if folder_id != recommended_keeper_id
                ]
                if recommended_keeper_id
                else [],
            )

        return dict(
            sorted(
                clusters.items(),
                key=lambda item: (
                    0 if item[1].confidence_bucket == "safe" else 1,
                    min(
                        (
                            pairs[pair_id].final_score
                            for pair_id in item[1].pair_ids
                        ),
                        default=0.0,
                    ) * -1,
                ),
            )
        )

    def _collect_component(self, start_folder_id: str, graph: Dict[str, Set[str]], seen: Set[str]) -> Set[str]:
        component: Set[str] = set()
        stack = [start_folder_id]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.add(current)
            stack.extend(graph[current] - seen)
        return component

    def _component_pairs(
        self,
        component: Iterable[str],
        pair_lookup_by_folder_ids: Dict[frozenset[str], str],
    ) -> Set[str]:
        component_list = sorted(component)
        pair_ids: Set[str] = set()
        for index, folder_id in enumerate(component_list):
            for other_folder_id in component_list[index + 1 :]:
                pair_id = pair_lookup_by_folder_ids.get(frozenset({folder_id, other_folder_id}))
                if pair_id:
                    pair_ids.add(pair_id)
        return pair_ids

    def _pick_keeper(
        self,
        component: Set[str],
        albums: Dict[str, AlbumSummary],
    ) -> tuple[Optional[str], List[RecommendationReason], List[str], bool]:
        ranked: List[tuple[int, float, str, str]] = []
        reasons: List[RecommendationReason] = []
        reason_codes: List[str] = []
        for folder_id in component:
            album = albums[folder_id]
            ranked.append(
                (
                    1 if album.in_preferred_root else 0,
                    album.quality_score if album.quality_score is not None else -1.0,
                    album.path.as_posix().lower(),
                    folder_id,
                )
            )
        ranked.sort(reverse=True)
        if not ranked:
            reasons.append(RecommendationReason("no_keeper", "לא נמצא אלבום מומלץ לשמירה."))
            reason_codes.append("no_keeper")
            return None, reasons, reason_codes, False

        winner = ranked[0]
        recommended_keeper_id = winner[3]
        if len(ranked) > 1 and ranked[0][:2] == ranked[1][:2]:
            reasons.append(RecommendationReason("keeper_conflict", "אין keeper יחיד וברור על בסיס root מועדף ואיכות."))
            reason_codes.append("keeper_conflict")
            return None, reasons, reason_codes, False

        winner_album = albums[recommended_keeper_id]
        if winner_album.in_preferred_root:
            reasons.append(RecommendationReason("preferred_root_keeper", "האלבום המומלץ נמצא תחת תיקיית השורש המועדפת."))
            reason_codes.append("preferred_root_keeper")
        else:
            reasons.append(RecommendationReason("quality_keeper", "האלבום המומלץ נבחר לפי ציון האיכות הגבוה ביותר."))
            reason_codes.append("quality_keeper")
        return recommended_keeper_id, reasons, reason_codes, True

    def _keeper_covers_members(
        self,
        component: Set[str],
        component_pairs: Set[str],
        pairs: Dict[str, PairAnalysis],
        keeper_id: Optional[str],
    ) -> bool:
        if keeper_id is None:
            return False
        safe_neighbors: Set[str] = set()
        for pair_id in component_pairs:
            pair = pairs[pair_id]
            if not (pair.is_identical_by_hash or pair.final_score >= config.SAFE_DELETE_MIN_SIMILARITY):
                continue
            if pair.folder1_id == keeper_id:
                safe_neighbors.add(pair.folder2_id)
            elif pair.folder2_id == keeper_id:
                safe_neighbors.add(pair.folder1_id)
        return all(folder_id == keeper_id or folder_id in safe_neighbors for folder_id in component)

    def _is_in_preferred_root(self, folder_path: Path) -> bool:
        if not self.preferred_root:
            return False
        return folder_path == self.preferred_root or self.preferred_root in folder_path.parents

