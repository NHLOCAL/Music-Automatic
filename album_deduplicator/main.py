import argparse
from collections import defaultdict
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional, FrozenSet
import time
import sys
from music_dup_lib import config
from music_dup_lib import utils
from music_dup_lib.models import FolderInfo, FolderComparisonResult
from music_dup_lib.core.data_store import DataStore
from music_dup_lib.core.file_processor import FileProcessor
from music_dup_lib.core.folder_scanner import FolderScanner
from music_dup_lib.core.comparison_engine import ComparisonEngine
from music_dup_lib.core.quality_analyzer import QualityAnalyzer
from music_dup_lib.core.action_handler import ActionHandler
from music_dup_lib.external.ml_similarity_model import MLSimilarityModel
try:
    from music_dup_lib.external.gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
    if not GEMINI_AVAILABLE:
        logging.warning(f"Gemini API Key ({config.GEMINI_API_KEY_ENV_VAR}) not found or 'requests'/'Pillow'/'google-generativeai' missing. Gemini analysis will be disabled.")
except ImportError as e:
    logging.warning(f"Could not import GeminiAnalyzer module (check 'google-generativeai', 'requests', 'Pillow'): {e}. Gemini analysis disabled.")
    GeminiAnalyzer = None
    GEMINI_AVAILABLE = False
    GEMINI_API_KEY = None
logger: Optional[logging.Logger] = None
def display_comparison_results(results: List[FolderComparisonResult], all_folders: Dict[Path, FolderInfo]):
    if not results:
        print(utils.AnsiColors.GREEN + "\nNo significantly similar folders found." + utils.AnsiColors.RESET)
        return
    print(utils.AnsiColors.CYAN + "\n--- Similarity Comparison Results ---" + utils.AnsiColors.RESET)
    print(f"(Showing pairs with similarity >= {config.MINIMAL_DISPLAY_SIMILARITY}%)\n")
    for result in results:
        f1_path = result.folder1_path
        f2_path = result.folder2_path
        primary_score = result.final_combined_score if result.final_combined_score is not None else \
                        (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score)
        f1_info = all_folders.get(f1_path)
        f2_info = all_folders.get(f2_path)
        q1_str = f"(Q: {f1_info.quality_score:.2f}%)" if f1_info and f1_info.quality_score is not None else "(Q: N/A)"
        q2_str = f"(Q: {f2_info.quality_score:.2f}%)" if f2_info and f2_info.quality_score is not None else "(Q: N/A)"
        color = utils.AnsiColors.GREEN if primary_score >= 90 else utils.AnsiColors.YELLOW if primary_score >= 70 else utils.AnsiColors.RESET
        print(f"Pair: '{utils.AnsiColors.BLUE}{f1_path.name}{utils.AnsiColors.RESET}' {q1_str} <-> '{utils.AnsiColors.BLUE}{f2_path.name}{utils.AnsiColors.RESET}' {q2_str}")
        if result.final_combined_score is not None:
            print(f"  Combined Similarity Score: {color}{result.final_combined_score:.2f}%{utils.AnsiColors.RESET}")
            if result.ml_similarity_score is not None:
                 print(f"    ML Model Score: {result.ml_similarity_score:.4f}")
            print(f"    Algorithmic Score (raw): {result.weighted_score:.2f}%")
        elif result.ml_similarity_score is not None:
            print(f"  ML Model Score: {color}{result.ml_similarity_score:.4f}%{utils.AnsiColors.RESET}")
            print(f"    Algorithmic Score (raw): {result.weighted_score:.2f}%")
        else:
            print(f"  Algorithmic Score: {color}{result.weighted_score:.2f}%{utils.AnsiColors.RESET}")
        if result.is_identical_by_hash:
            print(f"    {utils.AnsiColors.MAGENTA}(Identical by file hashes){utils.AnsiColors.RESET}")
        if result.gemini_error:
            err_prefix = utils.AnsiColors.RED + "Gemini Error:" + utils.AnsiColors.RESET
            if "API_ERROR: Prompt Blocked" in result.gemini_error:
                 err_prefix = utils.AnsiColors.YELLOW + "Gemini Blocked:" + utils.AnsiColors.RESET
            elif "API_ERROR: Request timed out" in result.gemini_error:
                 err_prefix = utils.AnsiColors.YELLOW + "Gemini Timeout:" + utils.AnsiColors.RESET
            print(f"  {err_prefix} {result.gemini_error[:150]}{'...' if len(result.gemini_error) > 150 else ''}")
        elif result.gemini_verdict is not None:
            verdict = result.gemini_verdict
            verdict_text = "Unknown Verdict"
            verdict_color = utils.AnsiColors.RED
            if verdict == 'duplicate':
                verdict_text = "Likely Duplicate"
                verdict_color = utils.AnsiColors.GREEN
            elif verdict == 'different':
                verdict_text = "Likely Different"
                verdict_color = utils.AnsiColors.YELLOW
            elif verdict == 'uncertain':
                verdict_text = "Uncertain"
                verdict_color = utils.AnsiColors.MAGENTA
            similarity_str = f"{result.gemini_similarity_score:.1f}%" if result.gemini_similarity_score is not None else "N/A"
            print(f"  {utils.AnsiColors.CYAN}Gemini Verdict:{utils.AnsiColors.RESET} {verdict_color}{verdict_text}{utils.AnsiColors.RESET} (Gemini Similarity: {similarity_str})")
            if result.gemini_reason:
                reason_preview = result.gemini_reason.replace('\n', ' ').strip()
                print(f"  {utils.AnsiColors.CYAN}Gemini Reason:{utils.AnsiColors.RESET} {reason_preview[:200]}{'...' if len(reason_preview) > 200 else ''}")
        if logging.getLogger().isEnabledFor(logging.DEBUG) and result.similarity_scores:
            details = []
            for k, v in sorted(result.similarity_scores.items()):
                if k == 'additional_metadata_details':
                    add_meta_dict = v if isinstance(v, dict) else {}
                    add_meta = ", ".join([f"{mk.split(':')[0]}:{mv:.2f}" for mk, mv in sorted(add_meta_dict.items())])
                    if add_meta: details.append(f"AddMeta=({add_meta})")
                elif isinstance(v, float):
                    details.append(f"{k}={v:.2f}")
            if details:
                 print(f"  Scores: [ {', '.join(details)} ]")
        print("-" * 20)
def display_quality_results_grouped(all_folders: Dict[Path, FolderInfo], comparison_results: List[FolderComparisonResult]):
    print(utils.AnsiColors.CYAN + "\n--- Folder Quality Assessment (Grouped by Similarity) ---" + utils.AnsiColors.RESET)
    graph: Dict[Path, Set[Path]] = defaultdict(set)
    nodes_in_graph: Set[Path] = set()
    for result in comparison_results:
        f1_path, f2_path = result.folder1_path, result.folder2_path
        graph[f1_path].add(f2_path)
        graph[f2_path].add(f1_path)
        nodes_in_graph.add(f1_path)
        nodes_in_graph.add(f2_path)
    if not nodes_in_graph:
        print("No similar folder groups to display quality for.")
        print(utils.AnsiColors.CYAN + "--- End of Quality Assessment ---" + utils.AnsiColors.RESET)
        return
    processed_nodes: Set[Path] = set()
    group_count = 0
    sorted_nodes = sorted(list(nodes_in_graph), key=str)
    for start_node in sorted_nodes:
        if start_node not in processed_nodes:
            group_count += 1
            component_paths: Set[Path] = set()
            stack = [start_node]
            visited_in_component: Set[Path] = set()
            while stack:
                current_path = stack.pop()
                if current_path not in visited_in_component and current_path in nodes_in_graph:
                    visited_in_component.add(current_path)
                    processed_nodes.add(current_path)
                    component_paths.add(current_path)
                    neighbors = graph.get(current_path, set())
                    stack.extend(neighbors - visited_in_component)
            if len(component_paths) > 1:
                print(f"\n{utils.AnsiColors.MAGENTA}Group {group_count} (Similar Folders):{utils.AnsiColors.RESET}")
                component_folders = sorted(
                    [all_folders[p] for p in component_paths if p in all_folders and all_folders[p].quality_score is not None],
                    key=lambda f: (f.quality_score is not None, f.quality_score), reverse=True
                )
                if not component_folders:
                    if logger: logger.info(f"Group {group_count} has no folders with calculated quality scores. Component paths: {[str(p) for p in component_paths]}")
                    continue
                for i, folder in enumerate(component_folders):
                    quality = folder.quality_score if folder.quality_score is not None else -1.0
                    q_str = f"{quality:.2f}%" if quality >= 0 else "N/A "
                    color = utils.AnsiColors.RESET
                    if quality >= 0:
                         color = utils.AnsiColors.GREEN if i == 0 else utils.AnsiColors.YELLOW if quality > 50 else utils.AnsiColors.RED
                    marker = "👑 (Best)" if i == 0 and quality >=0 else " " * 9
                    print(f"  {marker} {color}{q_str:<7}{utils.AnsiColors.RESET} '{folder.path}'")
                    if logging.getLogger().isEnabledFor(logging.DEBUG) and folder.quality_breakdown:
                        breakdown_str = ", ".join([f"{k}: {v:.1f}" for k, v in sorted(folder.quality_breakdown.items())])
                        print(f"      Breakdown: [{breakdown_str}]")
    print(utils.AnsiColors.CYAN + "\n--- End of Quality Assessment ---" + utils.AnsiColors.RESET)
def _select_representatives(
    all_folders: Dict[Path, FolderInfo],
    comparison_results: List[FolderComparisonResult],
    similarity_threshold: float
) -> Dict[Path, Path]:
    if logger: logger.info(f"Selecting representatives for clusters with similarity >= {similarity_threshold}%...")
    representative_map: Dict[Path, Path] = {path: path for path in all_folders}
    graph: Dict[Path, Set[Path]] = defaultdict(set)
    nodes_in_graph: Set[Path] = set()
    relevant_results = [
        r for r in comparison_results
        if (r.final_combined_score if r.final_combined_score is not None else \
            (r.ml_similarity_score if r.ml_similarity_score is not None else r.weighted_score)) >= similarity_threshold
    ]
    if not relevant_results:
        if logger: logger.info("No pairs met the high similarity threshold for representative selection.")
        return representative_map
    for result in relevant_results:
        f1_path, f2_path = result.folder1_path, result.folder2_path
        if f1_path in all_folders and f2_path in all_folders:
            graph[f1_path].add(f2_path)
            graph[f2_path].add(f1_path)
            nodes_in_graph.add(f1_path)
            nodes_in_graph.add(f2_path)
        else:
             if logger: logger.warning(f"Skipping edge for representative selection: Folder data missing for pair {f1_path.name}, {f2_path.name}")
    seen: Set[Path] = set()
    clusters_found = 0
    for node_path in list(nodes_in_graph):
        if node_path not in seen and node_path in all_folders:
            component_paths: Set[Path] = set()
            stack = [node_path]
            visited_in_component: Set[Path] = set()
            while stack:
                current_path = stack.pop()
                if current_path not in visited_in_component and current_path in nodes_in_graph and current_path in all_folders:
                    visited_in_component.add(current_path)
                    seen.add(current_path)
                    component_paths.add(current_path)
                    stack.extend(graph.get(current_path, set()) - visited_in_component)
            if len(component_paths) > 1:
                component_folders_all_info = [all_folders[p] for p in component_paths if p in all_folders]
                component_folders = [f for f in component_folders_all_info if f and f.quality_score is not None]
                if len(component_folders) > 1:
                    clusters_found += 1
                    best_folder = max(component_folders, key=lambda f: f.quality_score if f.quality_score is not None else -1.0)
                    representative_path = best_folder.path
                    if logger: logger.debug(f"Cluster found. Representative: {representative_path.name} (Q:{best_folder.quality_score:.2f}) for folders: {[f.path.name for f in component_folders]}")
                    for folder_path in component_paths:
                         if folder_path in all_folders:
                            representative_map[folder_path] = representative_path
                elif component_folders:
                     if logger: logger.debug(f"Component starting at {node_path.name} reduced to one valid folder after quality score check ({component_folders[0].path.name}), not changing representative for this group.")
                else:
                    if logger: logger.warning(f"Component starting at {node_path.name} had no folders with quality scores. Paths: {[f.path.name for f in component_folders_all_info]}. Representatives not updated for this group.")
    if logger: logger.info(f"Representative selection complete. Found {clusters_found} clusters.")
    return representative_map
def run_gemini_analysis(
    comparison_results: List[FolderComparisonResult],
    all_folders: Dict[Path, FolderInfo],
    gemini_range_str: str,
    cached_results_map: Dict[FrozenSet[str], FolderComparisonResult]
) -> None:
    global logger
    if not GEMINI_AVAILABLE or not GeminiAnalyzer:
        if logger: logger.warning("Gemini analysis skipped (API Key missing, module/dependencies unavailable, or explicitly disabled).")
        return
    try:
        min_sim_str, max_sim_str = gemini_range_str.split('-')
        min_sim = float(min_sim_str)
        max_sim = float(max_sim_str)
        if not (0 <= min_sim <= 100 and 0 <= max_sim <= 100 and min_sim <= max_sim):
            raise ValueError("Invalid range values (must be 0-100 and min <= max)")
    except ValueError as e:
        if logger: logger.error(f"Invalid Gemini similarity range '{gemini_range_str}'. Error: {e}. Skipping Gemini analysis.")
        print(f"{utils.AnsiColors.RED}Error: Invalid Gemini similarity range '{gemini_range_str}'. Skipping Gemini analysis.{utils.AnsiColors.RESET}")
        return
    representative_map = _select_representatives(
        all_folders,
        comparison_results,
        config.GEMINI_HIGH_SIMILARITY_THRESHOLD_FOR_REPRESENTATIVE
    )
    if logger: logger.info(f"Filtering pairs for Gemini analysis (Range: {min_sim}%-{max_sim}%, Rep Threshold: {config.GEMINI_HIGH_SIMILARITY_THRESHOLD_FOR_REPRESENTATIVE}%)...")
    pairs_to_analyze: List[FolderComparisonResult] = []
    processed_representative_pairs: Set[Tuple[str, str]] = set()
    candidate_results = [
        result for result in comparison_results
        if min_sim <= (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score) <= max_sim and not result.is_identical_by_hash
    ]
    skipped_count_rep = 0
    skipped_count_dup_rep = 0
    for result in candidate_results:
        f1_path = result.folder1_path
        f2_path = result.folder2_path
        if f1_path not in representative_map or f2_path not in representative_map:
             if logger: logger.warning(f"Skipping pair ({f1_path.name}, {f2_path.name}) for Gemini: Folder path not found in representative map.")
             continue
        rep1 = representative_map[f1_path]
        rep2 = representative_map[f2_path]
        if rep1 == rep2:
            skipped_count_rep += 1
            if logger: logger.debug(f"Skipping Gemini (Same Rep): {f1_path.name} ({rep1.name}) <-> {f2_path.name} ({rep2.name})")
            continue
        rep1_str = str(rep1)
        rep2_str = str(rep2)
        sorted_list_of_two_strings = sorted((rep1_str, rep2_str))
        canonical_rep_pair: Tuple[str, str] = (sorted_list_of_two_strings[0], sorted_list_of_two_strings[1])
        if canonical_rep_pair in processed_representative_pairs:
            skipped_count_dup_rep += 1
            if logger: logger.debug(f"Skipping Gemini (Duplicate Rep Pair): {f1_path.name} ({rep1.name}) <-> {f2_path.name} ({rep2.name})")
            continue
        pairs_to_analyze.append(result)
        processed_representative_pairs.add(canonical_rep_pair)
        if logger: logger.debug(f"Adding pair for Gemini: {f1_path.name} <-> {f2_path.name} (Reps: {rep1.name} <-> {rep2.name})")
    if not pairs_to_analyze:
        if logger: logger.info(f"No folder pairs remaining for Gemini analysis after filtering (Range: {min_sim}-{max_sim}%, Rep Threshold: {config.GEMINI_HIGH_SIMILARITY_THRESHOLD_FOR_REPRESENTATIVE}%). Skipped {skipped_count_rep} same-rep pairs, {skipped_count_dup_rep} duplicate-rep pairs.")
        print(f"\nNo folder pairs found within the specified range ({min_sim}-{max_sim}%) for Gemini analysis after optimization.")
        return
    pairs_to_analyze.sort(key=lambda x: (x.ml_similarity_score if x.ml_similarity_score is not None else x.weighted_score), reverse=True)
    total_candidates = len(candidate_results)
    final_count = len(pairs_to_analyze)
    if logger: logger.info(f"Gemini analysis will run on {final_count} pairs (filtered from {total_candidates}). Skipped {skipped_count_rep} same-rep pairs, {skipped_count_dup_rep} duplicate-rep pairs.")
    print(f"\n{utils.AnsiColors.CYAN}--- Running Optimized Gemini Analysis ({final_count} pairs between {min_sim}-{max_sim}%, reduced from {total_candidates}) ---{utils.AnsiColors.RESET}")
    try:
        gemini_analyzer = GeminiAnalyzer()
    except ValueError as e:
        if logger: logger.error(f"Failed to initialize Gemini Analyzer: {e}.")
        print(f"{utils.AnsiColors.RED}Error: Failed to initialize Gemini Analyzer. Check API Key ({config.GEMINI_API_KEY_ENV_VAR}).{utils.AnsiColors.RESET}")
        return
    except Exception as e:
        if logger: logger.error(f"Unexpected error initializing Gemini Analyzer: {e}", exc_info=True)
        print(f"{utils.AnsiColors.RED}Error: Unexpected error initializing Gemini Analyzer.{utils.AnsiColors.RESET}")
        return
    analysis_count = 0
    cached_hits_count = 0
    start_time = time.time()
    for i, result in enumerate(pairs_to_analyze):
        f1 = all_folders.get(result.folder1_path)
        f2 = all_folders.get(result.folder2_path)
        if not f1 or not f2:
            if logger: logger.warning(f"Skipping Gemini analysis for pair ({result.folder1_path.name}, {result.folder2_path.name}): FolderInfo missing.")
            continue
        progress = f"({i+1}/{len(pairs_to_analyze)})"
        cache_key = frozenset({str(result.folder1_path), str(result.folder2_path)})
        if cached_results_map and cache_key in cached_results_map:
            cached_result = cached_results_map[cache_key]
            if cached_result.gemini_verdict is not None and cached_result.gemini_error is None:
                result.gemini_verdict = cached_result.gemini_verdict
                result.gemini_similarity_score = cached_result.gemini_similarity_score
                result.gemini_reason = cached_result.gemini_reason
                result.gemini_error = None
                if logger: logger.info(f"{progress} Using cached Gemini result for pair ({f1.path.name}, {f2.path.name}). Verdict: {result.gemini_verdict}")
                print(f"{progress} Using cached Gemini result for pair: '{f1.path.name}' <-> '{f2.path.name}'. Verdict: {result.gemini_verdict}")
                cached_hits_count += 1
                analysis_count += 1
                continue
            else:
                if logger: logger.debug(f"Cached Gemini result for pair ({f1.path.name}, {f2.path.name}) was invalid (verdict: {cached_result.gemini_verdict}, error: {cached_result.gemini_error}) or incomplete. Will re-analyze.")
        score_for_gemini = result.ml_similarity_score if result.ml_similarity_score is not None else None
        basis_score_str = f"ML Score: {score_for_gemini:.2f}%" if score_for_gemini is not None else "No Score Provided"
        print(f"{progress} Analyzing pair: '{f1.path.name}' <-> '{f2.path.name}' ({basis_score_str}) with Gemini API", end='\r')
        if logger: logger.info(f"{progress} Sending pair to Gemini API: {f1.path.name} <-> {f2.path.name}")
        verdict, gemini_sim_score, reason_or_error = gemini_analyzer.analyze_pair(f1, f2, score_for_gemini)
        print(" " * 120, end='\r')
        is_error = reason_or_error and ("API_ERROR" in reason_or_error or "PARSE_ERROR" in reason_or_error or "TIMEOUT" in reason_or_error or "UNEXPECTED" in reason_or_error)
        is_invalid_response = verdict is None and not is_error
        if is_error or is_invalid_response:
            result.gemini_error = reason_or_error
            result.gemini_verdict = None
            result.gemini_similarity_score = None
            result.gemini_reason = None
            log_message = f"Gemini analysis failed or returned invalid verdict for pair ({f1.path.name}, {f2.path.name}): {reason_or_error}"
            if logger: logger.warning(log_message)
            print(f"{progress} {utils.AnsiColors.RED}Error/Invalid Verdict analyzing pair: '{f1.path.name}' <-> '{f2.path.name}'. See logs.{utils.AnsiColors.RESET}")
        else:
            result.gemini_verdict = verdict
            result.gemini_similarity_score = gemini_sim_score
            result.gemini_reason = reason_or_error
            result.gemini_error = None
            verdict_display = verdict if verdict else "Inconclusive"
            gemini_sim_score_str = f"{gemini_sim_score:.1f}%" if gemini_sim_score is not None else "N/A"
            print(f"{progress} Analyzed pair: '{f1.path.name}' <-> '{f2.path.name}'. Verdict: {verdict_display} (Gemini Similarity: {gemini_sim_score_str})")
        analysis_count += 1
        time.sleep(config.GEMINI_API_DELAY_SECONDS)
    end_time = time.time()
    duration = end_time - start_time
    api_calls_made = analysis_count - cached_hits_count
    print(" " * 120, end='\r')
    print(f"{utils.AnsiColors.CYAN}--- Gemini Analysis Complete ({analysis_count} pairs processed in {duration:.2f}s; {cached_hits_count} from cache, {api_calls_made} via API) ---{utils.AnsiColors.RESET}")
    if logger: logger.info(f"Gemini analysis finished. Processed {analysis_count} pairs in {duration:.2f} seconds. Used cache for {cached_hits_count} pairs, made {api_calls_made} API calls.")
def run_analysis(args):
    global logger
    if not getattr(run_analysis, 'logger_initialized', False):
        utils.setup_logging(args.log_level, config.LOGS_DIR)
        logger = logging.getLogger(__name__)
        run_analysis.logger_initialized = True
    if logger: logger.info("Starting Music Duplicate Detector Analysis")
    if logger: logger.info(f"Run arguments: {vars(args)}")
    data_store = DataStore(
        music_cache_file=config.MUSIC_DATA_CACHE_FILE,
        comparison_cache_file=config.COMPARISON_RESULTS_CACHE_FILE
    )
    enable_hashing = not args.disable_hash
    file_processor = FileProcessor(enable_hashing=enable_hashing)
    folder_scanner = FolderScanner(file_processor, data_store, force_rescan=args.force_rescan)
    comparison_engine = ComparisonEngine(enable_hashing=enable_hashing)
    quality_analyzer = QualityAnalyzer(preferred_bitrate=args.bitrate)
    ml_similarity_model = None
    if args.ml_scoring:
        ml_similarity_model = MLSimilarityModel()
        if not ml_similarity_model.model_loaded:
            if logger: logger.warning("ML scoring was requested (--ml-scoring) but model failed to load. Proceeding without ML scoring.")
    else:
        if logger: logger.info("ML scoring not requested (--ml-scoring flag not set).")
    start_scan_time = time.time()
    root_paths = [Path(p) for p in args.folders]
    all_scanned_folders: Dict[Path, FolderInfo] = folder_scanner.scan_folders(root_paths)
    scan_duration = time.time() - start_scan_time
    if logger: logger.info(f"Folder scanning finished in {scan_duration:.2f} seconds.")
    cached_comparison_results_map: Dict[FrozenSet[str], FolderComparisonResult] = {}
    if args.force_rescan or args.clear_comparison_cache:
        if logger: logger.info("`--force-rescan` or `--clear-comparison-cache` is set. Skipping load of cached comparison results to ensure fresh Gemini analysis if needed.")
        print("`--force-rescan` or `--clear-comparison-cache` is set. Cached comparison results will be ignored, and Gemini analysis will be re-fetched for relevant pairs.")
    else:
        cached_comparison_results_map = data_store.load_comparison_results()
        if cached_comparison_results_map:
            if logger: logger.info(f"Loaded {len(cached_comparison_results_map)} cached comparison results into map.")
        else:
            if logger: logger.info("No cached comparison results found or loaded.")
    if not all_scanned_folders:
        if logger: logger.warning("No valid music folders found or processed. Exiting.")
        print("No music folders meeting the criteria were found in the specified paths.")
        return
    start_compare_time = time.time()
    all_comparison_results: List[FolderComparisonResult] = comparison_engine.find_similar_folders(all_scanned_folders)
    compare_duration = time.time() - start_compare_time
    if logger:
        logger.info(f"Folder comparison finished in {compare_duration:.2f} seconds. Processed {len(all_comparison_results)} total pairs.")
    if args.ml_scoring and ml_similarity_model and ml_similarity_model.model_loaded:
        if logger: logger.info("Enhancing comparison results with ML model predictions...")
        ml_predictions_made = 0
        for result in all_comparison_results:
            folder1_info = all_scanned_folders.get(result.folder1_path)
            folder2_info = all_scanned_folders.get(result.folder2_path)
            if folder1_info and folder2_info:
                ml_score = ml_similarity_model.predict_similarity_for_pair(
                    folder1_info, folder2_info, result
                )
                if ml_score is not None:
                    result.ml_similarity_score = ml_score
                    ml_predictions_made += 1
            else:
                if logger: logger.warning(f"FolderInfo not found for pair {result.folder1_path.name} - {result.folder2_path.name} "
                                           f"during ML enhancement. Skipping ML for this pair.")
        if logger: logger.info(f"ML enhancement complete. {ml_predictions_made} predictions made.")
    elif args.ml_scoring and (not ml_similarity_model or not ml_similarity_model.model_loaded):
        if logger: logger.warning("ML scoring requested but model is not available/loaded. Proceeding without ML scores.")
    else:
        if logger: logger.info("ML scoring was not requested. Skipping ML enhancement step.")
    folders_for_quality_analysis: Set[Path] = set()
    if all_comparison_results:
        for result in all_comparison_results:
            current_score = result.final_combined_score if result.final_combined_score is not None else \
                            (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score)
            if current_score >= config.MINIMAL_DISPLAY_SIMILARITY:
                folders_for_quality_analysis.add(result.folder1_path)
                folders_for_quality_analysis.add(result.folder2_path)
    if folders_for_quality_analysis:
        start_quality_time = time.time()
        if logger: logger.info(f"Calculating quality scores for {len(folders_for_quality_analysis)} folders involved in potentially similar pairs...")
        processed_quality_count = 0
        for folder_path in folders_for_quality_analysis:
            folder_info = all_scanned_folders.get(folder_path)
            if folder_info:
                quality_analyzer.calculate_quality(folder_info)
                processed_quality_count +=1
            else:
                if logger: logger.warning(f"Folder {folder_path} not found in all_scanned_folders for quality analysis.")
        quality_duration = time.time() - start_quality_time
        if logger: logger.info(f"Quality score calculation complete for {processed_quality_count} folders in {quality_duration:.2f} seconds.")
    else:
        if logger: logger.info("No similar folder pairs found meeting display criteria. Skipping quality score calculation.")
    if args.gemini_analysis:
        run_gemini_analysis(
            all_comparison_results,
            all_scanned_folders,
            args.gemini_range,
            cached_results_map=cached_comparison_results_map
        )
    else:
        if logger: logger.info("Gemini analysis was not requested (--gemini-analysis flag not set).")
    for result in all_comparison_results:
        algorithmic_component = result.weighted_score
        if args.ml_scoring and result.ml_similarity_score is not None:
            algorithmic_component = result.ml_similarity_score
            if logger: logger.debug(f"Using ML score ({algorithmic_component:.4f}) as base for final combined score for pair {result.folder1_path.name} - {result.folder2_path.name}")
        if result.gemini_verdict is not None and \
           result.gemini_similarity_score is not None and \
           result.gemini_error is None:
            try:
                gemini_score_val = float(result.gemini_similarity_score)
                gemini_score_val = min(max(gemini_score_val, 0.0), 100.0)
                result.final_combined_score = (algorithmic_component * config.ALGORITHMIC_SCORE_WEIGHT) + \
                                              (gemini_score_val * config.GEMINI_SCORE_WEIGHT)
                result.final_combined_score = min(max(result.final_combined_score, 0.0), 100.0)
            except (ValueError, TypeError):
                if logger: logger.warning(f"Could not parse gemini_similarity_score '{result.gemini_similarity_score}' as float for pair {result.folder1_path.name} - {result.folder2_path.name}. Using algorithmic component as final.")
                result.final_combined_score = algorithmic_component
        else:
            result.final_combined_score = algorithmic_component
    if logger: logger.info("Final combined scores calculated for all comparison results from this run.")
    results_to_cache = [
        r for r in all_comparison_results
        if (r.final_combined_score if r.final_combined_score is not None else \
            (r.ml_similarity_score if r.ml_similarity_score is not None else r.weighted_score)) >= config.MIN_SCORE_FOR_CACHING
    ]
    if results_to_cache:
        if logger: logger.info(f"Saving/Updating {len(results_to_cache)} comparison results (score >= {config.MIN_SCORE_FOR_CACHING}%) to cache: {data_store.comparison_cache_file}")
        data_store.save_comparison_results(results_to_cache)
        if logger: logger.info("Comparison results saved/updated successfully in cache.")
    else:
        if logger: logger.info(f"No new/updated comparison results from this run met the threshold ({config.MIN_SCORE_FOR_CACHING}%) to save to cache.")
    display_results_list = [
        r for r in all_comparison_results
        if (r.final_combined_score if r.final_combined_score is not None else \
            (r.ml_similarity_score if r.ml_similarity_score is not None else r.weighted_score)) >= config.MINIMAL_DISPLAY_SIMILARITY
    ]
    display_results_list.sort(
        key=lambda x: x.final_combined_score if x.final_combined_score is not None else \
                      (x.ml_similarity_score if x.ml_similarity_score is not None else x.weighted_score),
        reverse=True
    )
    display_comparison_results(display_results_list, all_scanned_folders)
    if display_results_list:
        display_quality_results_grouped(all_scanned_folders, display_results_list)
    else:
        if logger: logger.info("No comparison results meeting the display threshold to show.")
    preferred_root_path_obj = Path(args.preferred_root) if args.preferred_root else None
    action_handler = ActionHandler(all_scanned_folders, file_processor, preferred_root_path=preferred_root_path_obj)
    merge_candidates = [
        r for r in display_results_list
        if (r.final_combined_score if r.final_combined_score is not None else \
            (r.ml_similarity_score if r.ml_similarity_score is not None else r.weighted_score)) >= config.MIN_SIMILARITY_FOR_MERGE
    ]
    if merge_candidates:
        try:
            print(f"\nFound {len(merge_candidates)} pairs with similarity >= {config.MIN_SIMILARITY_FOR_MERGE}% eligible for merging.")
            user_input_merge = input(f"Merge metadata/art for these {len(merge_candidates)} pairs? (y/n): ").strip().lower()
        except EOFError:
            user_input_merge = 'n'
            print("Non-interactive mode detected, skipping merge confirmation.")
        if user_input_merge == 'y':
            action_handler.merge_similar_folders(merge_candidates)
            print("Metadata merge process finished.")
        else:
            print("Skipping metadata merge.")
            if logger: logger.info("User skipped merging.")
    else:
        if logger: logger.info(f"No pairs met the threshold ({config.MIN_SIMILARITY_FOR_MERGE}%) for merging.")
        print(f"\nNo folder pairs found with similarity >= {config.MIN_SIMILARITY_FOR_MERGE}% for merging.")
    min_similarity_for_delete = None
    try:
        if display_results_list:
             del_thresh_input = input(f"\nEnter minimum combined similarity % to mark for deletion (e.g., {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}), or leave blank to skip: ").strip()
             if del_thresh_input:
                 min_similarity_for_delete = float(del_thresh_input)
                 if not (0 <= min_similarity_for_delete <= 100):
                     print(f"{utils.AnsiColors.YELLOW}Warning: Invalid threshold '{del_thresh_input}'. Using default: {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%{utils.AnsiColors.RESET}")
                     min_similarity_for_delete = config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
                     if logger: logger.warning(f"Invalid delete threshold input '{del_thresh_input}', using default {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}")
        else:
             print("\nNo similar pairs found to prompt for deletion.")
    except ValueError:
        print(f"{utils.AnsiColors.RED}Error: Invalid input. Please enter a number.{utils.AnsiColors.RESET}")
        print(f"Using default threshold for potential deletion: {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%")
        min_similarity_for_delete = config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
        if logger: logger.warning(f"Invalid delete threshold input (not a number), using default {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}")
    except EOFError:
        min_similarity_for_delete = None
        print("Non-interactive mode detected, skipping deletion prompt.")
    if min_similarity_for_delete is not None:
        # Use the filtered display_results_list for identifying folders to delete
        folders_to_delete_pairs = action_handler.identify_folders_to_delete(display_results_list, min_similarity_for_delete)
        if folders_to_delete_pairs:
            if args.preferred_root:
                 print(f"{utils.AnsiColors.CYAN}Note: Preferred root folder for keeping files is '{args.preferred_root}'. This overrides quality score in some cases.{utils.AnsiColors.RESET}")
            action_handler.delete_folders_interactive(folders_to_delete_pairs)
        else:
             print(f"No folders identified for deletion with similarity >= {min_similarity_for_delete}%.")
             if logger: logger.info(f"No folders met deletion criteria with threshold {min_similarity_for_delete}%.")
    else:
        print("Skipping deletion process.")
        if logger: logger.info("Deletion process skipped.")
    total_duration = time.time() - start_scan_time
    if logger: logger.info(f"Analysis finished. Total execution time: {total_duration:.2f} seconds.")
    print(f"\nAnalysis complete. Total time: {total_duration:.2f}s")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyzes music folders to find duplicates, assess quality, and optionally leverage Gemini API for deeper comparison.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("folders", nargs="+", metavar="FOLDER",
                        help="One or more root folder paths to scan for music.")
    parser.add_argument("-l", "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default=config.DEFAULT_LOG_LEVEL,
                        help="Set the logging level.")
    parser.add_argument("-p", "--preferred-root", type=str, default=None, metavar="PREF_ROOT_PATH",
                        help="Optional. Path to a root folder that should be preferred for keeping files in case of duplicates. Must be one of the input FOLDERs.")
    scan_group = parser.add_argument_group('Scanning and Analysis Options')
    scan_group.add_argument("-b", "--bitrate", choices=["128", "high"], default="128",
                            help="Preferred bitrate target for quality assessment.")
    scan_group.add_argument("-d", "--disable-hash", action="store_true",
                            help="Disable file hashing (faster scan, less accurate identity check).")
    scan_group.add_argument("-r", "--force-rescan", action="store_true",
                            help="Force rescan of folder metadata, ignoring music data cache. Also forces re-fetching of Gemini results if comparison cache is not cleared.")
    scan_group.add_argument(
        "-c", "--clear-comparison-cache",
        action="store_true",
        help="Clear the cached comparison and Gemini results before running. "
             "This forces re-computation of algorithmic similarities if they were cached "
             "and re-fetching all Gemini analysis results."
    )
    ml_group = parser.add_argument_group('Machine Learning Model Options')
    ml_group.add_argument("-m", "--ml-scoring", action="store_true",
                          help=f"Enable similarity scoring using the local ML model. Requires '{config.ML_MODEL_FILE.name}' in data directory.")
    gemini_group = parser.add_argument_group('Gemini Analysis Options (Optional)')
    gemini_group.add_argument("-g", "--gemini-analysis", action="store_true",
                              help=f"Enable Gemini API analysis. Requires '{config.GEMINI_API_KEY_ENV_VAR}' env var and 'google-generativeai', 'requests', 'Pillow'.")
    gemini_group.add_argument("-gr", "--gemini-range", type=str, default=config.DEFAULT_GEMINI_SIMILARITY_RANGE,
                              metavar="MIN-MAX",
                              help="Similarity range ('min-max' percentage, based on algorithmic or ML score) for sending pairs to Gemini API.")
    args = parser.parse_args()
    # --- START OF FIX ---
    log_level_initial = getattr(logging, args.log_level.upper(), logging.INFO)
    # --- END OF FIX ---
    logging.basicConfig(level=log_level_initial, format=config.LOG_FORMAT, handlers=[logging.StreamHandler()])
    logger = logging.getLogger(__name__)
    if args.clear_comparison_cache:
        print(f"Attempting to clear comparison results cache: {config.COMPARISON_RESULTS_CACHE_FILE}")
        if logger: logger.info(f"User requested clearing of comparison results cache: {config.COMPARISON_RESULTS_CACHE_FILE}")
        try:
            if config.COMPARISON_RESULTS_CACHE_FILE.exists():
                 config.COMPARISON_RESULTS_CACHE_FILE.unlink()
                 print(f"Successfully cleared comparison results cache: {config.COMPARISON_RESULTS_CACHE_FILE}")
                 if logger: logger.info(f"Successfully cleared comparison results cache: {config.COMPARISON_RESULTS_CACHE_FILE}")
            else:
                 print(f"Comparison results cache file did not exist or was already deleted: {config.COMPARISON_RESULTS_CACHE_FILE}")
                 if logger: logger.info(f"Comparison results cache file did not exist or was already deleted: {config.COMPARISON_RESULTS_CACHE_FILE}")
        except Exception as e:
            if logger: logger.error(f"Error clearing comparison results cache {config.COMPARISON_RESULTS_CACHE_FILE}: {e}", exc_info=True)
            print(f"{utils.AnsiColors.RED}Error clearing comparison results cache {config.COMPARISON_RESULTS_CACHE_FILE}: {e}{utils.AnsiColors.RESET}")
    valid_folders = []
    invalid_paths = []
    if not args.folders:
         parser.error("No input folders specified.")
    for folder_str in args.folders:
        p = Path(folder_str)
        try:
            if p.is_dir():
                valid_folders.append(p.resolve())
            else:
                invalid_paths.append(folder_str)
        except OSError as e:
            if logger: logger.error(f"Error accessing path '{folder_str}': {e}")
            invalid_paths.append(f"{folder_str} (Error: {e})")
        except Exception as e:
            if logger: logger.error(f"Invalid path specified '{folder_str}': {e}")
            invalid_paths.append(f"{folder_str} (Invalid Path)")
    if invalid_paths:
        print(f"{utils.AnsiColors.RED}Error: The following input paths are invalid or inaccessible:{utils.AnsiColors.RESET}")
        for invalid in invalid_paths:
            print(f"- {invalid}")
        if not valid_folders:
            print("No valid folders provided. Exiting.")
            sys.exit(1)
        else:
            print("Proceeding with the valid paths...")
    args.folders = [str(p) for p in valid_folders]
    if args.preferred_root:
        pref_root_path = Path(args.preferred_root).resolve()
        if not pref_root_path.is_dir():
            print(f"{utils.AnsiColors.RED}Error: Preferred root path '{args.preferred_root}' is not a valid directory.{utils.AnsiColors.RESET}")
            sys.exit(1)
        if not any(pref_root_path == Path(f_str).resolve() for f_str in args.folders):
            print(f"{utils.AnsiColors.RED}Error: Preferred root path '{args.preferred_root}' must be one of the input FOLDERs.{utils.AnsiColors.RESET}")
            resolved_input_folders = [str(Path(f).resolve()) for f in args.folders]
            print(f"Input folders provided (resolved): {resolved_input_folders}")
            sys.exit(1)
        args.preferred_root = str(pref_root_path)
        if logger: logger.info(f"Preferred root for keeping files set to: {args.preferred_root}")
    if args.gemini_analysis and not GEMINI_AVAILABLE:
        print(f"{utils.AnsiColors.YELLOW}Warning: Gemini analysis requested (--gemini-analysis) but the API key ({config.GEMINI_API_KEY_ENV_VAR}) is missing or required libraries ('google-generativeai', 'requests', 'Pillow') are not installed properly. Gemini analysis will be skipped.{utils.AnsiColors.RESET}")
        if logger: logger.warning(f"Gemini analysis requested but disabled (API Key: {bool(GEMINI_API_KEY)}, Module Import: {GeminiAnalyzer is not None}).")
        args.gemini_analysis = False
    if args.ml_scoring:
        if not config.ML_MODEL_FILE.exists():
            print(f"{utils.AnsiColors.YELLOW}Warning: ML scoring requested (--ml-scoring) but the model file '{config.ML_MODEL_FILE}' was not found. ML scoring will be disabled.{utils.AnsiColors.RESET}")
            if logger: logger.warning(f"ML scoring requested but model file '{config.ML_MODEL_FILE}' not found. Disabling ML scoring for this run.")
            args.ml_scoring = False
    try:
        run_analysis(args)
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
        if logger: logger.warning("Analysis interrupted by user (KeyboardInterrupt).")
        sys.exit(1)
    except Exception as e:
        if logger: logger.error(f"An unexpected error occurred during analysis: {e}", exc_info=True)
        print(f"\n{utils.AnsiColors.RED}An unexpected error occurred. Please check the logs in the 'logs' directory for details.{utils.AnsiColors.RESET}")
        sys.exit(1)