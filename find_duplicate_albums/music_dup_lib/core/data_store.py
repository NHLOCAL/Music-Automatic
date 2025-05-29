import datetime
import json
import logging
from pathlib import Path
import shutil
from typing import Dict, Any, List, Union, FrozenSet

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
        if self.music_cache_file.exists():
            logger.info(f"Loading music data cache from: {self.music_cache_file}")
            try:
                with open(self.music_cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    if isinstance(data, dict):
                        logger.info(f"Successfully loaded data for {len(data)} folders from music cache.")
                        return data
                    else:
                        logger.error(f"Music cache file {self.music_cache_file} does not contain a valid JSON dictionary. Using empty cache.")
                        self._backup_corrupted_file(self.music_cache_file)
                        return {}
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from music cache file {self.music_cache_file}: {e}. Using empty cache.")
                self._backup_corrupted_file(self.music_cache_file)
                return {}
            except Exception as e:
                logger.error(f"Unexpected error loading music cache file {self.music_cache_file}: {e}", exc_info=True)
                return {}
        else:
            logger.info("Music data cache file not found. Starting with an empty cache.")
            return {}

    def save_data(self, data_to_update: Dict[str, Any]):
        logger.info(f"Attempting to save/update music data cache to: {self.music_cache_file}")


        existing_music_data = self.load_data()

        logger.info(f"Loaded {len(existing_music_data)} existing music data entries. Merging with {len(data_to_update)} new/updated entries.")



        existing_music_data.update(data_to_update)

        logger.info(f"Total music data entries after merge: {len(existing_music_data)}")


        try:
            self.music_cache_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.music_cache_file, 'w', encoding='utf-8') as f:
                json.dump(existing_music_data, f, ensure_ascii=False, indent=4)
            logger.info(f"Music data cache successfully updated and saved with {len(existing_music_data)} total entries.")
        except TypeError as e:
             logger.error(f"Error serializing updated music data to JSON: {e}. Data might contain non-serializable types.", exc_info=True)
        except OSError as e:
             logger.error(f"OS error saving updated music data cache file {self.music_cache_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving updated music data cache file {self.music_cache_file}: {e}", exc_info=True)

    def _backup_corrupted_file(self, file_path: Path):
        if file_path.exists() and file_path.stat().st_size > 0:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            backup_name = f"{file_path.stem}.corrupted_{timestamp}{file_path.suffix}"
            backup_path = file_path.with_name(backup_name)
            try:
                shutil.move(str(file_path), str(backup_path))
                logger.warning(f"Backed up corrupted/invalid file {file_path} to: {backup_path}")
            except Exception as e:
                logger.error(f"Could not back up corrupted/invalid file {file_path}: {e}")
        elif not file_path.exists():
            logger.debug(f"File {file_path} does not exist, no backup needed.")
        else:
            logger.debug(f"File {file_path} is empty, no backup needed. It will be overwritten or created.")


    def load_comparison_results(self) -> Dict[FrozenSet[str], FolderComparisonResult]:
        if not self.comparison_cache_file.exists():
            logger.info("Comparison results cache file not found. Returning empty map.")
            return {}

        logger.info(f"Loading comparison results from: {self.comparison_cache_file}")
        results_map: Dict[FrozenSet[str], FolderComparisonResult] = {}
        try:
            with open(self.comparison_cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.error(f"Comparison cache file {self.comparison_cache_file} does not contain a valid JSON list. Using empty cache.")
                self._backup_corrupted_file(self.comparison_cache_file)
                return {}

            for item in data:
                try:
                    f1_path_str = item["folder1_path"]
                    f2_path_str = item["folder2_path"]

                    if not isinstance(f1_path_str, str) or not isinstance(f2_path_str, str):
                        logger.warning(f"Found non-string path in cache item: {item}. Converting to string.")
                        f1_path_str = str(f1_path_str)
                        f2_path_str = str(f2_path_str)

                    pair_key = frozenset({f1_path_str, f2_path_str})
                    gemini_similarity_val = item.get("gemini_similarity_score")
                    if gemini_similarity_val is None:
                        gemini_similarity_val = item.get("gemini_confidence") # Legacy key

                    result = FolderComparisonResult(
                        folder1_path=Path(f1_path_str),
                        folder2_path=Path(f2_path_str),
                        similarity_scores=item.get("similarity_scores", {}),
                        weighted_score=item.get("weighted_score", 0.0),
                        is_identical_by_hash=item.get("is_identical_by_hash", False),
                        gemini_verdict=item.get("gemini_verdict"),
                        gemini_similarity_score=gemini_similarity_val,
                        gemini_reason=item.get("gemini_reason"),
                        gemini_error=item.get("gemini_error"),
                        final_combined_score=item.get("final_combined_score")
                    )
                    results_map[pair_key] = result
                except KeyError as e:
                    logger.error(f"Missing key {e} in item from comparison cache {self.comparison_cache_file}. Skipping item: {item}", exc_info=False)
                except Exception as e:
                    logger.error(f"Error processing item from comparison cache {self.comparison_cache_file}: {item}. Error: {e}", exc_info=True)

            logger.info(f"Successfully loaded {len(results_map)} comparison results into map from cache.")
            return results_map

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from comparison cache file {self.comparison_cache_file}: {e}. Using empty cache.")
            self._backup_corrupted_file(self.comparison_cache_file)
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading comparison cache file {self.comparison_cache_file}: {e}", exc_info=True)
            return {}

    def save_comparison_results(self,
                                results_to_update: Union[List[FolderComparisonResult], Dict[FrozenSet[Path], FolderComparisonResult], Dict[FrozenSet[str], FolderComparisonResult]]):

        logger.info(f"Attempting to save/update comparison results to: {self.comparison_cache_file}")

        existing_results_map: Dict[FrozenSet[str], FolderComparisonResult] = self.load_comparison_results() # Ensure type

        logger.info(f"Loaded {len(existing_results_map)} existing comparison results. Merging with {len(results_to_update) if isinstance(results_to_update, (list,dict)) else 'N/A'} new/updated results.")

        update_map_str_keys: Dict[FrozenSet[str], FolderComparisonResult] = {}
        if isinstance(results_to_update, list):
            for res in results_to_update:
                key = frozenset({str(res.folder1_path), str(res.folder2_path)})
                update_map_str_keys[key] = res
        elif isinstance(results_to_update, dict):
            # Handle both Dict[FrozenSet[Path], ...] and Dict[FrozenSet[str], ...]
            for key_set, res_val in results_to_update.items(): # Iterate directly
                if not key_set: continue # Skip empty keys
                first_element = next(iter(key_set), None)
                if isinstance(first_element, Path):
                    str_key_set = frozenset({str(p) for p in key_set}) # type: ignore
                    update_map_str_keys[str_key_set] = res_val
                elif isinstance(first_element, str):
                    update_map_str_keys[key_set] = res_val # type: ignore # Already FrozenSet[str]
                else:
                     logger.warning(f"Unsupported key type in results_to_update dictionary: {type(first_element)}. Skipping item.")

        existing_results_map.update(update_map_str_keys)

        logger.info(f"Total comparison results after merge: {len(existing_results_map)}")

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