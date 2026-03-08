from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .. import config
from ..core.comparison_engine import ComparisonEngine
from ..core.data_store import DataStore
from ..core.file_processor import FileProcessor
from ..core.folder_scanner import FolderScanner
from ..models import FolderInfo
from .dto import AnalysisCounts, AnalysisSnapshot
from .recommendation_service import RecommendationService
from .scoring_service import ScoringService

logger = logging.getLogger(__name__)


@dataclass
class AnalysisOptions:
    folders: List[Path]
    preferred_root: Optional[Path] = None
    bitrate_mode: str = "128"
    force_rescan: bool = False
    clear_cache: bool = False
    gemini_enabled: bool = False
    disable_hash: bool = False
    full_hash_scan: bool = False


@dataclass
class AnalysisProgressEvent:
    step: str
    stage: str
    message: str
    human_message: str
    current: int
    total: int


ProgressHandler = Callable[[AnalysisProgressEvent], None]


class AnalysisOrchestrator:
    def __init__(self, data_store: Optional[DataStore] = None):
        self.data_store = data_store or DataStore(
            music_cache_file=config.MUSIC_DATA_CACHE_FILE,
            comparison_cache_file=config.COMPARISON_RESULTS_CACHE_FILE,
        )

    def run(self, options: AnalysisOptions, progress_handler: Optional[ProgressHandler] = None) -> AnalysisSnapshot:
        self._emit(progress_handler, "setup", "מכין ניתוח", 0, 1)
        if options.clear_cache and config.COMPARISON_RESULTS_CACHE_FILE.exists():
            config.COMPARISON_RESULTS_CACHE_FILE.unlink()

        hash_strategy = self._hash_strategy_for_options(options)
        file_processor = FileProcessor(
            enable_hashing=not options.disable_hash,
            full_hash_scan=options.full_hash_scan,
        )
        folder_scanner = FolderScanner(
            file_processor=file_processor,
            data_store=self.data_store,
            force_rescan=options.force_rescan,
        )
        comparison_engine = ComparisonEngine(enable_hashing=not options.disable_hash)

        self._emit(progress_handler, "scan", "סורק תיקיות", 0, len(options.folders) or 1)
        scanned_folders = folder_scanner.scan_folders(options.folders)
        self._emit(progress_handler, "scan", "סריקה הושלמה", len(options.folders) or 1, len(options.folders) or 1)

        comparison_results = comparison_engine.find_similar_folders(scanned_folders)
        cached_results_map = {}
        if not options.force_rescan and not options.clear_cache:
            cached_results_map = self.data_store.load_comparison_results(cache_profile=hash_strategy)

        scoring_service = ScoringService(
            preferred_bitrate=options.bitrate_mode,
            use_gemini=options.gemini_enabled,
        )
        pair_analyses, warnings = scoring_service.apply_scores(
            comparison_results=comparison_results,
            all_folders=scanned_folders,
            cached_results_map=cached_results_map,
            progress_callback=lambda step, message, current, total: self._emit(
                progress_handler, step, message, current, total
            ),
        )

        if comparison_results:
            self.data_store.save_comparison_results(comparison_results, cache_profile=hash_strategy)

        recommendation_service = RecommendationService(preferred_root=options.preferred_root)
        album_summaries = recommendation_service.build_album_summaries(scanned_folders)
        clusters = recommendation_service.build_clusters(
            folders=scanned_folders,
            pairs=pair_analyses,
            albums=album_summaries,
        )

        safe_clusters = sum(1 for cluster in clusters.values() if cluster.confidence_bucket == "safe")
        review_clusters = sum(1 for cluster in clusters.values() if cluster.confidence_bucket == "review")

        snapshot = AnalysisSnapshot(
            folders=scanned_folders,
            albums=album_summaries,
            pairs=pair_analyses,
            clusters=clusters,
            counts=AnalysisCounts(
                folders=len(scanned_folders),
                compared_pairs=len(pair_analyses),
                safe_clusters=safe_clusters,
                review_clusters=review_clusters,
            ),
            warnings=warnings,
        )
        self._emit(progress_handler, "complete", "הניתוח הושלם", 1, 1)
        return snapshot

    def _hash_strategy_for_options(self, options: AnalysisOptions) -> str:
        if options.disable_hash:
            return "none"
        if options.full_hash_scan:
            return "full"
        return "partial"

    def _emit(
        self,
        progress_handler: Optional[ProgressHandler],
        step: str,
        message: str,
        current: int,
        total: int,
    ) -> None:
        if progress_handler is None:
            return
        progress_handler(
            AnalysisProgressEvent(
                step=step,
                stage=self._stage_for_step(step),
                message=message,
                human_message=self._human_message_for_step(step, message),
                current=current,
                total=total,
            )
        )

    def _stage_for_step(self, step: str) -> str:
        mapping = {
            "setup": "setup",
            "scan": "scan",
            "quality": "quality",
            "scoring": "compare",
            "complete": "complete",
        }
        return mapping.get(step, step)

    def _human_message_for_step(self, step: str, fallback: str) -> str:
        messages = {
            "setup": "מכין את סביבת העבודה וההגדרות לפני תחילת הסריקה.",
            "scan": "סורק תיקיות ומזהה אלבומים שאפשר להשוות.",
            "quality": "מחשב איכות, עטיפות ונתוני שמע כדי להבין איזה עותק עדיף לשמור.",
            "scoring": "משווה בין האלבומים ובודק אם מדובר בכפילויות בטוחות או במקרים גבוליים.",
            "complete": "הניתוח הסתיים. אפשר להתחיל לעבור על הקבוצות הבטוחות והקבוצות שדורשות סקירה.",
        }
        return messages.get(step, fallback)
