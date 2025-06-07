import datetime
import json
import logging
import pickle
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
            logger.info("Comparison results cache file (.pkl) not found. Returning empty map.")
            return {}
        logger.info(f"Loading comparison results from Pickle file: {self.comparison_cache_file}")
        try:
            with open(self.comparison_cache_file, 'rb') as f:
                data = pickle.load(f)
            if not isinstance(data, dict):
                logger.error(f"Comparison cache file {self.comparison_cache_file} does not contain a valid dictionary. Using empty cache.")
                self._backup_corrupted_file(self.comparison_cache_file)
                return {}
            logger.info(f"Successfully loaded {len(data)} comparison results into map from Pickle cache.")
            return data
        except pickle.UnpicklingError as e:
            logger.error(f"Error unpickling from comparison cache file {self.comparison_cache_file}: {e}. Using empty cache.")
            self._backup_corrupted_file(self.comparison_cache_file)
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading comparison cache file {self.comparison_cache_file}: {e}", exc_info=True)
            return {}
    def save_comparison_results(self,
                                results_to_update: Union[List[FolderComparisonResult], Dict[FrozenSet[Path], FolderComparisonResult], Dict[FrozenSet[str], FolderComparisonResult]]):
        logger.info(f"Attempting to save/update comparison results to Pickle file: {self.comparison_cache_file}")
        existing_results_map: Dict[FrozenSet[str], FolderComparisonResult] = self.load_comparison_results()
        logger.info(f"Loaded {len(existing_results_map)} existing comparison results. Merging with {len(results_to_update) if isinstance(results_to_update, (list, dict)) else 'N/A'} new/updated results.")
        update_map_str_keys: Dict[FrozenSet[str], FolderComparisonResult] = {}
        if isinstance(results_to_update, list):
            for res in results_to_update:
                key = frozenset({str(res.folder1_path), str(res.folder2_path)})
                update_map_str_keys[key] = res
        elif isinstance(results_to_update, dict):
            for key_set, res_val in results_to_update.items():
                if not key_set: continue
                # --- START OF FIX ---
                # This conversion correctly handles both FrozenSet[Path] and FrozenSet[str]
                # by ensuring all items become strings, satisfying the dictionary's key type.
                str_key_set = frozenset(str(item) for item in key_set)
                update_map_str_keys[str_key_set] = res_val
                # --- END OF FIX ---
        
        existing_results_map.update(update_map_str_keys)
        logger.info(f"Total comparison results after merge: {len(existing_results_map)}")
        try:
            self.comparison_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.comparison_cache_file, 'wb') as f:
                pickle.dump(existing_results_map, f)
            logger.info(f"Comparison results cache successfully updated and saved with {len(existing_results_map)} total entries.")
        except pickle.PicklingError as e:
            logger.error(f"Error pickling updated comparison results: {e}. Results might contain non-serializable types.", exc_info=True)
        except OSError as e:
            logger.error(f"OS error saving updated comparison cache file {self.comparison_cache_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving updated comparison cache file {self.comparison_cache_file}: {e}", exc_info=True)