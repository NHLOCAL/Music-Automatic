from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


AnalysisStatus = Literal["queued", "running", "completed", "failed"]
ConfidenceBucket = Literal["safe", "review"]
ResolutionState = Literal["auto", "user_selected", "skipped", "deleted"]
HighlightTone = Literal["positive", "negative", "neutral", "warning"]


def stable_id(prefix: str, value: str) -> str:
    digest = sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


@dataclass
class RecommendationReason:
    code: str
    message: str


@dataclass
class ComparisonHighlight:
    id: str
    label: str
    album_id: Optional[str]
    tone: HighlightTone
    value: Optional[str] = None


@dataclass
class AlbumSummary:
    folder_id: str
    path: Path
    name: str
    quality_score: Optional[float]
    avg_bitrate: float
    file_count: int
    in_preferred_root: bool
    has_album_art: bool
    lossless_ratio: float
    lyrics_ratio: float
    total_size_mb: float
    preferred_root_rank: Optional[int] = None


@dataclass
class PairAnalysis:
    pair_id: str
    folder1_id: str
    folder2_id: str
    folder1_path: Path
    folder2_path: Path
    algorithmic_score: float
    ml_score: Optional[float]
    base_score: float
    gemini_score: Optional[float]
    final_score: float
    gemini_verdict: Optional[str]
    gemini_reason: Optional[str]
    gemini_error: Optional[str]
    is_identical_by_hash: bool
    similarity_scores: Dict[str, Any] = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)


@dataclass
class AlbumCluster:
    cluster_id: str
    folder_ids: List[str]
    pair_ids: List[str]
    recommended_keeper_id: Optional[str]
    confidence_bucket: ConfidenceBucket
    reason_codes: List[str]
    reasons: List[RecommendationReason]
    deletable_folder_ids: List[str]
    human_summary: str
    resolution_state: ResolutionState = "skipped"
    recommended_keeper_reason: Optional[str] = None
    comparison_highlights: List[ComparisonHighlight] = field(default_factory=list)
    technical_summary: str = ""


@dataclass
class AnalysisWarnings:
    ml_unavailable: bool = False
    gemini_unavailable: bool = False
    warnings: List[str] = field(default_factory=list)


@dataclass
class AnalysisCounts:
    folders: int = 0
    compared_pairs: int = 0
    safe_clusters: int = 0
    review_clusters: int = 0


@dataclass
class DeletePreviewItem:
    folder_id: str
    folder_path: Path
    folder_name: str
    keeper_folder_id: str
    keeper_folder_name: str
    keeper_folder_path: Path
    cluster_id: str
    estimated_size_mb: float = 0.0
    selection_source: ResolutionState = "auto"


@dataclass
class DeletePreview:
    items: List[DeletePreviewItem] = field(default_factory=list)
    total_size_mb: float = 0.0
    auto_selected_count: int = 0
    manual_selected_count: int = 0

    @property
    def total_count(self) -> int:
        return len(self.items)


@dataclass
class DeleteExecutionItem:
    folder_id: str
    folder_path: Path
    success: bool
    message: str
    size_mb: float = 0.0


@dataclass
class DeleteExecution:
    moved_count: int
    failed_count: int
    total_size_mb: float = 0.0
    results: List[DeleteExecutionItem] = field(default_factory=list)


@dataclass
class AnalysisSnapshot:
    folders: Dict[Path, Any] = field(default_factory=dict)
    albums: Dict[str, AlbumSummary] = field(default_factory=dict)
    pairs: Dict[str, PairAnalysis] = field(default_factory=dict)
    clusters: Dict[str, AlbumCluster] = field(default_factory=dict)
    counts: AnalysisCounts = field(default_factory=AnalysisCounts)
    warnings: AnalysisWarnings = field(default_factory=AnalysisWarnings)

    def bucket_clusters(self, bucket: Literal["safe", "review", "all"]) -> List[AlbumCluster]:
        ordered = list(self.clusters.values())
        if bucket == "all":
            return ordered
        return [cluster for cluster in ordered if cluster.confidence_bucket == bucket]
