# data_store.py
import datetime
import json
import logging
from pathlib import Path
import shutil
from typing import Dict, Any, List

from .. import config
from ..models import FolderComparisonResult

logger = logging.getLogger(__name__)

class DataStore:
    """Handles loading and saving persistent data including music metadata and comparison results."""

    def __init__(self, 
                 music_cache_file: Path = config.MUSIC_DATA_CACHE_FILE,
                 comparison_cache_file: Path = config.COMPARISON_RESULTS_CACHE_FILE):
        self.music_cache_file = music_cache_file
        self.comparison_cache_file = comparison_cache_file

    def load_data(self) -> Dict[str, Any]:
        """Loads the music data cache from the JSON file."""
        if self.music_cache_file.exists():
            logger.info(f"Loading music data cache from: {self.music_cache_file}")
            try:
                with open(self.music_cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Basic validation: ensure it's a dictionary
                    if isinstance(data, dict):
                        logger.info(f"Successfully loaded data for {len(data)} folders from music cache.")
                        return data
                    else:
                        logger.error(f"Music cache file {self.music_cache_file} does not contain a valid JSON dictionary. Ignoring cache.")
                        return {}
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from music cache file {self.music_cache_file}: {e}. Ignoring cache.")
                self._backup_corrupted_file(self.music_cache_file)
                return {}
            except Exception as e:
                logger.error(f"Unexpected error loading music cache file {self.music_cache_file}: {e}", exc_info=True)
                return {}
        else:
            logger.info("Music data cache file not found. Starting fresh scan.")
            return {}

    def save_data(self, data: Dict[str, Any]):
        """Saves the music data cache to the JSON file."""
        logger.info(f"Saving music data cache for {len(data)} folders to: {self.music_cache_file}")
        try:
            # Ensure parent directory exists
            self.music_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.music_cache_file, 'w', encoding='utf-8') as f:
                # Use indent for readability, ensure_ascii=False for non-ASCII chars
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info("Music data cache saved successfully.")
        except TypeError as e:
             logger.error(f"Error serializing data to JSON for music cache: {e}. Data might contain non-serializable types.", exc_info=True)
        except OSError as e:
             logger.error(f"OS error saving music cache file {self.music_cache_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving music cache file {self.music_cache_file}: {e}", exc_info=True)

    def _backup_corrupted_file(self, file_path: Path):
        """Creates a backup of a potentially corrupted file."""
        if file_path.exists():
            backup_path = file_path.with_suffix(f".corrupted_{datetime.datetime.now():%Y%m%d%H%M%S}{file_path.suffix}")
            try:
                shutil.move(str(file_path), str(backup_path))
                logger.warning(f"Backed up corrupted file {file_path} to: {backup_path}")
            except Exception as e:
                logger.error(f"Could not back up corrupted file {file_path}: {e}")

    def load_comparison_results(self) -> List[FolderComparisonResult]:
        """Loads the comparison results cache from the JSON file."""
        if not self.comparison_cache_file.exists():
            logger.info("Comparison results cache file not found. Returning empty list.")
            return []

        logger.info(f"Loading comparison results from: {self.comparison_cache_file}")
        try:
            with open(self.comparison_cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                logger.error(f"Comparison cache file {self.comparison_cache_file} does not contain a valid JSON list. Ignoring cache.")
                self._backup_corrupted_file(self.comparison_cache_file)
                return []

            results = []
            for item in data:
                try:
                    result = FolderComparisonResult(
                        folder1_path=Path(item["folder1_path"]),
                        folder2_path=Path(item["folder2_path"]),
                        similarity_scores=item.get("similarity_scores", {}),
                        weighted_score=item.get("weighted_score", 0.0),
                        # Make sure all fields from FolderComparisonResult are handled
                        # Using .get() for optional fields to avoid KeyError if cache is old
                        files1_count=item.get("files1_count"),
                        files2_count=item.get("files2_count"),
                        matched_filenames=item.get("matched_filenames", {}),
                        matched_titles=item.get("matched_titles", {}),
                        matched_albums=item.get("matched_albums", {}),
                        matched_artists=item.get("matched_artists", {}),
                        matched_albumartists=item.get("matched_albumartists", {}),
                        matched_durations=item.get("matched_durations", {}),
                        hash_comparison_result=item.get("hash_comparison_result", {}), # This might need more specific loading if it's complex
                        is_identical_by_hash=item.get("is_identical_by_hash", False),
                        album_art_comparison=item.get("album_art_comparison", {}), # Same here
                        gemini_verdict=item.get("gemini_verdict"),
                        gemini_confidence=item.get("gemini_confidence"),
                        gemini_reason=item.get("gemini_reason"),
                        gemini_error=item.get("gemini_error")
                    )
                    results.append(result)
                except KeyError as e:
                    logger.error(f"Missing key {e} in item from comparison cache {self.comparison_cache_file}. Skipping item: {item}", exc_info=True)
                except Exception as e: # Catch other errors during item processing
                    logger.error(f"Error processing item from comparison cache {self.comparison_cache_file}: {item}. Error: {e}", exc_info=True)

            logger.info(f"Successfully loaded {len(results)} comparison results from cache.")
            return results

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from comparison cache file {self.comparison_cache_file}: {e}. Ignoring cache.")
            self._backup_corrupted_file(self.comparison_cache_file)
            return []
        except Exception as e:
            logger.error(f"Unexpected error loading comparison cache file {self.comparison_cache_file}: {e}", exc_info=True)
            return []

    def save_comparison_results(self, results: List[FolderComparisonResult]):
        """Saves the comparison results to the JSON file."""
        logger.info(f"Saving {len(results)} comparison results to: {self.comparison_cache_file}")
        
        data_to_save = []
        for result in results:
            item = {
                "folder1_path": str(result.folder1_path),
                "folder2_path": str(result.folder2_path),
                "similarity_scores": result.similarity_scores,
                "weighted_score": result.weighted_score,
                "files1_count": result.files1_count,
                "files2_count": result.files2_count,
                "matched_filenames": result.matched_filenames,
                "matched_titles": result.matched_titles,
                "matched_albums": result.matched_albums,
                "matched_artists": result.matched_artists,
                "matched_albumartists": result.matched_albumartists,
                "matched_durations": result.matched_durations,
                "hash_comparison_result": result.hash_comparison_result,
                "is_identical_by_hash": result.is_identical_by_hash,
                "album_art_comparison": result.album_art_comparison,
                "gemini_verdict": result.gemini_verdict,
                "gemini_confidence": result.gemini_confidence,
                "gemini_reason": result.gemini_reason,
                "gemini_error": result.gemini_error,
            }
            data_to_save.append(item)

        try:
            self.comparison_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.comparison_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            logger.info("Comparison results cache saved successfully.")
        except TypeError as e:
            logger.error(f"Error serializing comparison results to JSON: {e}. Results might contain non-serializable types.", exc_info=True)
        except OSError as e:
            logger.error(f"OS error saving comparison cache file {self.comparison_cache_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving comparison cache file {self.comparison_cache_file}: {e}", exc_info=True)

