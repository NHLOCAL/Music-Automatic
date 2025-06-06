import argparse
import logging
from pathlib import Path
import random
import time
from datetime import datetime
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set, FrozenSet, Any
from itertools import combinations
from collections import defaultdict
from sklearn.model_selection import train_test_split
import numpy as np
import re
import sys

# --- הגדרת נתיבים ---
SIMILARITY_MODEL_PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SIMILARITY_MODEL_PROJECT_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))

# --- ייבואים מ-album_deduplicator ---
from album_deduplicator.music_dup_lib import config as app_config
from album_deduplicator.music_dup_lib import utils
from album_deduplicator.music_dup_lib.models import FolderInfo, FolderComparisonResult, FileInfo
from album_deduplicator.music_dup_lib.core.data_store import DataStore
from album_deduplicator.music_dup_lib.core.comparison_engine import ComparisonEngine
from album_deduplicator.music_dup_lib.external.ml_similarity_model import MLSimilarityModel

try:
    from album_deduplicator.music_dup_lib.external.gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
    if not GEMINI_AVAILABLE:
        logging.warning(f"Gemini API Key ({app_config.GEMINI_API_KEY_ENV_VAR}) not found. Gemini labeling will be limited.")
except ImportError:
    logging.warning("Could not import GeminiAnalyzer from album_deduplicator.music_dup_lib.external. Gemini labeling disabled.")
    GeminiAnalyzer = None
    GEMINI_AVAILABLE = False

# --- קבועים של פרויקט similarity_model ---
DATA_DIR = SIMILARITY_MODEL_PROJECT_ROOT / "data"
LOGS_DIR_SIM_MODEL = SIMILARITY_MODEL_PROJECT_ROOT / "logs"

TRAIN_DATASET_FILE = DATA_DIR / "album_pair_features_train.csv"
TEST_DATASET_FILE = DATA_DIR / "album_pair_features_test.csv"
TEST_SPLIT_RATIO = 0.2
DATASET_RANDOM_STATE = 42

HIGH_CERTAINTY_THRESHOLD = 85.0
LOW_CERTAINTY_THRESHOLD = 30.0

DEFINITE_DUPLICATE_LABEL = 98.0
DEFINITE_DIFFERENT_LABEL = 2.0

NEGATIVE_TO_POSITIVE_RATIO = 10
MAX_GEMINI_CANDIDATES_FROM_SAMPLING = 1000

### --- MODIFIED: Constants for incremental and filtered caching ---
MIN_SCORE_TO_CACHE = 15.0  # Only cache pairs with a weighted score > 5.0
CACHE_SAVE_BATCH_SIZE = 50000 # Save to disk every 5000 new valuable entries

logger = logging.getLogger("SimilarityModel.DatasetBuilder")

# ... (פונקציות העזר נשארות זהות) ...
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
        "avg_other_file_size_bytes": None, "total_other_file_size_bytes": None,
    }
    if not folder_info.files and not folder_info.other_files:
        return {k: 0.0 for k in stats.keys()}

    if folder_info.files:
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

    if folder_info.other_files:
        other_file_sizes = [f.get('size_bytes', 0) for f in folder_info.other_files if f.get('size_bytes', 0) > 0]
        if other_file_sizes:
            stats["avg_other_file_size_bytes"] = float(np.mean(other_file_sizes))
            stats["total_other_file_size_bytes"] = float(np.sum(other_file_sizes))

    final_stats: Dict[str, float] = {}
    for key in ["avg_duration", "std_duration", "min_duration", "max_duration", "total_duration",
                "std_bitrate", "min_bitrate", "max_bitrate",
                "avg_other_file_size_bytes", "total_other_file_size_bytes"]:
        final_stats[key] = stats.get(key, 0.0) if stats.get(key) is not None else 0.0
    return final_stats

def extract_features_for_pair(
    folder1_info: FolderInfo,
    folder2_info: FolderInfo,
    comparison_result: Optional[FolderComparisonResult]
) -> Optional[Dict[str, any]]:
    features = {}
    if not folder1_info or not folder2_info: return None

    f1_avg_bitrate = folder1_info.avg_bitrate if folder1_info.avg_bitrate is not None else 0.0
    f2_avg_bitrate = folder2_info.avg_bitrate if folder2_info.avg_bitrate is not None else 0.0
    features['f1_avg_bitrate'] = f1_avg_bitrate
    features['f2_avg_bitrate'] = f2_avg_bitrate
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

    folder1_stats = _calculate_folder_stats(folder1_info)
    folder2_stats = _calculate_folder_stats(folder2_info)

    for stat_key in ["avg_duration", "std_duration", "min_duration", "max_duration", "total_duration",
                     "std_bitrate", "min_bitrate", "max_bitrate",
                     "avg_other_file_size_bytes", "total_other_file_size_bytes"]:
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
        if stat_key == "total_other_file_size_bytes":
            if s1_val == 0 and s2_val == 0:
                features['ratio_total_other_file_size_bytes'] = 1.0
            else:
                features['ratio_total_other_file_size_bytes'] = min(s1_val,s2_val) / max(1.0, s1_val, s2_val)

    f1_parent_name = folder1_info.parent_folder_name
    f2_parent_name = folder2_info.parent_folder_name
    features['f1_parent_folder_name_len'] = len(f1_parent_name) if f1_parent_name else 0
    features['f2_parent_folder_name_len'] = len(f2_parent_name) if f2_parent_name else 0
    features['diff_parent_folder_name_len'] = abs(features['f1_parent_folder_name_len'] - features['f2_parent_folder_name_len'])
    features['parent_folder_names_match'] = 1.0 if f1_parent_name and f1_parent_name == f2_parent_name else 0.0
    features['jaccard_parent_folder_names'] = calculate_word_jaccard_index(f1_parent_name, f2_parent_name)

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

    f1_other_files_details: List[Dict[str, Any]] = folder1_info.other_files
    f2_other_files_details: List[Dict[str, Any]] = folder2_info.other_files

    f1_other_files_names = {f['name'] for f in f1_other_files_details}
    f2_other_files_names = {f['name'] for f in f2_other_files_details}

    features['f1_num_other_files'] = len(f1_other_files_details)
    features['f2_num_other_files'] = len(f2_other_files_details)
    features['diff_num_other_files'] = abs(features['f1_num_other_files'] - features['f2_num_other_files'])
    if max(features['f1_num_other_files'], features['f2_num_other_files']) > 0:
        features['ratio_num_other_files'] = min(features['f1_num_other_files'], features['f2_num_other_files']) / \
                                            max(1.0, features['f1_num_other_files'], features['f2_num_other_files'])
    else:
        features['ratio_num_other_files'] = 1.0

    features['jaccard_other_file_names'] = calculate_jaccard_index(f1_other_files_names, f2_other_files_names)

    common_other_file_names = f1_other_files_names.intersection(f2_other_files_names)
    other_files_hash_match_count = 0
    other_files_size_similarity_sum = 0.0
    if common_other_file_names:
        f1_other_map = {f['name']: f for f in f1_other_files_details}
        f2_other_map = {f['name']: f for f in f2_other_files_details}
        for name in common_other_file_names:
            of1 = f1_other_map[name]
            of2 = f2_other_map[name]
            if of1.get('hash') and of2.get('hash') and of1['hash'] == of2['hash']:
                other_files_hash_match_count += 1
            s1, s2 = of1.get('size_bytes', 0), of2.get('size_bytes', 0)
            if s1 > 0 and s2 > 0:
                ratio = min(s1, s2) / max(s1, s2)
                other_files_size_similarity_sum += 1.0 if ratio >= 0.95 else ratio * ratio
            elif s1 == 0 and s2 == 0:
                other_files_size_similarity_sum += 1.0
    num_common_other_files = len(common_other_file_names)
    features['other_files_common_hash_ratio'] = other_files_hash_match_count / num_common_other_files if num_common_other_files > 0 else 0.0
    features['other_files_common_avg_size_similarity'] = other_files_size_similarity_sum / num_common_other_files if num_common_other_files > 0 else 0.0

    if comparison_result:
        sim_scores = comparison_result.similarity_scores
        comp_feature_keys = [
            'file_hash', 'file_size', 'filename', 'title', 'album',
            'artist', 'albumartist', 'folder_name', 'album_art_hash', 'duration'
        ]
        for key in comp_feature_keys:
            features[f'comp_{key}_similarity'] = sim_scores.get(key, 0.0)
        features['comp_other_files_similarity'] = sim_scores.get('other_files_similarity', 0.0)
        add_meta_details = sim_scores.get('additional_metadata_details', {})
        if add_meta_details and isinstance(add_meta_details, dict): # Ensure it's a dict
            features['comp_avg_add_meta_similarity'] = sum(add_meta_details.values()) / len(add_meta_details) if add_meta_details else 0.0
            features['comp_count_high_add_meta_similarity'] = sum(1 for v in add_meta_details.values() if v >= 0.8)
            for meta_key, meta_sim_score in add_meta_details.items():
                safe_meta_key = re.sub(r'[^a-zA-Z0-9_]', '_', meta_key.lower())
                features[f'comp_add_meta_sim_{safe_meta_key}'] = meta_sim_score
        else:
            features['comp_avg_add_meta_similarity'] = 0.0
            features['comp_count_high_add_meta_similarity'] = 0.0
            expected_add_meta_sim_tags = [
                'length', 'date', 'tracknumber', 'genre', 'media', 'composer', 'encodedby',
                'discnumber', 'organization', 'grouping', 'bpm', 'copyright', 'barcode',
                'conductor', 'website', 'version', 'compilation', 'titlesort', 'albumsort',
                'lyricist', 'isrc', 'author', 'originaldate'
            ]
            for meta_tag in expected_add_meta_sim_tags:
                features[f'comp_add_meta_sim_{meta_tag}'] = 0.0

    else:
        comp_keys_to_zero = [
            'comp_file_hash_similarity', 'comp_file_size_similarity', 'comp_filename_similarity',
            'comp_title_similarity', 'comp_album_similarity', 'comp_artist_similarity',
            'comp_albumartist_similarity', 'comp_folder_name_similarity', 'comp_album_art_hash_similarity',
            'comp_duration_similarity', 'comp_other_files_similarity',
            'comp_avg_add_meta_similarity', 'comp_count_high_add_meta_similarity'
        ]
        expected_add_meta_sim_tags = [
            'length', 'date', 'tracknumber', 'genre', 'media', 'composer', 'encodedby',
            'discnumber', 'organization', 'grouping', 'bpm', 'copyright', 'barcode',
            'conductor', 'website', 'version', 'compilation', 'titlesort', 'albumsort',
            'lyricist', 'isrc', 'author', 'originaldate'
        ]
        for meta_tag in expected_add_meta_sim_tags:
            comp_keys_to_zero.append(f'comp_add_meta_sim_{meta_tag}')

        for k_comp in comp_keys_to_zero:
            features[k_comp] = 0.0
        features['other_files_common_hash_ratio'] = 0.0
        features['other_files_common_avg_size_similarity'] = 0.0
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
        path=Path(path_str),
        folder_name=folder_dict.get('folder_name', Path(path_str).name),
        parent_folder_name=folder_dict.get('parent_folder_name', Path(path_str).parent.name),
        files=[_file_info_from_dict(f_dict) for f_dict in folder_dict.get('files',[])],
        other_files=folder_dict.get('other_files', []),
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
    LOGS_DIR_SIM_MODEL.mkdir(parents=True, exist_ok=True)
    utils.setup_logging(args.log_level, LOGS_DIR_SIM_MODEL / "dataset_builder.log")
    logger.info("Starting dataset construction...")

    data_store = DataStore()
    comparison_engine = ComparisonEngine(enable_hashing=app_config.ENABLE_HASHING)
    ml_similarity_model = MLSimilarityModel()
    if not ml_similarity_model.model_loaded:
        logger.warning("MLSimilarityModel failed to load. Deciding score will fall back to algorithmic.")
    
    gemini_analyzer = None
    gemini_actually_available = GEMINI_AVAILABLE and not args.disable_gemini
    if gemini_actually_available:
        try:
            gemini_analyzer = GeminiAnalyzer()
            logger.info("Gemini Analyzer initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Analyzer: {e}. Gemini labeling will be skipped.", exc_info=True)
            gemini_actually_available = False

    cached_music_data = data_store.load_data()
    if not cached_music_data:
        logger.error("Music data cache is empty. Run main scanner first.")
        return
        
    all_music_folders = {Path(p): _folder_info_from_dict(p, d) for p, d in cached_music_data.items()}
    logger.info(f"Loaded {len(all_music_folders)} FolderInfo objects.")

    existing_comparison_results = data_store.load_comparison_results()
    logger.info(f"Loaded {len(existing_comparison_results)} existing comparison results from cache.")
    
    ### --- MODIFIED: Full scan logic with filtering and incremental saving ---
    if args.full_scan:
        logger.info(f"---[ Full Scan Mode: Filtering pairs with score < {MIN_SCORE_TO_CACHE} and saving incrementally ]---")
        
        groups_by_file_count = defaultdict(list)
        for path, folder_info in all_music_folders.items():
            audio_file_count = len(folder_info.files)
            if audio_file_count > 0:
                groups_by_file_count[audio_file_count].append(path)
        
        total_pairs_to_check_after_filtering = 0
        for group in groups_by_file_count.values():
            n = len(group)
            if n >= 2:
                total_pairs_to_check_after_filtering += n * (n - 1) // 2

        original_total = len(all_music_folders) * (len(all_music_folders) - 1) // 2
        logger.info(f"Filtering by audio file count reduced potential pairs from {original_total} to {total_pairs_to_check_after_filtering}.")

        if not args.update_comparison_cache:
            logger.warning("Full scan is enabled, but --update-comparison-cache is not. New comparison results will NOT be saved to disk.")
        
        cached_pairs = set(existing_comparison_results.keys())
        new_valuable_entries = 0
        pairs_processed = 0
        new_results_batch = {}

        root_logger = logging.getLogger()
        console_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                console_handler = handler
                root_logger.removeHandler(handler)
                break
        
        try:
            for file_count, folder_paths in groups_by_file_count.items():
                if len(folder_paths) < 2:
                    continue
                
                for f1p, f2p in combinations(folder_paths, 2):
                    pairs_processed += 1
                    pair_key = frozenset({str(f1p), str(f2p)})
                    if pair_key in cached_pairs:
                        continue

                    folder1 = all_music_folders[f1p]
                    folder2 = all_music_folders[f2p]
                    comp_res = comparison_engine.compare_two_folders(folder1, folder2)

                    if comp_res and comp_res.weighted_score >= MIN_SCORE_TO_CACHE:
                        existing_comparison_results[pair_key] = comp_res # Keep in memory for this run
                        new_valuable_entries += 1
                        
                        if args.update_comparison_cache:
                            new_results_batch[pair_key] = comp_res
                            if len(new_results_batch) >= CACHE_SAVE_BATCH_SIZE:
                                sys.stdout.write("\n") # Newline before saving message
                                logger.info(f"Saving a batch of {len(new_results_batch)} new results to cache...")
                                current_cache = data_store.load_comparison_results()
                                current_cache.update(new_results_batch)
                                data_store.save_comparison_results(current_cache)
                                new_results_batch.clear()
                                logger.info("Batch saved. Resuming scan...")

                    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    status_line = (
                        f"{now_str} - [Full Scan] Checked pair {pairs_processed}/{total_pairs_to_check_after_filtering} | "
                        f"Found valuable new entries: {new_valuable_entries}"
                    )
                    sys.stdout.write(f"\r{status_line}   ")
                    sys.stdout.flush()

            sys.stdout.write('\n')
            sys.stdout.flush()

            # Save any remaining items in the final batch
            if args.update_comparison_cache and new_results_batch:
                logger.info(f"Saving final batch of {len(new_results_batch)} new results to cache...")
                current_cache = data_store.load_comparison_results()
                current_cache.update(new_results_batch)
                data_store.save_comparison_results(current_cache)
                logger.info("Final batch saved.")

        finally:
            if console_handler:
                root_logger.addHandler(console_handler)

        logger.info(f"Full scan complete. Added {new_valuable_entries} new valuable entries to the cache.")
        logger.info("---[ Exiting Full Scan Mode, proceeding with dataset construction ]---")
    ### --- END of modified logic ---
    
    processed_pairs = set()
    
    positive_pairs = []
    hard_negative_pairs_from_cache = []
    easy_negative_pairs_from_cache = []
    gemini_candidates_new = []

    logger.info("Phase 1: Categorizing pairs from existing comparison cache...")
    for pair_key, comp_res in existing_comparison_results.items():
        processed_pairs.add(pair_key)
        f1p, f2p = comp_res.folder1_path, comp_res.folder2_path
        if f1p not in all_music_folders or f2p not in all_music_folders:
            continue
        
        folder1, folder2 = all_music_folders[f1p], all_music_folders[f2p]
        
        ml_score = ml_similarity_model.predict_similarity_for_pair(folder1, folder2, comp_res) if ml_similarity_model.model_loaded else None
        deciding_score = ml_score if ml_score is not None else comp_res.weighted_score

        if deciding_score >= HIGH_CERTAINTY_THRESHOLD or comp_res.gemini_verdict == 'duplicate':
            label = DEFINITE_DUPLICATE_LABEL if comp_res.gemini_verdict != 'duplicate' else comp_res.gemini_similarity_score
            label_source = 'gemini_cached' if comp_res.gemini_verdict == 'duplicate' else ('ml_high_certainty' if ml_score is not None else 'algo_high_certainty')
            positive_pairs.append((folder1, folder2, comp_res, label, label_source))
        elif deciding_score < LOW_CERTAINTY_THRESHOLD:
            easy_negative_pairs_from_cache.append((folder1, folder2, comp_res, DEFINITE_DIFFERENT_LABEL, 'easy_negative_cached'))
        else:
            if comp_res.gemini_verdict in ['different', 'uncertain']:
                hard_negative_pairs_from_cache.append((folder1, folder2, comp_res, comp_res.gemini_similarity_score, 'hard_negative_gemini_cached'))
            elif gemini_actually_available and comp_res.gemini_verdict is None:
                gemini_candidates_new.append((folder1, folder2, comp_res, deciding_score))
    
    logger.info(f"Initial categorization complete. Positives: {len(positive_pairs)}, Hard Negatives: {len(hard_negative_pairs_from_cache)}, Easy Negatives: {len(easy_negative_pairs_from_cache)}, New Gemini Candidates: {len(gemini_candidates_new)}")

    logger.info("Phase 2: Assembling balanced negative dataset...")
    n_positive = len(positive_pairs)
    negative_quota = n_positive * NEGATIVE_TO_POSITIVE_RATIO
    logger.info(f"Found {n_positive} positive samples. Setting negative sample quota to: {negative_quota}")

    final_negative_pairs = []
    final_negative_pairs.extend(hard_negative_pairs_from_cache)
    logger.info(f"Added {len(hard_negative_pairs_from_cache)} hard negatives from cache.")
    
    needed_more_negatives = negative_quota - len(final_negative_pairs)
    if needed_more_negatives > 0:
        random.shuffle(easy_negative_pairs_from_cache)
        added_easy = easy_negative_pairs_from_cache[:needed_more_negatives]
        final_negative_pairs.extend(added_easy)
        logger.info(f"Added {len(added_easy)} easy negatives from cache to meet quota.")

    logger.info("Phase 3: Sampling to fill remaining quotas...")
    all_folder_paths_list = list(all_music_folders.keys())
    max_sampling_attempts = len(all_folder_paths_list) * 10
    
    for attempt in range(max_sampling_attempts):
        if len(final_negative_pairs) >= negative_quota and len(gemini_candidates_new) >= MAX_GEMINI_CANDIDATES_FROM_SAMPLING:
            logger.info("All quotas filled. Stopping sampling.")
            break

        if len(all_folder_paths_list) < 2: break
        
        idx1, idx2 = random.sample(range(len(all_folder_paths_list)), 2)
        f1p, f2p = all_folder_paths_list[idx1], all_folder_paths_list[idx2]
        current_pair_key = frozenset({str(f1p), str(f2p)})

        if current_pair_key in processed_pairs:
            continue
        processed_pairs.add(current_pair_key)

        folder1, folder2 = all_music_folders[f1p], all_music_folders[f2p]
        comp_res = comparison_engine.compare_two_folders(folder1, folder2)

        if comp_res:
            ml_score = ml_similarity_model.predict_similarity_for_pair(folder1, folder2, comp_res) if ml_similarity_model.model_loaded else None
            deciding_score = ml_score if ml_score is not None else comp_res.weighted_score
            
            if deciding_score < LOW_CERTAINTY_THRESHOLD and len(final_negative_pairs) < negative_quota:
                final_negative_pairs.append((folder1, folder2, comp_res, DEFINITE_DIFFERENT_LABEL, 'easy_negative_sampled'))
            elif LOW_CERTAINTY_THRESHOLD <= deciding_score < HIGH_CERTAINTY_THRESHOLD and len(gemini_candidates_new) < MAX_GEMINI_CANDIDATES_FROM_SAMPLING:
                gemini_candidates_new.append((folder1, folder2, comp_res, deciding_score))
                existing_comparison_results[current_pair_key] = comp_res

    logger.info(f"Sampling complete. Final negatives: {len(final_negative_pairs)}. New Gemini candidates: {len(gemini_candidates_new)}.")

    gemini_processed_pairs = []
    if gemini_actually_available and gemini_analyzer and gemini_candidates_new:
        logger.info(f"Phase 4: Running Gemini analysis on {len(gemini_candidates_new)} candidate pairs...")
        for f1_info, f2_info, comp_res_gemini, score_for_gemini in gemini_candidates_new:
            time.sleep(app_config.GEMINI_API_DELAY_SECONDS)
            logger.info(f"Sending to Gemini: {f1_info.path.name} vs {f2_info.path.name} (Score: {score_for_gemini:.2f})")
            verdict, gemini_sim_score, reason = gemini_analyzer.analyze_pair(f1_info, f2_info, score_for_gemini)
            
            pair_key = frozenset({str(f1_info.path), str(f2_info.path)})
            comp_res_gemini.gemini_verdict = verdict
            comp_res_gemini.gemini_similarity_score = gemini_sim_score
            comp_res_gemini.gemini_reason = reason
            comp_res_gemini.gemini_error = None if "ERROR" not in reason.upper() else reason
            existing_comparison_results[pair_key] = comp_res_gemini

            if gemini_sim_score is not None and comp_res_gemini.gemini_error is None:
                if verdict == 'duplicate':
                     gemini_processed_pairs.append((f1_info, f2_info, comp_res_gemini, gemini_sim_score, 'gemini_positive_new'))
                else:
                     gemini_processed_pairs.append((f1_info, f2_info, comp_res_gemini, gemini_sim_score, 'gemini_negative_new'))

    logger.info("Phase 5: Assembling final dataset...")
    
    all_labeled_pairs = positive_pairs + final_negative_pairs + gemini_processed_pairs
    logger.info(f"Total labeled pairs for dataset: {len(all_labeled_pairs)} (Positives: {len(positive_pairs)}, Negatives: {len(final_negative_pairs)}, Gemini-processed: {len(gemini_processed_pairs)})")

    dataset_rows = []
    for f1, f2, res, label, source in all_labeled_pairs:
        features = extract_features_for_pair(f1, f2, res)
        if features:
            features['target_label'] = label
            features['label_source'] = source
            features['folder1_path_id'] = str(f1.path)
            features['folder2_path_id'] = str(f2.path)
            dataset_rows.append(features)

    if not dataset_rows:
        logger.warning("No data rows were generated for the dataset. Exiting.")
        return

    final_df = pd.DataFrame(dataset_rows)
    final_df.dropna(subset=['target_label'], inplace=True)
    final_df.fillna(0.0, inplace=True)

    logger.info(f"Total dataset rows before split: {final_df.shape[0]}")
    if final_df.shape[0] > 0:
        logger.info(f"Label source distribution:\n{final_df['label_source'].value_counts(dropna=False)}")
        logger.info(f"Target label statistics:\n{final_df['target_label'].describe(percentiles=[.1, .25, .5, .75, .9])}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if final_df.shape[0] < 2:
        final_df.to_csv(TRAIN_DATASET_FILE, index=False, encoding='utf-8')
        logger.warning(f"Dataset has < 2 rows. Saved all to: {TRAIN_DATASET_FILE}")
    else:
        train_df, test_df = train_test_split(final_df, test_size=TEST_SPLIT_RATIO, random_state=DATASET_RANDOM_STATE, shuffle=True)
        train_df.to_csv(TRAIN_DATASET_FILE, index=False, encoding='utf-8')
        test_df.to_csv(TEST_DATASET_FILE, index=False, encoding='utf-8')
        logger.info(f"Training ({train_df.shape[0]} rows) and testing ({test_df.shape[0]} rows) datasets saved.")

    # The final save is now less critical for --full-scan, but still necessary for results from Gemini or sampling.
    # Since the in-memory dictionary is now much smaller, this is no longer a bottleneck.
    if args.update_comparison_cache:
        logger.info(f"Updating comparison_results_cache.json with final results...")
        data_store.save_comparison_results(existing_comparison_results)
        logger.info("Comparison cache updated successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a balanced training dataset for the music duplicate detection ML model.")
    parser.add_argument("-l", "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO", help="Set the logging level.")
    parser.add_argument("-f", "--full-scan", action="store_true",
                        help="Perform a full comparison of all folder pairs, filtered by audio file count.")
    parser.add_argument("-d", "--disable-gemini", action="store_true",
                        help="Completely disable new Gemini API calls, even if API key is present.")
    parser.add_argument("-u", "--update-comparison-cache", action="store_true",
                        help="Update the main comparison_results_cache.json with new results.")
    cli_args = parser.parse_args()

    build_dataset(cli_args)