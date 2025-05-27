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

# OUTPUT_DATASET_FILE = Path("similarity_model/data/album_pair_features.csv") # Old
TRAIN_DATASET_FILE = Path("similarity_model/data/album_pair_features_train.csv")
TEST_DATASET_FILE = Path("similarity_model/data/album_pair_features_test.csv")
TEST_SPLIT_RATIO = 0.2  # Should match TEST_SET_SIZE in train_model.py (for consistency)
DATASET_RANDOM_STATE = 42 # Should match RANDOM_STATE_SEED in train_model.py (for consistency)


HIGH_CERTAINTY_THRESHOLD = 85.0
LOW_CERTAINTY_THRESHOLD = 35.0

DEFINITE_DUPLICATE_LABEL = 98.0
DEFINITE_DIFFERENT_LABEL = 2.0

MAX_LOW_SIM_PAIRS_FROM_SAMPLING = 5000
MAX_GEMINI_CANDIDATES_FROM_SAMPLING = 2000

logger = logging.getLogger("DatasetBuilder") # Specific logger for this module

# --- פונקציות עזר שהיו בדיון הקודם ---
def calculate_jaccard_index(set1: Set[str], set2: Set[str]) -> float:
    if not set1 and not set2: return 1.0
    intersection_size = len(set1.intersection(set2))
    union_size = len(set1.union(set2))
    return intersection_size / union_size if union_size > 0 else 0.0

def extract_features_for_pair(
    folder1_info: FolderInfo,
    folder2_info: FolderInfo,
    comparison_result: Optional[FolderComparisonResult]
) -> Optional[Dict[str, any]]:
    features = {}
    if not folder1_info or not folder2_info: return None
    # Removed: features['f1_avg_bitrate'] = folder1_info.avg_bitrate
    # Removed: features['f2_avg_bitrate'] = folder2_info.avg_bitrate
    features['diff_avg_bitrate'] = abs(folder1_info.avg_bitrate - folder2_info.avg_bitrate)
    # Removed: features['ratio_avg_bitrate'] = min(folder1_info.avg_bitrate, folder2_info.avg_bitrate) / max(1.0, folder1_info.avg_bitrate, folder2_info.avg_bitrate)
    
    features['jaccard_unique_artists'] = calculate_jaccard_index(folder1_info.unique_artists, folder2_info.unique_artists)
    features['jaccard_unique_albums'] = calculate_jaccard_index(folder1_info.unique_albums, folder2_info.unique_albums)
    
    features['f1_generic_filename_score'] = folder1_info.generic_filename_score
    features['f2_generic_filename_score'] = folder2_info.generic_filename_score
    features['diff_generic_filename_score'] = abs(folder1_info.generic_filename_score - folder2_info.generic_filename_score)
    
    features['f1_generic_title_score'] = folder1_info.generic_title_score
    features['f2_generic_title_score'] = folder2_info.generic_title_score
    features['diff_generic_title_score'] = abs(folder1_info.generic_title_score - folder2_info.generic_title_score)
    
    # Removed: features['f1_has_art'] = 1.0 if folder1_info.album_art_hash else 0.0
    # Removed: features['f2_has_art'] = 1.0 if folder2_info.album_art_hash else 0.0
    # Removed: features['both_has_art'] = 1.0 if folder1_info.album_art_hash and folder2_info.album_art_hash else 0.0
    # Removed: features['art_hashes_match'] = 1.0 if folder1_info.album_art_hash and folder1_info.album_art_hash == folder2_info.album_art_hash else 0.0
    
    if comparison_result:
        sim_scores = comparison_result.similarity_scores
        features['comp_file_hash_similarity'] = sim_scores.get('file_hash', 0.0)
        features['comp_file_size_similarity'] = sim_scores.get('file_size', 0.0)
        features['comp_filename_similarity'] = sim_scores.get('filename', 0.0)
        features['comp_title_similarity'] = sim_scores.get('title', 0.0)
        features['comp_album_similarity'] = sim_scores.get('album', 0.0)
        features['comp_artist_similarity'] = sim_scores.get('artist', 0.0)
        features['comp_albumartist_similarity'] = sim_scores.get('albumartist', 0.0)
        features['comp_folder_name_similarity'] = sim_scores.get('folder_name', 0.0)
        features['comp_album_art_hash_similarity'] = sim_scores.get('album_art_hash', 0.0) # This one remains
        features['comp_duration_similarity'] = sim_scores.get('duration', 0.0)
        # Removed: features['comp_is_identical_by_hash'] = 1.0 if comparison_result.is_identical_by_hash else 0.0
        
        add_meta_details = sim_scores.get('additional_metadata_details', {})
        if add_meta_details:
            features['comp_avg_add_meta_similarity'] = sum(add_meta_details.values()) / len(add_meta_details) if add_meta_details else 0.0
            features['comp_count_high_add_meta_similarity'] = sum(1 for v in add_meta_details.values() if v >= 0.8)
        else:
            features['comp_avg_add_meta_similarity'] = 0.0
            features['comp_count_high_add_meta_similarity'] = 0.0
    else:
        comp_keys_to_zero = [
            'comp_file_hash_similarity', 'comp_file_size_similarity', 'comp_filename_similarity',
            'comp_title_similarity', 'comp_album_similarity', 'comp_artist_similarity',
            'comp_albumartist_similarity', 'comp_folder_name_similarity', 'comp_album_art_hash_similarity',
            'comp_duration_similarity', # 'comp_is_identical_by_hash' removed from this list
            'comp_avg_add_meta_similarity', 'comp_count_high_add_meta_similarity'
        ]
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
    return FolderInfo(
        path=Path(path_str), folder_name=folder_dict['folder_name'],
        parent_folder_name=folder_dict.get('parent_folder_name', Path(path_str).parent.name),
        files=[_file_info_from_dict(f_dict) for f_dict in folder_dict.get('files',[])],
        album_art_hash=folder_dict.get('album_art_hash'),
        file_hashes_present=folder_dict.get('file_hashes_present', False),
        avg_bitrate=folder_dict.get('avg_bitrate', 0.0),
        unique_artists=set(folder_dict.get('unique_artists', [])),
        unique_albums=set(folder_dict.get('unique_albums', [])),
        generic_filename_score=folder_dict.get('generic_filename_score', 0.0),
        generic_title_score=folder_dict.get('generic_title_score', 0.0),
        quality_score=folder_dict.get('quality_score'),
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

        if len(folder1.files) != len(folder2.files):
            logger.debug(f"Skipping cached pair {f1p.name}-{f2p.name} due to different file counts: "
                         f"{len(folder1.files)} vs {len(folder2.files)}. Not adding to dataset.")
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

        if len(folder1.files) != len(folder2.files):
            logger.debug(f"Skipping sampled pair {f1p_path_obj.name}-{f2p_path_obj.name} due to different file counts: "
                         f"{len(folder1.files)} vs {len(folder2.files)}. Not adding to dataset.")
            continue

        fresh_comp_res = comparison_engine.compare_two_folders(folder1, folder2)
        label = None
        label_source = "unknown_sampled"

        if not fresh_comp_res:
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
            else:
                if gemini_actually_available and new_gemini_candidates_count < MAX_GEMINI_CANDIDATES_FROM_SAMPLING:
                    gemini_candidates_new.append((folder1, folder2, fresh_comp_res))
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
        logger.info(f"Running Gemini analysis on {len(gemini_candidates_new)} new candidate pairs (all with matching file counts)...")
        gemini_api_calls = 0
        for f1_info, f2_info, comp_res_for_gemini in gemini_candidates_new:
            if len(f1_info.files) != len(f2_info.files):
                logger.warning(f"Unexpected: Gemini candidate {f1_info.path.name} vs {f2_info.path.name} "
                               f"has different file counts ({len(f1_info.files)} vs {len(f2_info.files)}) "
                               f"at Gemini processing stage. Skipping.")
                continue

            f1p_path_obj, f2p_path_obj = f1_info.path, f2_info.path
            algo_score = comp_res_for_gemini.weighted_score
            logger.info(f"Gemini ({gemini_api_calls+1}/{len(gemini_candidates_new)}): {f1p_path_obj.name} vs {f2p_path_obj.name} (Algo: {algo_score:.2f})")

            time.sleep(app_config.GEMINI_API_DELAY_SECONDS)
            verdict, gemini_sim_score, reason_or_error = gemini_analyzer.analyze_pair(f1_info, f2_info, algo_score)
            gemini_api_calls += 1

            label = None
            label_source = "gemini_new_run_failed"
            
            current_pair_key_str_for_gemini = frozenset({str(f1p_path_obj), str(f2p_path_obj)})

            if gemini_sim_score is not None and ("ERROR" not in reason_or_error and verdict is not None):
                label = gemini_sim_score
                label_source = "gemini_new_run_success"
                comp_res_for_gemini.gemini_verdict = verdict
                comp_res_for_gemini.gemini_similarity_score = gemini_sim_score
                comp_res_for_gemini.gemini_reason = reason_or_error
                comp_res_for_gemini.gemini_error = None
                existing_comparison_results_str_keys[current_pair_key_str_for_gemini] = comp_res_for_gemini
            else:
                logger.warning(f"Gemini analysis failed or returned invalid data for {f1p_path_obj.name} vs {f2p_path_obj.name}. "
                               f"Error/Reason: {reason_or_error}. This pair will not be added with Gemini label.")
                if current_pair_key_str_for_gemini in existing_comparison_results_str_keys:
                    existing_comparison_results_str_keys[current_pair_key_str_for_gemini].gemini_error = reason_or_error
                    existing_comparison_results_str_keys[current_pair_key_str_for_gemini].gemini_verdict = None
                    existing_comparison_results_str_keys[current_pair_key_str_for_gemini].gemini_similarity_score = None
                    existing_comparison_results_str_keys[current_pair_key_str_for_gemini].gemini_reason = None

            if label is not None:
                features = extract_features_for_pair(f1_info, f2_info, comp_res_for_gemini)
                if features:
                    features['target_label'] = label
                    features['label_source'] = label_source
                    features['folder1_path_id'] = str(f1p_path_obj)
                    features['folder2_path_id'] = str(f2p_path_obj)
                    dataset_rows.append(features)
    else:
        logger.info("Skipping new Gemini runs (Gemini unavailable, analyzer init failed, or no new candidates).")

    if not dataset_rows:
        logger.warning("No data rows were generated for the dataset (possibly due to file count filtering or other criteria). Exiting.")
        if args.update_comparison_cache and existing_comparison_results_str_keys:
            logger.info(f"Updating comparison_results_cache.json with {len(existing_comparison_results_str_keys)} entries (even if dataset is empty)...")
            data_store.save_comparison_results(existing_comparison_results_str_keys)
            logger.info("Comparison cache updated.")
        return

    final_df = pd.DataFrame(dataset_rows)
    final_df.dropna(subset=['target_label'], inplace=True) # Critical: rows without a target are useless
    final_df.fillna(0.0, inplace=True) # Fill other NaNs with 0.0, assuming features should be numeric or handled

    logger.info(f"Total dataset rows before split: {final_df.shape[0]}, columns: {final_df.shape[1]}.")
    logger.info(f"Target label statistics (full dataset):\n{final_df['target_label'].describe()}")
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
        else: # 0 rows
             logger.info("Dataset is empty, no files will be saved.")
    else:
        logger.info(f"Splitting dataset into training ({1-TEST_SPLIT_RATIO:.0%}) and testing ({TEST_SPLIT_RATIO:.0%}).")
        try:
            # Stratify by label_source if there's enough variety and it's deemed important.
            # For now, a simple random split. If target_label was categorical, could stratify on it.
            # For continuous target, stratification is more complex or less common.
            train_df, test_df = train_test_split(
                final_df,
                test_size=TEST_SPLIT_RATIO,
                random_state=DATASET_RANDOM_STATE,
                shuffle=True
                # stratify=final_df['label_source'] # Optional, if useful and data supports it
            )
        except ValueError as e: # Happens if a class in stratify has only 1 member
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
            TRAIN_DATASET_FILE.parent.mkdir(parents=True, exist_ok=True) # Ensures directory exists
            train_df.to_csv(TRAIN_DATASET_FILE, index=False, encoding='utf-8')
            logger.info(f"Training dataset successfully saved to: {TRAIN_DATASET_FILE}")

            TEST_DATASET_FILE.parent.mkdir(parents=True, exist_ok=True) # Ensure dir for test file too
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
    build_dataset(cli_args)