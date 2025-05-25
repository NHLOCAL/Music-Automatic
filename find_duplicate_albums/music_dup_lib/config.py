import logging
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

MUSIC_DATA_CACHE_FILE = DATA_DIR / "music_data.json"
COMPARISON_RESULTS_CACHE_FILE = DATA_DIR / "comparison_results_cache.json"
ARTIST_CSV_FILE = DATA_DIR / "singer-list.csv"

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

    'additional_metadata_field_weight': 0.2
}


GEMINI_SCORE_WEIGHT = 0.7
ALGORITHMIC_SCORE_WEIGHT = 0.3


QUALITY_WEIGHTS = {
    'hebrew_metadata': 2.0,
    'metadata_completeness': 2.0,
    'has_album_art': 1.0,
    'bitrate_score': 2.0,
    'non_repetitive_names': 1.0,
    'consistent_artist': 1.5,
    'consistent_album': 1.5,
    'lossless_format': 2.0,
    'has_lyrics': 1.0
}

HIGH_BITRATE_TARGET = 320
MID_BITRATE_TARGET = 128
BITRATE_SCORE_TOLERANCE = 192

MIN_SIMILARITY_FOR_MERGE = 80.0

DEFAULT_MIN_SIMILARITY_FOR_DELETE = 85.0

DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

MAX_WORKERS = None
LRU_CACHE_SIZE = 10000

JIBRISH_FIX_LANGUAGE = "heb"

GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
GEMINI_SYSTEM_INST_FILE = Path("gemini_system_instruction.txt")
GEMINI_MODEL_NAME = "gemini-2.5-flash-preview-05-20" # "gemini-2.5-flash-lite"
DEFAULT_GEMINI_SIMILARITY_RANGE = "50-90"
GEMINI_API_DELAY_SECONDS = 0.5
GEMINI_HIGH_SIMILARITY_THRESHOLD_FOR_REPRESENTATIVE = 95.0