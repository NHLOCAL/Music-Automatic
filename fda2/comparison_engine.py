# comparison_engine.py
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from itertools import combinations
from collections import defaultdict
import re # For normalization

import config
from models import FolderInfo, FileInfo, FolderComparisonResult
from utils import cached_string_similarity, normalize_filename_for_sort

logger = logging.getLogger(__name__)

class ComparisonEngine:
    """Compares pairs of FolderInfo objects to determine similarity."""

    def __init__(self, enable_hashing: bool = config.ENABLE_HASHING):
        self.enable_hashing = enable_hashing
        # Dynamically adjust weights based on hashing status
        self.weights = self._get_adjusted_weights(config.SIMILARITY_WEIGHTS, enable_hashing)
        self.total_base_weight = sum(self.weights.values()) # Sum of base parameters
        logger.info(f"Comparison Engine initialized. Hashing enabled: {self.enable_hashing}")
        logger.debug(f"Using similarity weights: {self.weights}")

    def _get_adjusted_weights(self, base_weights: Dict[str, float], hashing_enabled: bool) -> Dict[str, float]:
        """ Adjusts weights, removing hash weight if hashing is disabled. """
        adjusted = base_weights.copy()
        if not hashing_enabled and 'file_hash' in adjusted:
            del adjusted['file_hash']
        # Distribute artist/albumartist weight if one is missing (optional refinement)
        # For now, just use the weights as defined, comparison logic handles missing values.
        return adjusted

    def find_similar_folders(self, all_folders: Dict[Path, FolderInfo]) -> List[FolderComparisonResult]:
        """
        Compares all pairs of folders and returns a list of results for pairs
        exceeding the minimum display threshold.
        """
        logger.info(f"Starting comparison of {len(all_folders)} folders.")
        similar_folder_pairs: List[FolderComparisonResult] = []
        folder_items = list(all_folders.values()) # Convert to list for combinations

        # Use combinations to compare each pair only once
        for folder1, folder2 in combinations(folder_items, 2):
            comparison_result = self.compare_two_folders(folder1, folder2)
            if comparison_result and comparison_result.weighted_score >= config.MINIMAL_DISPLAY_SIMILARITY:
                similar_folder_pairs.append(comparison_result)
                logger.debug(f"Found potential match: {folder1.path.name} vs {folder2.path.name} -> Score: {comparison_result.weighted_score:.2f}%")


        # Sort results by weighted score, descending
        similar_folder_pairs.sort(key=lambda x: x.weighted_score, reverse=True)

        logger.info(f"Comparison complete. Found {len(similar_folder_pairs)} pairs above display threshold ({config.MINIMAL_DISPLAY_SIMILARITY}%).")
        return similar_folder_pairs


    def compare_two_folders(self, folder1: FolderInfo, folder2: FolderInfo) -> Optional[FolderComparisonResult]:
        """Calculates the similarity between two specific folders."""

        # --- Pre-checks for quick rejection ---
        # 1. Different number of files (unless allowing partial matches - not implemented here)
        if len(folder1.files) != len(folder2.files):
            logger.debug(f"Skipping comparison: Different file counts ({len(folder1.files)} vs {len(folder2.files)}) for {folder1.path.name} and {folder2.path.name}")
            return None

        # 2. Significantly different album names (if both exist)
        # Use folder level unique albums if available and consistent
        album1_repr = next(iter(folder1.unique_albums), None) if len(folder1.unique_albums) == 1 else None
        album2_repr = next(iter(folder2.unique_albums), None) if len(folder2.unique_albums) == 1 else None
        if album1_repr and album2_repr:
             album_similarity = cached_string_similarity(album1_repr, album2_repr)
             # Use a threshold lower than the display threshold but high enough to filter obvious mismatches
             if album_similarity < 0.5:
                 logger.debug(f"Skipping comparison: Low album name similarity ({album_similarity:.2f}) for {folder1.path.name} and {folder2.path.name}")
                 return None


        # --- Detailed Comparison ---
        similarity_scores: Dict[str, float] = {}
        is_identical_by_hash = False

        # Sort files within each folder consistently for pairwise comparison
        # Use normalized filename (lowercase, spaces standardized)
        files1 = sorted(folder1.files, key=lambda x: normalize_filename_for_sort(x.filename))
        files2 = sorted(folder2.files, key=lambda x: normalize_filename_for_sort(x.filename))
        num_files = len(files1) # Should be same as len(files2)

        # 1. File Hash Similarity (if enabled and hashes are present)
        if self.enable_hashing and folder1.file_hashes_present and folder2.file_hashes_present:
            hash_match_count = sum(1 for f1, f2 in zip(files1, files2) if f1.file_hash == f2.file_hash)
            similarity_scores['file_hash'] = hash_match_count / num_files if num_files > 0 else 0.0
            # Optimization: If all hashes match, consider them identical and assign max score
            if similarity_scores['file_hash'] == 1.0:
                 logger.info(f"Folders identical by hash: {folder1.path.name} and {folder2.path.name}")
                 is_identical_by_hash = True
                 # Assign perfect score components where applicable
                 for key in self.weights:
                      similarity_scores[key] = 1.0
                 weighted_score = 100.0 # Max score
                 # No need to calculate other scores if identical by hash
                 return FolderComparisonResult(
                     folder1_path=folder1.path,
                     folder2_path=folder2.path,
                     similarity_scores=similarity_scores,
                     weighted_score=weighted_score,
                     is_identical_by_hash=True
                 )
        elif self.enable_hashing:
             # If hashing is enabled but not all files have hashes, mark score as 0 or indicate issue
             similarity_scores['file_hash'] = 0.0
             logger.debug(f"Hashing enabled, but not all files have hashes for pair: {folder1.path.name}, {folder2.path.name}")


        # --- Calculate other similarity metrics (only if not identical by hash) ---

        # 2. File Size Similarity (Pairwise)
        size_similarity_sum = 0.0
        for f1, f2 in zip(files1, files2):
            s1, s2 = f1.size_mb, f2.size_mb
            if s1 > 0 and s2 > 0:
                # Score 1 if sizes are within 5% of each other, 0 otherwise (strict)
                ratio = min(s1, s2) / max(s1, s2)
                size_similarity_sum += 1.0 if ratio >= 0.95 else 0.0
            # If one size is 0, similarity is 0 for that pair
        similarity_scores['file_size'] = size_similarity_sum / num_files if num_files > 0 else 0.0

        # 3. Folder Name Similarity
        # Use folder name from FolderInfo directly
        folder_name_sim = cached_string_similarity(folder1.folder_name, folder2.folder_name)
        similarity_scores['folder_name'] = folder_name_sim if folder_name_sim >= config.BASE_STRING_SIMILARITY_THRESHOLD else 0.0

        # 4. Album Art Hash Similarity
        similarity_scores['album_art_hash'] = 1.0 if folder1.album_art_hash and folder1.album_art_hash == folder2.album_art_hash else 0.0

        # --- Pairwise File Attribute Similarities (Filename, Title, Artist, Album, Duration) ---
        filename_sim_sum = 0.0
        title_sim_sum = 0.0
        artist_sim_sum = 0.0
        album_sim_sum = 0.0
        albumartist_sim_sum = 0.0
        duration_sim_sum = 0.0
        additional_metadata_matches = defaultdict(int) # Count matches for other tags

        # Apply adjustments for generic names
        max_generic_filename = max(folder1.generic_filename_score, folder2.generic_filename_score)
        max_generic_title = max(folder1.generic_title_score, folder2.generic_title_score)

        filename_adjustment = (1.0 - (max_generic_filename * config.GENERIC_NAME_REDUCTION_FACTOR)) \
                               if max_generic_filename > config.GENERIC_NAME_SIMILARITY_THRESHOLD else 1.0
        title_adjustment = (1.0 - (max_generic_title * config.GENERIC_NAME_REDUCTION_FACTOR)) \
                           if max_generic_title > config.GENERIC_NAME_SIMILARITY_THRESHOLD else 1.0


        for f1, f2 in zip(files1, files2):
            # Filename
            fn_sim = cached_string_similarity(f1.filename, f2.filename)
            # Use stem for comparison? No, use full name but adjust score based on folder's generic score
            filename_sim_sum += (fn_sim * filename_adjustment) if fn_sim >= config.BASE_STRING_SIMILARITY_THRESHOLD else 0.0

            # Title
            if f1.title and f2.title:
                 t_sim = cached_string_similarity(f1.title, f2.title)
                 title_sim_sum += (t_sim * title_adjustment) if t_sim >= config.BASE_STRING_SIMILARITY_THRESHOLD else 0.0

            # Artist
            if f1.artist and f2.artist:
                art_sim = cached_string_similarity(f1.artist, f2.artist)
                artist_sim_sum += art_sim if art_sim >= config.BASE_STRING_SIMILARITY_THRESHOLD else 0.0

             # AlbumArtist
            if f1.albumartist and f2.albumartist:
                aa_sim = cached_string_similarity(f1.albumartist, f2.albumartist)
                albumartist_sim_sum += aa_sim if aa_sim >= config.BASE_STRING_SIMILARITY_THRESHOLD else 0.0

            # Album
            if f1.album and f2.album:
                alb_sim = cached_string_similarity(f1.album, f2.album)
                album_sim_sum += alb_sim if alb_sim >= config.BASE_STRING_SIMILARITY_THRESHOLD else 0.0

            # Duration
            d1, d2 = f1.duration, f2.duration
            if d1 is not None and d2 is not None and d1 > 0 and d2 > 0:
                 # Similar if within 5% (or absolute diff < 5s?) Let's use ratio for consistency.
                 ratio = min(d1, d2) / max(d1, d2)
                 duration_sim_sum += 1.0 if ratio >= 0.95 else 0.0 # Strict match for duration

            # Additional Metadata (compare common keys in all_tags)
            tags1 = f1.all_tags
            tags2 = f2.all_tags
            # Exclude already compared primary fields and potentially problematic ones
            exclude_keys = {'title', 'artist', 'album', 'albumartist', 'duration', 'bitrate', 'lyrics', 'filename', 'filepath'}
            common_keys = (set(tags1.keys()) & set(tags2.keys())) - exclude_keys
            for key in common_keys:
                 v1, v2 = tags1.get(key), tags2.get(key)
                 # Simple exact match (case-insensitive for strings)
                 if v1 and v2:
                      if isinstance(v1, str) and isinstance(v2, str):
                           if v1.strip().lower() == v2.strip().lower():
                                additional_metadata_matches[key] += 1
                      elif v1 == v2: # For non-string types
                            additional_metadata_matches[key] += 1


        # Calculate average scores for pairwise comparisons
        similarity_scores['filename'] = filename_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['title'] = title_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['artist'] = artist_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['albumartist'] = albumartist_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['album'] = album_sim_sum / num_files if num_files > 0 else 0.0
        similarity_scores['duration'] = duration_sim_sum / num_files if num_files > 0 else 0.0

        # Calculate score from additional metadata matches
        # Score is based on the proportion of files where a specific tag matches
        additional_metadata_scores = {
            key: count / num_files for key, count in additional_metadata_matches.items()
        }
        # Store the detailed scores for potential debugging/display
        similarity_scores['additional_metadata_details'] = additional_metadata_scores
        # Calculate a single representative score for weighting (average score across matching fields?)
        # Or add weight for *each* matching field? Let's weight each matching field.
        additional_metadata_weighted_sum = sum(
             score * config.SIMILARITY_WEIGHTS['additional_metadata_field_weight']
             for score in additional_metadata_scores.values()
        )

        # --- Calculate Final Weighted Score ---
        weighted_score_sum = 0.0
        current_total_weight = 0.0

        # Sum weighted scores from base parameters
        for param, weight in self.weights.items():
             # Special handling for artist/albumartist: use the max score if one is missing, or average?
             # Let's use the score directly for whichever field is present, weight applies individually.
             if param in similarity_scores:
                 weighted_score_sum += similarity_scores[param] * weight
                 current_total_weight += weight

        # Add the weighted sum from additional metadata fields
        weighted_score_sum += additional_metadata_weighted_sum
        # Add the weights used for additional metadata to the total weight
        current_total_weight += len(additional_metadata_scores) * config.SIMILARITY_WEIGHTS['additional_metadata_field_weight']


        # Normalize the final score to be out of 100
        final_weighted_score = (weighted_score_sum / current_total_weight) * 100 if current_total_weight > 0 else 0.0

        # Log detailed scores at DEBUG level
        if logger.isEnabledFor(logging.DEBUG):
             score_details = ", ".join([f"{k}: {v:.2f}" for k, v in similarity_scores.items() if k != 'additional_metadata_details'])
             add_meta_details = similarity_scores.get('additional_metadata_details', {})
             add_meta_str = ", ".join([f"{k}_add: {v:.2f}" for k, v in add_meta_details.items()])
             logger.debug(f"Comparison Details ({folder1.path.name} vs {folder2.path.name}): Scores=[{score_details}], AddMeta=[{add_meta_str}], FinalScore={final_weighted_score:.2f}")


        return FolderComparisonResult(
            folder1_path=folder1.path,
            folder2_path=folder2.path,
            similarity_scores=similarity_scores, # Store detailed scores
            weighted_score=final_weighted_score,
            is_identical_by_hash=False # Already handled the True case
        )

