from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

from .. import config
from ..core.quality_analyzer import QualityAnalyzer
from ..external.ml_similarity_model import MLSimilarityModel
from ..models import FolderComparisonResult, FolderInfo
from .dto import AnalysisWarnings, PairAnalysis, stable_id

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, int, int], None]
CacheResultCallback = Callable[[FolderComparisonResult], None]

if TYPE_CHECKING:
    from ..external.gemini_analyzer import GeminiAnalyzer as GeminiAnalyzerType
else:
    GeminiAnalyzerType = Any

try:
    from ..external.gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY

    GEMINI_RUNTIME_AVAILABLE = bool(GEMINI_API_KEY)
except ImportError:
    GeminiAnalyzer = None
    GEMINI_RUNTIME_AVAILABLE = False


class ScoringService:
    def __init__(self, preferred_bitrate: str = "128", use_gemini: bool = False):
        self.preferred_bitrate = preferred_bitrate
        self.use_gemini = use_gemini
        self.quality_analyzer = QualityAnalyzer(preferred_bitrate=preferred_bitrate)
        self.ml_model = MLSimilarityModel()

    def apply_scores(
        self,
        comparison_results: List[FolderComparisonResult],
        all_folders: Dict[Path, FolderInfo],
        cached_results_map: Dict[FrozenSet[str], FolderComparisonResult],
        progress_callback: Optional[ProgressCallback] = None,
        cache_result_callback: Optional[CacheResultCallback] = None,
    ) -> tuple[Dict[str, PairAnalysis], AnalysisWarnings]:
        warnings = AnalysisWarnings()
        self._calculate_quality_scores(comparison_results, all_folders, progress_callback)

        if not self.ml_model.model_loaded:
            warnings.ml_unavailable = True
            warnings.warnings.append(
                "מודל החיזוי המקומי לא זמין כרגע. המערכת עדיין שמישה, אבל תמליץ בזהירות גבוהה יותר."
            )

        gemini_analyzer = None
        if self.use_gemini:
            if GEMINI_RUNTIME_AVAILABLE and GeminiAnalyzer is not None:
                try:
                    gemini_analyzer = GeminiAnalyzer()
                except Exception as exc:
                    warnings.gemini_unavailable = True
                    warnings.warnings.append(
                        f"אימות Gemini לזוגות גבוליים לא זמין כרגע. התוצאות עדיין מוצגות, אבל בלי חוות דעת חיצונית. ({exc})"
                    )
                    logger.warning("Gemini initialization failed: %s", exc, exc_info=True)
            else:
                warnings.gemini_unavailable = True
                warnings.warnings.append(
                    "Gemini לא זמין. זוגות גבוליים עדיין יוצגו, אבל ההחלטה תתבסס רק על scoring פנימי."
                )

        total_pairs = len(comparison_results)
        pairs: Dict[str, PairAnalysis] = {}

        for chunk_start in range(0, total_pairs, self.ml_model.prediction_batch_size):
            chunk = comparison_results[chunk_start:chunk_start + self.ml_model.prediction_batch_size]
            self._populate_ml_scores_for_chunk(
                chunk_results=chunk,
                all_folders=all_folders,
                cached_results_map=cached_results_map,
            )

            for chunk_index, result in enumerate(chunk):
                offset = chunk_start + chunk_index + 1
                if progress_callback:
                    progress_callback("scoring", "מחשב ציוני דמיון", offset, total_pairs)

                cache_key = frozenset({str(result.folder1_path), str(result.folder2_path)})
                cached_result = cached_results_map.get(cache_key)
                folder1_info = all_folders.get(result.folder1_path)
                folder2_info = all_folders.get(result.folder2_path)
                if not folder1_info or not folder2_info:
                    continue

                algorithmic_score = float(result.weighted_score)
                ml_score = None if result.is_identical_by_hash else result.ml_similarity_score
                base_score = algorithmic_score
                reason_codes: List[str] = []

                if ml_score is not None:
                    base_score = (
                        algorithmic_score * config.BASE_SCORE_ALGORITHMIC_WEIGHT
                        + ml_score * config.BASE_SCORE_ML_WEIGHT
                    )
                    reason_codes.append("ml_blended")
                else:
                    reason_codes.append("algorithmic_only")

                gemini_score = None
                gemini_verdict = None
                gemini_reason = None
                gemini_error = None
                if self._should_run_gemini(base_score, result.is_identical_by_hash):
                    gemini_verdict, gemini_score, gemini_reason, gemini_error = self._resolve_gemini(
                        result=result,
                        cached_result=cached_result,
                        folder1_info=folder1_info,
                        folder2_info=folder2_info,
                        gemini_analyzer=gemini_analyzer,
                        base_score=base_score,
                    )
                    if gemini_score is not None:
                        reason_codes.append("gemini_reviewed")
                    elif gemini_error:
                        reason_codes.append("gemini_unavailable")

                final_score = base_score
                if gemini_score is not None:
                    final_score = (
                        base_score * config.FINAL_SCORE_BASE_WEIGHT
                        + gemini_score * config.FINAL_SCORE_GEMINI_WEIGHT
                    )

                if result.is_identical_by_hash:
                    reason_codes.append("identical_by_hash")
                elif config.is_safe_delete_candidate(final_score):
                    reason_codes.append("safe_threshold")
                elif config.is_review_candidate(final_score):
                    reason_codes.append("review_threshold")

                if self._should_cache_result(result, final_score):
                    cache_entry = self._build_cache_entry(result)
                    if cache_result_callback is not None:
                        cache_result_callback(cache_entry)

                if self._should_retain_pair(result, final_score):
                    folder_ids_sorted = sorted(
                        [
                            stable_id("folder", str(result.folder1_path)),
                            stable_id("folder", str(result.folder2_path)),
                        ]
                    )
                    pair_id = stable_id("pair", "|".join(folder_ids_sorted))
                    pairs[pair_id] = PairAnalysis(
                        pair_id=pair_id,
                        folder1_id=stable_id("folder", str(result.folder1_path)),
                        folder2_id=stable_id("folder", str(result.folder2_path)),
                        folder1_path=result.folder1_path,
                        folder2_path=result.folder2_path,
                        algorithmic_score=round(algorithmic_score, 4),
                        ml_score=round(ml_score, 4) if ml_score is not None else None,
                        base_score=round(base_score, 4),
                        gemini_score=round(gemini_score, 4) if gemini_score is not None else None,
                        final_score=round(final_score, 4),
                        gemini_verdict=gemini_verdict,
                        gemini_reason=gemini_reason,
                        gemini_error=gemini_error,
                        is_identical_by_hash=result.is_identical_by_hash,
                        similarity_scores=self._compact_similarity_scores(result.similarity_scores),
                        reason_codes=reason_codes,
                    )

                self._release_processed_result(result)
                comparison_results[offset - 1] = None  # type: ignore[list-item]

        return pairs, warnings

    def _should_retain_pair(self, result: FolderComparisonResult, final_score: float) -> bool:
        return result.is_identical_by_hash or config.is_review_candidate(final_score)

    def _should_cache_result(self, result: FolderComparisonResult, final_score: float) -> bool:
        return result.is_identical_by_hash or final_score >= config.MIN_SCORE_FOR_CACHING

    def _compact_similarity_scores(self, similarity_scores: Dict[str, Any]) -> Dict[str, Any]:
        compact: Dict[str, Any] = {}
        for key, value in similarity_scores.items():
            if key == "additional_metadata_details":
                if isinstance(value, dict):
                    details = {
                        meta_key: round(float(meta_value), 4)
                        for meta_key, meta_value in value.items()
                        if isinstance(meta_value, (float, int)) and meta_value > 0
                    }
                    if details:
                        compact[key] = details
                continue
            if isinstance(value, (float, int)):
                if value > 0:
                    compact[key] = round(float(value), 4)
                continue
            if value:
                compact[key] = value
        return compact

    def _build_cache_entry(self, result: FolderComparisonResult) -> FolderComparisonResult:
        return FolderComparisonResult(
            folder1_path=result.folder1_path,
            folder2_path=result.folder2_path,
            similarity_scores={},
            weighted_score=result.weighted_score,
            is_identical_by_hash=result.is_identical_by_hash,
            gemini_verdict=result.gemini_verdict,
            gemini_similarity_score=result.gemini_similarity_score,
            gemini_reason=result.gemini_reason,
            gemini_error=result.gemini_error,
            ml_similarity_score=result.ml_similarity_score,
            final_combined_score=result.final_combined_score,
        )

    def _release_processed_result(self, result: FolderComparisonResult) -> None:
        result.similarity_scores = {}

    def _populate_ml_scores_for_chunk(
        self,
        chunk_results: Sequence[FolderComparisonResult],
        all_folders: Dict[Path, FolderInfo],
        cached_results_map: Dict[FrozenSet[str], FolderComparisonResult],
    ) -> None:
        if not self.ml_model.model_loaded:
            return

        prediction_inputs: List[Tuple[FolderInfo, FolderInfo, FolderComparisonResult]] = []
        prediction_targets: List[FolderComparisonResult] = []

        for result in chunk_results:
            if result.is_identical_by_hash:
                result.ml_similarity_score = None
                continue

            cache_key = frozenset({str(result.folder1_path), str(result.folder2_path)})
            cached_result = cached_results_map.get(cache_key)
            cached_ml_score = getattr(cached_result, "ml_similarity_score", None) if cached_result else None
            if cached_ml_score is not None:
                result.ml_similarity_score = float(cached_ml_score)
                continue

            folder1_info = all_folders.get(result.folder1_path)
            folder2_info = all_folders.get(result.folder2_path)
            if not folder1_info or not folder2_info:
                continue

            prediction_inputs.append((folder1_info, folder2_info, result))
            prediction_targets.append(result)

        if not prediction_inputs:
            return

        predicted_scores = self.ml_model.predict_similarities_for_pairs(prediction_inputs)
        for result, predicted_score in zip(prediction_targets, predicted_scores):
            if predicted_score is not None:
                result.ml_similarity_score = predicted_score

    def _calculate_quality_scores(
        self,
        comparison_results: List[FolderComparisonResult],
        all_folders: Dict[Path, FolderInfo],
        progress_callback: Optional[ProgressCallback],
    ) -> None:
        folders_for_quality = {
            path
            for result in comparison_results
            for path in (result.folder1_path, result.folder2_path)
            if path in all_folders
        }
        total = len(folders_for_quality)
        for index, folder_path in enumerate(sorted(folders_for_quality), start=1):
            if progress_callback:
                progress_callback("quality", "מחשב איכות אלבומים", index, total)
            self.quality_analyzer.calculate_quality(all_folders[folder_path])

    def _should_run_gemini(self, base_score: float, is_identical_by_hash: bool) -> bool:
        return (
            self.use_gemini
            and not is_identical_by_hash
            and config.is_gemini_review_candidate(base_score)
        )

    def _resolve_gemini(
        self,
        result: FolderComparisonResult,
        cached_result: Optional[FolderComparisonResult],
        folder1_info: FolderInfo,
        folder2_info: FolderInfo,
        gemini_analyzer: Optional[GeminiAnalyzerType],
        base_score: float,
    ) -> tuple[Optional[str], Optional[float], Optional[str], Optional[str]]:
        if cached_result:
            cached_verdict = getattr(cached_result, "gemini_verdict", None)
            cached_score = getattr(cached_result, "gemini_similarity_score", None)
            cached_reason = getattr(cached_result, "gemini_reason", None)
            cached_error = getattr(cached_result, "gemini_error", None)
            if cached_verdict is not None and cached_error is None:
                result.gemini_verdict = cached_verdict
                result.gemini_similarity_score = cached_score
                result.gemini_reason = cached_reason
                result.gemini_error = None
                return cached_verdict, cached_score, cached_reason, None

        if gemini_analyzer is None:
            return None, None, None, "Gemini unavailable"

        verdict, gemini_score, reason = gemini_analyzer.analyze_pair(
            folder1_info,
            folder2_info,
            base_score,
        )
        result.gemini_verdict = verdict
        result.gemini_similarity_score = gemini_score
        if reason and ("API_ERROR" in reason or "PARSE_ERROR" in reason or "UNEXPECTED_PARSE_ERROR" in reason):
            result.gemini_error = reason
            return verdict, gemini_score, None, reason
        result.gemini_reason = reason
        result.gemini_error = None
        return verdict, gemini_score, reason, None
