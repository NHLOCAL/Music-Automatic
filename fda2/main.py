import argparse
from collections import defaultdict
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set # Added Set

# Import necessary components from other modules
import config
import utils
from models import FolderInfo, FolderComparisonResult # Added FolderComparisonResult
from data_store import DataStore
from file_processor import FileProcessor
from folder_scanner import FolderScanner
from comparison_engine import ComparisonEngine
from quality_analyzer import QualityAnalyzer
from action_handler import ActionHandler

# --- הסרת הגדרת הלוגינג הראשונית ---
# logger = utils.setup_logging(config.DEFAULT_LOG_LEVEL, config.LOGS_DIR)

# --- Presentation Logic ---
def display_comparison_results(results: List[FolderComparisonResult], all_folders: Dict[Path, FolderInfo]):
    """Prints the comparison results to the console."""
    if not results:
        print(utils.AnsiColors.GREEN + "\nNo significantly similar folders found." + utils.AnsiColors.RESET)
        return

    print(utils.AnsiColors.CYAN + "\n--- Similarity Comparison Results ---" + utils.AnsiColors.RESET)
    print(f"(Showing pairs with similarity >= {config.MINIMAL_DISPLAY_SIMILARITY}%)\n")

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

        # Debug: Show detailed scores if log level is DEBUG
        if logger.isEnabledFor(logging.DEBUG) and result.similarity_scores:
            details = []
            for k, v in result.similarity_scores.items():
                 if k == 'additional_metadata_details':
                      add_meta = ", ".join([f"{mk.split(':')[0]}:{mv:.2f}" for mk, mv in v.items()]) # Shorten key for display
                      if add_meta: details.append(f"AddMeta=({add_meta})")
                 elif isinstance(v, float):
                      details.append(f"{k}={v:.2f}")
                 # else: skip non-float details for brevity
            print(f"  Scores: [ {', '.join(details)} ]")

        print("-" * 20)

def display_quality_results_grouped(all_folders: Dict[Path, FolderInfo], comparison_results: List[FolderComparisonResult]):
    """Displays folder quality, grouped by similarity clusters."""
    print(utils.AnsiColors.CYAN + "\n--- Folder Quality Assessment (Grouped by Similarity) ---" + utils.AnsiColors.RESET)

    # Build graph based on MINIMAL_DISPLAY_SIMILARITY for grouping display
    graph: Dict[Path, Set[Path]] = defaultdict(set)
    nodes_in_graph: Set[Path] = set()
    for result in comparison_results: # Use all results >= display threshold
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
    for start_node in nodes_in_graph:
        if start_node not in processed_nodes:
            group_count += 1
            component_paths: Set[Path] = set()
            stack = [start_node]
            while stack:
                current_path = stack.pop()
                if current_path not in processed_nodes:
                    processed_nodes.add(current_path)
                    component_paths.add(current_path)
                    stack.extend(graph.get(current_path, set()) - processed_nodes)

            if component_paths:
                 print(f"\n{utils.AnsiColors.MAGENTA}Group {group_count} (Similar Folders):{utils.AnsiColors.RESET}")
                 component_folders = sorted(
                     [all_folders[p] for p in component_paths if p in all_folders and all_folders[p].quality_score is not None],
                     key=lambda f: f.quality_score, reverse=True # Sort best first
                 )

                 if not component_folders: continue # Should not happen if paths exist

                 best_folder = component_folders[0] # Highest quality is first

                 for i, folder in enumerate(component_folders):
                      quality = folder.quality_score
                      color = utils.AnsiColors.GREEN if i == 0 else utils.AnsiColors.YELLOW if quality > 50 else utils.AnsiColors.RED
                      marker = "👑 (Best)" if i == 0 else " " * 9
                      print(f"  {marker} {color}{quality:<7.2f}%{utils.AnsiColors.RESET} '{folder.path}'")
                      # Display breakdown if DEBUG level
                      if logger.isEnabledFor(logging.DEBUG) and folder.quality_breakdown:
                           breakdown_str = ", ".join([f"{k}: {v:.1f}" for k, v in folder.quality_breakdown.items()])
                           print(f"      Breakdown: [{breakdown_str}]")


    # Process single folders (not similar to others)
    if single_folders:
         print(f"\n{utils.AnsiColors.MAGENTA}Single Folders (No Significant Similarity Found):{utils.AnsiColors.RESET}")
         sorted_singles = sorted(
              [all_folders[p] for p in single_folders if p in all_folders and all_folders[p].quality_score is not None],
              key=lambda f: f.quality_score, reverse=True
         )
         for folder in sorted_singles:
              quality = folder.quality_score
              color = utils.AnsiColors.GREEN if quality > 75 else utils.AnsiColors.YELLOW if quality > 50 else utils.AnsiColors.RED
              print(f"    {color}{quality:<7.2f}%{utils.AnsiColors.RESET} '{folder.path}'")
              if logger.isEnabledFor(logging.DEBUG) and folder.quality_breakdown:
                    breakdown_str = ", ".join([f"{k}: {v:.1f}" for k, v in folder.quality_breakdown.items()])
                    print(f"      Breakdown: [{breakdown_str}]")

    print(utils.AnsiColors.CYAN + "\n--- End of Quality Assessment ---" + utils.AnsiColors.RESET)


# --- Main Execution Logic ---
def run_analysis(args):
    """Orchestrates the entire analysis process."""
    # Re-setup logging with level from args (moved inside run_analysis)
    if not hasattr(run_analysis, 'logger_initialized'): # Use a flag to initialize logger only once if needed
        utils.setup_logging(args.log_level, config.LOGS_DIR)
        run_analysis.logger_initialized = True
    global logger # Make sure we are using the module-level logger
    logger = logging.getLogger(__name__) # Get the logger instance

    logger.info("Starting Music Duplicate Detector Analysis")
    logger.info(f"Arguments: {args}")

    # --- Initialization ---
    data_store = DataStore(config.MUSIC_DATA_CACHE_FILE)
    enable_hashing = not args.disable_hash
    file_processor = FileProcessor(enable_hashing=enable_hashing)
    folder_scanner = FolderScanner(file_processor, data_store, force_rescan=args.force_rescan)
    comparison_engine = ComparisonEngine(enable_hashing=enable_hashing)
    quality_analyzer = QualityAnalyzer(preferred_bitrate=args.bitrate)
    # ActionHandler needs all_folders_data, initialize later


    # --- Step 1: Scan Folders & Process Files ---
    # Convert string paths from args to Path objects
    root_paths = [Path(p) for p in args.folders]
    all_scanned_folders: Dict[Path, FolderInfo] = folder_scanner.scan_folders(root_paths)

    if not all_scanned_folders:
         logger.warning("No valid music folders found or processed. Exiting.")
         print("No music folders meeting the criteria were found in the specified paths.")
         return


    # --- Step 2: Calculate Quality Scores ---
    logger.info("Calculating quality scores for all processed folders...")
    for folder_path, folder_info in all_scanned_folders.items():
         # Calculate quality (modifies folder_info in-place)
         quality_analyzer.calculate_quality(folder_info)
    logger.info("Quality score calculation complete.")

    # After quality calculation, update the cache with quality scores
    # (Optional: might slow down if many folders, could be done at the end)
    # data_store.save_data({str(p): folder_scanner._folder_info_to_dict(info) for p, info in all_scanned_folders.items()})


    # --- Step 3: Compare Folders for Similarity ---
    comparison_results: List[FolderComparisonResult] = comparison_engine.find_similar_folders(all_scanned_folders)


    # --- Step 4: Display Results ---
    display_comparison_results(comparison_results, all_scanned_folders)
    display_quality_results_grouped(all_scanned_folders, comparison_results) # Pass comparisons for grouping

    # --- Step 5: Initialize Action Handler (needs processed data) ---
    action_handler = ActionHandler(all_scanned_folders, file_processor)


    # --- Step 6: User Actions (Merge) ---
    if any(r.weighted_score >= config.MIN_SIMILARITY_FOR_MERGE for r in comparison_results):
         try:
             user_input_merge = input(f"\nMerge metadata/art for pairs with similarity >= {config.MIN_SIMILARITY_FOR_MERGE}%? (y/n): ").strip().lower()
         except EOFError:
             user_input_merge = 'n' # Default no in non-interactive

         if user_input_merge == 'y':
             action_handler.merge_similar_folders(comparison_results)
             print("Metadata merge process finished.")
             # Note: Merging might change metadata, ideally rescan/re-analyze quality if needed,
             # but for simplicity, we won't do that here. Assume merge is final step before delete.
         else:
             print("Skipping metadata merge.")
             logger.info("User skipped merging.")
    else:
         logger.info("No pairs met the threshold for merging.")


    # --- Step 7: User Actions (Delete) ---
    try:
        del_thresh_input = input(f"\nEnter minimum similarity % to mark for deletion (e.g., {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}), or leave blank to skip: ").strip()
        min_similarity_for_delete = float(del_thresh_input) if del_thresh_input else None
        if min_similarity_for_delete is not None and not (0 <= min_similarity_for_delete <= 100):
             print(f"Invalid threshold. Using default: {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%")
             min_similarity_for_delete = config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
             logger.warning(f"Invalid delete threshold input, using default {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}")

    except ValueError:
        print(f"Invalid input. Using default: {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%")
        min_similarity_for_delete = config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
        logger.warning(f"Invalid delete threshold input, using default {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}")
    except EOFError:
         min_similarity_for_delete = None # Skip in non-interactive

    if min_similarity_for_delete is not None:
        folders_to_delete_pairs = action_handler.identify_folders_to_delete(comparison_results, min_similarity_for_delete)
        action_handler.delete_folders_interactive(folders_to_delete_pairs)
    else:
        print("Skipping deletion process.")
        logger.info("Deletion process skipped.")


    logger.info("Analysis finished.")
    print("\nAnalysis complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Music Duplicate Detector and Quality Analyzer")

    parser.add_argument("folders", nargs="+",
                        help="One or more root folder paths containing music albums/folders.")
    parser.add_argument("-l", "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default=config.DEFAULT_LOG_LEVEL,
                        help="Set the logging level (output to console and file). Default: INFO.")
    parser.add_argument("-b", "--bitrate", choices=["128", "high"], default="128",
                        help="Preferred bitrate for quality assessment ('128' targets 128kbps, 'high' prefers >320kbps). Default: 128.")
    parser.add_argument("-d", "--disable-hash", action="store_true",
                        help="Disable file hashing. Comparison will rely more on metadata and size (faster but less accurate for identity).")
    parser.add_argument("-r", "--force-rescan", action="store_true",
                        help="Force rescan of all folders, ignoring the existing cache (music_data.json).")
    # Future: Add arguments for thresholds? e.g., --delete-threshold
    # parser.add_argument("--delete-threshold", type=float, default=config.DEFAULT_MIN_SIMILARITY_FOR_DELETE,
    #                     help=f"Minimum similarity percentage to offer deletion. Default: {config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}")


    args, unknown_args = parser.parse_known_args() # <--- שימוש ב-parse_known_args

    # --- הגדרה מותנית של לוגינג ---
    if '-h' not in unknown_args and '--help' not in unknown_args: # <--- בדיקה אם פרמטר עזרה לא הופעל
        logger = utils.setup_logging(args.log_level, config.LOGS_DIR)
    else:
        logger = logging.getLogger(__name__) # עדיין צריך logger ריק כדי למנוע שגיאות בהמשך הקוד

    # Validate input folders before starting
    valid_folders = []
    for folder_str in args.folders:
         p = Path(folder_str)
         if p.is_dir():
             valid_folders.append(folder_str)
         else:
             logger.error(f"Input path is not a valid directory: {folder_str}")
             print(f"Error: Path is not a directory: '{folder_str}'")
             exit(1) # Exit if any path is invalid

    # Replace args.folders with only the validated ones (although argparse nargs='+' ensures list)
    args.folders = valid_folders

    if not args.folders:
        print("Error: No valid input folders provided.")
        exit(1)


    run_analysis(args)
