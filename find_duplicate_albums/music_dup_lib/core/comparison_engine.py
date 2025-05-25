import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from itertools import combinations
from collections import defaultdict
import re

from .. import config
from ..models import FolderInfo, FileInfo, FolderComparisonResult
from ..utils import cached_string_similarity, normalize_filename_for_sort

logger = logging.getLogger(__name__)

class ComparisonEngine:


    def __init__(self, enable_hashing: bool = config.ENABLE_HASHING):
        self.enable_hashing = enable_hashing

        self.weights = self._get_adjusted_weights(config.SIMILARITY_WEIGHTS, enable_hashing)
        self.total_base_weight = sum(self.weights.values()) # This might need re-evaluation if 'file_hash' weight changes contextually
        logger.info(f"Comparison Engine initialized. Hashing enabled: {self.enable_hashing}")
        logger.debug(f"Using similarity weights: {self.weights}")

    def _get_adjusted_weights(self, base_weights: Dict[str, float], hashing_enabled: bool) -> Dict[str, float]:

        adjusted = base_weights.copy()
        if not hashing_enabled and 'file_hash' in adjusted:
            del adjusted['file_hash']


        return adjusted

    def find_similar_folders(self, all_folders: Dict[Path, FolderInfo]) -> List[FolderComparisonResult]:

        logger.info(f"Starting comparison of {len(all_folders)} folders.")
        similar_folder_pairs: List[FolderComparisonResult] = []
        folder_items = list(all_folders.values())


        for folder1, folder2 in combinations(folder_items, 2):
            comparison_result = self.compare_two_folders(folder1, folder2)
            if comparison_result and comparison_result.weighted_score >= config.MINIMAL_DISPLAY_SIMILARITY:
                similar_folder_pairs.append(comparison_result)
                # Debug log moved inside compare_two_folders for context
        
        similar_folder_pairs.sort(key=lambda x: x.weighted_score, reverse=True)

        logger.info(f"Comparison complete. Found {len(similar_folder_pairs)} pairs above display threshold ({config.MINIMAL_DISPLAY_SIMILARITY}%).")
        return similar_folder_pairs


    def compare_two_folders(self, folder1: FolderInfo, folder2: FolderInfo) -> Optional[FolderComparisonResult]:

        if len(folder1.files) != len(folder2.files) or len(folder1.files) == 0: # Added check for empty folders
            logger.debug(f"Skipping comparison: Different file counts ({len(folder1.files)} vs {len(folder2.files)}) or empty folders for {folder1.path.name} and {folder2.path.name}")
            return None

        album1_repr = next(iter(folder1.unique_albums), None) if len(folder1.unique_albums) == 1 else None
        album2_repr = next(iter(folder2.unique_albums), None) if len(folder2.unique_albums) == 1 else None
        if album1_repr and album2_repr:
             album_similarity = cached_string_similarity(album1_repr, album2_repr)
             if album_similarity < 0.5: # Check if albums are at least somewhat similar if both defined
                 logger.debug(f"Skipping comparison: Low album name similarity ({album_similarity:.2f}) for {folder1.path.name} and {folder2.path.name}")
                 return None

        similarity_scores: Dict[str, float] = {}
        
        files1 = sorted(folder1.files, key=lambda x: normalize_filename_for_sort(x.filename))
        files2 = sorted(folder2.files, key=lambda x: normalize_filename_for_sort(x.filename))
        num_files = len(files1)

        # 1. Handle perfect hash identity case first
        if self.enable_hashing and folder1.file_hashes_present and folder2.file_hashes_present:
            hash_match_count = sum(1 for f1, f2 in zip(files1, files2) if f1.file_hash and f2.file_hash and f1.file_hash == f2.file_hash)
            file_hash_similarity = hash_match_count / num_files if num_files > 0 else 0.0
            similarity_scores['file_hash'] = file_hash_similarity

            if file_hash_similarity == 1.0:
                logger.info(f"Folders are identical by file hashes: {folder1.path.name} and {folder2.path.name}")
                # For perfect hash match, all other relevant scores are effectively 1.0
                for key in self.weights:
                    similarity_scores[key] = 1.0
                # Ensure additional_metadata_details is populated correctly if it affects weights
                # For simplicity, if hashes are 100% identical, we assume max score.
                similarity_scores['additional_metadata_details'] = {} # Or fill with 1.0s if complex weighting used

                return FolderComparisonResult(
                    folder1_path=folder1.path,
                    folder2_path=folder2.path,
                    similarity_scores=similarity_scores,
                    weighted_score=100.0,
                    is_identical_by_hash=True
                )
        elif self.enable_hashing:
            # Hashing enabled, but one or both folders don't have all hashes (or hashing disabled for one of them)
            similarity_scores['file_hash'] = 0.0 
            logger.debug(f"Hashing enabled, but not all files have hashes for pair: {folder1.path.name}, {folder2.path.name}, or hash comparison not possible.")
        # If hashing is disabled entirely, 'file_hash' won't be in self.weights due to _get_adjusted_weights

        # --- Calculate individual similarity scores ---
        # File Size
        size_similarity_sum = 0.0
        for f1, f2 in zip(files1, files2):
            s1, s2 = f1.size_mb, f2.size_mb
            if s1 > 0 and s2 > 0:
                ratio = min(s1, s2) / max(s1, s2)
                size_similarity_sum += 1.0 if ratio >= 0.95 else ratio * ratio # Smoother penalty for size diff
        similarity_scores['file_size'] = size_similarity_sum / num_files if num_files > 0 else 0.0

        # Folder Name
        folder_name_sim = cached_string_similarity(folder1.folder_name, folder2.folder_name)
        similarity_scores['folder_name'] = folder_name_sim # No thresholding here, let weight handle importance

        # Album Art Hash
        similarity_scores['album_art_hash'] = 1.0 if folder1.album_art_hash and folder1.album_art_hash == folder2.album_art_hash else 0.0

        # Per-file metadata similarities
        filename_sim_sum = 0.0
        title_sim_sum = 0.0
        artist_sim_sum = 0.0
        album_sim_sum = 0.0
        albumartist_sim_sum = 0.0
        duration_sim_sum = 0.0
        additional_metadata_matches = defaultdict(int)

        # Generic name adjustments
        max_generic_filename = max(folder1.generic_filename_score, folder2.generic_filename_score)
        max_generic_title = max(folder1.generic_title_score, folder2.generic_title_score)

        filename_adjustment = (1.0 - (max_generic_filename * config.GENERIC_NAME_REDUCTION_FACTOR)) \
                               if max_generic_filename > config.GENERIC_NAME_SIMILARITY_THRESHOLD else 1.0
        title_adjustment = (1.0 - (max_generic_title * config.GENERIC_NAME_REDUCTION_FACTOR)) \
                           if max_generic_title > config.GENERIC_NAME_SIMILARITY_THRESHOLD else 1.0

        for f1, f2 in zip(files1, files2):
            fn_sim = cached_string_similarity(f1.filename, f2.filename)
            filename_sim_sum += (fn_sim * filename_adjustment) # No base threshold, let adjustment and weight handle

            if f1.title and f2.title:
                 t_sim = cached_string_similarity(f1.title, f2.title)
                 title_sim_sum += (t_sim * title_adjustment)
            elif f1.title or f2.title: # One has title, other doesn't
                 title_sim_sum += 0.0 # Penalize missing metadata

            if f1.artist and f2.artist:
                art_sim = cached_string_similarity(f1.artist, f2.artist)
                artist_sim_sum += art_sim
            elif f1.artist or f2.artist:
                artist_sim_sum += 0.0
            
            if f1.albumartist and f2.albumartist: # May be same as artist, or different (e.g. Various Artists)
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
                 duration_sim_sum += 1.0 if ratio >= 0.97 else (ratio * ratio if ratio > 0.8 else 0.0) # Stricter on duration, but smoother falloff
            elif d1 is not None or d2 is not None : # one has duration, other doesn't
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
                      elif v1 == v2: # For non-string types if any
                            additional_metadata_matches[key] += 1
        
        similarity_scores['filename'] = filename_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['title'] = title_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['artist'] = artist_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['albumartist'] = albumartist_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['album'] = album_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['duration'] = duration_sim_sum / num_files if num_files > 0 else 0.0
        
        additional_metadata_scores = {
            key: count / num_files for key, count in additional_metadata_matches.items()
        }
        similarity_scores['additional_metadata_details'] = additional_metadata_scores

        # --- Calculate Final Weighted Score ---
        weighted_score_sum = 0.0
        current_total_weight = 0.0

        for param, weight in self.weights.items():
             if param in similarity_scores: # Check if score was calculated (e.g. file_hash might be skipped if hashing disabled)
                 weighted_score_sum += similarity_scores[param] * weight
                 current_total_weight += weight
        
        additional_metadata_weighted_sum = sum(
             score * config.SIMILARITY_WEIGHTS['additional_metadata_field_weight']
             for score in additional_metadata_scores.values()
        )
        weighted_score_sum += additional_metadata_weighted_sum
        current_total_weight += len(additional_metadata_scores) * config.SIMILARITY_WEIGHTS['additional_metadata_field_weight']
        
        final_weighted_score = (weighted_score_sum / current_total_weight) * 100 if current_total_weight > 0 else 0.0

        # --- Boost score if metadata is strong but hash/other factors pulled it down ---
        # This applies only if not already identical by hash
        is_identical_by_hash = False # Will be true only if returned early

        # Check if 'file_hash' score exists and is low (or hashing was disabled for this pair)
        file_hash_score_for_boost_check = similarity_scores.get('file_hash', 0.0 if self.enable_hashing else 1.0) # if hashing disabled, don't penalize

        if file_hash_score_for_boost_check < 0.9: # If hash is not very high (or N/A but other factors are strong)
            metadata_strength_score_sum = 0.0
            metadata_strength_weight_sum = 0.0
            # Define important metadata fields for strength calculation
            # Using weights from config to determine importance for this specific calculation
            important_metadata_fields_for_boost = {
                'title': self.weights.get('title', config.SIMILARITY_WEIGHTS.get('title',0)),
                'album': self.weights.get('album', config.SIMILARITY_WEIGHTS.get('album',0)),
                'artist': self.weights.get('artist', config.SIMILARITY_WEIGHTS.get('artist',0)),
                'albumartist': self.weights.get('albumartist', config.SIMILARITY_WEIGHTS.get('albumartist',0)),
                'duration': self.weights.get('duration', config.SIMILARITY_WEIGHTS.get('duration',0)),
                'folder_name': self.weights.get('folder_name', config.SIMILARITY_WEIGHTS.get('folder_name',0)) * 0.5 # Folder name is a bit less critical than internal tags
            }

            for field, weight in important_metadata_fields_for_boost.items():
                if field in similarity_scores and weight > 0:
                    metadata_strength_score_sum += similarity_scores[field] * weight
                    metadata_strength_weight_sum += weight
            
            if metadata_strength_weight_sum > 0:
                avg_metadata_strength = (metadata_strength_score_sum / metadata_strength_weight_sum) # This is a score from 0 to 1

                # If metadata is very strong (e.g., >85%) and the current score is lagging significantly
                if avg_metadata_strength > 0.85 and final_weighted_score < (avg_metadata_strength * 100 * 0.90): # Check if score is <90% of what metadata strength suggests
                    
                    # Calculate a target score based purely on this strong metadata perception
                    target_score_based_on_metadata = avg_metadata_strength * 100
                    
                    # Bridge half the gap to this target score, but don't exceed a cap (e.g., 95%)
                    # to leave room for "perfect 100s" from hash.
                    boost_amount = (target_score_based_on_metadata - final_weighted_score) * 0.6 # Bridge 60% of the gap
                    new_score_before_cap = final_weighted_score + boost_amount
                    
                    final_weighted_score = min(new_score_before_cap, 96.0) # Cap the boosted score
                                        
                    logger.debug(f"Boosting score for '{folder1.path.name}' vs '{folder2.path.name}' due to strong metadata "
                                 f"(avg_meta_strength: {avg_metadata_strength:.2f}, initial_score: {final_weighted_score - boost_amount:.2f}). "
                                 f"New score: {final_weighted_score:.2f}")
        
        if logger.isEnabledFor(logging.DEBUG):
             score_details_list = []
             for k, v_score in sorted(similarity_scores.items()):
                 if k == 'additional_metadata_details':
                     add_meta_dict = v_score if isinstance(v_score, dict) else {}
                     add_meta_str_list = [f"{mk.split(':')[0]}:{mv:.2f}" for mk, mv in sorted(add_meta_dict.items())]
                     if add_meta_str_list: score_details_list.append(f"AddMeta=({', '.join(add_meta_str_list)})")
                 elif isinstance(v_score, float):
                     score_details_list.append(f"{k}={v_score:.2f}")
             
             score_details_str = ", ".join(score_details_list)
             logger.debug(f"Comparison Details ({folder1.path.name} vs {folder2.path.name}): Scores=[{score_details_str}], FinalScore={final_weighted_score:.2f}")

        return FolderComparisonResult(
            folder1_path=folder1.path,
            folder2_path=folder2.path,
            similarity_scores=similarity_scores,
            weighted_score=final_weighted_score,
            is_identical_by_hash=is_identical_by_hash # This will be False here, True only if returned early
        )