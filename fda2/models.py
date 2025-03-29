# models.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

# Using Optional[] for fields that might not be present
@dataclass
class FileInfo:
    """Represents metadata and properties of a single music file."""
    filename: str
    filepath: Path # Full path to the file
    extension: str
    size_mb: float
    file_hash: Optional[str] = None # Calculated hash (partial or full)
    duration: Optional[float] = None # In seconds
    bitrate: Optional[int] = None # In kbps
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    albumartist: Optional[str] = None
    # Store all other extracted tags for potential use (e.g., lyrics, genre)
    all_tags: Dict[str, Any] = field(default_factory=dict)
    metadata_complete: bool = False # Flag if core tags (title, artist, album) are present
    has_lyrics: bool = False # Flag if lyrics tag is present
    is_lossless: bool = False # Flag if file extension indicates lossless

@dataclass
class FolderInfo:
    """Represents aggregated information about a music folder."""
    path: Path
    folder_name: str
    parent_folder_name: str
    files: List[FileInfo] = field(default_factory=list)
    album_art_hash: Optional[str] = None # Hash of the primary album art found
    # Pre-calculated metrics for efficiency
    file_hashes_present: bool = False # True if all files have hashes
    avg_bitrate: float = 0.0
    unique_artists: Set[str] = field(default_factory=set)
    unique_albums: Set[str] = field(default_factory=set)
    # Generic name similarity scores (pre-calculated)
    generic_filename_score: float = 0.0
    generic_title_score: float = 0.0
    # Quality metrics
    hebrew_metadata_ratio: float = 0.0
    metadata_completeness_ratio: float = 0.0
    lossless_ratio: float = 0.0
    lyrics_ratio: float = 0.0
    # Overall calculated quality score
    quality_score: Optional[float] = None
    quality_breakdown: Dict[str, float] = field(default_factory=dict) # Store detailed quality scores

@dataclass
class FolderComparisonResult:
    """Stores the results of comparing two folders."""
    folder1_path: Path
    folder2_path: Path
    # Detailed similarity scores per parameter
    similarity_scores: Dict[str, float] = field(default_factory=dict)
    # Weighted overall similarity score
    weighted_score: float = 0.0
    # Flag if folders are considered identical based on file hashes
    is_identical_by_hash: bool = False
