# album_deduplicator/music_dup_lib/config.py
import logging
from pathlib import Path

# --- הגדרות נתיבים ---
# PROJECT_ROOT_ALBUM_DEDUP מתייחס לתיקיית השורש של פרויקט album_deduplicator
# מחושב יחסית למיקום קובץ זה (album_deduplicator/music_dup_lib/config.py)
PROJECT_ROOT_ALBUM_DEDUP = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT_ALBUM_DEDUP / "data"
DATA_DIR.mkdir(exist_ok=True) # ודא שהתיקייה קיימת

LOGS_DIR = PROJECT_ROOT_ALBUM_DEDUP / "logs"
LOGS_DIR.mkdir(exist_ok=True) # ודא שהתיקייה קיימת

# --- שמות קבצים (ללא נתיב DATA_DIR, הם ישולבו עם DATA_DIR בקוד שמשתמש בהם) ---
# כאשר ניגשים לקבצים אלו, יש להשתמש ב: DATA_DIR / MUSIC_DATA_CACHE_FILE
MUSIC_DATA_CACHE_FILE = "music_data.json"
COMPARISON_RESULTS_CACHE_FILE = "comparison_results_cache.json"
ARTIST_CSV_FILE = "singer-list.csv"

# הערה: ML_MODEL_FILE כאן כנראה מתייחס למודל ישן או לשימוש פנימי של album_deduplicator.
# פרויקט similarity_model מנהל את המודלים שלו בנפרד.
# אם אין בו שימוש, ניתן להסיר. אם יש, הקוד שמשתמש בו צריך לעשות DATA_DIR / ML_MODEL_FILE.
ML_MODEL_FILE = "lgbm_regressor_model.joblib"

# --- הגדרות סריקה ועיבוד קבצים ---
ALLOWED_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg'}
LOSSLESS_EXTENSIONS = {'.flac', '.wav'}
IGNORED_FILES = {'cover.jpg', 'folder.jpg', 'thumbs.db', 'desktop.ini',
                 'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg', 'cover.png', 'תמונה.jpg'}
ALBUM_ART_FILES = {'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg',
                   'cover.jpg', 'folder.jpg', 'cover.png', 'תמונה.jpg'}
MIN_FILES_PER_FOLDER = 3

# --- הגדרות Hashing ---
ENABLE_HASHING = True
HASH_CHUNK_SIZE = 4096
HASH_NUM_RANDOM_CHUNKS = 2

# --- הגדרות השוואה ודמיון ---
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
    'additional_metadata_field_weight': 0.2
}

# משקולות לשילוב ציון אלגוריתמי עם ציון Gemini
GEMINI_SCORE_WEIGHT = 0.7
ALGORITHMIC_SCORE_WEIGHT = 0.3

# --- הגדרות איכות אלבום ---
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
BITRATE_SCORE_TOLERANCE = 192 # Bitrate values above this (up to HIGH_BITRATE_TARGET) will get a linearly increasing score

# --- הגדרות פעולות על קבצים ---
MIN_SIMILARITY_FOR_MERGE = 80.0
DEFAULT_MIN_SIMILARITY_FOR_DELETE = 85.0

# --- הגדרות לוגינג ---
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

# --- הגדרות ביצועים ---
MAX_WORKERS = None  # None ישתמש ב- os.cpu_count()
LRU_CACHE_SIZE = 10000

# --- הגדרות תיקון ג'יבריש ---
JIBRISH_FIX_LANGUAGE = "heb"

# --- הגדרות Gemini ---
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY" # שם משתנה הסביבה
# קובץ ההנחיות ל-Gemini, נמצא יחסית למיקום קובץ זה, בתיקיית 'external'
GEMINI_SYSTEM_INST_FILE = Path(__file__).resolve().parent / "external" / "gemini_system_instruction.txt"
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest" # היה "gemini-1.5-flash-preview-05-20" לפני כן, שונה ל-latest.
DEFAULT_GEMINI_SIMILARITY_RANGE = "40-90" # טווח ציונים אלגוריתמיים שיועבר ל-Gemini כברירת מחדל
GEMINI_API_DELAY_SECONDS = 0.5 # השהייה בין קריאות ל-Gemini API (כדי למנוע rate limiting)
GEMINI_HIGH_SIMILARITY_THRESHOLD_FOR_REPRESENTATIVE = 95.0 # סף דמיון גבוה ש-Gemini צריך להחזיר כדי שתיקייה תיחשב כנציגה טובה.