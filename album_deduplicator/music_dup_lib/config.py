import logging
from pathlib import Path

# Path to the music_dup_lib directory itself
# e.g., /path/to/repo/album_deduplicator/music_dup_lib/
MUSIC_DUP_LIB_ROOT = Path(__file__).resolve().parent

# Path to the root of the album_deduplicator project
# e.g., /path/to/repo/album_deduplicator/
ALBUM_DEDUP_PROJECT_ROOT = MUSIC_DUP_LIB_ROOT.parent

# DATA_DIR and LOGS_DIR are now relative to the album_deduplicator project root
DATA_DIR = ALBUM_DEDUP_PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

LOGS_DIR = ALBUM_DEDUP_PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Filenames for cache files (will be combined with DATA_DIR by DataStore etc.)
MUSIC_DATA_CACHE_FILENAME = "music_data.json"
COMPARISON_RESULTS_CACHE_FILENAME = "comparison_results_cache.json"

# Actual Path objects for direct use if needed, constructed with DATA_DIR
MUSIC_DATA_CACHE_FILE = DATA_DIR / MUSIC_DATA_CACHE_FILENAME
COMPARISON_RESULTS_CACHE_FILE = DATA_DIR / COMPARISON_RESULTS_CACHE_FILENAME

ARTIST_CSV_FILENAME = "singer-list.csv"
ARTIST_CSV_FILE = DATA_DIR / ARTIST_CSV_FILENAME # Full path

ML_MODEL_FILENAME = "lgbm_regressor_model.joblib"
ML_MODEL_FILE = DATA_DIR / ML_MODEL_FILENAME # Full path

ALLOWED_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg'}
LOSSLESS_EXTENSIONS = {'.flac', '.wav'}
IGNORED_FILES = {'cover.jpg', 'folder.jpg', 'thumbs.db', 'desktop.ini',
                 'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg', 'cover.png', 'תמונה.jpg'}
ALBUM_ART_FILES = {'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg',
                   'cover.jpg', 'folder.jpg', 'cover.png', 'תמונה.jpg'}

MIN_FILES_PER_FOLDER = 3
ENABLE_HASHING = True
HASH_CHUNK_SIZE = 4096
HASH_NUM_RANDOM_CHUNKS = 2

MINIMAL_DISPLAY_SIMILARITY = 40.0
GENERIC_NAME_SIMILARITY_THRESHOLD = 0.7
GENERIC_NAME_REDUCTION_FACTOR = 0.5
BASE_STRING_SIMILARITY_THRESHOLD = 0.4

SIMILARITY_WEIGHTS = {
    'file_hash': 2.0,
    'file_size': 0.7,
    'filename': 1.4,
    'title': 1.4,
    'album': 1.0,
    'artist': 0.5,
    'albumartist': 0.5,
    'folder_name': 0.9,
    'album_art_hash': 0.8,
    'duration': 1.0,
    'other_files_similarity': 0.15,
    'additional_metadata_field_weight': 0.2 # Weight for each *individual* additional metadata field match
}

GEMINI_SCORE_WEIGHT = 0.7
ALGORITHMIC_SCORE_WEIGHT = 0.3 # Can be algo or ML score, depending on what's used as primary

QUALITY_WEIGHTS = {
    'hebrew_metadata': 2.0,
    'metadata_completeness': 2.0,
    'has_album_art': 1.0,
    'bitrate_score': 2.0,
    'non_repetitive_names': 1.0,
    'consistent_artist': 1.5,
    'consistent_album': 1.5,
    'lossless_format': 2.0, # Score based on lossless_ratio
    'has_lyrics': 1.0 # Score based on lyrics_ratio
}
HIGH_BITRATE_TARGET = 320  # kbps
MID_BITRATE_TARGET = 128   # kbps
BITRATE_SCORE_TOLERANCE = 192 # For 128kbps target, how far can it be to still get some score

MIN_SIMILARITY_FOR_MERGE = 80.0
DEFAULT_MIN_SIMILARITY_FOR_DELETE = 85.0

DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

MAX_WORKERS = None # os.cpu_count() will be used by default if None
LRU_CACHE_SIZE = 10000
JIBRISH_FIX_LANGUAGE = "heb"

# --- הגדרות Gemini ---
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY" # שם משתנה הסביבה
# קובץ ההנחיות ל-Gemini, נמצא יחסית למיקום קובץ זה, בתיקיית 'external' של music_dup_lib
GEMINI_SYSTEM_INST_FILE = MUSIC_DUP_LIB_ROOT / "external" / "gemini_system_instruction.txt"
GEMINI_MODEL_NAME = "gemini-2.5-flash-preview-05-20" # "gemini-2.5-flash-lite"
DEFAULT_GEMINI_SIMILARITY_RANGE = "40-90" # Min-Max % for sending pairs to Gemini
GEMINI_API_DELAY_SECONDS = 0.5 # Delay between API calls (seconds)
GEMINI_HIGH_SIMILARITY_THRESHOLD_FOR_REPRESENTATIVE = 95.0

# --- הגדרות עבור data_preparation.py (אם משתמשים ב-config זה כמקור) ---
# These might be used if data_preparation.py imports this config and needs these values.
# If data_preparation.py defines its own, these are just for reference or album_deduplicator's internal use.
FILTER_PAIRS_BY_FILE_COUNT_FOR_ML = True # Filter pairs if music file counts differ, for ML dataset features
FILTER_PAIRS_BY_FILE_COUNT_FOR_ML_GEMINI = True # Filter pairs for Gemini labeling if music file counts differ