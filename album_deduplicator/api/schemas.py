from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AnalysisSessionCreateRequest(BaseModel):
    folders: List[str]
    preferred_root: Optional[str] = None
    force_rescan: bool = False
    clear_cache: bool = False
    bitrate_mode: Literal["128", "high"] = "128"
    gemini_enabled: bool = False


class AnalysisSessionCreatedResponse(BaseModel):
    session_id: str
    status: Literal["queued"]


class ProgressState(BaseModel):
    step: str = "queued"
    message: str = "ממתין"
    current: int = 0
    total: int = 1
    percent: float = 0.0


class ModeSummary(BaseModel):
    ml_default_enabled: bool = True
    gemini_enabled: bool = False
    review_threshold: float
    safe_delete_threshold: float


class DegradedFlags(BaseModel):
    ml_unavailable: bool = False
    gemini_unavailable: bool = False
    warnings: List[str] = Field(default_factory=list)


class CountsResponse(BaseModel):
    folders: int = 0
    compared_pairs: int = 0
    safe_clusters: int = 0
    review_clusters: int = 0


class SessionStatusResponse(BaseModel):
    session_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: ProgressState
    mode_summary: ModeSummary
    degraded_flags: DegradedFlags
    counts: CountsResponse
    error: Optional[str] = None


class RecommendationReasonModel(BaseModel):
    code: str
    message: str


class TrackInfoModel(BaseModel):
    filename: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    duration: Optional[float] = None
    size_mb: float
    bitrate: Optional[int] = None


class FolderSummaryModel(BaseModel):
    folder_id: str
    path: str
    name: str
    quality_score: Optional[float]
    avg_bitrate: float
    file_count: int
    in_preferred_root: bool
    has_album_art: bool
    lossless_ratio: float
    lyrics_ratio: float
    tracks: List[TrackInfoModel] = Field(default_factory=list)


class PairScoreBreakdownModel(BaseModel):
    pair_id: str
    folder1_id: str
    folder2_id: str
    algorithmic_score: float
    ml_score: Optional[float]
    base_score: float
    gemini_score: Optional[float]
    final_score: float
    gemini_verdict: Optional[str]
    gemini_reason: Optional[str]
    gemini_error: Optional[str]
    is_identical_by_hash: bool
    similarity_scores: Dict[str, Any] = Field(default_factory=dict)
    reason_codes: List[str] = Field(default_factory=list)


class ClusterSummaryModel(BaseModel):
    cluster_id: str
    confidence_bucket: Literal["safe", "review"]
    recommended_keeper_id: Optional[str]
    reason_codes: List[str] = Field(default_factory=list)
    reasons: List[RecommendationReasonModel] = Field(default_factory=list)
    deletable_folder_ids: List[str] = Field(default_factory=list)
    albums: List[FolderSummaryModel] = Field(default_factory=list)
    pairs: List[PairScoreBreakdownModel] = Field(default_factory=list)


class ClusterListResponse(BaseModel):
    clusters: List[ClusterSummaryModel] = Field(default_factory=list)


class DecisionItem(BaseModel):
    cluster_id: str
    keeper_id: Optional[str] = None


class DecisionsRequest(BaseModel):
    decisions: List[DecisionItem] = Field(default_factory=list)


class DeletePreviewItemModel(BaseModel):
    folder_id: str
    folder_path: str
    folder_name: str
    keeper_folder_id: str
    keeper_folder_name: str
    keeper_folder_path: str
    cluster_id: str


class DeletePreviewResponse(BaseModel):
    items: List[DeletePreviewItemModel] = Field(default_factory=list)
    total_count: int = 0


class DeleteExecutionRequest(BaseModel):
    folder_ids: List[str] = Field(default_factory=list)


class DeleteExecutionItemModel(BaseModel):
    folder_id: str
    folder_path: str
    success: bool
    message: str


class DeleteExecutionResponse(BaseModel):
    moved_count: int
    failed_count: int
    results: List[DeleteExecutionItemModel] = Field(default_factory=list)
