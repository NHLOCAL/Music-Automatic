# File: music_dup_lib/core/data_store.py
import datetime
import json
import logging
from pathlib import Path
import shutil
from typing import Dict, Any, List, Union, FrozenSet # Added Union, FrozenSet

from .. import config
from ..models import FolderComparisonResult

logger = logging.getLogger(__name__)

class DataStore:

    def __init__(self,
                 music_cache_file: Path = config.MUSIC_DATA_CACHE_FILE,
                 comparison_cache_file: Path = config.COMPARISON_RESULTS_CACHE_FILE):
        self.music_cache_file = music_cache_file
        self.comparison_cache_file = comparison_cache_file

    def load_data(self) -> Dict[str, Any]:
        # ... (no change in this method) ...
        if self.music_cache_file.exists():
            logger.info(f"Loading music data cache from: {self.music_cache_file}")
            try:
                with open(self.music_cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

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
        # ... (no change in this method) ...
        logger.info(f"Saving music data cache for {len(data)} folders to: {self.music_cache_file}")
        try:
            self.music_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.music_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info("Music data cache saved successfully.")
        except TypeError as e:
             logger.error(f"Error serializing data to JSON for music cache: {e}. Data might contain non-serializable types.", exc_info=True)
        except OSError as e:
             logger.error(f"OS error saving music cache file {self.music_cache_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving music cache file {self.music_cache_file}: {e}", exc_info=True)

    def _backup_corrupted_file(self, file_path: Path):
        # ... (no change in this method) ...
        if file_path.exists():
            backup_path = file_path.with_suffix(f".corrupted_{datetime.datetime.now():%Y%m%d%H%M%S}{file_path.suffix}")
            try:
                shutil.move(str(file_path), str(backup_path))
                logger.warning(f"Backed up corrupted file {file_path} to: {backup_path}")
            except Exception as e:
                logger.error(f"Could not back up corrupted file {file_path}: {e}")

    def load_comparison_results(self) -> Dict[FrozenSet[str], FolderComparisonResult]: # Changed return type
        if not self.comparison_cache_file.exists():
            logger.info("Comparison results cache file not found. Returning empty map.")
            return {} # Return empty dict

        logger.info(f"Loading comparison results from: {self.comparison_cache_file}")
        results_map: Dict[FrozenSet[str], FolderComparisonResult] = {} # Initialize a map
        try:
            with open(self.comparison_cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.error(f"Comparison cache file {self.comparison_cache_file} does not contain a valid JSON list. Ignoring cache.")
                self._backup_corrupted_file(self.comparison_cache_file)
                return {}

            for item in data:
                try:
                    # Ensure paths are strings for the key
                    f1_path_str = item["folder1_path"]
                    f2_path_str = item["folder2_path"]
                    
                    # Validate that these are indeed strings, not already Path objects if loaded from an old cache
                    if not isinstance(f1_path_str, str) or not isinstance(f2_path_str, str):
                        logger.warning(f"Found non-string path in cache item: {item}. Converting to string.")
                        f1_path_str = str(f1_path_str)
                        f2_path_str = str(f2_path_str)

                    pair_key = frozenset({f1_path_str, f2_path_str})

                    gemini_similarity_val = item.get("gemini_similarity_score")
                    if gemini_similarity_val is None:
                        gemini_similarity_val = item.get("gemini_confidence") # Legacy support

                    result = FolderComparisonResult(
                        folder1_path=Path(f1_path_str), # Convert to Path for the object
                        folder2_path=Path(f2_path_str), # Convert to Path for the object
                        similarity_scores=item.get("similarity_scores", {}),
                        weighted_score=item.get("weighted_score", 0.0),
                        is_identical_by_hash=item.get("is_identical_by_hash", False),
                        gemini_verdict=item.get("gemini_verdict"),
                        gemini_similarity_score=gemini_similarity_val,
                        gemini_reason=item.get("gemini_reason"),
                        gemini_error=item.get("gemini_error"),
                        final_combined_score=item.get("final_combined_score")
                    )
                    results_map[pair_key] = result # Add to map
                except KeyError as e:
                    logger.error(f"Missing key {e} in item from comparison cache {self.comparison_cache_file}. Skipping item: {item}", exc_info=False) # exc_info=False for less verbose logs on common errors
                except Exception as e:
                    logger.error(f"Error processing item from comparison cache {self.comparison_cache_file}: {item}. Error: {e}", exc_info=True)

            logger.info(f"Successfully loaded {len(results_map)} comparison results into map from cache.")
            return results_map

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from comparison cache file {self.comparison_cache_file}: {e}. Ignoring cache.")
            self._backup_corrupted_file(self.comparison_cache_file)
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading comparison cache file {self.comparison_cache_file}: {e}", exc_info=True)
            return {}

    def save_comparison_results(self, 
                                results_to_update: Union[List[FolderComparisonResult], Dict[FrozenSet[Path], FolderComparisonResult], Dict[FrozenSet[str], FolderComparisonResult]]):
        
        logger.info(f"Attempting to save/update comparison results to: {self.comparison_cache_file}")

        # Step 1: Load existing cache into a map
        # This now returns Dict[FrozenSet[str], FolderComparisonResult]
        existing_results_map = self.load_comparison_results()
        
        logger.info(f"Loaded {len(existing_results_map)} existing results. Merging with {len(results_to_update) if isinstance(results_to_update, (list,dict)) else 'N/A'} new/updated results.")

        # Step 2: Convert new/updated results to a map with string path keys and merge
        update_map_str_keys: Dict[FrozenSet[str], FolderComparisonResult] = {}
        if isinstance(results_to_update, list):
            for res in results_to_update:
                key = frozenset({str(res.folder1_path), str(res.folder2_path)})
                update_map_str_keys[key] = res
        elif isinstance(results_to_update, dict):
            # Check if keys are FrozenSet[Path] or FrozenSet[str]
            sample_key = next(iter(results_to_update.keys()), None)
            if sample_key and isinstance(next(iter(sample_key)), Path): # Keys are FrozenSet[Path]
                for path_key_set, res in results_to_update.items():
                    str_key_set = frozenset({str(p) for p in path_key_set})
                    update_map_str_keys[str_key_set] = res
            else: # Assume keys are already FrozenSet[str] or it's empty
                update_map_str_keys = results_to_update
        
        existing_results_map.update(update_map_str_keys)
        
        logger.info(f"Total results after merge: {len(existing_results_map)}")

        # Step 3: Convert the merged map values back to a list of dicts for JSON serialization
        data_to_save_as_list = []
        for result_obj in existing_results_map.values():
            item = {
                "folder1_path": str(result_obj.folder1_path),
                "folder2_path": str(result_obj.folder2_path),
                "similarity_scores": result_obj.similarity_scores,
                "weighted_score": result_obj.weighted_score,
                "is_identical_by_hash": result_obj.is_identical_by_hash,
                "gemini_verdict": result_obj.gemini_verdict,
                "gemini_similarity_score": result_obj.gemini_similarity_score,
                "gemini_reason": result_obj.gemini_reason,
                "gemini_error": result_obj.gemini_error,
                "final_combined_score": result_obj.final_combined_score
            }
            data_to_save_as_list.append(item)

        # Step 4: Save the complete list to file (overwrite mode is fine here, as we've merged in memory)
        try:
            self.comparison_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.comparison_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save_as_list, f, ensure_ascii=False, indent=4)
            logger.info(f"Comparison results cache successfully updated and saved with {len(data_to_save_as_list)} total entries.")
        except TypeError as e:
            logger.error(f"Error serializing updated comparison results to JSON: {e}. Results might contain non-serializable types.", exc_info=True)
        except OSError as e:
            logger.error(f"OS error saving updated comparison cache file {self.comparison_cache_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving updated comparison cache file {self.comparison_cache_file}: {e}", exc_info=True)