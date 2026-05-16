from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

@dataclass(slots=True)
class FileInfo:

    filename: str
    filepath: Path
    extension: str
    size_mb: float
    file_hash: Optional[str] = None
    duration: Optional[float] = None
    bitrate: Optional[int] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    albumartist: Optional[str] = None

    all_tags: Dict[str, Any] = field(default_factory=dict)
    metadata_complete: bool = False
    has_lyrics: bool = False
    is_lossless: bool = False

@dataclass(slots=True)
class FolderInfo:

    path: Path
    folder_name: str
    parent_folder_name: str
    files: List[FileInfo] = field(default_factory=list)
    album_art_hash: Optional[str] = None
    other_files: List[Dict[str, Any]] = field(default_factory=list) 

    file_hashes_present: bool = False
    avg_bitrate: float = 0.0
    unique_artists: Set[str] = field(default_factory=set)
    unique_albums: Set[str] = field(default_factory=set)

    generic_filename_score: float = 0.0
    generic_title_score: float = 0.0

    hebrew_metadata_ratio: float = 0.0
    metadata_completeness_ratio: float = 0.0
    lossless_ratio: float = 0.0
    lyrics_ratio: float = 0.0

    quality_score: Optional[float] = None
    quality_breakdown: Dict[str, float] = field(default_factory=dict)

@dataclass(slots=True)
class FolderComparisonResult:
    folder1_path: Path
    folder2_path: Path

    similarity_scores: Dict[str, Any] = field(default_factory=dict) # Changed from Dict[str, float] to Dict[str, Any]
    weighted_score: float = 0.0
    is_identical_by_hash: bool = False

    gemini_verdict: Optional[str] = None
    gemini_similarity_score: Optional[float] = None
    gemini_reason: Optional[str] = None
    gemini_error: Optional[str] = None

    ml_similarity_score: Optional[float] = None
    final_combined_score: Optional[float] = None
