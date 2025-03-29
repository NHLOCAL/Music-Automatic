# data_store.py
import datetime
import json
import logging
from pathlib import Path
import shutil
from typing import Dict, Any

import config

logger = logging.getLogger(__name__)

class DataStore:
    """Handles loading and saving the persistent music data cache."""

    def __init__(self, cache_file: Path = config.MUSIC_DATA_CACHE_FILE):
        self.cache_file = cache_file

    def load_data(self) -> Dict[str, Any]:
        """Loads the music data cache from the JSON file."""
        if self.cache_file.exists():
            logger.info(f"Loading music data cache from: {self.cache_file}")
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Basic validation: ensure it's a dictionary
                    if isinstance(data, dict):
                        logger.info(f"Successfully loaded data for {len(data)} folders from cache.")
                        return data
                    else:
                        logger.error(f"Cache file {self.cache_file} does not contain a valid JSON dictionary. Ignoring cache.")
                        return {}
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from cache file {self.cache_file}: {e}. Ignoring cache.")
                # Optionally backup the corrupted file
                self._backup_corrupted_cache()
                return {}
            except Exception as e:
                logger.error(f"Unexpected error loading cache file {self.cache_file}: {e}", exc_info=True)
                return {}
        else:
            logger.info("Cache file not found. Starting fresh scan.")
            return {}

    def save_data(self, data: Dict[str, Any]):
        """Saves the music data cache to the JSON file."""
        logger.info(f"Saving music data cache for {len(data)} folders to: {self.cache_file}")
        try:
            # Ensure parent directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                # Use indent for readability, ensure_ascii=False for non-ASCII chars
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info("Music data cache saved successfully.")
        except TypeError as e:
             logger.error(f"Error serializing data to JSON: {e}. Data might contain non-serializable types.", exc_info=True)
        except OSError as e:
             logger.error(f"OS error saving cache file {self.cache_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving cache file {self.cache_file}: {e}", exc_info=True)

    def _backup_corrupted_cache(self):
        """Creates a backup of a potentially corrupted cache file."""
        if self.cache_file.exists():
            backup_path = self.cache_file.with_suffix(f".corrupted_{datetime.datetime.now():%Y%m%d%H%M%S}.json")
            try:
                shutil.move(str(self.cache_file), str(backup_path))
                logger.warning(f"Backed up corrupted cache file to: {backup_path}")
            except Exception as e:
                logger.error(f"Could not back up corrupted cache file {self.cache_file}: {e}")

