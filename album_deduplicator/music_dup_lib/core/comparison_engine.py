import logging
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

from .. import config
from ..models import FileInfo, FolderComparisonResult, FolderInfo
from ..utils import cached_string_similarity, normalize_filename_for_sort
logger = logging.getLogger(__name__)

ComparisonProgressCallback = Callable[[int, int], None]


@dataclass(slots=True)
class PreparedFolderComparisonData:
    sorted_files: Tuple[FileInfo, ...]
    file_hashes: Tuple[Optional[str], ...]
    other_files_map: Dict[str, Dict[str, Any]]
    other_file_names: FrozenSet[str]
    num_files: int

class ComparisonEngine:
    def __init__(self, enable_hashing: bool = config.ENABLE_HASHING):
        self.enable_hashing = enable_hashing
        self.weights = self._get_adjusted_weights(config.SIMILARITY_WEIGHTS, enable_hashing)
        self.total_base_weight = sum(self.weights.values())
        self._prepared_folder_cache: Dict[Path, PreparedFolderComparisonData] = {}
        logger.info(f"Comparison Engine initialized. Hashing enabled: {self.enable_hashing}")
        logger.debug(f"Using similarity weights: {self.weights}")
    def _get_adjusted_weights(self, base_weights: Dict[str, float], hashing_enabled: bool) -> Dict[str, float]:
        adjusted = base_weights.copy()
        if not hashing_enabled:
            if 'file_hash' in adjusted:
                del adjusted['file_hash']
        return adjusted
    def _prepare_folder(self, folder: FolderInfo) -> PreparedFolderComparisonData:
        cached = self._prepared_folder_cache.get(folder.path)
        if cached is not None:
            return cached

        sorted_files = tuple(sorted(folder.files, key=lambda item: normalize_filename_for_sort(item.filename)))
        other_files_map = {item['name']: item for item in folder.other_files}
        prepared = PreparedFolderComparisonData(
            sorted_files=sorted_files,
            file_hashes=tuple(file_info.file_hash for file_info in sorted_files),
            other_files_map=other_files_map,
            other_file_names=frozenset(other_files_map.keys()),
            num_files=len(sorted_files),
        )
        self._prepared_folder_cache[folder.path] = prepared
        return prepared

    def _compare_other_files(
        self,
        prepared_folder1: PreparedFolderComparisonData,
        prepared_folder2: PreparedFolderComparisonData,
        hashing_enabled: bool,
    ) -> float:
        if not prepared_folder1.other_file_names and not prepared_folder2.other_file_names:
            return 1.0  # No other files in either, so perfectly similar in this aspect
        map1 = prepared_folder1.other_files_map
        map2 = prepared_folder2.other_files_map
        all_names = prepared_folder1.other_file_names | prepared_folder2.other_file_names
        if not all_names: # Should be caught by the first check, but as a safeguard
            return 1.0
        total_score = 0.0
        # Define internal weights for sub-comparison of each file
        # These are not the global SIMILARITY_WEIGHTS
        OTHER_FILE_SIZE_WEIGHT = 0.6
        OTHER_FILE_HASH_WEIGHT = 0.4
        for name in all_names:
            file1_details = map1.get(name)
            file2_details = map2.get(name)
            if file1_details and file2_details:
                # File exists in both folders
                current_file_score_parts = []
                current_file_weight_sum = 0
                # Size comparison
                s1, s2 = file1_details['size_bytes'], file2_details['size_bytes']
                size_score = 0.0
                if s1 == s2:
                    size_score = 1.0
                elif max(s1, s2) > 0:
                    size_score = min(s1, s2) / max(s1, s2)
                current_file_score_parts.append(size_score * OTHER_FILE_SIZE_WEIGHT)
                current_file_weight_sum += OTHER_FILE_SIZE_WEIGHT
                # Hash comparison (if enabled and hashes exist)
                if hashing_enabled:
                    h1, h2 = file1_details.get('hash'), file2_details.get('hash')
                    hash_score = 0.0 # Default if hashes not comparable
                    if h1 and h2: # Both files have hashes
                        if h1 == h2:
                            hash_score = 1.0
                        else: # Hashes exist but are different
                            hash_score = 0.0
                    # If only one has a hash, or neither has, hash_score remains 0 for this part.
                    # This means non-existence of hash is treated as a non-match for the hash component.
                    current_file_score_parts.append(hash_score * OTHER_FILE_HASH_WEIGHT)
                    current_file_weight_sum += OTHER_FILE_HASH_WEIGHT
                file_match_score = sum(current_file_score_parts) / current_file_weight_sum if current_file_weight_sum > 0 else 0.0
                total_score += file_match_score
            else:
                # File exists in only one folder, contributes 0 to total_score for this file
                pass
        # Normalize by the total number of unique "other" files across both folders
        return total_score / len(all_names) if len(all_names) > 0 else 1.0
        
    def find_similar_folders(
        self,
        all_folders: Dict[Path, FolderInfo],
        progress_callback: Optional[ComparisonProgressCallback] = None,
    ) -> List[FolderComparisonResult]:
        logger.info(f"Starting comparison of {len(all_folders)} folders.")
        comparison_results: List[FolderComparisonResult] = []
        folders_by_file_count: Dict[int, List[FolderInfo]] = defaultdict(list)
        for folder in all_folders.values():
            if folder.files:
                folders_by_file_count[len(folder.files)].append(folder)

        total_pairs = sum(
            len(group) * (len(group) - 1) // 2
            for group in folders_by_file_count.values()
            if len(group) > 1
        )

        current_index = 0
        for file_count in sorted(folders_by_file_count):
            group = folders_by_file_count[file_count]
            if len(group) < 2:
                continue

            for folder1, folder2 in combinations(group, 2):
                current_index += 1
                comparison_result = self.compare_two_folders(folder1, folder2)

                if comparison_result:
                    comparison_results.append(comparison_result)

                if progress_callback:
                    progress_callback(current_index, total_pairs)
        
        # Sort is optional here but can be helpful for debugging the full list.
        # The main sorting for display will happen in main.py on the filtered list.
        comparison_results.sort(key=lambda x: x.weighted_score, reverse=True)
        
        logger.info(f"Comparison complete. Returning {len(comparison_results)} total processed pairs for caching and further analysis.")
        return comparison_results

    def compare_two_folders(self, folder1: FolderInfo, folder2: FolderInfo) -> Optional[FolderComparisonResult]:
        prepared_folder1 = self._prepare_folder(folder1)
        prepared_folder2 = self._prepare_folder(folder2)

        if prepared_folder1.num_files != prepared_folder2.num_files or prepared_folder1.num_files == 0:
            logger.debug(f"Skipping comparison: Different music file counts ({len(folder1.files)} vs {len(folder2.files)}) or empty music folders for {folder1.path.name} and {folder2.path.name}")
            return None
        similarity_scores: Dict[str, Any] = {} # Changed to Dict[str, Any]
        files1 = prepared_folder1.sorted_files
        files2 = prepared_folder2.sorted_files
        num_files = prepared_folder1.num_files # Number of music files
        # --- Compare "Other Files" ---
        similarity_scores['other_files_similarity'] = self._compare_other_files(
            prepared_folder1, prepared_folder2, self.enable_hashing
        )
        if self.enable_hashing and folder1.file_hashes_present and folder2.file_hashes_present:
            hash_match_count = sum(
                1
                for hash1, hash2 in zip(prepared_folder1.file_hashes, prepared_folder2.file_hashes)
                if hash1 and hash2 and hash1 == hash2
            )
            file_hash_similarity = hash_match_count / num_files if num_files > 0 else 0.0
            similarity_scores['file_hash'] = file_hash_similarity
            if file_hash_similarity == 1.0:
                logger.info(f"Folders are identical by music file hashes: {folder1.path.name} and {folder2.path.name}")
                # If music files are identical, we consider the core content identical.
                # The weighted_score will be 100.0.
                # All other similarity_scores (except 'other_files_similarity' which is already calculated)
                # will be set to 1.0 to reflect this music file identity for the purpose of weighting.
                # This ensures other factors don't pull down the score from 100% if music files match perfectly.
                for key in self.weights:
                    if key != 'other_files_similarity' and key not in similarity_scores:
                         similarity_scores[key] = 1.0
                if 'additional_metadata_details' not in similarity_scores: # Ensure it exists even if empty
                    similarity_scores['additional_metadata_details'] = {}
                return FolderComparisonResult(
                    folder1_path=folder1.path,
                    folder2_path=folder2.path,
                    similarity_scores=similarity_scores, # Includes 'other_files_similarity'
                    weighted_score=100.0, # Overall score is 100 due to identical music files
                    is_identical_by_hash=True # This flag refers to music files
                )
        elif self.enable_hashing:
            similarity_scores['file_hash'] = 0.0
            logger.debug(f"Hashing enabled, but not all music files have hashes for pair: {folder1.path.name}, {folder2.path.name}, or hash comparison not possible.")
        # If hashing is disabled entirely, 'file_hash' won't be in self.weights due to _get_adjusted_weights
        size_similarity_sum = 0.0
        for f1, f2 in zip(files1, files2):
            s1, s2 = f1.size_mb, f2.size_mb
            if s1 > 0 and s2 > 0:
                ratio = min(s1, s2) / max(s1, s2)
                size_similarity_sum += 1.0 if ratio >= 0.95 else ratio * ratio
        similarity_scores['file_size'] = size_similarity_sum / num_files if num_files > 0 else 0.0
        folder_name_sim = cached_string_similarity(folder1.folder_name, folder2.folder_name)
        similarity_scores['folder_name'] = folder_name_sim
        similarity_scores['album_art_hash'] = 1.0 if folder1.album_art_hash and folder1.album_art_hash == folder2.album_art_hash else 0.0
        filename_sim_sum = 0.0
        title_sim_sum = 0.0
        artist_sim_sum = 0.0
        album_sim_sum = 0.0
        albumartist_sim_sum = 0.0
        duration_sim_sum = 0.0
        additional_metadata_matches: Dict[str, int] = defaultdict(int)
        max_generic_filename = max(folder1.generic_filename_score, folder2.generic_filename_score)
        max_generic_title = max(folder1.generic_title_score, folder2.generic_title_score)
        filename_adjustment = (1.0 - (max_generic_filename * config.GENERIC_NAME_REDUCTION_FACTOR)) \
                               if max_generic_filename > config.GENERIC_NAME_SIMILARITY_THRESHOLD else 1.0
        title_adjustment = (1.0 - (max_generic_title * config.GENERIC_NAME_REDUCTION_FACTOR)) \
                           if max_generic_title > config.GENERIC_NAME_SIMILARITY_THRESHOLD else 1.0
        for f1, f2 in zip(files1, files2):
            fn_sim = cached_string_similarity(f1.filename, f2.filename)
            filename_sim_sum += (fn_sim * filename_adjustment)
            if f1.title and f2.title:
                 t_sim = cached_string_similarity(f1.title, f2.title)
                 title_sim_sum += (t_sim * title_adjustment)
            elif f1.title or f2.title:
                 title_sim_sum += 0.0
            if f1.artist and f2.artist:
                art_sim = cached_string_similarity(f1.artist, f2.artist)
                artist_sim_sum += art_sim
            elif f1.artist or f2.artist:
                artist_sim_sum += 0.0
            if f1.albumartist and f2.albumartist:
                aa_sim = cached_string_similarity(f1.albumartist, f2.albumartist)
                albumartist_sim_sum += aa_sim
            elif f1.albumartist or f2.albumartist:
                albumartist_sim_sum += 0.0
            if f1.album and f2.album:
                alb_sim = cached_string_similarity(f1.album, f2.album)
                album_sim_sum += alb_sim
            elif f1.album or f2.album:
                album_sim_sum += 0.0
            d1, d2 = f1.duration, f2.duration
            if d1 is not None and d2 is not None and d1 > 0 and d2 > 0:
                 ratio = min(d1, d2) / max(d1, d2)
                 duration_sim_sum += 1.0 if ratio >= 0.97 else (ratio * ratio if ratio > 0.8 else 0.0)
            elif d1 is not None or d2 is not None :
                duration_sim_sum += 0.0
            tags1 = f1.all_tags
            tags2 = f2.all_tags
            exclude_keys = {'title', 'artist', 'album', 'albumartist', 'duration', 'bitrate', 'lyrics', 'filename', 'filepath'}
            common_keys = (set(tags1.keys()) & set(tags2.keys())) - exclude_keys
            for key in common_keys:
                 v1, v2 = tags1.get(key), tags2.get(key)
                 if v1 and v2:
                      if isinstance(v1, str) and isinstance(v2, str):
                           if v1.strip().lower() == v2.strip().lower():
                                additional_metadata_matches[key] += 1
                      elif v1 == v2:
                            additional_metadata_matches[key] += 1
        similarity_scores['filename'] = filename_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['title'] = title_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['artist'] = artist_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['albumartist'] = albumartist_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['album'] = album_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['duration'] = duration_sim_sum / num_files if num_files > 0 else 0.0
        additional_metadata_scores: Dict[str, float] = { # Ensure type
            key: count / num_files for key, count in additional_metadata_matches.items()
        }
        similarity_scores['additional_metadata_details'] = additional_metadata_scores # This is Dict[str, float]
        weighted_score_sum = 0.0
        current_total_weight = 0.0
        for param, weight in self.weights.items():
             score_value = similarity_scores.get(param) # Can be float or Dict for 'additional_metadata_details'
             if score_value is not None and isinstance(score_value, (float, int)): # Process only numeric scores here
                 weighted_score_sum += score_value * weight
                 current_total_weight += weight
             elif param == 'file_hash' and not self.enable_hashing:
                 pass
             elif param != 'additional_metadata_details' and score_value is None: # Log only if not the special details dict
                 logger.debug(f"Weight defined for '{param}' but score not found in similarity_scores for pair {folder1.path.name} vs {folder2.path.name}. Skipping this weight.")
        # Handle 'additional_metadata_details' separately as its value in similarity_scores is a dict
        add_meta_details_dict = similarity_scores.get('additional_metadata_details')
        if isinstance(add_meta_details_dict, dict):
            additional_metadata_weighted_sum = sum(
                score * config.SIMILARITY_WEIGHTS['additional_metadata_field_weight']
                for score in add_meta_details_dict.values() if isinstance(score, (float, int))
            )
            weighted_score_sum += additional_metadata_weighted_sum
            current_total_weight += len(add_meta_details_dict) * config.SIMILARITY_WEIGHTS['additional_metadata_field_weight']
        final_weighted_score = (weighted_score_sum / current_total_weight) * 100 if current_total_weight > 0 else 0.0
        is_identical_by_hash = False # This refers to music files, determined earlier if hash_similarity == 1.0
        file_hash_score_for_boost_check = similarity_scores.get('file_hash', 0.0 if self.enable_hashing else 1.0)
        if not isinstance(file_hash_score_for_boost_check, (float, int)): # Ensure it's numeric for comparison
            file_hash_score_for_boost_check = 0.0
        if file_hash_score_for_boost_check < 0.9:
            metadata_strength_score_sum = 0.0
            metadata_strength_weight_sum = 0.0
            important_metadata_fields_for_boost = {
                'title': self.weights.get('title', config.SIMILARITY_WEIGHTS.get('title',0)),
                'album': self.weights.get('album', config.SIMILARITY_WEIGHTS.get('album',0)),
                'artist': self.weights.get('artist', config.SIMILARITY_WEIGHTS.get('artist',0)),
                'albumartist': self.weights.get('albumartist', config.SIMILARITY_WEIGHTS.get('albumartist',0)),
                'duration': self.weights.get('duration', config.SIMILARITY_WEIGHTS.get('duration',0)),
                'folder_name': self.weights.get('folder_name', config.SIMILARITY_WEIGHTS.get('folder_name',0)) * 0.5
            }
            for field, weight in important_metadata_fields_for_boost.items():
                field_score = similarity_scores.get(field)
                if isinstance(field_score, (float, int)) and weight > 0:
                    metadata_strength_score_sum += field_score * weight
                    metadata_strength_weight_sum += weight
            if metadata_strength_weight_sum > 0:
                avg_metadata_strength = (metadata_strength_score_sum / metadata_strength_weight_sum)
                if avg_metadata_strength > 0.7 and final_weighted_score < (avg_metadata_strength * 100 * 0.90):
                    target_score_based_on_metadata = avg_metadata_strength * 100
                    boost_amount = (target_score_based_on_metadata - final_weighted_score) * 0.6
                    new_score_before_cap = final_weighted_score + boost_amount
                    final_weighted_score = min(new_score_before_cap, 96.0)
                    logger.debug(f"Boosting score for '{folder1.path.name}' vs '{folder2.path.name}' due to strong metadata "
                                 f"(avg_meta_strength: {avg_metadata_strength:.2f}, initial_score: {final_weighted_score - boost_amount:.2f}). "
                                 f"New score: {final_weighted_score:.2f}")
        if logger.isEnabledFor(logging.DEBUG):
             score_details_list = []
             for k, v_score in sorted(similarity_scores.items()):
                 if k == 'additional_metadata_details':
                     add_meta_dict = v_score if isinstance(v_score, dict) else {}
                     add_meta_str_list = [f"{mk.split(':')[0]}:{mv:.2f}" for mk, mv in sorted(add_meta_dict.items()) if isinstance(mv, (float,int))]
                     if add_meta_str_list: score_details_list.append(f"AddMeta=({', '.join(add_meta_str_list)})")
                 elif isinstance(v_score, (float, int)):
                     score_details_list.append(f"{k}={v_score:.2f}")
             score_details_str = ", ".join(score_details_list)
             logger.debug(f"Comparison Details ({folder1.path.name} vs {folder2.path.name}): Scores=[{score_details_str}], FinalScore={final_weighted_score:.2f}")
        return FolderComparisonResult(
            folder1_path=folder1.path,
            folder2_path=folder2.path,
            similarity_scores=similarity_scores,
            weighted_score=final_weighted_score,
            is_identical_by_hash=is_identical_by_hash
        )
