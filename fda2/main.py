# main.py
import argparse
from collections import defaultdict
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
import time
import sys

# Import necessary components from other modules
import config
import utils
from models import FolderInfo, FolderComparisonResult # Ensure FolderComparisonResult is imported
from data_store import DataStore
from file_processor import FileProcessor
from folder_scanner import FolderScanner
from comparison_engine import ComparisonEngine
from quality_analyzer import QualityAnalyzer
from action_handler import ActionHandler

# Import Gemini analyzer and handle availability
try:
    from gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
    if not GEMINI_AVAILABLE:
        logging.warning(f"Gemini API Key ({config.GEMINI_API_KEY_ENV_VAR}) not found or 'requests'/'Pillow'/'google-generativeai' missing. Gemini analysis will be disabled.")
except ImportError as e:
    logging.warning(f"Could not import GeminiAnalyzer module (check 'google-generativeai', 'requests', 'Pillow'): {e}. Gemini analysis disabled.")
    GeminiAnalyzer = None
    GEMINI_AVAILABLE = False
    GEMINI_API_KEY = None


# --- Presentation Logic ---
def display_comparison_results(results: List[FolderComparisonResult], all_folders: Dict[Path, FolderInfo]):
    """Prints the comparison results to the console, including Gemini analysis if available."""
    if not results:
        print(utils.AnsiColors.GREEN + "\nNo significantly similar folders found." + utils.AnsiColors.RESET)
        return

    print(utils.AnsiColors.CYAN + "\n--- Similarity Comparison Results ---" + utils.AnsiColors.RESET)
    print(f"(Showing pairs with similarity >= {config.MINIMAL_DISPLAY_SIMILARITY}%)\n")

    results.sort(key=lambda x: x.weighted_score, reverse=True) # Ensure sorted display

    for result in results:
        f1_path = result.folder1_path
        f2_path = result.folder2_path
        score = result.weighted_score
        f1_info = all_folders.get(f1_path)
        f2_info = all_folders.get(f2_path)
        q1_str = f"(Q: {f1_info.quality_score:.2f}%)" if f1_info and f1_info.quality_score is not None else "(Q: N/A)"
        q2_str = f"(Q: {f2_info.quality_score:.2f}%)" if f2_info and f2_info.quality_score is not None else "(Q: N/A)"

        color = utils.AnsiColors.GREEN if score >= 90 else utils.AnsiColors.YELLOW if score >= 70 else utils.AnsiColors.RESET
        print(f"Pair: '{utils.AnsiColors.BLUE}{f1_path.name}{utils.AnsiColors.RESET}' {q1_str} <-> '{utils.AnsiColors.BLUE}{f2_path.name}{utils.AnsiColors.RESET}' {q2_str}")
        print(f"  Similarity Score: {color}{score:.2f}%{utils.AnsiColors.RESET}")
        if result.is_identical_by_hash:
            print(f"  {utils.AnsiColors.MAGENTA}(Identical by file hashes){utils.AnsiColors.RESET}")

        # --- Display Gemini Results (UPDATED for verdict string) ---
        if result.gemini_error:
            # Display specific error types differently? Optional.
            err_prefix = utils.AnsiColors.RED + "Gemini Error:" + utils.AnsiColors.RESET
            if "API_ERROR: Prompt Blocked" in result.gemini_error:
                 err_prefix = utils.AnsiColors.YELLOW + "Gemini Blocked:" + utils.AnsiColors.RESET
            elif "API_ERROR: Request timed out" in result.gemini_error:
                 err_prefix = utils.AnsiColors.YELLOW + "Gemini Timeout:" + utils.AnsiColors.RESET

            print(f"  {err_prefix} {result.gemini_error[:150]}{'...' if len(result.gemini_error) > 150 else ''}")

        elif result.gemini_verdict is not None: # Check the new verdict field
            verdict = result.gemini_verdict
            verdict_text = "Unknown Verdict" # Default text
            verdict_color = utils.AnsiColors.RED # Default color for unknown

            if verdict == 'duplicate':
                verdict_text = "Likely Duplicate"
                verdict_color = utils.AnsiColors.GREEN
            elif verdict == 'different':
                verdict_text = "Likely Different"
                verdict_color = utils.AnsiColors.YELLOW # Keep yellow for different? Or make it red/less prominent?
            elif verdict == 'uncertain':
                verdict_text = "Uncertain"
                verdict_color = utils.AnsiColors.MAGENTA # Magenta or Cyan for uncertain

            conf_str = f"{result.gemini_confidence:.1f}%" if result.gemini_confidence is not None else "N/A"
            print(f"  {utils.AnsiColors.CYAN}Gemini Verdict:{utils.AnsiColors.RESET} {verdict_color}{verdict_text}{utils.AnsiColors.RESET} (Confidence: {conf_str})")
            if result.gemini_reason:
                reason_preview = result.gemini_reason.replace('\n', ' ').strip()
                print(f"  {utils.AnsiColors.CYAN}Gemini Reason:{utils.AnsiColors.RESET} {reason_preview[:200]}{'...' if len(reason_preview) > 200 else ''}")
        # --- End Gemini Display ---

        # Debug: Show detailed scores if log level is DEBUG
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

# --- (display_quality_results_grouped remains the same) ---
def display_quality_results_grouped(all_folders: Dict[Path, FolderInfo], comparison_results: List[FolderComparisonResult]):
    """Displays folder quality, grouped by similarity clusters."""
    print(utils.AnsiColors.CYAN + "\n--- Folder Quality Assessment (Grouped by Similarity) ---" + utils.AnsiColors.RESET)

    graph: Dict[Path, Set[Path]] = defaultdict(set)
    nodes_in_graph: Set[Path] = set()
    for result in comparison_results:
        if result.weighted_score >= config.MINIMAL_DISPLAY_SIMILARITY:
             f1_path, f2_path = result.folder1_path, result.folder2_path
             graph[f1_path].add(f2_path)
             graph[f2_path].add(f1_path)
             nodes_in_graph.add(f1_path)
             nodes_in_graph.add(f2_path)

    all_folder_paths = set(all_folders.keys())
    single_folders = all_folder_paths - nodes_in_graph
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

                if not component_folders: continue

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

    if single_folders:
        print(f"\n{utils.AnsiColors.MAGENTA}Single Folders (No Significant Similarity Found):{utils.AnsiColors.RESET}")
        sorted_singles = sorted(
            [all_folders[p] for p in single_folders if p in all_folders],
            key=lambda f: (f.quality_score is not None, f.quality_score if f.quality_score is not None else -1), reverse=True
        )
        for folder in sorted_singles:
            quality = folder.quality_score if folder.quality_score is not None else -1.0
            q_str = f"{quality:.2f}%" if quality >= 0 else "N/A "
            color = utils.AnsiColors.RESET
            if quality >=0:
                 color = utils.AnsiColors.GREEN if quality > 75 else utils.AnsiColors.YELLOW if quality > 50 else utils.AnsiColors.RED
            print(f"    {color}{q_str:<7}{utils.AnsiColors.RESET} '{folder.path}'")
            if logging.getLogger().isEnabledFor(logging.DEBUG) and folder.quality_breakdown:
                breakdown_str = ", ".join([f"{k}: {v:.1f}" for k, v in sorted(folder.quality_breakdown.items())])
                print(f"      Breakdown: [{breakdown_str}]")

    print(utils.AnsiColors.CYAN + "\n--- End of Quality Assessment ---" + utils.AnsiColors.RESET)


# --- Gemini Analysis Function ---
def run_gemini_analysis(
    comparison_results: List[FolderComparisonResult],
    all_folders: Dict[Path, FolderInfo],
    gemini_range_str: str
) -> None:
    """Runs Gemini analysis on folder pairs within the specified similarity range."""
    global logger

    if not GEMINI_AVAILABLE or not GeminiAnalyzer:
        logger.warning("Gemini analysis skipped (API Key missing, module/dependencies unavailable, or explicitly disabled).")
        return

    try:
        min_sim_str, max_sim_str = gemini_range_str.split('-')
        min_sim = float(min_sim_str)
        max_sim = float(max_sim_str)
        if not (0 <= min_sim <= 100 and 0 <= max_sim <= 100 and min_sim <= max_sim):
            raise ValueError("Invalid range values (must be 0-100 and min <= max)")
    except ValueError as e:
        logger.error(f"Invalid Gemini similarity range '{gemini_range_str}'. Error: {e}. Skipping Gemini analysis.")
        print(f"{utils.AnsiColors.RED}Error: Invalid Gemini similarity range '{gemini_range_str}'. Skipping Gemini analysis.{utils.AnsiColors.RESET}")
        return

    logger.info(f"Starting Gemini analysis for pairs with similarity between {min_sim}% and {max_sim}%...")
    pairs_to_analyze = [
        result for result in comparison_results
        if min_sim <= result.weighted_score <= max_sim and not result.is_identical_by_hash
    ]

    if not pairs_to_analyze:
        logger.info("No folder pairs found within the specified range for Gemini analysis.")
        print("\nNo folder pairs found within the specified range for Gemini analysis.")
        return

    pairs_to_analyze.sort(key=lambda x: x.weighted_score, reverse=True)
    print(f"\n{utils.AnsiColors.CYAN}--- Running Gemini Analysis ({len(pairs_to_analyze)} pairs between {min_sim}-{max_sim}%) ---{utils.AnsiColors.RESET}")

    try:
        gemini_analyzer = GeminiAnalyzer()
    except ValueError as e:
        logger.error(f"Failed to initialize Gemini Analyzer: {e}.")
        print(f"{utils.AnsiColors.RED}Error: Failed to initialize Gemini Analyzer. Check API Key ({config.GEMINI_API_KEY_ENV_VAR}).{utils.AnsiColors.RESET}")
        return
    except Exception as e:
         logger.error(f"Unexpected error initializing Gemini Analyzer: {e}", exc_info=True)
         print(f"{utils.AnsiColors.RED}Error: Unexpected error initializing Gemini Analyzer.{utils.AnsiColors.RESET}")
         return

    analysis_count = 0
    start_time = time.time()
    for i, result in enumerate(pairs_to_analyze):
        f1 = all_folders.get(result.folder1_path)
        f2 = all_folders.get(result.folder2_path)
        if not f1 or not f2:
            logger.warning(f"Skipping Gemini analysis for pair ({result.folder1_path.name}, {result.folder2_path.name}): FolderInfo missing.")
            continue

        progress = f"({i+1}/{len(pairs_to_analyze)})"
        print(f"{progress} Analyzing pair: '{f1.path.name}' <-> '{f2.path.name}' (Score: {result.weighted_score:.2f}%)", end='\r')
        logger.info(f"{progress} Sending pair to Gemini: {f1.path.name} <-> {f2.path.name}")

        # UPDATED: Call analyze_pair which now returns verdict string
        verdict, conf, reason_or_error = gemini_analyzer.analyze_pair(f1, f2, result.weighted_score)

        print(" " * 120, end='\r') # Clear progress line

        # Store results in the FolderComparisonResult object
        # Check if the third return value indicates an error or if verdict is None after validation
        is_error = reason_or_error and ("API_ERROR" in reason_or_error or "PARSE_ERROR" in reason_or_error or "TIMEOUT" in reason_or_error or "UNEXPECTED" in reason_or_error)
        is_invalid_response = verdict is None and not is_error # Handle cases where verdict is None due to invalid value, not API error

        if is_error or is_invalid_response:
            result.gemini_error = reason_or_error # Store the error message or reason for invalid verdict
            result.gemini_verdict = None # Ensure verdict is None
            result.gemini_confidence = None
            result.gemini_reason = None # Clear reason if it was part of an invalid response structure
            log_message = f"Gemini analysis failed or returned invalid verdict for pair ({f1.path.name}, {f2.path.name}): {reason_or_error}"
            logger.warning(log_message)
            print(f"{progress} {utils.AnsiColors.RED}Error/Invalid Verdict analyzing pair: '{f1.path.name}' <-> '{f2.path.name}'. See logs.{utils.AnsiColors.RESET}")
        else:
            result.gemini_verdict = verdict # Store the validated string verdict
            result.gemini_confidence = conf
            result.gemini_reason = reason_or_error # Store the valid reason
            result.gemini_error = None # Clear error field on success

            verdict_display = verdict if verdict else "Inconclusive" # Should not be None here, but good practice
            conf_str = f"{conf:.1f}%" if conf is not None else "N/A"
            print(f"{progress} Analyzed pair: '{f1.path.name}' <-> '{f2.path.name}'. Verdict: {verdict_display} ({conf_str})")

        analysis_count += 1
        time.sleep(config.GEMINI_API_DELAY_SECONDS)

    end_time = time.time()
    duration = end_time - start_time
    print(" " * 120, end='\r')
    print(f"{utils.AnsiColors.CYAN}--- Gemini Analysis Complete ({analysis_count} pairs analyzed in {duration:.2f}s) ---{utils.AnsiColors.RESET}")
    logger.info(f"Gemini analysis finished. Analyzed {analysis_count} pairs in {duration:.2f} seconds.")


# --- Main Execution Logic ---
def run_analysis(args):
    """Orchestrates the entire analysis process."""
    global logger
    if not getattr(run_analysis, 'logger_initialized', False):
        utils.setup_logging(args.log_level, config.LOGS_DIR)
        run_analysis.logger_initialized = True
        logger = logging.getLogger(__name__)

    logger.info("Starting Music Duplicate Detector Analysis")
    logger.info(f"Run arguments: {vars(args)}")

    # --- Initialization ---
    data_store = DataStore(config.MUSIC_DATA_CACHE_FILE)
    enable_hashing = not args.disable_hash
    file_processor = FileProcessor(enable_hashing=enable_hashing)
    folder_scanner = FolderScanner(file_processor, data_store, force_rescan=args.force_rescan)
    comparison_engine = ComparisonEngine(enable_hashing=enable_hashing)
    quality_analyzer = QualityAnalyzer(preferred_bitrate=args.bitrate)


    # --- Step 1: Scan Folders & Process Files ---
    start_scan_time = time.time()
    root_paths = [Path(p) for p in args.folders]
    all_scanned_folders: Dict[Path, FolderInfo] = folder_scanner.scan_folders(root_paths)
    scan_duration = time.time() - start_scan_time
    logger.info(f"Folder scanning finished in {scan_duration:.2f} seconds.")

    if not all_scanned_folders:
        logger.warning("No valid music folders found or processed. Exiting.")
        print("No music folders meeting the criteria were found in the specified paths.")
        return


    # --- Step 2: Calculate Quality Scores ---
    start_quality_time = time.time()
    logger.info("Calculating quality scores for all processed folders...")
    processed_count = 0
    for folder_info in all_scanned_folders.values():
        quality_analyzer.calculate_quality(folder_info)
        processed_count +=1
    quality_duration = time.time() - start_quality_time
    logger.info(f"Quality score calculation complete for {processed_count} folders in {quality_duration:.2f} seconds.")

    # --- Step 3: Compare Folders for Similarity ---
    start_compare_time = time.time()
    comparison_results: List[FolderComparisonResult] = comparison_engine.find_similar_folders(all_scanned_folders)
    compare_duration = time.time() - start_compare_time
    logger.info(f"Folder comparison finished in {compare_duration:.2f} seconds. Found {len(comparison_results)} pairs above display threshold.")


    # --- Step 3.5: Optional Gemini Analysis ---
    if args.gemini_analysis:
        run_gemini_analysis(comparison_results, all_scanned_folders, args.gemini_range)
    else:
        logger.info("Gemini analysis was not requested (--gemini-analysis flag not set).")


    # --- Step 4: Display Results ---
    # Display functions now handle the new gemini_verdict field
    display_comparison_results(comparison_results, all_scanned_folders)
    display_quality_results_grouped(all_scanned_folders, comparison_results)

    # --- Step 5: Initialize Action Handler ---
    action_handler = ActionHandler(all_scanned_folders, file_processor)


    # --- Step 6: User Actions (Merge) ---
    merge_candidates = [r for r in comparison_results if r.weighted_score >= config.MIN_SIMILARITY_FOR_MERGE]
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
            logger.info("User skipped merging.")
    else:
        logger.info(f"No pairs met the threshold ({config.MIN_SIMILARITY_FOR_MERGE}%) for merging.")
        print(f"\nNo folder pairs found with similarity >= {config.MIN_SIMILARITY_FOR_MERGE}% for merging.")


    # --- Step 7: User Actions (Delete) ---
    min_similarity_for_delete = None # Initialize
    try:
        if any(r.weighted_score >= config.MINIMAL_DISPLAY_SIMILARITY for r in comparison_results):
             del_thresh_input = input(f"\nEnter minimum similarity % to mark for deletion (e.g., {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}), or leave blank to skip: ").strip()
             if del_thresh_input:
                 min_similarity_for_delete = float(del_thresh_input)
                 if not (0 <= min_similarity_for_delete <= 100):
                     print(f"{utils.AnsiColors.YELLOW}Warning: Invalid threshold '{del_thresh_input}'. Using default: {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%{utils.AnsiColors.RESET}")
                     min_similarity_for_delete = config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
                     logger.warning(f"Invalid delete threshold input '{del_thresh_input}', using default {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}")
             # If input is blank, min_similarity_for_delete remains None
        else:
             print("\nNo similar pairs found, skipping deletion prompt.")
             # min_similarity_for_delete remains None

    except ValueError:
        print(f"{utils.AnsiColors.RED}Error: Invalid input. Please enter a number.{utils.AnsiColors.RESET}")
        print(f"Using default threshold for potential deletion: {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%")
        min_similarity_for_delete = config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
        logger.warning(f"Invalid delete threshold input (not a number), using default {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}")
    except EOFError:
        min_similarity_for_delete = None
        print("Non-interactive mode detected, skipping deletion prompt.")


    if min_similarity_for_delete is not None:
        folders_to_delete_pairs = action_handler.identify_folders_to_delete(comparison_results, min_similarity_for_delete)
        if folders_to_delete_pairs:
            action_handler.delete_folders_interactive(folders_to_delete_pairs)
        else:
             print(f"No folders identified for deletion with similarity >= {min_similarity_for_delete}%.")
             logger.info(f"No folders met deletion criteria with threshold {min_similarity_for_delete}%.")
    else:
        print("Skipping deletion process.")
        logger.info("Deletion process skipped.")


    total_duration = time.time() - start_scan_time
    logger.info(f"Analysis finished. Total execution time: {total_duration:.2f} seconds.")
    print(f"\nAnalysis complete. Total time: {total_duration:.2f}s")


if __name__ == "__main__":
    # --- Argument Parser Setup ---
    parser = argparse.ArgumentParser(
        description="Analyzes music folders to find duplicates, assess quality, and optionally leverage Gemini API for deeper comparison.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("folders", nargs="+", metavar="FOLDER",
                        help="One or more root folder paths to scan for music.")
    parser.add_argument("-l", "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default=config.DEFAULT_LOG_LEVEL,
                        help="Set the logging level.")

    scan_group = parser.add_argument_group('Scanning and Analysis Options')
    scan_group.add_argument("-b", "--bitrate", choices=["128", "high"], default="128",
                            help="Preferred bitrate target for quality assessment.")
    scan_group.add_argument("-d", "--disable-hash", action="store_true",
                            help="Disable file hashing (faster scan, less accurate identity check).")
    scan_group.add_argument("-r", "--force-rescan", action="store_true",
                            help="Force rescan, ignoring cache.")

    gemini_group = parser.add_argument_group('Gemini Analysis Options (Optional)')
    gemini_group.add_argument("-g", "--gemini-analysis", action="store_true",
                              help=f"Enable Gemini API analysis. Requires '{config.GEMINI_API_KEY_ENV_VAR}' env var and 'google-generativeai', 'requests', 'Pillow'.")
    gemini_group.add_argument("-gr", "--gemini-range", type=str, default=config.DEFAULT_GEMINI_SIMILARITY_RANGE,
                              metavar="MIN-MAX",
                              help="Similarity range ('min-max' percentage) for sending pairs to Gemini API.")

    args = parser.parse_args()

    # --- Initial Logging Setup ---
    log_level_initial = getattr(logging, args.log_level.upper(), logging.INFO)
    # Basic config first to catch early path errors
    logging.basicConfig(level=log_level_initial, format=config.LOG_FORMAT, handlers=[logging.StreamHandler()])
    logger = logging.getLogger(__name__)

    # --- Validate Input Folders ---
    valid_folders = []
    invalid_paths = []
    if not args.folders:
         parser.error("No input folders specified.")

    for folder_str in args.folders:
        p = Path(folder_str)
        try:
            if p.is_dir():
                # Use resolve() to get absolute path, handles relative paths better
                valid_folders.append(p.resolve())
            else:
                invalid_paths.append(folder_str)
        except OSError as e:
            logger.error(f"Error accessing path '{folder_str}': {e}")
            invalid_paths.append(f"{folder_str} (Error: {e})")
        except Exception as e:
            logger.error(f"Invalid path specified '{folder_str}': {e}")
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

    # Store validated, resolved paths as strings for consistency within args
    args.folders = [str(p) for p in valid_folders]

    # --- Check Gemini Availability vs. Request ---
    if args.gemini_analysis and not GEMINI_AVAILABLE:
        print(f"{utils.AnsiColors.YELLOW}Warning: Gemini analysis requested (--gemini-analysis) but the API key ({config.GEMINI_API_KEY_ENV_VAR}) is missing or required libraries ('google-generativeai', 'requests', 'Pillow') are not installed properly. Gemini analysis will be skipped.{utils.AnsiColors.RESET}")
        logger.warning(f"Gemini analysis requested but disabled (API Key: {bool(GEMINI_API_KEY)}, Module Import: {GeminiAnalyzer is not None}).")
        args.gemini_analysis = False # Ensure it's disabled if not available


    # --- Start Main Process ---
    try:
        # run_analysis will set up file logging
        run_analysis(args)
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
        logger.warning("Analysis interrupted by user (KeyboardInterrupt).")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred during analysis: {e}", exc_info=True)
        print(f"\n{utils.AnsiColors.RED}An unexpected error occurred. Please check the logs in the 'logs' directory for details.{utils.AnsiColors.RESET}")
        sys.exit(1)