# config.py
import logging
from pathlib import Path

# --- Paths ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)  # Ensure data directory exists
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True) # Ensure logs directory exists

MUSIC_DATA_CACHE_FILE = DATA_DIR / "music_data.json"
ARTIST_CSV_FILE = DATA_DIR / "singer-list.csv"

# --- File Handling ---
ALLOWED_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg'}
LOSSLESS_EXTENSIONS = {'.flac', '.wav'}
IGNORED_FILES = {'cover.jpg', 'folder.jpg', 'thumbs.db', 'desktop.ini', 
                 'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg', 'cover.png', 'תמונה.jpg'} # Consolidate ignored/art files
ALBUM_ART_FILES = {'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg', 
                   'cover.jpg', 'folder.jpg', 'cover.png', 'תמונה.jpg'}
MIN_FILES_PER_FOLDER = 3 # Minimum music files to consider a folder an album/collection

# --- Hashing ---
ENABLE_HASHING = True # Default value, can be overridden by args
HASH_CHUNK_SIZE = 4096
HASH_NUM_RANDOM_CHUNKS = 2

# --- Comparison ---
# Minimum similarity score for a pair to be even considered/displayed
MINIMAL_DISPLAY_SIMILARITY = 50.0
# Threshold for considering names "generic" (influences file/title score adjustment)
GENERIC_NAME_SIMILARITY_THRESHOLD = 0.7
# Reduction factor applied to file/title similarity if names are deemed generic
GENERIC_NAME_REDUCTION_FACTOR = 0.5
# Base similarity threshold below which string comparisons are ignored (to avoid noise)
BASE_STRING_SIMILARITY_THRESHOLD = 0.4
# Weighting for different parameters in similarity calculation (ensure they sum reasonably, e.g., to 10 or 100)
# Note: albumartist shares weight with artist, handled in logic
SIMILARITY_WEIGHTS = {
    'file_hash': 2.2,
    'file_size': 0.7,
    'filename': 1.4, # Renamed from 'file' for clarity
    'title': 1.4,
    'album': 0.9,
    'artist': 0.5,  # Combined weight for artist/albumartist is 1.0
    'albumartist': 0.5,
    'folder_name': 0.9,
    'album_art_hash': 0.5, # Renamed from 'album_art'
    'duration': 1.0,
    # Additional metadata weight is applied per matching field found
    'additional_metadata_field_weight': 0.1 # Reduced weight per field
}

# --- Quality Assessment ---
# Weighting for different parameters in quality calculation
QUALITY_WEIGHTS = {
    'hebrew_metadata': 2.0,
    'metadata_completeness': 2.0,
    'has_album_art': 1.0,
    'bitrate_score': 2.0,
    'non_repetitive_names': 1.0, # Score based on (1 - generic_similarity)
    'consistent_artist': 1.5,
    'consistent_album': 1.5,
    'lossless_format': 2.0,
    'has_lyrics': 1.0
}
# Bitrate thresholds for quality scoring
HIGH_BITRATE_TARGET = 320 # kbps
MID_BITRATE_TARGET = 128 # kbps
BITRATE_SCORE_TOLERANCE = 192 # Denominator for distance calculation for 128kbps target

# --- Actions ---
# Minimum similarity score required to offer merging folders
MIN_SIMILARITY_FOR_MERGE = 80.0
# Default minimum similarity score required to offer deleting folders (can be overridden by user)
DEFAULT_MIN_SIMILARITY_FOR_DELETE = 85.0

# --- Logging ---
DEFAULT_LOG_LEVEL = "INFO"# Default, overridden by args
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

# --- Performance ---
MAX_WORKERS = None # Use os.cpu_count()
LRU_CACHE_SIZE = 10000

# --- Jibrish ---
JIBRISH_FIX_LANGUAGE = "heb" # Target language for fixing jibrish


# --- Gemini Analysis ---
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY" # שם משתנה הסביבה
GEMINI_SYSTEM_INST_FILE = Path("gemini_system_instruction.txt") # נתיב לקובץ ההוראות
GEMINI_MODEL_NAME = "gemini-2.0-flash-lite" # שימוש במודל עדכני יותר, או gemini-pro
DEFAULT_GEMINI_SIMILARITY_RANGE = "50-90" # טווח ברירת מחדל לניתוח Gemini (ציון דמיון באחוזים)
GEMINI_API_DELAY_SECONDS = 0.5 # הוספה: עיכוב בשניות בין קריאות ל-API כדי למנוע חסימה
GEMINI_HIGH_SIMILARITY_THRESHOLD_FOR_REPRESENTATIVE = 95.0