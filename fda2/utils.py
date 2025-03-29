# utils.py
import logging
import datetime
import os
from pathlib import Path
import re
from rapidfuzz import fuzz
from functools import lru_cache
from jibrish_to_hebrew import fix_jibrish, check_jibrish

import config # Import the configuration

# --- ANSI Color Codes ---
class AnsiColors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

# --- Logging Setup ---
def setup_logging(log_level_str: str = "INFO", log_dir: Path = config.LOGS_DIR):
    """Configures logging for the application."""
    log_level = getattr(logging, log_level_str.upper(), config.DEFAULT_LOG_LEVEL)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f'duplicate_detector_{timestamp}.log'

    # Remove existing handlers to avoid duplicate logs if called multiple times
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=log_level,
        format=config.LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler() # Log to console as well
        ]
    )
    # Set higher level for noisy libraries if needed
    logging.getLogger("mutagen").setLevel(logging.WARNING)

    logging.info(f"Logging initialized at level: {log_level_str.upper()}. Logs: {log_file}")
    return logging.getLogger(__name__) # Return a logger instance

# --- String Similarity ---
@lru_cache(maxsize=config.LRU_CACHE_SIZE)
def cached_string_similarity(a: str, b: str) -> float:
    """Calculates normalized string similarity using fuzz.ratio, cached."""
    if not a or not b:
        return 0.0
    # Normalize: lower case and strip whitespace
    a_norm = a.lower().strip()
    b_norm = b.lower().strip()
    if not a_norm or not b_norm:
        return 0.0 # Avoid division by zero or weird results for empty strings
    return fuzz.ratio(a_norm, b_norm) / 100.0

# --- Jibrish Handling ---
def fix_jibrish_text(text: str | None) -> str | None:
    """Checks for jibrish and fixes it if found."""
    if text and check_jibrish(text):
        try:
            fixed = fix_jibrish(text, config.JIBRISH_FIX_LANGUAGE)
            logging.debug(f"Fixed jibrish: '{text}' -> '{fixed}'")
            return fixed
        except Exception as e:
            logging.warning(f"Failed to fix jibrish for text '{text}': {e}")
            return text # Return original if fixing fails
    return text

def contains_hebrew(text: str | None) -> bool:
    """Checks if a string contains Hebrew characters."""
    if not text:
        return False
    return any('\u0590' <= char <= '\u05EA' for char in text)

# --- Other Helpers ---
def get_file_size_mb(filepath: str | Path) -> float:
    """Gets file size in megabytes, returns 0 on error."""
    try:
        size_bytes = os.path.getsize(filepath)
        return size_bytes / (1024 * 1024)
    except OSError as e:
        logging.error(f"Error getting file size for {filepath}: {e}")
        return 0.0

def normalize_filename_for_sort(filename: str) -> str:
    """ Normalizes filename for consistent sorting (lowercase, spaces)."""
    return re.sub(r'\s+', ' ', filename).strip().lower()
