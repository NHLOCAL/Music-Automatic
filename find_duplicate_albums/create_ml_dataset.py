# File: create_ml_dataset.py
import argparse
import logging
from pathlib import Path
import random
import time
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set, FrozenSet
from itertools import combinations
from sklearn.model_selection import train_test_split # Required for splitting
import numpy as np # Added for numerical operations (std, mean, etc.)
import re # Added for regex in word jaccard

from music_dup_lib import config as app_config
from music_dup_lib import utils
from music_dup_lib.models import FolderInfo, FolderComparisonResult, FileInfo
from music_dup_lib.core.data_store import DataStore
from music_dup_lib.core.comparison_engine import ComparisonEngine

try:
    from music_dup_lib.external.gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
    if not GEMINI_AVAILABLE:
        logging.warning(f"Gemini API Key ({app_config.GEMINI_API_KEY_ENV_VAR}) not found. Gemini labeling will be limited.")
except ImportError:
    logging.warning("Could not import GeminiAnalyzer. Gemini labeling disabled.")
    GeminiAnalyzer = None
    GEMINI_AVAILABLE = False

TRAIN_DATASET_FILE = Path("similarity_model/data/album_pair_features_train.csv")
TEST_DATASET_FILE = Path("similarity_model/data/album_pair_features_test.csv")
TEST_SPLIT_RATIO = 0.2
DATASET_RANDOM_STATE = 42

HIGH_CERTAINTY_THRESHOLD = 85.0
LOW_CERTAINTY_THRESHOLD = 35.0

DEFINITE_DUPLICATE_LABEL = 98.0
DEFINITE_DIFFERENT_LABEL = 2.0

MAX_LOW_SIM_PAIRS_FROM_SAMPLING = 5000
MAX_GEMINI_CANDIDATES_FROM_SAMPLING = 2000

logger = logging.getLogger("DatasetBuilder")

def calculate_jaccard_index(set1: Set[str], set2: Set[str]) -> float:
    if not set1 and not set2: return 1.0
    intersection_size = len(set1.intersection(set2))
    union_size = len(set1.union(set2))
    return intersection_size / union_size if union_size > 0 else 0.0

def calculate_word_jaccard_index(str1: Optional[str], str2: Optional[str]) -> float:
    if not str1 and not str2: return 1.0
    if not str1 or not str2: return 0.0

    words1 = set(re.findall(r'\w+', str1.lower()))
    words2 = set(re.findall(r'\w+', str2.lower()))
    return calculate_jaccard_index(words1, words2)

def _calculate_folder_stats(folder_info: FolderInfo) -> Dict[str, float]:
    stats: Dict[str, Optional[float]] = {
        "avg_duration": None, "std_duration": None, "min_duration": None, "max_duration": None, "total_duration": None,
        "std_bitrate": None, "min_bitrate": None, "max_bitrate": None,
        # folder_info.avg_bitrate is used directly
    }
    if not folder_info.files:
        # Fill with 0.0 if no files, for consistency
        return {k: 0.0 for k in stats.keys()}

    durations = [f.duration for f in folder_info.files if f.duration is not None and f.duration > 0]
    bitrates = [f.bitrate for f in folder_info.files if f.bitrate is not None and f.bitrate > 0]

    if durations:
        stats["avg_duration"] = float(np.mean(durations))
        stats["std_duration"] = float(np.std(durations)) if len(durations) > 1 else 0.0
        stats["min_duration"] = float(np.min(durations))
        stats["max_duration"] = float(np.max(durations))
        stats["total_duration"] = float(np.sum(durations))
    
    if bitrates:
        stats["std_bitrate"] = float(np.std(bitrates)) if len(bitrates) > 1 else 0.0
        stats["min_bitrate"] = float(np.min(bitrates))
        stats["max_bitrate"] = float(np.max(bitrates))

    # Ensure all stat keys exist and are floats (0.0 if None)
    final_stats: Dict[str, float] = {}
    for key in ["avg_duration", "std_duration", "min_duration", "max_duration", "total_duration",
                "std_bitrate", "min_bitrate", "max_bitrate"]:
        final_stats[key] = stats.get(key, 0.0) if stats.get(key) is not None else 0.0
            
    return final_stats

def extract_features_for_pair(
    folder1_info: FolderInfo,
    folder2_info: FolderInfo,
    comparison_result: Optional[FolderComparisonResult]
) -> Optional[Dict[str, any]]:
    features = {}
    if not folder1_info or not folder2_info: return None

    # --- Basic FolderInfo stats (already somewhat present) ---
    f1_avg_bitrate = folder1_info.avg_bitrate if folder1_info.avg_bitrate is not None else 0.0
    f2_avg_bitrate = folder2_info.avg_bitrate if folder2_info.avg_bitrate is not None else 0.0
    features['f1_avg_bitrate'] = f1_avg_bitrate # Re-adding for individual assessment
    features['f2_avg_bitrate'] = f2_avg_bitrate # Re-adding
    features['diff_avg_bitrate'] = abs(f1_avg_bitrate - f2_avg_bitrate)
    
    features['jaccard_unique_artists'] = calculate_jaccard_index(folder1_info.unique_artists, folder2_info.unique_artists)
    features['jaccard_unique_albums'] = calculate_jaccard_index(folder1_info.unique_albums, folder2_info.unique_albums)
    
    f1_gen_fname_score = folder1_info.generic_filename_score if folder1_info.generic_filename_score is not None else 0.0
    f2_gen_fname_score = folder2_info.generic_filename_score if folder2_info.generic_filename_score is not None else 0.0
    features['f1_generic_filename_score'] = f1_gen_fname_score
    features['f2_generic_filename_score'] = f2_gen_fname_score
    features['diff_generic_filename_score'] = abs(f1_gen_fname_score - f2_gen_fname_score)
    
    f1_gen_title_score = folder1_info.generic_title_score if folder1_info.generic_title_score is not None else 0.0
    f2_gen_title_score = folder2_info.generic_title_score if folder2_info.generic_title_score is not None else 0.0
    features['f1_generic_title_score'] = f1_gen_title_score
    features['f2_generic_title_score'] = f2_gen_title_score
    features['diff_generic_title_score'] = abs(f1_gen_title_score - f2_gen_title_score)

    # --- New: Detailed file stats (duration, bitrate variations) ---
    folder1_stats = _calculate_folder_stats(folder1_info)
    folder2_stats = _calculate_folder_stats(folder2_info)

    for stat_key in ["avg_duration", "std_duration", "min_duration", "max_duration", "total_duration",
                     "std_bitrate", "min_bitrate", "max_bitrate"]:
        s1_val = folder1_stats[stat_key]
        s2_val = folder2_stats[stat_key]
        features[f'f1_{stat_key}'] = s1_val
        features[f'f2_{stat_key}'] = s2_val
        features[f'diff_{stat_key}'] = abs(s1_val - s2_val)
        if stat_key == "total_duration":
            if s1_val == 0 and s2_val == 0:
                features['ratio_total_duration'] = 1.0
            else:
                features['ratio_total_duration'] = min(s1_val, s2_val) / max(1.0, s1_val, s2_val)
    
    # --- New: Parent folder name features ---
    f1_parent_name = folder1_info.parent_folder_name
    f2_parent_name = folder2_info.parent_folder_name
    features['f1_parent_folder_name_len'] = len(f1_parent_name) if f1_parent_name else 0
    features['f2_parent_folder_name_len'] = len(f2_parent_name) if f2_parent_name else 0
    features['diff_parent_folder_name_len'] = abs(features['f1_parent_folder_name_len'] - features['f2_parent_folder_name_len'])
    features['parent_folder_names_match'] = 1.0 if f1_parent_name and f1_parent_name == f2_parent_name else 0.0
    features['jaccard_parent_folder_names'] = calculate_word_jaccard_index(f1_parent_name, f2_parent_name)

    # --- New: Quality score and other FolderInfo ratios ---
    quality_related_fields = {
        'quality_score': (folder1_info.quality_score, folder2_info.quality_score),
        'hebrew_metadata_ratio': (folder1_info.hebrew_metadata_ratio, folder2_info.hebrew_metadata_ratio),
        'metadata_completeness_ratio': (folder1_info.metadata_completeness_ratio, folder2_info.metadata_completeness_ratio),
        'lossless_ratio': (folder1_info.lossless_ratio, folder2_info.lossless_ratio),
        'lyrics_ratio': (folder1_info.lyrics_ratio, folder2_info.lyrics_ratio),
    }
    for field, (val1, val2) in quality_related_fields.items():
        v1 = val1 if val1 is not None else 0.0
        v2 = val2 if val2 is not None else 0.0
        features[f'f1_{field}'] = v1
        features[f'f2_{field}'] = v2
        features[f'diff_{field}'] = abs(v1 - v2)

    # --- Features from ComparisonResult (if available) ---
    if comparison_result:
        sim_scores = comparison_result.similarity_scores
        comp_feature_keys = [
            'file_hash', 'file_size', 'filename', 'title', 'album', 
            'artist', 'albumartist', 'folder_name', 'album_art_hash', 'duration'
        ]
        for key in comp_feature_keys:
            features[f'comp_{key}_similarity'] = sim_scores.get(key, 0.0)
        
        add_meta_details = sim_scores.get('additional_metadata_details', {})
        if add_meta_details:
            features['comp_avg_add_meta_similarity'] = sum(add_meta_details.values()) / len(add_meta_details) if add_meta_details else 0.0
            features['comp_count_high_add_meta_similarity'] = sum(1 for v in add_meta_details.values() if v >= 0.8)
            # New: unpack additional_metadata_details into separate features
            for meta_key, meta_sim_score in add_meta_details.items():
                # Sanitize key for feature name (e.g. replace spaces, non-alphanum with underscore)
                safe_meta_key = re.sub(r'[^a-zA-Z0-9_]', '_', meta_key.lower())
                features[f'comp_add_meta_sim_{safe_meta_key}'] = meta_sim_score
        else:
            features['comp_avg_add_meta_similarity'] = 0.0
            features['comp_count_high_add_meta_similarity'] = 0.0
            # If no add_meta_details, the specific comp_add_meta_sim_<key> features won't be added,
            # and will be handled by final_df.fillna(0.0) later.
    else:
        # If no comparison_result, zero out all comparison-derived features
        comp_keys_to_zero = [
            'comp_file_hash_similarity', 'comp_file_size_similarity', 'comp_filename_similarity',
            'comp_title_similarity', 'comp_album_similarity', 'comp_artist_similarity',
            'comp_albumartist_similarity', 'comp_folder_name_similarity', 'comp_album_art_hash_similarity',
            'comp_duration_similarity',
            'comp_avg_add_meta_similarity', 'comp_count_high_add_meta_similarity'
        ]
        # Also zero out potential comp_add_meta_sim_<key> features if they were expected.
        # This is trickier as we don't know all possible keys beforehand.
        # However, if comparison_result is None, they wouldn't have been added anyway.
        # The final_df.fillna(0.0) will handle any columns that exist in some rows but not others.
        for k_comp in comp_keys_to_zero:
            features[k_comp] = 0.0
    return features

def _file_info_from_dict(data: Dict[str, any]) -> FileInfo:
    return FileInfo(
        filename=data.get("filename", "unknown.mp3"), filepath=Path(data.get("filepath", "unknown.mp3")),
        extension=data.get("extension", ".mp3"), size_mb=float(data.get("size_mb", 0.0)),
        file_hash=data.get("file_hash"),
        duration=float(data.get("duration", 0.0)) if data.get("duration") is not None else None,
        bitrate=int(data.get("bitrate",0)) if data.get("bitrate") is not None else None,
        title=data.get("title"), artist=data.get("artist"), album=data.get("album"),
        albumartist=data.get("albumartist"), all_tags=data.get("all_tags", {}),
        metadata_complete=bool(data.get("metadata_complete", False)),
        has_lyrics=bool(data.get("has_lyrics", False)),
        is_lossless=bool(data.get("is_lossless", False))
    )

def _folder_info_from_dict(path_str: str, folder_dict: Dict[str, any]) -> FolderInfo:
    # Ensure all expected fields by FolderInfo are present, even if None
    return FolderInfo(
        path=Path(path_str),
        folder_name=folder_dict.get('folder_name', Path(path_str).name),
        parent_folder_name=folder_dict.get('parent_folder_name', Path(path_str).parent.name),
        files=[_file_info_from_dict(f_dict) for f_dict in folder_dict.get('files',[])],
        album_art_hash=folder_dict.get('album_art_hash'),
        file_hashes_present=folder_dict.get('file_hashes_present', False),
        avg_bitrate=folder_dict.get('avg_bitrate', 0.0),
        unique_artists=set(folder_dict.get('unique_artists', [])),
        unique_albums=set(folder_dict.get('unique_albums', [])),
        generic_filename_score=folder_dict.get('generic_filename_score', 0.0),
        generic_title_score=folder_dict.get('generic_title_score', 0.0),
        quality_score=folder_dict.get('quality_score'), # Will be None if not in cache
        quality_breakdown=folder_dict.get('quality_breakdown', {}),
        hebrew_metadata_ratio=folder_dict.get('hebrew_metadata_ratio', 0.0),
        metadata_completeness_ratio=folder_dict.get('metadata_completeness_ratio', 0.0),
        lossless_ratio=folder_dict.get('lossless_ratio', 0.0),
        lyrics_ratio=folder_dict.get('lyrics_ratio', 0.0)
    )

def build_dataset(args):
    utils.setup_logging(args.log_level, app_config.LOGS_DIR / "dataset_builder")
    logger.info("Starting dataset construction for ML model.")

    data_store = DataStore()
    comparison_engine = ComparisonEngine(enable_hashing=app_config.ENABLE_HASHING)
    gemini_analyzer = None
    gemini_actually_available = GEMINI_AVAILABLE and not args.disable_gemini
    if gemini_actually_available:
        try:
            gemini_analyzer = GeminiAnalyzer()
            logger.info("Gemini Analyzer initialized.")
        except ValueError as e:
            logger.error(f"Failed to initialize Gemini Analyzer: {e}. Gemini labeling will be skipped.")
            gemini_actually_available = False
    else:
        logger.warning("Gemini analysis is disabled by flag or due to API key/module issues.")

    all_music_folders: Dict[Path, FolderInfo] = {}
    cached_music_data = data_store.load_data()
    if not cached_music_data:
        logger.error("Music data cache (music_data.json) is empty. Run main scanner first.")
        return
    for path_str, folder_data_dict in cached_music_data.items():
        try:
            all_music_folders[Path(path_str)] = _folder_info_from_dict(path_str, folder_data_dict)
        except Exception as e:
            logger.error(f"Error parsing folder data for {path_str} from cache: {e}", exc_info=True)
    logger.info(f"Loaded {len(all_music_folders)} FolderInfo objects.")
    if not all_music_folders: return

    existing_comparison_results_str_keys: Dict[FrozenSet[str], FolderComparisonResult] = data_store.load_comparison_results()
    logger.info(f"Loaded {len(existing_comparison_results_str_keys)} existing comparison results from cache.")

    dataset_rows: List[Dict[str, any]] = []
    processed_pairs: Set[FrozenSet[str]] = set()
    gemini_candidates_new: List[Tuple[FolderInfo, FolderInfo, FolderComparisonResult]] = []

    logger.info("Processing pairs from existing comparison cache...")
    for pair_key_str, comp_res in existing_comparison_results_str_keys.items():
        f1p, f2p = comp_res.folder1_path, comp_res.folder2_path 

        if f1p not in all_music_folders or f2p not in all_music_folders:
            logger.warning(f"FolderInfo missing for pair from cache: {f1p.name}, {f2p.name}. Skipping.")
            processed_pairs.add(pair_key_str)
            continue

        folder1 = all_music_folders[f1p]
        folder2 = all_music_folders[f2p]

        if len(folder1.files) != len(folder2.files) and app_config.FILTER_PAIRS_BY_FILE_COUNT_FOR_ML:
            logger.debug(f"Skipping cached pair {f1p.name}-{f2p.name} due to different file counts "
                         f"({len(folder1.files)} vs {len(folder2.files)}) and "
                         f"FILTER_PAIRS_BY_FILE_COUNT_FOR_ML is True. Not adding to dataset.")
            processed_pairs.add(pair_key_str)
            continue

        processed_pairs.add(pair_key_str)

        current_algorithmic_score = comp_res.weighted_score
        label = None
        label_source = "unknown"

        if current_algorithmic_score >= HIGH_CERTAINTY_THRESHOLD:
            label = DEFINITE_DUPLICATE_LABEL
            label_source = "algo_high_certainty_cached"
        elif current_algorithmic_score < LOW_CERTAINTY_THRESHOLD:
            label = DEFINITE_DIFFERENT_LABEL
            label_source = "algo_low_certainty_cached"
        else:
            if comp_res.gemini_similarity_score is not None and comp_res.gemini_error is None:
                label = comp_res.gemini_similarity_score
                label_source = "gemini_cached"
            elif gemini_actually_available:
                gemini_candidates_new.append((folder1, folder2, comp_res))
            else:
                label_source = "gemini_range_no_gemini_available"
                logger.debug(f"Pair {f1p.name}-{f2p.name} in Gemini range but Gemini unavailable and no cached score. Skipping labeling.")

        if label is not None:
            features = extract_features_for_pair(folder1, folder2, comp_res)
            if features:
                features['target_label'] = label
                features['label_source'] = label_source
                features['folder1_path_id'] = str(f1p)
                features['folder2_path_id'] = str(f2p)
                dataset_rows.append(features)

    logger.info("Sampling and processing additional pairs...")
    all_folder_paths_list = list(all_music_folders.keys())
    num_total_folders = len(all_folder_paths_list)

    max_sampling_attempts = max( (MAX_LOW_SIM_PAIRS_FROM_SAMPLING + MAX_GEMINI_CANDIDATES_FROM_SAMPLING) * 20, num_total_folders * 5 )
    if num_total_folders < 2: max_sampling_attempts = 0

    low_sim_pairs_count = sum(1 for r in dataset_rows if r['label_source'].startswith("algo_low"))
    new_gemini_candidates_count = len(gemini_candidates_new)

    for attempt in range(max_sampling_attempts):
        if low_sim_pairs_count >= MAX_LOW_SIM_PAIRS_FROM_SAMPLING and \
           new_gemini_candidates_count >= MAX_GEMINI_CANDIDATES_FROM_SAMPLING:
            logger.info("Reached sampling limits for low similarity and new Gemini candidates.")
            break

        idx1, idx2 = random.sample(range(num_total_folders), 2)
        f1p_path_obj, f2p_path_obj = all_folder_paths_list[idx1], all_folder_paths_list[idx2]

        current_pair_key_str = frozenset({str(f1p_path_obj), str(f2p_path_obj)})

        if current_pair_key_str in processed_pairs:
            continue
        processed_pairs.add(current_pair_key_str)

        folder1 = all_music_folders[f1p_path_obj]
        folder2 = all_music_folders[f2p_path_obj]

        if len(folder1.files) != len(folder2.files) and app_config.FILTER_PAIRS_BY_FILE_COUNT_FOR_ML:
            logger.debug(f"Skipping sampled pair {f1p_path_obj.name}-{f2p_path_obj.name} due to different file counts "
                         f"({len(folder1.files)} vs {len(folder2.files)}) and "
                         f"FILTER_PAIRS_BY_FILE_COUNT_FOR_ML is True. Not adding to dataset.")
            continue

        fresh_comp_res = comparison_engine.compare_two_folders(folder1, folder2)
        label = None
        label_source = "unknown_sampled"

        if not fresh_comp_res: # Should ideally not happen if folders are valid
            if low_sim_pairs_count < MAX_LOW_SIM_PAIRS_FROM_SAMPLING:
                label = DEFINITE_DIFFERENT_LABEL
                label_source = "algo_no_comparison_result_sampled"
                low_sim_pairs_count += 1
        else:
            current_algorithmic_score = fresh_comp_res.weighted_score
            if current_algorithmic_score >= HIGH_CERTAINTY_THRESHOLD:
                label = DEFINITE_DUPLICATE_LABEL
                label_source = "algo_high_certainty_sampled"
            elif current_algorithmic_score < LOW_CERTAINTY_THRESHOLD:
                if low_sim_pairs_count < MAX_LOW_SIM_PAIRS_FROM_SAMPLING:
                    label = DEFINITE_DIFFERENT_LABEL
                    label_source = "algo_low_certainty_sampled"
                    low_sim_pairs_count += 1
            else: # In Gemini range
                if gemini_actually_available and new_gemini_candidates_count < MAX_GEMINI_CANDIDATES_FROM_SAMPLING:
                    gemini_candidates_new.append((folder1, folder2, fresh_comp_res))
                    # Add to cache so Gemini results can be saved later
                    existing_comparison_results_str_keys[current_pair_key_str] = fresh_comp_res
                    new_gemini_candidates_count += 1
                else:
                    label_source = "gemini_range_no_gemini_available_sampled"
                    logger.debug(f"Sampled pair {f1p_path_obj.name}-{f2p_path_obj.name} in Gemini range but Gemini unavailable/limit reached. Skipping.")

        if label is not None:
            features = extract_features_for_pair(folder1, folder2, fresh_comp_res)
            if features:
                features['target_label'] = label
                features['label_source'] = label_source
                features['folder1_path_id'] = str(f1p_path_obj)
                features['folder2_path_id'] = str(f2p_path_obj)
                dataset_rows.append(features)

        if attempt % 1000 == 0 and attempt > 0:
            logger.info(f"Sampling: Attempt {attempt}/{max_sampling_attempts}. "
                        f"Dataset rows: {len(dataset_rows)}. Low_sim_added: {low_sim_pairs_count}. "
                        f"New Gemini candidates: {new_gemini_candidates_count}.")

    if gemini_actually_available and gemini_analyzer and gemini_candidates_new:
        logger.info(f"Running Gemini analysis on {len(gemini_candidates_new)} new candidate pairs...")
        gemini_api_calls = 0
        for f1_info, f2_info, comp_res_for_gemini in gemini_candidates_new:
            # Re-check file count condition for Gemini candidates as it's critical for some Gemini prompts
            if len(f1_info.files) != len(f2_info.files) and app_config.FILTER_PAIRS_BY_FILE_COUNT_FOR_ML_GEMINI:
                logger.warning(f"Skipping Gemini for {f1_info.path.name} vs {f2_info.path.name} "
                               f"due to different file counts ({len(f1_info.files)} vs {len(f2_info.files)}) "
                               f"and FILTER_PAIRS_BY_FILE_COUNT_FOR_ML_GEMINI is True.")
                continue

            f1p_path_obj, f2p_path_obj = f1_info.path, f2_info.path
            algo_score = comp_res_for_gemini.weighted_score
            logger.info(f"Gemini ({gemini_api_calls+1}/{len(gemini_candidates_new)}): {f1p_path_obj.name} vs {f2p_path_obj.name} (Algo: {algo_score:.2f})")

            time.sleep(app_config.GEMINI_API_DELAY_SECONDS) # Respect API rate limits
            verdict, gemini_sim_score, reason_or_error = gemini_analyzer.analyze_pair(f1_info, f2_info, algo_score)
            gemini_api_calls += 1

            label = None
            label_source = "gemini_new_run_failed"
            
            current_pair_key_str_for_gemini = frozenset({str(f1p_path_obj), str(f2p_path_obj)})

            # Update the comparison result object in existing_comparison_results_str_keys
            # This ensures that if we save the cache, it has the Gemini info.
            # It might be a new comp_res (from sampling) or an existing one (from cache but without Gemini score)
            target_comp_res_obj = existing_comparison_results_str_keys.get(current_pair_key_str_for_gemini)
            if not target_comp_res_obj: # Should not happen if logic is correct
                logger.error(f"Consistency issue: comp_res object not found in cache for Gemini pair {f1p_path_obj} - {f2p_path_obj}")
                target_comp_res_obj = comp_res_for_gemini # Fallback to the one passed in

            if gemini_sim_score is not None and ("ERROR" not in reason_or_error.upper() if reason_or_error else True and verdict is not None):
                label = gemini_sim_score
                label_source = "gemini_new_run_success"
                target_comp_res_obj.gemini_verdict = verdict
                target_comp_res_obj.gemini_similarity_score = gemini_sim_score
                target_comp_res_obj.gemini_reason = reason_or_error
                target_comp_res_obj.gemini_error = None
            else:
                logger.warning(f"Gemini analysis failed or returned invalid data for {f1p_path_obj.name} vs {f2p_path_obj.name}. "
                               f"Error/Reason: {reason_or_error}. This pair will not be added with Gemini label.")
                target_comp_res_obj.gemini_error = reason_or_error
                target_comp_res_obj.gemini_verdict = None
                target_comp_res_obj.gemini_similarity_score = None
                target_comp_res_obj.gemini_reason = None
            
            existing_comparison_results_str_keys[current_pair_key_str_for_gemini] = target_comp_res_obj


            if label is not None:
                features = extract_features_for_pair(f1_info, f2_info, target_comp_res_obj) # Use updated comp_res
                if features:
                    features['target_label'] = label
                    features['label_source'] = label_source
                    features['folder1_path_id'] = str(f1p_path_obj)
                    features['folder2_path_id'] = str(f2p_path_obj)
                    dataset_rows.append(features)
    else:
        logger.info("Skipping new Gemini runs (Gemini unavailable, analyzer init failed, or no new candidates).")

    if not dataset_rows:
        logger.warning("No data rows were generated for the dataset. Exiting.")
        if args.update_comparison_cache and existing_comparison_results_str_keys:
            logger.info(f"Updating comparison_results_cache.json with {len(existing_comparison_results_str_keys)} entries (even if dataset is empty)...")
            data_store.save_comparison_results(existing_comparison_results_str_keys)
            logger.info("Comparison cache updated.")
        return

    final_df = pd.DataFrame(dataset_rows)
    final_df.dropna(subset=['target_label'], inplace=True) 
    final_df.fillna(0.0, inplace=True) 

    logger.info(f"Total dataset rows before split: {final_df.shape[0]}, columns: {final_df.shape[1]}.")
    if final_df.shape[0] > 0:
        logger.info(f"Columns: {final_df.columns.tolist()}")
        logger.info(f"Target label statistics (full dataset):\n{final_df['target_label'].describe(percentiles=[.02, .1, .25, .5, .75, .9, .98])}")
        logger.info(f"Label source distribution (full dataset):\n{final_df['label_source'].value_counts(dropna=False)}")

    if final_df.shape[0] < 2:
        logger.warning("Dataset has less than 2 rows. Cannot split into training and testing sets. Saving all to train file if any.")
        if final_df.shape[0] == 1:
            try:
                TRAIN_DATASET_FILE.parent.mkdir(parents=True, exist_ok=True)
                final_df.to_csv(TRAIN_DATASET_FILE, index=False, encoding='utf-8')
                logger.info(f"Single row dataset saved to: {TRAIN_DATASET_FILE}")
            except Exception as e:
                logger.error(f"Error saving single row dataset to {TRAIN_DATASET_FILE}: {e}", exc_info=True)
        else:
             logger.info("Dataset is empty, no files will be saved.")
    else:
        logger.info(f"Splitting dataset into training ({1-TEST_SPLIT_RATIO:.0%}) and testing ({TEST_SPLIT_RATIO:.0%}).")
        try:
            train_df, test_df = train_test_split(
                final_df,
                test_size=TEST_SPLIT_RATIO,
                random_state=DATASET_RANDOM_STATE,
                shuffle=True
            )
        except ValueError as e: 
            logger.warning(f"Could not stratify during train-test split (Reason: {e}). Performing non-stratified split.")
            train_df, test_df = train_test_split(
                final_df,
                test_size=TEST_SPLIT_RATIO,
                random_state=DATASET_RANDOM_STATE,
                shuffle=True
            )

        logger.info(f"Training set shape: {train_df.shape}")
        logger.info(f"Testing set shape: {test_df.shape}")

        try:
            TRAIN_DATASET_FILE.parent.mkdir(parents=True, exist_ok=True)
            train_df.to_csv(TRAIN_DATASET_FILE, index=False, encoding='utf-8')
            logger.info(f"Training dataset successfully saved to: {TRAIN_DATASET_FILE}")

            TEST_DATASET_FILE.parent.mkdir(parents=True, exist_ok=True)
            test_df.to_csv(TEST_DATASET_FILE, index=False, encoding='utf-8')
            logger.info(f"Testing dataset successfully saved to: {TEST_DATASET_FILE}")
        except Exception as e:
            logger.error(f"Error saving train/test datasets: {e}", exc_info=True)

    if args.update_comparison_cache and existing_comparison_results_str_keys:
        logger.info(f"Updating comparison_results_cache.json with {len(existing_comparison_results_str_keys)} entries...")
        data_store.save_comparison_results(existing_comparison_results_str_keys)
        logger.info("Comparison cache updated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a training dataset for music duplicate detection ML model, using Gemini for labeling.")
    parser.add_argument("-l", "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO", help="Set the logging level.")
    parser.add_argument("--disable-gemini", action="store_true",
                        help="Completely disable new Gemini API calls, even if API key is present. Will only use cached Gemini results if available.")
    parser.add_argument("--update-comparison-cache", action="store_true",
                        help="Update the comparison_results_cache.json file with any new Gemini results or new comparisons made during dataset creation.")
    cli_args = parser.parse_args()

    # Example of how config items might be set (these should ideally be in music_dup_lib.config)
    if not hasattr(app_config, 'FILTER_PAIRS_BY_FILE_COUNT_FOR_ML'):
        app_config.FILTER_PAIRS_BY_FILE_COUNT_FOR_ML = True # Default for example
    if not hasattr(app_config, 'FILTER_PAIRS_BY_FILE_COUNT_FOR_ML_GEMINI'):
        app_config.FILTER_PAIRS_BY_FILE_COUNT_FOR_ML_GEMINI = True # Default for example
        
    build_dataset(cli_args)