import datetime
import hashlib
import json
import logging
import os
import pickle
from pathlib import Path
import shutil
import tempfile
from contextlib import contextmanager
from typing import Dict, Any, List, Union, FrozenSet, Optional
from .. import config
from ..models import FolderComparisonResult
logger = logging.getLogger(__name__)
class DataStore:
    def __init__(self,
                 music_cache_file: Path = config.MUSIC_DATA_CACHE_FILE,
                 comparison_cache_file: Path = config.COMPARISON_RESULTS_CACHE_FILE):
        self.music_cache_file = music_cache_file
        self.comparison_cache_file = comparison_cache_file
    @staticmethod
    def _comparison_context(scoring_profile: str = "128") -> str:
        # Increment when comparison or ML feature semantics change.
        context = {"version": 1, "bitrate_mode": scoring_profile}
        for name in (
            "SIMILARITY_WEIGHTS", "GENERIC_NAME_REDUCTION_FACTOR", "GENERIC_NAME_SIMILARITY_THRESHOLD",
            "BASE_SCORE_ALGORITHMIC_WEIGHT", "BASE_SCORE_ML_WEIGHT", "GEMINI_MODEL_NAME", "GEMINI_THINKING_LEVEL",
            "QUALITY_WEIGHTS", "HIGH_BITRATE_TARGET", "MID_BITRATE_TARGET", "BITRATE_SCORE_TOLERANCE",
            "BASE_STRING_SIMILARITY_THRESHOLD",
        ):
            context[name] = getattr(config, name)
        context["model"] = None
        for path in (config.ML_MODEL_FILE, config.SIMILARITY_MODEL_FALLBACK_FILE):
            try:
                file_stat = path.stat()
            except OSError:
                continue
            context["model"] = (str(path), file_stat.st_size, file_stat.st_mtime_ns)
            break
        try:
            context["prompt"] = hashlib.sha256(config.GEMINI_SYSTEM_INST_FILE.read_bytes()).hexdigest()
        except OSError:
            context["prompt"] = None
        return hashlib.sha256(json.dumps(context, sort_keys=True).encode("utf-8")).hexdigest()
    @staticmethod
    @contextmanager
    def _atomic_cache_writer(path: Path, mode: str, **kwargs):
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode=mode, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False, **kwargs
            ) as stream:
                temporary_path = Path(stream.name)
                yield stream
            # Replace only after serialization and buffered writes both succeed.
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
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
    def save_data(self, data_to_update: Dict[str, Any], merge: bool = True):
        logger.info(f"Attempting to save/update music data cache to: {self.music_cache_file}")
        if merge:
            existing_music_data = self.load_data()
            logger.info(f"Loaded {len(existing_music_data)} existing music data entries. Merging with {len(data_to_update)} new/updated entries.")
            existing_music_data.update(data_to_update)
            data_to_write = existing_music_data
        else:
            data_to_write = data_to_update
            logger.info(f"Writing {len(data_to_write)} music data entries without reloading existing cache.")
        logger.info(f"Total music data entries after merge: {len(data_to_write)}")
        try:
            self.music_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self._atomic_cache_writer(self.music_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_write, f, ensure_ascii=False, separators=(',', ':'))
            logger.info(f"Music data cache successfully updated and saved with {len(data_to_write)} total entries.")
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
    def load_comparison_results(
        self, cache_profile: str = "partial", folder_signatures: Optional[Dict[str, str]] = None,
        scoring_profile: str = "128",
    ) -> Dict[FrozenSet[str], FolderComparisonResult]:
        if not self.comparison_cache_file.exists():
            logger.info("Comparison results cache file (.pkl) not found. Returning empty map.")
            return {}
        logger.info(f"Loading comparison results from Pickle file: {self.comparison_cache_file}")
        try:
            with open(self.comparison_cache_file, 'rb') as f:
                data = pickle.load(f)
            metadata = {"cache_profile": "partial"}
            results = data
            if isinstance(data, dict) and "results" in data and isinstance(data.get("metadata"), dict):
                metadata = data.get("metadata", metadata)
                results = data.get("results", {})
            if not isinstance(results, dict):
                logger.error(f"Comparison cache file {self.comparison_cache_file} does not contain a valid dictionary. Using empty cache.")
                self._backup_corrupted_file(self.comparison_cache_file)
                return {}
            stored_profile = metadata.get("cache_profile", "partial")
            if stored_profile != cache_profile:
                logger.info(
                    "Ignoring comparison cache because profile %s does not match requested %s.",
                    stored_profile,
                    cache_profile,
                )
                return {}
            if folder_signatures is not None:
                if metadata.get("comparison_context") != self._comparison_context(scoring_profile):
                    logger.info("Ignoring comparison cache because scoring inputs changed or are unversioned")
                    return {}
                stored_signatures = metadata.get("folder_signatures", {})
                if not isinstance(stored_signatures, dict):
                    return {}
                # Remove stale pairs in place instead of allocating another full cache.
                stale_keys = [
                    key for key in results
                    if not isinstance(key, frozenset) or len(key) != 2 or any(
                        path not in folder_signatures or stored_signatures.get(path) != folder_signatures[path]
                        for path in key
                    )
                ]
                for key in stale_keys:
                    del results[key]
            logger.info(f"Successfully loaded {len(results)} comparison results into map from Pickle cache.")
            return results
        except pickle.UnpicklingError as e:
            logger.error(f"Error unpickling from comparison cache file {self.comparison_cache_file}: {e}. Using empty cache.")
            self._backup_corrupted_file(self.comparison_cache_file)
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading comparison cache file {self.comparison_cache_file}: {e}", exc_info=True)
            return {}
    def save_comparison_results(self,
                                results_to_update: Union[List[FolderComparisonResult], Dict[FrozenSet[Path], FolderComparisonResult], Dict[FrozenSet[str], FolderComparisonResult]],
                                cache_profile: str = "partial",
                                existing_results_map: Union[Dict[FrozenSet[str], FolderComparisonResult], None] = None,
                                folder_signatures: Optional[Dict[str, str]] = None,
                                scoring_profile: str = "128"):
        logger.info(f"Attempting to save/update comparison results to Pickle file: {self.comparison_cache_file}")
        if existing_results_map is None:
            existing_results_map = self.load_comparison_results(
                cache_profile=cache_profile, folder_signatures=folder_signatures, scoring_profile=scoring_profile
            )
            logger.info(f"Loaded {len(existing_results_map)} existing comparison results. Merging with {len(results_to_update) if isinstance(results_to_update, (list, dict)) else 'N/A'} new/updated results.")
        else:
            existing_results_map = dict(existing_results_map)
            logger.info(
                f"Reusing in-memory comparison cache with {len(existing_results_map)} existing entries. "
                f"Merging with {len(results_to_update) if isinstance(results_to_update, (list, dict)) else 'N/A'} new/updated results."
            )
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
            with self._atomic_cache_writer(self.comparison_cache_file, 'wb') as f:
                pickle.dump(
                    {
                        "metadata": {
                            "cache_profile": cache_profile,
                            "folder_signatures": folder_signatures or {},
                            "comparison_context": self._comparison_context(scoring_profile) if folder_signatures is not None else None,
                        },
                        "results": existing_results_map,
                    },
                    f,
                )
            logger.info(f"Comparison results cache successfully updated and saved with {len(existing_results_map)} total entries.")
        except pickle.PicklingError as e:
            logger.error(f"Error pickling updated comparison results: {e}. Results might contain non-serializable types.", exc_info=True)
        except OSError as e:
            logger.error(f"OS error saving updated comparison cache file {self.comparison_cache_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving updated comparison cache file {self.comparison_cache_file}: {e}", exc_info=True)
