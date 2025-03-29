# main.py
import argparse
from collections import defaultdict
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional # Added Optional
import time # הוספנו time למדידת זמנים
import sys # הוספנו sys ליציאה במקרה של שגיאת תיקיות

# Import necessary components from other modules
import config
import utils
from models import FolderInfo, FolderComparisonResult
from data_store import DataStore
from file_processor import FileProcessor
from folder_scanner import FolderScanner
from comparison_engine import ComparisonEngine
from quality_analyzer import QualityAnalyzer
from action_handler import ActionHandler

# ייבוא המנתח החדש של Gemini והטיפול בזמינותו
try:
    # ודא ש-gemini_analyzer.py נמצא בנתיב ה-PYTHONPATH או באותה תיקייה
    from gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY) # בדוק אם המפתח קיים כבר בזמן הייבוא
    if not GEMINI_AVAILABLE:
        # Log warning, but don't stop execution yet
        logging.warning(f"Gemini API Key ({config.GEMINI_API_KEY_ENV_VAR}) not found or 'requests'/'Pillow' missing. Gemini analysis will be disabled.")
except ImportError as e:
    # Log if the module itself couldn't be imported
    logging.warning(f"Could not import GeminiAnalyzer module: {e}. Gemini analysis disabled.")
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

        # --- Display Gemini Results ---
        if result.gemini_error:
            print(f"  {utils.AnsiColors.RED}Gemini Error:{utils.AnsiColors.RESET} {result.gemini_error[:150]}{'...' if len(result.gemini_error) > 150 else ''}")
        elif result.gemini_is_duplicate is not None:
            verdict_color = utils.AnsiColors.GREEN if result.gemini_is_duplicate else utils.AnsiColors.YELLOW
            verdict_text = "Likely Duplicate" if result.gemini_is_duplicate else "Likely NOT Duplicate"
            conf_str = f"{result.gemini_confidence:.1f}%" if result.gemini_confidence is not None else "N/A"
            print(f"  {utils.AnsiColors.CYAN}Gemini Verdict:{utils.AnsiColors.RESET} {verdict_color}{verdict_text}{utils.AnsiColors.RESET} (Confidence: {conf_str})")
            if result.gemini_reason:
                # Prevent reason overwhelming the output
                reason_preview = result.gemini_reason.replace('\n', ' ').strip()
                print(f"  {utils.AnsiColors.CYAN}Gemini Reason:{utils.AnsiColors.RESET} {reason_preview[:200]}{'...' if len(reason_preview) > 200 else ''}")
        # --- End Gemini Display ---

        # Debug: Show detailed scores if log level is DEBUG
        if logging.getLogger().isEnabledFor(logging.DEBUG) and result.similarity_scores:
            details = []
            for k, v in sorted(result.similarity_scores.items()): # Sort for consistent order
                if k == 'additional_metadata_details':
                    add_meta_dict = v if isinstance(v, dict) else {}
                    add_meta = ", ".join([f"{mk.split(':')[0]}:{mv:.2f}" for mk, mv in sorted(add_meta_dict.items())])
                    if add_meta: details.append(f"AddMeta=({add_meta})")
                elif isinstance(v, float):
                    details.append(f"{k}={v:.2f}")
                # else: skip non-float details for brevity
            if details: # Only print if there are details to show
                 print(f"  Scores: [ {', '.join(details)} ]")

        print("-" * 20)


def display_quality_results_grouped(all_folders: Dict[Path, FolderInfo], comparison_results: List[FolderComparisonResult]):
    """Displays folder quality, grouped by similarity clusters."""
    print(utils.AnsiColors.CYAN + "\n--- Folder Quality Assessment (Grouped by Similarity) ---" + utils.AnsiColors.RESET)

    # Build graph based on MINIMAL_DISPLAY_SIMILARITY for grouping display
    graph: Dict[Path, Set[Path]] = defaultdict(set)
    nodes_in_graph: Set[Path] = set()
    for result in comparison_results: # Use all results >= display threshold
        if result.weighted_score >= config.MINIMAL_DISPLAY_SIMILARITY:
             f1_path, f2_path = result.folder1_path, result.folder2_path
             graph[f1_path].add(f2_path)
             graph[f2_path].add(f1_path)
             nodes_in_graph.add(f1_path)
             nodes_in_graph.add(f2_path)

    # Include folders not in any comparison pair
    all_folder_paths = set(all_folders.keys())
    single_folders = all_folder_paths - nodes_in_graph

    processed_nodes: Set[Path] = set()
    group_count = 0

    # Process connected components (groups)
    sorted_nodes = sorted(list(nodes_in_graph), key=str) # Sort for consistent group order
    for start_node in sorted_nodes:
        if start_node not in processed_nodes:
            group_count += 1
            component_paths: Set[Path] = set()
            stack = [start_node]
            visited_in_component: Set[Path] = set() # Track visited within current component traversal

            while stack:
                current_path = stack.pop()
                if current_path not in visited_in_component and current_path in nodes_in_graph: # Check if node is part of the graph
                    visited_in_component.add(current_path)
                    processed_nodes.add(current_path) # Mark as globally processed
                    component_paths.add(current_path)
                    # Add neighbors that are part of the graph connections and not yet visited in this component
                    neighbors = graph.get(current_path, set())
                    stack.extend(neighbors - visited_in_component)


            if len(component_paths) > 1: # Only display groups with more than one member
                print(f"\n{utils.AnsiColors.MAGENTA}Group {group_count} (Similar Folders):{utils.AnsiColors.RESET}")
                component_folders = sorted(
                    [all_folders[p] for p in component_paths if p in all_folders and all_folders[p].quality_score is not None],
                    key=lambda f: (f.quality_score is not None, f.quality_score), reverse=True # Sort best first, handle None quality
                )

                if not component_folders: continue # Skip if no valid folders in component

                best_folder = component_folders[0] # Highest quality is first

                for i, folder in enumerate(component_folders):
                    quality = folder.quality_score if folder.quality_score is not None else -1.0 # Use -1 for sorting/display if None
                    q_str = f"{quality:.2f}%" if quality >= 0 else "N/A "
                    color = utils.AnsiColors.RESET
                    if quality >= 0:
                         color = utils.AnsiColors.GREEN if i == 0 else utils.AnsiColors.YELLOW if quality > 50 else utils.AnsiColors.RED
                    marker = "👑 (Best)" if i == 0 and quality >=0 else " " * 9
                    print(f"  {marker} {color}{q_str:<7}{utils.AnsiColors.RESET} '{folder.path}'")
                    # Display breakdown if DEBUG level
                    if logging.getLogger().isEnabledFor(logging.DEBUG) and folder.quality_breakdown:
                        breakdown_str = ", ".join([f"{k}: {v:.1f}" for k, v in sorted(folder.quality_breakdown.items())])
                        print(f"      Breakdown: [{breakdown_str}]")


    # Process single folders (not similar to others)
    if single_folders:
        print(f"\n{utils.AnsiColors.MAGENTA}Single Folders (No Significant Similarity Found):{utils.AnsiColors.RESET}")
        sorted_singles = sorted(
            [all_folders[p] for p in single_folders if p in all_folders],
            key=lambda f: (f.quality_score is not None, f.quality_score if f.quality_score is not None else -1), reverse=True # Sort by quality, handle None
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
    global logger # Ensure we use the configured logger

    # Double check availability here in case it changed or wasn't checked before
    if not GEMINI_AVAILABLE or not GeminiAnalyzer:
        logger.warning("Gemini analysis skipped (API Key missing, module/dependencies unavailable, or explicitly disabled).")
        # No need to print here, the main block handles the initial warning
        return

    try:
        min_sim_str, max_sim_str = gemini_range_str.split('-')
        min_sim = float(min_sim_str)
        max_sim = float(max_sim_str)
        if not (0 <= min_sim <= 100 and 0 <= max_sim <= 100 and min_sim <= max_sim):
            raise ValueError("Invalid range values (must be 0-100 and min <= max)")
    except ValueError as e:
        logger.error(f"Invalid Gemini similarity range '{gemini_range_str}'. Error: {e}. Please use format 'min-max' (e.g., '50-90'). Skipping Gemini analysis.")
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

    # Sort pairs for consistent processing order (optional)
    pairs_to_analyze.sort(key=lambda x: x.weighted_score, reverse=True)

    print(f"\n{utils.AnsiColors.CYAN}--- Running Gemini Analysis ({len(pairs_to_analyze)} pairs between {min_sim}-{max_sim}%) ---{utils.AnsiColors.RESET}")

    try:
        gemini_analyzer = GeminiAnalyzer()
    except ValueError as e: # Catches API key missing error during instantiation
        logger.error(f"Failed to initialize Gemini Analyzer: {e}. Make sure {config.GEMINI_API_KEY_ENV_VAR} is set.")
        print(f"{utils.AnsiColors.RED}Error: Failed to initialize Gemini Analyzer. Check API Key ({config.GEMINI_API_KEY_ENV_VAR}).{utils.AnsiColors.RESET}")
        return
    except Exception as e: # Catch other potential init errors
         logger.error(f"Unexpected error initializing Gemini Analyzer: {e}", exc_info=True)
         print(f"{utils.AnsiColors.RED}Error: Unexpected error initializing Gemini Analyzer.{utils.AnsiColors.RESET}")
         return


    analysis_count = 0
    start_time = time.time()
    # Use enumerate for progress tracking
    for i, result in enumerate(pairs_to_analyze):
        f1 = all_folders.get(result.folder1_path)
        f2 = all_folders.get(result.folder2_path)
        if not f1 or not f2:
            logger.warning(f"Skipping Gemini analysis for pair ({result.folder1_path.name}, {result.folder2_path.name}): FolderInfo missing.")
            continue

        # Print progress
        progress = f"({i+1}/{len(pairs_to_analyze)})"
        print(f"{progress} Analyzing pair: '{f1.path.name}' <-> '{f2.path.name}' (Score: {result.weighted_score:.2f}%)", end='\r')
        logger.info(f"{progress} Sending pair to Gemini: {f1.path.name} <-> {f2.path.name}")

        is_dup, conf, reason_or_error = gemini_analyzer.analyze_pair(f1, f2, result.weighted_score)

        # Clear the progress line before printing result/moving to next
        print(" " * 120, end='\r') # Adjust width as needed

        # Store results in the FolderComparisonResult object
        # Check if the third return value indicates an error
        is_error = reason_or_error and ("API_ERROR" in reason_or_error or "PARSE_ERROR" in reason_or_error or "TIMEOUT" in reason_or_error)

        if is_error:
            result.gemini_error = reason_or_error
            result.gemini_is_duplicate = None
            result.gemini_confidence = None
            result.gemini_reason = None
            logger.warning(f"Gemini analysis failed for pair ({f1.path.name}, {f2.path.name}): {reason_or_error}")
            print(f"{progress} {utils.AnsiColors.RED}Error analyzing pair: '{f1.path.name}' <-> '{f2.path.name}'. See logs.{utils.AnsiColors.RESET}")
        else:
            result.gemini_is_duplicate = is_dup
            result.gemini_confidence = conf
            result.gemini_reason = reason_or_error
            result.gemini_error = None # Ensure error field is cleared on success
            verdict = "Duplicate" if is_dup else "Not Duplicate" if is_dup is False else "Uncertain"
            conf_str = f"{conf:.1f}%" if conf is not None else "N/A"
            print(f"{progress} Analyzed pair: '{f1.path.name}' <-> '{f2.path.name}'. Verdict: {verdict} ({conf_str})")

        analysis_count += 1
        # Optional: Add a small delay between API calls to manage rate limits
        time.sleep(config.GEMINI_API_DELAY_SECONDS) # Add GEMINI_API_DELAY_SECONDS = 1.0 (or similar) to config.py


    end_time = time.time()
    duration = end_time - start_time
    # Final summary message
    print(" " * 120, end='\r') # Clear the last progress line
    print(f"{utils.AnsiColors.CYAN}--- Gemini Analysis Complete ({analysis_count} pairs analyzed in {duration:.2f}s) ---{utils.AnsiColors.RESET}")
    logger.info(f"Gemini analysis finished. Analyzed {analysis_count} pairs in {duration:.2f} seconds.")


# --- Main Execution Logic ---
def run_analysis(args):
    """Orchestrates the entire analysis process."""
    global logger # Ensure we use the configured logger
    # Re-setup logging with level from args (moved inside run_analysis to ensure correct level)
    # Use a flag to initialize logger only once if run_analysis is called multiple times (though unlikely here)
    if not getattr(run_analysis, 'logger_initialized', False):
        utils.setup_logging(args.log_level, config.LOGS_DIR)
        run_analysis.logger_initialized = True # Set flag
        logger = logging.getLogger(__name__) # Get the logger instance *after* setup

    logger.info("Starting Music Duplicate Detector Analysis")
    logger.info(f"Run arguments: {vars(args)}") # Log parsed arguments

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
        return # Exit if no folders were processed


    # --- Step 2: Calculate Quality Scores ---
    start_quality_time = time.time()
    logger.info("Calculating quality scores for all processed folders...")
    processed_count = 0
    for folder_info in all_scanned_folders.values(): # Iterate through values directly
        quality_analyzer.calculate_quality(folder_info)
        processed_count +=1
    quality_duration = time.time() - start_quality_time
    logger.info(f"Quality score calculation complete for {processed_count} folders in {quality_duration:.2f} seconds.")

    # Optional: Update cache with quality scores here if desired
    # data_store.save_data({str(p): folder_scanner._folder_info_to_dict(info) for p, info in all_scanned_folders.items()})


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
    # The display functions now handle Gemini results internally
    display_comparison_results(comparison_results, all_scanned_folders)
    display_quality_results_grouped(all_scanned_folders, comparison_results)

    # --- Step 5: Initialize Action Handler (needs processed data) ---
    action_handler = ActionHandler(all_scanned_folders, file_processor)


    # --- Step 6: User Actions (Merge) ---
    # Check if any results meet the merge threshold *before* asking the user
    if any(r.weighted_score >= config.MIN_SIMILARITY_FOR_MERGE for r in comparison_results):
        try:
            # Filter results for merging *before* asking
            merge_candidates = [r for r in comparison_results if r.weighted_score >= config.MIN_SIMILARITY_FOR_MERGE]
            print(f"\nFound {len(merge_candidates)} pairs with similarity >= {config.MIN_SIMILARITY_FOR_MERGE}% eligible for merging.")
            user_input_merge = input(f"Merge metadata/art for these {len(merge_candidates)} pairs? (y/n): ").strip().lower()
        except EOFError: # Handle non-interactive environments
            user_input_merge = 'n'
            print("Non-interactive mode detected, skipping merge confirmation.")

        if user_input_merge == 'y':
            action_handler.merge_similar_folders(merge_candidates) # Pass only relevant candidates
            print("Metadata merge process finished.")
            # Note: Merging might change metadata. Re-analysis is complex and not implemented here.
        else:
            print("Skipping metadata merge.")
            logger.info("User skipped merging.")
    else:
        logger.info(f"No pairs met the threshold ({config.MIN_SIMILARITY_FOR_MERGE}%) for merging.")
        print(f"\nNo folder pairs found with similarity >= {config.MIN_SIMILARITY_FOR_MERGE}% for merging.")


    # --- Step 7: User Actions (Delete) ---
    try:
        # Ask for threshold only if there are potential candidates based on *display* threshold
        if any(r.weighted_score >= config.MINIMAL_DISPLAY_SIMILARITY for r in comparison_results):
             del_thresh_input = input(f"\nEnter minimum similarity % to mark for deletion (e.g., {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}), or leave blank to skip: ").strip()
             if del_thresh_input:
                 min_similarity_for_delete = float(del_thresh_input)
                 if not (0 <= min_similarity_for_delete <= 100):
                     print(f"{utils.AnsiColors.YELLOW}Warning: Invalid threshold '{del_thresh_input}'. Must be between 0 and 100. Using default: {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%{utils.AnsiColors.RESET}")
                     min_similarity_for_delete = config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
                     logger.warning(f"Invalid delete threshold input '{del_thresh_input}', using default {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}")
             else:
                 min_similarity_for_delete = None # User skipped
        else:
             min_similarity_for_delete = None # No candidates shown, skip asking
             print("\nNo similar pairs found, skipping deletion prompt.")


    except ValueError: # Catch if input is not a number
        print(f"{utils.AnsiColors.RED}Error: Invalid input. Please enter a number between 0 and 100.{utils.AnsiColors.RESET}")
        print(f"Using default threshold for potential deletion: {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%")
        min_similarity_for_delete = config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
        logger.warning(f"Invalid delete threshold input (not a number), using default {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}")
    except EOFError: # Handle non-interactive environments
        min_similarity_for_delete = None
        print("Non-interactive mode detected, skipping deletion prompt.")


    if min_similarity_for_delete is not None:
        folders_to_delete_pairs = action_handler.identify_folders_to_delete(comparison_results, min_similarity_for_delete)
        if folders_to_delete_pairs: # Only proceed if folders were identified
            action_handler.delete_folders_interactive(folders_to_delete_pairs)
        else:
             print(f"No folders identified for deletion with similarity >= {min_similarity_for_delete}%.")
             logger.info(f"No folders met deletion criteria with threshold {min_similarity_for_delete}%.")
    else:
        print("Skipping deletion process.")
        logger.info("Deletion process skipped.")


    total_duration = time.time() - start_scan_time # Measure total time from scan start
    logger.info(f"Analysis finished. Total execution time: {total_duration:.2f} seconds.")
    print(f"\nAnalysis complete. Total time: {total_duration:.2f}s")


if __name__ == "__main__":
    # --- Argument Parser Setup ---
    parser = argparse.ArgumentParser(
        description="Analyzes music folders to find duplicates, assess quality, and optionally leverage Gemini API for deeper comparison.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show default values in help message
    )

    # --- Input/Output Arguments ---
    parser.add_argument("folders", nargs="+", metavar="FOLDER",
                        help="One or more root folder paths to scan for music.")
    parser.add_argument("-l", "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default=config.DEFAULT_LOG_LEVEL,
                        help="Set the logging level (affects console and file output).")

    # --- Scanning & Analysis Options ---
    scan_group = parser.add_argument_group('Scanning and Analysis Options')
    scan_group.add_argument("-b", "--bitrate", choices=["128", "high"], default="128",
                            help="Preferred bitrate target for quality assessment ('128' targets ~128kbps, 'high' prefers >=320kbps).")
    scan_group.add_argument("-d", "--disable-hash", action="store_true",
                            help="Disable file hashing (provides faster scan but less accurate identity check).")
    scan_group.add_argument("-r", "--force-rescan", action="store_true",
                            help="Force rescan of all folders, ignoring the existing cache.")

    # --- Gemini Analysis Options ---
    gemini_group = parser.add_argument_group('Gemini Analysis Options (Optional)')
    gemini_group.add_argument("-g", "--gemini-analysis", action="store_true", # הוספת קיצור -g
                              help=f"Enable Gemini API analysis for selected folder pairs. Requires the '{config.GEMINI_API_KEY_ENV_VAR}' environment variable and necessary libraries ('requests', 'Pillow').")
    gemini_group.add_argument("-gr", "--gemini-range", type=str, default=config.DEFAULT_GEMINI_SIMILARITY_RANGE, # הוספת קיצור -gr
                              metavar="MIN-MAX",
                              help="Similarity range ('min-max' percentage, e.g., '50-90') for sending pairs to Gemini API.")

    # --- Action Thresholds (Example - Currently handled interactively) ---
    # action_group = parser.add_argument_group('Action Thresholds')
    # action_group.add_argument("--merge-threshold", type=float, default=config.MIN_SIMILARITY_FOR_MERGE, metavar="PERCENT",
    #                           help="Similarity threshold (percentage) to offer merging metadata.")
    # action_group.add_argument("--delete-threshold", type=float, default=config.DEFAULT_MIN_SIMILARITY_FOR_DELETE, metavar="PERCENT",
    #                           help="Default similarity threshold (percentage) to offer deletion.")


    args = parser.parse_args()

    # --- Initial Logging Setup ---
    log_level_initial = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level_initial, format=config.LOG_FORMAT, handlers=[logging.StreamHandler()])
    logger = logging.getLogger(__name__) # Get logger for initial messages

    # --- Validate Input Folders ---
    valid_folders = []
    invalid_paths = []
    if not args.folders:
         parser.error("No input folders specified.") # Use parser.error for better message

    for folder_str in args.folders:
        p = Path(folder_str)
        try:
            if p.is_dir():
                valid_folders.append(p.resolve())
            else:
                invalid_paths.append(folder_str)
        except OSError as e:
            logger.error(f"Error accessing path '{folder_str}': {e}")
            invalid_paths.append(f"{folder_str} (Error: {e})")
        except Exception as e: # Catch other potential errors
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

    args.folders = [str(p) for p in valid_folders] # Store validated paths as strings for consistency if needed

    # --- Check Gemini Availability vs. Request ---
    if args.gemini_analysis and not GEMINI_AVAILABLE:
        print(f"{utils.AnsiColors.YELLOW}Warning: Gemini analysis requested (--gemini-analysis) but the API key ({config.GEMINI_API_KEY_ENV_VAR}) is missing or required libraries ('requests', 'Pillow') are not installed properly. Gemini analysis will be skipped.{utils.AnsiColors.RESET}")
        logger.warning(f"Gemini analysis requested but disabled (API Key: {bool(GEMINI_API_KEY)}, Module Import: {GeminiAnalyzer is not None}).")
        args.gemini_analysis = False

    # --- Start Main Process ---
    try:
        run_analysis(args)
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
        logger.warning("Analysis interrupted by user (KeyboardInterrupt).")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred during analysis: {e}", exc_info=True)
        print(f"\n{utils.AnsiColors.RED}An unexpected error occurred. Please check the logs in the 'logs' directory for details.{utils.AnsiColors.RESET}")
        sys.exit(1)
