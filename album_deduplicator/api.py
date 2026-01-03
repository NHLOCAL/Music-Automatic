"""
FastAPI service exposing album deduplication workflows for the new React UI.
"""
from __future__ import annotations

import logging
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from music_dup_lib import config, utils
from music_dup_lib.core.action_handler import ActionHandler
from music_dup_lib.core.comparison_engine import ComparisonEngine
from music_dup_lib.core.data_store import DataStore
from music_dup_lib.core.file_processor import FileProcessor
from music_dup_lib.core.folder_scanner import FolderScanner
from music_dup_lib.core.quality_analyzer import QualityAnalyzer
from music_dup_lib.models import FolderComparisonResult, FolderInfo
from music_dup_lib.external.ml_similarity_model import MLSimilarityModel

try:
    from music_dup_lib.external.gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY

    GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
except Exception:  # pragma: no cover - defensive import for environments without Gemini
    GeminiAnalyzer = None
    GEMINI_AVAILABLE = False
    GEMINI_API_KEY = None

logger = logging.getLogger(__name__)
app = FastAPI(title="Album Deduplicator API", version="1.0.0")


@lru_cache(maxsize=1)
def _cached_ml_model() -> MLSimilarityModel:
    """Load the ML model once per process to avoid noisy errors and reloads."""
    return MLSimilarityModel()


class ScanRequest(BaseModel):
    folders: List[str] = Field(..., description="Folders to scan for albums")
    force_rescan: bool = False
    clear_comparison_cache: bool = False
    enable_hashing: bool = True
    ml_scoring: bool = False
    gemini_enabled: bool = False
    preferred_bitrate: str = Field("high", description="Quality analyzer preference")


class JobStatus(BaseModel):
    id: str
    status: str
    progress: float
    message: str
    errors: List[str]


class FolderPayload(BaseModel):
    path: str
    track_count: int
    quality_score: Optional[float]
    quality_breakdown: Dict[str, float]
    avg_bitrate: Optional[float]


class ComparisonPayload(BaseModel):
    folder1: str
    folder2: str
    weighted_score: float
    ml_similarity_score: Optional[float]
    final_combined_score: Optional[float]
    is_identical_by_hash: bool
    gemini_verdict: Optional[str]
    gemini_similarity_score: Optional[float]
    gemini_reason: Optional[str]
    gemini_error: Optional[str]


class ScanResult(BaseModel):
    folders: List[FolderPayload]
    comparisons: List[ComparisonPayload]


class ActionRequest(BaseModel):
    job_id: str
    pairs: List[List[str]] = Field(..., description="Pairs of folder paths to act on")
    action: str = Field("merge", description="Action to take (currently only 'merge')")


class ActionResponse(BaseModel):
    job_id: str
    action: str
    processed: int


class FeatureFlags(BaseModel):
    gemini_available: bool
    ml_available: bool


class _JobRecord:
    def __init__(self, request: ScanRequest):
        self.request = request
        self.id = str(uuid.uuid4())
        self.status = "queued"
        self.progress = 0.0
        self.message = "Waiting to start"
        self.errors: List[str] = []
        self.result: Optional[ScanResult] = None
        self.folders: Dict[str, FolderInfo] = {}
        self.comparisons: List[FolderComparisonResult] = []


class _AlbumDeduplicationService:
    def __init__(self):
        self.jobs: Dict[str, _JobRecord] = {}

    def start_job(self, request: ScanRequest, background: BackgroundTasks) -> JobStatus:
        job = _JobRecord(request)
        self.jobs[job.id] = job
        background.add_task(self._execute_job, job)
        return self._status(job)

    def get_job(self, job_id: str) -> _JobRecord:
        if job_id not in self.jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return self.jobs[job_id]

    def _status(self, job: _JobRecord) -> JobStatus:
        return JobStatus(
            id=job.id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            errors=job.errors,
        )

    def _execute_job(self, job: _JobRecord):
        try:
            job.status = "running"
            job.message = "Scanning folders"
            utils.setup_logging(config.DEFAULT_LOG_LEVEL, config.LOGS_DIR)
            data_store = DataStore(
                music_cache_file=config.MUSIC_DATA_CACHE_FILE,
                comparison_cache_file=config.COMPARISON_RESULTS_CACHE_FILE,
            )
            file_processor = FileProcessor(enable_hashing=job.request.enable_hashing)
            folder_scanner = FolderScanner(file_processor, data_store, force_rescan=job.request.force_rescan)
            comparison_engine = ComparisonEngine(enable_hashing=job.request.enable_hashing)
            quality_analyzer = QualityAnalyzer(preferred_bitrate=job.request.preferred_bitrate)

            root_paths = [Path(path) for path in job.request.folders]
            all_scanned_folders = folder_scanner.scan_folders(root_paths)
            job.progress = 0.25

            for folder in all_scanned_folders.values():
                quality_analyzer.calculate_quality(folder)
            job.progress = 0.4

            comparison_results = comparison_engine.find_similar_folders(all_scanned_folders)
            job.progress = 0.6

            job.folders = {str(path): folder for path, folder in all_scanned_folders.items()}
            job.comparisons = comparison_results

            cached_comparison_results_map = data_store.load_comparison_results()

            ml_model = None
            if job.request.ml_scoring:
                ml_model = _cached_ml_model()
                if not ml_model.model_loaded:
                    detail = ml_model.load_error or "ML model requested but failed to load; continuing without ML scores"
                    job.errors.append(detail)
                    ml_model = None

            if ml_model:
                for result in comparison_results:
                    cache_key = frozenset({str(result.folder1_path), str(result.folder2_path)})
                    cached_result = cached_comparison_results_map.get(cache_key)
                    if cached_result and cached_result.ml_similarity_score is not None:
                        result.ml_similarity_score = cached_result.ml_similarity_score
                        continue
                    f1 = all_scanned_folders.get(result.folder1_path)
                    f2 = all_scanned_folders.get(result.folder2_path)
                    if f1 and f2:
                        ml_score = ml_model.predict_similarity_for_pair(f1, f2, result)
                        result.ml_similarity_score = ml_score
            job.progress = 0.75

            if job.request.gemini_enabled:
                if not GEMINI_AVAILABLE or not GeminiAnalyzer:
                    job.errors.append("Gemini was requested but is unavailable in this environment")
                else:
                    gemini_analyzer = GeminiAnalyzer()
                    total_pairs = len(comparison_results)
                    for idx, result in enumerate(comparison_results):
                        cache_key = frozenset({str(result.folder1_path), str(result.folder2_path)})
                        cached_result = cached_comparison_results_map.get(cache_key)
                        if cached_result and cached_result.gemini_verdict:
                            result.gemini_verdict = cached_result.gemini_verdict
                            result.gemini_similarity_score = cached_result.gemini_similarity_score
                            result.gemini_reason = cached_result.gemini_reason
                            result.gemini_error = cached_result.gemini_error
                        else:
                            basis_score = result.ml_similarity_score if result.ml_similarity_score is not None else None
                            verdict, sim_score, reason_or_error = gemini_analyzer.analyze_pair(
                                all_scanned_folders.get(result.folder1_path),
                                all_scanned_folders.get(result.folder2_path),
                                basis_score,
                            )
                            result.gemini_verdict = verdict
                            result.gemini_similarity_score = sim_score
                            if verdict:
                                result.gemini_reason = reason_or_error
                            else:
                                result.gemini_error = reason_or_error
                        if total_pairs:
                            job.progress = 0.75 + 0.2 * ((idx + 1) / total_pairs)
                        time.sleep(config.GEMINI_API_DELAY_SECONDS)

            data_store.save_data({str(path): folder.to_dict() for path, folder in all_scanned_folders.items()})
            data_store.save_comparison_results(comparison_results)

            job.result = ScanResult(
                folders=[
                    FolderPayload(
                        path=str(folder.path),
                        track_count=len(folder.files),
                        quality_score=folder.quality_score,
                        quality_breakdown=folder.quality_breakdown or {},
                        avg_bitrate=folder.avg_bitrate,
                    )
                    for folder in all_scanned_folders.values()
                ],
                comparisons=[
                    ComparisonPayload(
                        folder1=str(res.folder1_path),
                        folder2=str(res.folder2_path),
                        weighted_score=res.weighted_score,
                        ml_similarity_score=res.ml_similarity_score,
                        final_combined_score=res.final_combined_score,
                        is_identical_by_hash=res.is_identical_by_hash,
                        gemini_verdict=res.gemini_verdict,
                        gemini_similarity_score=res.gemini_similarity_score,
                        gemini_reason=res.gemini_reason,
                        gemini_error=res.gemini_error,
                    )
                    for res in comparison_results
                    if res.weighted_score >= config.MINIMAL_DISPLAY_SIMILARITY
                ],
            )
            job.status = "completed"
            job.message = "Scan complete"
            job.progress = 1.0
        except Exception as exc:  # pragma: no cover - runtime safeguard
            logger.exception("Scan job failed")
            job.status = "failed"
            job.message = "Scan failed"
            job.errors.append(str(exc))
            job.progress = 1.0

    def action(self, request: ActionRequest) -> ActionResponse:
        job = self.get_job(request.job_id)
        if job.status != "completed" or not job.result:
            raise HTTPException(status_code=400, detail="Job not complete")
        if request.action != "merge":
            raise HTTPException(status_code=400, detail="Unsupported action")
        if not job.folders:
            raise HTTPException(status_code=400, detail="Folder data missing for this job")

        folder_map = {Path(path): info for path, info in job.folders.items()}
        comparison_map = {(str(c.folder1_path), str(c.folder2_path)): c for c in job.comparisons}

        pairs_to_merge: List[FolderComparisonResult] = []
        for folder1, folder2 in request.pairs:
            lookup = comparison_map.get((folder1, folder2)) or comparison_map.get((folder2, folder1))
            if lookup:
                pairs_to_merge.append(lookup)

        processed = 0
        if pairs_to_merge:
            file_processor = FileProcessor(enable_hashing=True)
            action_handler = ActionHandler(all_folders_data=folder_map, file_processor=file_processor)
            action_handler.merge_similar_folders(pairs_to_merge)
            processed = len(pairs_to_merge)

        return ActionResponse(job_id=request.job_id, action=request.action, processed=processed)


def get_feature_flags() -> FeatureFlags:
    ml_model = _cached_ml_model()
    return FeatureFlags(gemini_available=GEMINI_AVAILABLE, ml_available=ml_model.model_loaded)


service = _AlbumDeduplicationService()


@app.get("/api/features", response_model=FeatureFlags)
def features():
    return get_feature_flags()


@app.post("/api/scan", response_model=JobStatus)
def scan(request: ScanRequest, background_tasks: BackgroundTasks):
    return service.start_job(request, background_tasks)


@app.get("/api/scan/{job_id}", response_model=JobStatus)
def scan_status(job_id: str):
    job = service.get_job(job_id)
    return service._status(job)


@app.get("/api/scan/{job_id}/results", response_model=ScanResult)
def scan_results(job_id: str):
    job = service.get_job(job_id)
    if job.status != "completed" or not job.result:
        raise HTTPException(status_code=400, detail="Results not available")
    return job.result


@app.post("/api/actions", response_model=ActionResponse)
def execute_action(request: ActionRequest):
    return service.action(request)
