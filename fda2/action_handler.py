# action_handler.py
from collections import defaultdict
import logging
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Set
from send2trash import send2trash # Keep using send2trash for safety

import config
from models import FolderInfo, FileInfo, FolderComparisonResult
from utils import AnsiColors
# Need FileProcessor potentially for metadata merging, though maybe simpler logic is ok
from file_processor import FileProcessor # Or just use mutagen directly here
from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3

logger = logging.getLogger(__name__)

class ActionHandler:
    """Handles actions like merging metadata or deleting/trashing folders."""

    def __init__(self, all_folders_data: Dict[Path, FolderInfo],
                 file_processor: FileProcessor): # Pass FileProcessor for potential advanced merging
        self.all_folders_data = all_folders_data
        self.file_processor = file_processor # Used for metadata access

    # --- Merging Logic ---

    def merge_similar_folders(self, comparison_results: List[FolderComparisonResult]):
        """
        Iterates through highly similar folders and merges metadata/art from the
        lower quality folder to the higher quality one.
        """
        logger.info("Starting merge process for highly similar folders...")
        merged_pairs_count = 0
        for result in comparison_results:
            if result.weighted_score >= config.MIN_SIMILARITY_FOR_MERGE:
                folder1_path = result.folder1_path
                folder2_path = result.folder2_path

                folder1_info = self.all_folders_data.get(folder1_path)
                folder2_info = self.all_folders_data.get(folder2_path)

                if not folder1_info or not folder2_info:
                    logger.warning(f"Skipping merge: Folder data missing for pair {folder1_path.name}, {folder2_path.name}")
                    continue

                # Ensure quality scores are calculated
                if folder1_info.quality_score is None or folder2_info.quality_score is None:
                     logger.warning(f"Skipping merge: Quality score not calculated for pair {folder1_path.name}, {folder2_path.name}. Run quality analysis first.")
                     continue


                # Decide preferred folder (higher quality wins, tie break?)
                # TODO: Refine tie-breaking logic (e.g., path length, bitrate preference?)
                if folder1_info.quality_score >= folder2_info.quality_score:
                    preferred_folder, other_folder = folder1_info, folder2_info
                else:
                    preferred_folder, other_folder = folder2_info, folder1_info

                logger.info(f"Merging: Preferred={preferred_folder.path.name} (Q:{preferred_folder.quality_score:.2f}), Other={other_folder.path.name} (Q:{other_folder.quality_score:.2f})")

                try:
                    self._perform_merge(preferred_folder, other_folder)
                    merged_pairs_count += 1
                except Exception as e:
                    logger.error(f"Error during merge between {preferred_folder.path.name} and {other_folder.path.name}: {e}", exc_info=True)

            else:
                 # Stop iterating once scores drop below merge threshold (since list is sorted)
                 break


        if merged_pairs_count > 0:
            logger.info(f"Merge process complete. Merged metadata for {merged_pairs_count} pairs.")
        else:
            logger.info("No folder pairs met the similarity threshold for merging.")


    def _perform_merge(self, preferred_folder: FolderInfo, other_folder: FolderInfo):
        """Performs the actual merge operations (metadata, album art)."""

        # 1. Merge Album Art (Copy if missing in preferred)
        self._merge_album_art(preferred_folder.path, other_folder.path)

        # 2. Merge File Metadata (Copy missing tags from other to preferred)
        # Create mappings for efficient lookup (hash or filename)
        pref_files_map = {f.filename: f for f in preferred_folder.files} # Use filename as fallback key
        other_files_map = {f.filename: f for f in other_folder.files}
        if preferred_folder.file_hashes_present and other_folder.file_hashes_present:
             # Use hash if available and reliable
            pref_files_map = {f.file_hash: f for f in preferred_folder.files if f.file_hash}
            other_files_map = {f.file_hash: f for f in other_folder.files if f.file_hash}
            lookup_key = 'hash'
        else:
             lookup_key = 'filename'
             logger.debug(f"Merging metadata using filename matching for {preferred_folder.path.name} <-> {other_folder.path.name} (hashes incomplete)")


        for key, pref_file_info in pref_files_map.items():
            other_file_info = other_files_map.get(key)

            if other_file_info:
                try:
                    self._merge_single_file_metadata(pref_file_info.filepath, other_file_info.filepath)
                except Exception as e:
                    logger.error(f"Failed to merge metadata for file pair ({pref_file_info.filename}, {other_file_info.filename}): {e}", exc_info=False) # Reduce noise for file errors
            else:
                 logger.warning(f"Could not find matching file in other folder for {pref_file_info.filename} (using key: {lookup_key}) during merge.")


    def _merge_album_art(self, preferred_path: Path, other_path: Path):
        """Copies standard album art files if missing in preferred folder."""
        preferred_has_art = any((preferred_path / art_name).is_file() for art_name in config.ALBUM_ART_FILES)

        if not preferred_has_art:
            for art_name in config.ALBUM_ART_FILES:
                other_art_file = other_path / art_name
                if other_art_file.is_file():
                    preferred_art_dest = preferred_path / art_name
                    try:
                        shutil.copy2(other_art_file, preferred_art_dest) # copy2 preserves metadata
                        logger.info(f"Copied album art '{art_name}' from {other_path.name} to {preferred_path.name}")
                        # Found and copied one, assume it's the main art
                        break
                    except OSError as e:
                        logger.error(f"Error copying album art {art_name} from {other_path.name} to {preferred_path.name}: {e}")
                    # Don't break on error, maybe another art file can be copied

        else:
            logger.debug(f"Preferred folder {preferred_path.name} already has album art file. Skipping art merge.")


    def _merge_single_file_metadata(self, pref_filepath: Path, other_filepath: Path):
        """Merges EasyID3 tags from other file to preferred file if missing."""
        metadata_changed = False
        try:
            # Use EasyID3 for simplicity in merging common tags
            pref_audio = EasyID3(pref_filepath)
            other_audio = EasyID3(other_filepath)

            for key in other_audio.keys():
                # If key is missing in preferred OR if preferred value is empty/None
                if key not in pref_audio or not pref_audio.get(key) or not pref_audio[key][0]:
                    pref_audio[key] = other_audio[key]
                    metadata_changed = True
                    logger.debug(f"Copied tag '{key}' value '{other_audio[key]}' from {other_filepath.name} to {pref_filepath.name}")

            # TODO: Consider merging non-EasyID3 tags (like lyrics, detailed comments) if necessary
            # This would require using MutagenFile and more complex logic

            if metadata_changed:
                try:
                    pref_audio.save()
                    logger.info(f"Saved updated metadata for: {pref_filepath.name}")
                except Exception as e:
                    logger.error(f"Error saving merged metadata for {pref_filepath.name}: {e}")

        except Exception as e:
            # Catch potential errors reading the files
            logger.error(f"Error accessing metadata for merging ({pref_filepath.name}, {other_filepath.name}): {e}")


    # --- Deletion Logic ---

    def identify_folders_to_delete(self, comparison_results: List[FolderComparisonResult],
                                     min_similarity_for_delete: float) -> List[Tuple[FolderInfo, FolderInfo]]:
        """
        Identifies folders to potentially delete based on similarity and quality.
        Uses graph components to find the best folder within each cluster of duplicates.
        Returns a list of tuples: (folder_to_delete, best_folder_in_group).
        """
        logger.info(f"Identifying folders for potential deletion (Similarity >= {min_similarity_for_delete}%)...")
        folders_to_delete: List[Tuple[FolderInfo, FolderInfo]] = []
        # Build a graph of folders connected by high similarity
        graph: Dict[Path, Set[Path]] = defaultdict(set)
        nodes_in_graph: Set[Path] = set() # Keep track of all folders involved

        for result in comparison_results:
            if result.weighted_score >= min_similarity_for_delete:
                f1_path, f2_path = result.folder1_path, result.folder2_path
                graph[f1_path].add(f2_path)
                graph[f2_path].add(f1_path)
                nodes_in_graph.add(f1_path)
                nodes_in_graph.add(f2_path)
            else:
                 # Stop early as results are sorted
                 break

        # Find connected components (clusters of similar folders)
        seen: Set[Path] = set()
        for node_path in nodes_in_graph:
            if node_path not in seen:
                component_paths: Set[Path] = set()
                stack = [node_path]
                while stack:
                    current_path = stack.pop()
                    if current_path not in seen:
                        seen.add(current_path)
                        component_paths.add(current_path)
                        # Add neighbors that are part of the graph connections
                        stack.extend(graph.get(current_path, set()) - seen)

                # Process the found component if it has more than one folder
                if len(component_paths) > 1:
                    component_folders = [self.all_folders_data[p] for p in component_paths if p in self.all_folders_data]
                    # Filter out if data is missing (shouldn't happen ideally)
                    component_folders = [f for f in component_folders if f.quality_score is not None]

                    if len(component_folders) > 1:
                         # Find the best folder in the component based on quality score
                         # Add tie-breakers if necessary (e.g., path length, specific tags)
                         best_folder = max(component_folders, key=lambda f: f.quality_score)

                         # Add all others in the component to the deletion list
                         for folder in component_folders:
                             if folder.path != best_folder.path:
                                 folders_to_delete.append((folder, best_folder))
                                 logger.debug(f"Marked for deletion: {folder.path.name} (Keep: {best_folder.path.name})")


        logger.info(f"Identified {len(folders_to_delete)} folders for potential deletion.")
        return folders_to_delete


    def delete_folders_interactive(self, folders_to_delete_pairs: List[Tuple[FolderInfo, FolderInfo]]):
        """
        Presents the list of folders to delete and asks for user confirmation
        before moving them to the system's trash.
        """
        if not folders_to_delete_pairs:
            print(AnsiColors.GREEN + "No folders marked for deletion based on the criteria." + AnsiColors.RESET)
            logger.info("No folders met deletion criteria.")
            return

        print(AnsiColors.YELLOW + "\n--- Folders Recommended for Deletion (Moved to Trash) ---" + AnsiColors.RESET)
        # Sort for consistent display
        folders_to_delete_pairs.sort(key=lambda pair: str(pair[0].path))
        for folder_to_delete, best_folder in folders_to_delete_pairs:
            q_del = folder_to_delete.quality_score
            q_best = best_folder.quality_score
            print(f"- To Trash: '{AnsiColors.RED}{folder_to_delete.path}{AnsiColors.RESET}' (Q: {q_del:.2f}%)")
            print(f"  Keep:     '{AnsiColors.GREEN}{best_folder.path}{AnsiColors.RESET}' (Q: {q_best:.2f}%)")
            # Optionally show similarity score between these two? Requires looking up the original comparison.

        print(AnsiColors.YELLOW + "--- End of List ---" + AnsiColors.RESET)

        try:
            confirmation = input(AnsiColors.YELLOW + f"\nMove the {len(folders_to_delete_pairs)} folders listed above to the system trash? (y/n): " + AnsiColors.RESET).strip().lower()
        except EOFError: # Handle non-interactive environments
             confirmation = 'n'
             print("Non-interactive mode detected, cancelling delete operation.")


        if confirmation == 'y':
            logger.warning(f"User confirmed deletion of {len(folders_to_delete_pairs)} folders.")
            trashed_count = 0
            failed_count = 0
            for folder_to_delete, best_folder in folders_to_delete_pairs:
                try:
                    # Double check the folder still exists before trashing
                    if folder_to_delete.path.exists():
                         send2trash(str(folder_to_delete.path)) # send2trash needs string path
                         print(f"Moved to trash: '{folder_to_delete.path}'")
                         logger.warning(f"Moved to trash: {folder_to_delete.path} (preferred was {best_folder.path})")
                         trashed_count += 1
                    else:
                         print(f"Skipped missing folder: '{folder_to_delete.path}'")
                         logger.warning(f"Skipped trashing missing folder: {folder_to_delete.path}")

                except Exception as e:
                    failed_count += 1
                    print(AnsiColors.RED + f"Error moving folder '{folder_to_delete.path}' to trash: {e}" + AnsiColors.RESET)
                    logger.error(f"Error moving folder '{folder_to_delete.path}' to trash: {e}", exc_info=True)

            print(AnsiColors.GREEN + f"\nTrash operation complete. Successfully moved {trashed_count} folders." + AnsiColors.RESET)
            if failed_count > 0:
                print(AnsiColors.RED + f"{failed_count} folders could not be moved." + AnsiColors.RESET)
            logger.info(f"Trash process finished. Moved: {trashed_count}, Failed: {failed_count}")

        else:
            print("Deletion cancelled by user.")
            logger.info("Trash process cancelled by user.")

