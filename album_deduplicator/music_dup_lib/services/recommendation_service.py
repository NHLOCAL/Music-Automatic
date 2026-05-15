from __future__ import annotations

import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from .. import config
from ..models import FolderInfo
from .dto import (
    AlbumCluster,
    AlbumSummary,
    ComparisonHighlight,
    PairAnalysis,
    RecommendationReason,
    stable_id,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, preferred_root: Optional[Path] = None):
        self.preferred_root = preferred_root
        self._normalized_preferred_root = self._normalize_path(preferred_root) if preferred_root else None

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
                total_size_mb=round(sum(file.size_mb for file in folder_info.files), 2),
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
            if pair.is_identical_by_hash or config.is_review_candidate(pair.final_score)
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

            component_list = sorted(component)
            component_pairs = self._component_pairs(component, pair_lookup_by_folder_ids)
            recommended_keeper_id, keeper_reasons, reason_codes, clear_keeper = self._pick_keeper(component, albums)
            pairwise_complete = self._has_full_pairwise_coverage(component_list, component_pairs)
            all_pairs_safe = pairwise_complete and all(
                pair.is_identical_by_hash or config.is_safe_delete_candidate(pair.final_score)
                for pair in (pairs[pair_id] for pair_id in component_pairs)
            )
            keeper_covers_members = self._keeper_covers_members(component, component_pairs, pairs, recommended_keeper_id)

            if not pairwise_complete:
                reason_codes.append("pairwise_validation_incomplete")
                keeper_reasons.append(
                    RecommendationReason(
                        "pairwise_validation_incomplete",
                        "לא כל הזוגות בתוך הקבוצה אומתו ישירות, ולכן אי אפשר להציע מחיקה אוטומטית.",
                    )
                )

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
            comparison_highlights = self._build_comparison_highlights(component_list, albums)
            recommended_keeper_reason = keeper_reasons[0].message if keeper_reasons else None
            human_summary = self._build_human_summary(
                component_list=component_list,
                pairs=pairs,
                pair_ids=component_pairs,
                albums=albums,
                recommended_keeper_id=recommended_keeper_id,
                confidence_bucket=confidence_bucket,
                clear_keeper=clear_keeper,
                pairwise_complete=pairwise_complete,
            )
            clusters[cluster_id] = AlbumCluster(
                cluster_id=cluster_id,
                folder_ids=component_list,
                pair_ids=sorted(component_pairs),
                recommended_keeper_id=recommended_keeper_id,
                confidence_bucket=confidence_bucket,
                reason_codes=reason_codes,
                reasons=keeper_reasons,
                deletable_folder_ids=[
                    folder_id for folder_id in component_list if folder_id != recommended_keeper_id
                ]
                if recommended_keeper_id
                else [],
                human_summary=human_summary,
                resolution_state="auto" if confidence_bucket == "safe" and recommended_keeper_id else "skipped",
                recommended_keeper_reason=recommended_keeper_reason,
                comparison_highlights=comparison_highlights,
                technical_summary=self._build_technical_summary(component_list, component_pairs, pairs),
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

    def _has_full_pairwise_coverage(
        self,
        component_list: List[str],
        component_pairs: Set[str],
    ) -> bool:
        expected_pair_count = len(component_list) * (len(component_list) - 1) // 2
        return len(component_pairs) == expected_pair_count

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
            if not (pair.is_identical_by_hash or config.is_safe_delete_candidate(pair.final_score)):
                continue
            if pair.folder1_id == keeper_id:
                safe_neighbors.add(pair.folder2_id)
            elif pair.folder2_id == keeper_id:
                safe_neighbors.add(pair.folder1_id)
        return all(folder_id == keeper_id or folder_id in safe_neighbors for folder_id in component)

    def _is_in_preferred_root(self, folder_path: Path) -> bool:
        if not self._normalized_preferred_root:
            return False
        normalized_folder_path = self._normalize_path(folder_path)
        if normalized_folder_path == self._normalized_preferred_root:
            return True
        try:
            common_path = os.path.commonpath([normalized_folder_path, self._normalized_preferred_root])
        except ValueError:
            return False
        return common_path == self._normalized_preferred_root

    def _normalize_path(self, path: Path) -> str:
        return os.path.normcase(os.path.normpath(str(path.resolve(strict=False))))

    def _build_human_summary(
        self,
        component_list: List[str],
        pairs: Dict[str, PairAnalysis],
        pair_ids: Set[str],
        albums: Dict[str, AlbumSummary],
        recommended_keeper_id: Optional[str],
        confidence_bucket: str,
        clear_keeper: bool,
        pairwise_complete: bool,
    ) -> str:
        pair_scores = [pairs[pair_id].final_score for pair_id in pair_ids]
        min_score = min(pair_scores) if pair_scores else 0.0
        album_count = len(component_list)
        if recommended_keeper_id is None or not clear_keeper:
            return (
                f"נמצאו {album_count} אלבומים דומים, אבל אין עותק מוביל ברור ולכן נדרשת בדיקה ידנית לפני כל מחיקה."
            )

        keeper = albums[recommended_keeper_id]
        if not pairwise_complete:
            return (
                f"נמצאו {album_count} אלבומים דומים מאוד, אבל לא כל הזוגות בתוך הקבוצה אומתו ישירות. "
                f"ההמלצה הראשונית היא לשמור את \"{keeper.name}\" ולבצע סקירה ידנית."
            )

        if confidence_bucket == "safe":
            if keeper.in_preferred_root:
                return (
                    f"נמצאו {album_count} עותקים כמעט זהים. מומלץ לשמור את \"{keeper.name}\" כי הוא נמצא בתיקייה "
                    "המועדפת וכל הקשרים בקבוצה בטוחים למחיקה."
                )
            return (
                f"נמצאו {album_count} עותקים כמעט זהים. מומלץ לשמור את \"{keeper.name}\" כי הוא נראה כעותק "
                "האיכותי ביותר בקבוצה."
            )

        if config.is_review_candidate(min_score):
            return (
                f"האלבומים נראים דומים מאוד, אבל עדיין חסר ביטחון מספיק למחיקה אוטומטית. "
                f"ההמלצה הראשונית היא לשמור את \"{keeper.name}\"."
            )
        return (
            f"יש דמיון מהותי בין האלבומים, אבל המערכת לא בטוחה מספיק כדי למחוק. "
            f"הבדיקה הידנית צריכה להתמקד ב\"{keeper.name}\" כעותק מועדף ראשוני."
        )

    def _build_comparison_highlights(
        self,
        component_list: List[str],
        albums: Dict[str, AlbumSummary],
    ) -> List[ComparisonHighlight]:
        if len(component_list) < 2:
            return []

        component_albums = [albums[folder_id] for folder_id in component_list]
        highlights: List[ComparisonHighlight] = []

        def add_highlight(label: str, album_id: Optional[str], tone: str, value: Optional[str] = None) -> None:
            highlights.append(
                ComparisonHighlight(
                    id=stable_id("highlight", f"{label}|{album_id}|{value or ''}"),
                    label=label,
                    album_id=album_id,
                    tone=tone,
                    value=value,
                )
            )

        quality_candidates = [album for album in component_albums if album.quality_score is not None]
        if quality_candidates:
            best_quality = max(album.quality_score for album in quality_candidates if album.quality_score is not None)
            worst_quality = min(album.quality_score for album in quality_candidates if album.quality_score is not None)
            if best_quality > worst_quality:
                winner = next(album for album in quality_candidates if album.quality_score == best_quality)
                add_highlight("איכות גבוהה יותר", winner.folder_id, "positive", f"{best_quality:.1f}%")

        best_bitrate = max(album.avg_bitrate for album in component_albums)
        worst_bitrate = min(album.avg_bitrate for album in component_albums)
        if best_bitrate > worst_bitrate:
            winner = next(album for album in component_albums if album.avg_bitrate == best_bitrate)
            add_highlight("ביטרייט גבוה יותר", winner.folder_id, "positive", f"{round(best_bitrate)} kbps")

        if any(album.has_album_art for album in component_albums) and not all(album.has_album_art for album in component_albums):
            winner = next((album for album in component_albums if album.has_album_art), None)
            if winner:
                add_highlight("כולל עטיפת אלבום", winner.folder_id, "positive")
            for album in component_albums:
                if not album.has_album_art:
                    add_highlight("ללא עטיפה", album.folder_id, "warning")

        if any(album.in_preferred_root for album in component_albums):
            winner = next((album for album in component_albums if album.in_preferred_root), None)
            if winner:
                add_highlight("נמצא בתיקייה המועדפת", winner.folder_id, "neutral")

        best_file_count = max(album.file_count for album in component_albums)
        worst_file_count = min(album.file_count for album in component_albums)
        if best_file_count != worst_file_count:
            winner = next(album for album in component_albums if album.file_count == best_file_count)
            add_highlight("כולל יותר שירים", winner.folder_id, "positive", str(best_file_count))

        best_lossless = max(album.lossless_ratio for album in component_albums)
        if best_lossless > 0:
            winner = next(album for album in component_albums if album.lossless_ratio == best_lossless)
            add_highlight("יחס lossless גבוה יותר", winner.folder_id, "positive", f"{best_lossless:.0%}")

        best_lyrics = max(album.lyrics_ratio for album in component_albums)
        if best_lyrics > 0:
            winner = next(album for album in component_albums if album.lyrics_ratio == best_lyrics)
            add_highlight("יותר קבצים עם מילים", winner.folder_id, "neutral", f"{best_lyrics:.0%}")

        return highlights

    def _build_technical_summary(
        self,
        component_list: List[str],
        pair_ids: Set[str],
        pairs: Dict[str, PairAnalysis],
    ) -> str:
        if not pair_ids:
            return "אין פירוט טכני זמין."
        pair_values = [pairs[pair_id] for pair_id in pair_ids]
        min_score = min(pair.final_score for pair in pair_values)
        identical_count = sum(1 for pair in pair_values if pair.is_identical_by_hash)
        summary = (
            f"{len(pair_values)} זוגות הושוו. הציון הנמוך ביותר בקבוצה הוא {min_score:.1f}%. "
            f"{identical_count} זוגות זוהו כזהים לחלוטין לפי hash."
        )
        expected_pair_count = len(component_list) * (len(component_list) - 1) // 2
        missing_pair_count = expected_pair_count - len(pair_values)
        if missing_pair_count > 0:
            missing_pairs_text = (
                "חסר עוד זוג אחד"
                if missing_pair_count == 1
                else f"חסרים עוד {missing_pair_count} זוגות"
            )
            summary += f" {missing_pairs_text} כדי לאמת pairwise מלא לכל חברי הקבוצה."
        return summary
