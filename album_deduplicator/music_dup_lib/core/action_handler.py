from collections import defaultdict
import logging
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Set, Optional, Union
from send2trash import send2trash


from .. import config
from ..models import FolderInfo, FileInfo, FolderComparisonResult
from ..utils import AnsiColors


from .file_processor import FileProcessor


from mutagen._util import MutagenError # General Mutagen error
from mutagen._file import File as MutagenFile # More specific import
from mutagen.easyid3 import EasyID3

logger = logging.getLogger(__name__)

class ActionHandler:


    def __init__(self, all_folders_data: Dict[Path, FolderInfo],
                 file_processor: FileProcessor,
                 preferred_root_path: Optional[Path] = None):
        self.all_folders_data = all_folders_data
        self.file_processor = file_processor
        self.preferred_root_path = preferred_root_path
        if self.preferred_root_path:
            logger.info(f"ActionHandler initialized with preferred root path: {self.preferred_root_path}")


    def merge_similar_folders(self, comparison_results: List[FolderComparisonResult]):

        logger.info("Starting merge process for highly similar folders...")
        merged_pairs_count = 0
        # comparison_results here are already filtered by MIN_SIMILARITY_FOR_MERGE on final_combined_score in main.py
        # So, merge_candidates is essentially the same as comparison_results passed here.
        merge_candidates = comparison_results

        if not merge_candidates:
             logger.info("No folder pairs met the similarity threshold for merging.")
             return

        logger.info(f"Found {len(merge_candidates)} pairs eligible for merge (Combined Score >= {config.MIN_SIMILARITY_FOR_MERGE}%).")

        for result in merge_candidates:
            folder1_path = result.folder1_path
            folder2_path = result.folder2_path

            folder1_info = self.all_folders_data.get(folder1_path)
            folder2_info = self.all_folders_data.get(folder2_path)

            if not folder1_info or not folder2_info:
                logger.warning(f"Skipping merge: Folder data missing for pair {folder1_path.name}, {folder2_path.name}")
                continue


            if folder1_info.quality_score is None or folder2_info.quality_score is None:
                 logger.warning(f"Skipping merge: Quality score not calculated for pair {folder1_path.name}, {folder2_path.name}. Run quality analysis first.")
                 continue

            preferred_folder, other_folder = folder1_info, folder2_info


            f1_in_pref = self.preferred_root_path and (folder1_path == self.preferred_root_path or self.preferred_root_path in folder1_path.parents)
            f2_in_pref = self.preferred_root_path and (folder2_path == self.preferred_root_path or self.preferred_root_path in folder2_path.parents)

            if f1_in_pref and not f2_in_pref:
                preferred_folder, other_folder = folder1_info, folder2_info
                logger.info(f"Merge preference: {folder1_info.path.name} is in preferred root.")
            elif f2_in_pref and not f1_in_pref:
                preferred_folder, other_folder = folder2_info, folder1_info
                logger.info(f"Merge preference: {folder2_info.path.name} is in preferred root.")
            else:
                # Ensure quality_score is not None before comparison for sorting
                q1 = folder1_info.quality_score if folder1_info.quality_score is not None else -1.0
                q2 = folder2_info.quality_score if folder2_info.quality_score is not None else -1.0
                if q1 >= q2:
                    preferred_folder, other_folder = folder1_info, folder2_info
                else:
                    preferred_folder, other_folder = folder2_info, folder1_info
                logger.info(f"Merge preference based on quality: {preferred_folder.path.name} (Q:{preferred_folder.quality_score:.2f})")


            logger.info(f"Merging: Preferred={preferred_folder.path.name} (Q:{preferred_folder.quality_score:.2f}), Other={other_folder.path.name} (Q:{other_folder.quality_score:.2f})")

            try:
                self._perform_merge(preferred_folder, other_folder)
                merged_pairs_count += 1
            except Exception as e:
                logger.error(f"Error during merge between {preferred_folder.path.name} and {other_folder.path.name}: {e}", exc_info=True)

        if merged_pairs_count > 0:
            logger.info(f"Merge process complete. Merged metadata for {merged_pairs_count} pairs.")



    def _perform_merge(self, preferred_folder: FolderInfo, other_folder: FolderInfo):



        self._merge_album_art(preferred_folder.path, other_folder.path)



        pref_files_map = {f.filename: f for f in preferred_folder.files}
        other_files_map = {f.filename: f for f in other_folder.files}
        if preferred_folder.file_hashes_present and other_folder.file_hashes_present:

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
                    logger.error(f"Failed to merge metadata for file pair ({pref_file_info.filename}, {other_file_info.filename}): {e}", exc_info=False)
            else:
                 logger.warning(f"Could not find matching file in other folder for {pref_file_info.filename} (using key: {lookup_key}) during merge.")


    def _merge_album_art(self, preferred_path: Path, other_path: Path):

        preferred_has_art = any((preferred_path / art_name).is_file() for art_name in config.ALBUM_ART_FILES)

        if not preferred_has_art:
            for art_name in config.ALBUM_ART_FILES:
                other_art_file = other_path / art_name
                if other_art_file.is_file():
                    preferred_art_dest = preferred_path / art_name
                    try:
                        shutil.copy2(other_art_file, preferred_art_dest)
                        logger.info(f"Copied album art '{art_name}' from {other_path.name} to {preferred_path.name}")

                        break
                    except OSError as e:
                        logger.error(f"Error copying album art {art_name} from {other_path.name} to {preferred_path.name}: {e}")


        else:
            logger.debug(f"Preferred folder {preferred_path.name} already has album art file. Skipping art merge.")


    def _merge_single_file_metadata(self, pref_filepath: Path, other_filepath: Path):

        metadata_changed = False
        try:

            pref_audio = EasyID3(pref_filepath)
            other_audio = EasyID3(other_filepath)

            for key in other_audio.keys():

                if key not in pref_audio or not pref_audio.get(key) or not pref_audio[key][0]:
                    pref_audio[key] = other_audio[key]
                    metadata_changed = True
                    logger.debug(f"Copied tag '{key}' value '{other_audio[key]}' from {other_filepath.name} to {pref_filepath.name}")




            if metadata_changed:
                try:
                    pref_audio.save()
                    logger.info(f"Saved updated metadata for: {pref_filepath.name}")
                except Exception as e:
                    logger.error(f"Error saving merged metadata for {pref_filepath.name}: {e}")

        except MutagenError as me: # Catch specific Mutagen errors
            logger.error(f"Mutagen error accessing metadata for merging ({pref_filepath.name}, {other_filepath.name}): {me}")
        except Exception as e:
            logger.error(f"General error accessing metadata for merging ({pref_filepath.name}, {other_filepath.name}): {e}")




    def identify_folders_to_delete(self, comparison_results: List[FolderComparisonResult],
                                     min_similarity_for_delete: float) -> List[Tuple[FolderInfo, FolderInfo]]:

        logger.info(f"Identifying folders for potential deletion (Combined Similarity >= {min_similarity_for_delete}%)...")
        if self.preferred_root_path:
            logger.info(f"Preferred root path for keeping files: {self.preferred_root_path}")
        folders_to_delete: List[Tuple[FolderInfo, FolderInfo]] = []

        graph: Dict[Path, Set[Path]] = defaultdict(set)
        nodes_in_graph: Set[Path] = set()


        relevant_results = [
            r for r in comparison_results 
            if (r.final_combined_score if r.final_combined_score is not None else r.weighted_score) >= min_similarity_for_delete
        ]

        for result in relevant_results:
            f1_path, f2_path = result.folder1_path, result.folder2_path
            graph[f1_path].add(f2_path)
            graph[f2_path].add(f1_path)
            nodes_in_graph.add(f1_path)
            nodes_in_graph.add(f2_path)


        seen: Set[Path] = set()
        for node_path in list(nodes_in_graph):
            if node_path not in seen:
                component_paths: Set[Path] = set()
                stack = [node_path]
                visited_in_component: Set[Path] = set()

                while stack:
                    current_path = stack.pop()
                    if current_path not in visited_in_component and current_path in nodes_in_graph:
                        visited_in_component.add(current_path)
                        seen.add(current_path) # Mark globally seen
                        component_paths.add(current_path)
                        # Add neighbors that are part of the graph connections
                        stack.extend(graph.get(current_path, set()) - visited_in_component)

                # Process the found component if it has more than one folder
                if len(component_paths) > 1:
                    component_folders = [self.all_folders_data[p] for p in component_paths if p in self.all_folders_data]
                    
                    # Filter out folders with no quality score before determining 'best_folder'
                    valid_component_folders = [f for f in component_folders if f and f.quality_score is not None]

                    if len(valid_component_folders) > 1:
                        best_folder: Optional[FolderInfo] = None
                        folders_in_preferred_root: List[FolderInfo] = []

                        if self.preferred_root_path:
                            for folder in valid_component_folders: # Iterate over valid folders
                                if folder.path == self.preferred_root_path or self.preferred_root_path in folder.path.parents:
                                    folders_in_preferred_root.append(folder)

                        if folders_in_preferred_root:
                            if len(folders_in_preferred_root) == 1:
                                best_folder = folders_in_preferred_root[0]
                                logger.info(f"Component includes one folder '{best_folder.path.name}' in preferred root '{self.preferred_root_path}'. It will be kept.")
                            else:
                                # Key for max must handle None, provide a default like -1.0
                                best_folder = max(folders_in_preferred_root, key=lambda f: f.quality_score if f.quality_score is not None else -1.0)
                                quality_str = f"{best_folder.quality_score:.2f}" if best_folder.quality_score is not None else "N/A"
                                logger.info(f"Component includes multiple folders in preferred root '{self.preferred_root_path}'. "
                                            f"Keeping '{best_folder.path.name}' (Q:{quality_str}) from this subset.")
                        else:
                            # Key for max must handle None, provide a default like -1.0
                            best_folder = max(valid_component_folders, key=lambda f: f.quality_score if f.quality_score is not None else -1.0)
                            quality_str = f"{best_folder.quality_score:.2f}" if best_folder.quality_score is not None else "N/A"
                            logger.debug(f"Component selection: No specific preferred root match for this component. Defaulting to best quality: "
                                         f"'{best_folder.path.name}' (Q:{quality_str}).")

                        if best_folder: # best_folder should now always be a FolderInfo object if valid_component_folders had > 1 item
                            for folder_to_check in valid_component_folders: # Iterate over valid folders
                                if folder_to_check.path != best_folder.path:
                                    folders_to_delete.append((folder_to_check, best_folder))
                                    logger.debug(f"Marked for deletion: {folder_to_check.path.name} (Keep: {best_folder.path.name} based on selection logic)")
                        else:
                            # This case should be less likely now if valid_component_folders had items
                            logger.warning(f"Could not determine a best folder for component: {[f.path.name for f in valid_component_folders if f in self.all_folders_data]}. Skipping deletion for this group.")
                    elif valid_component_folders: # Exactly one valid folder
                        logger.debug(f"Component reduced to one valid folder after quality score filtering: {valid_component_folders[0].path.name}. No duplicates within this component.")
                    else: # No valid folders (all had None quality score or were missing)
                        logger.debug(f"Component starting at {node_path.name} has no folders with valid quality scores. Skipping deletion for this group.")


        logger.info(f"Identified {len(folders_to_delete)} folders for potential deletion based on combined score.")
        return folders_to_delete


    def delete_folders_interactive(self, folders_to_delete_pairs: List[Tuple[FolderInfo, FolderInfo]]):

        if not folders_to_delete_pairs:
            print(AnsiColors.GREEN + "No folders marked for deletion based on the criteria." + AnsiColors.RESET)
            logger.info("No folders met deletion criteria.")
            return


        grouped_deletions: Dict[Path, Tuple[FolderInfo, List[FolderInfo]]] = {}
        total_folders_to_delete = 0
        for folder_to_delete, best_folder in folders_to_delete_pairs:
            best_path = best_folder.path
            if best_path not in grouped_deletions:

                grouped_deletions[best_path] = (best_folder, [])
            grouped_deletions[best_path][1].append(folder_to_delete)
            total_folders_to_delete += 1

        print(AnsiColors.YELLOW + "\n--- Folders Recommended for Deletion (Grouped by Kept Folder) ---" + AnsiColors.RESET)


        sorted_best_paths = sorted(grouped_deletions.keys(), key=str)
        group_num = 1

        folders_to_actually_trash: List[FolderInfo] = []

        for best_path in sorted_best_paths:
            best_folder_info, folders_to_trash_list = grouped_deletions[best_path]


            q_best = best_folder_info.quality_score if best_folder_info.quality_score is not None else -1.0
            q_best_str = f"{q_best:.2f}%" if q_best >= 0 else "N/A"

            print(f"\n{AnsiColors.CYAN}Group {group_num}:{AnsiColors.RESET}")
            print(f"  {AnsiColors.GREEN}Keep:     '{best_folder_info.path}' (Q: {q_best_str}){AnsiColors.RESET}")


            folders_to_trash_list.sort(key=lambda f: str(f.path))
            for folder_to_delete in folders_to_trash_list:
                q_del = folder_to_delete.quality_score if folder_to_delete.quality_score is not None else -1.0
                q_del_str = f"{q_del:.2f}%" if q_del >= 0 else "N/A"
                print(f"  {AnsiColors.RED}To Trash: '{folder_to_delete.path}' (Q: {q_del_str}){AnsiColors.RESET}")
                folders_to_actually_trash.append(folder_to_delete)

            group_num += 1

        print(AnsiColors.YELLOW + "--- End of Grouped List ---" + AnsiColors.RESET)

        try:

            confirmation = input(AnsiColors.YELLOW + f"\nMove the {total_folders_to_delete} folders listed 'To Trash' above to the system trash? (y/n): " + AnsiColors.RESET).strip().lower()
        except EOFError:
             confirmation = 'n'
             print("Non-interactive mode detected, cancelling delete operation.")


        if confirmation == 'y':
            logger.warning(f"User confirmed deletion of {total_folders_to_delete} folders.")
            trashed_count = 0
            failed_count = 0

            for folder_to_delete in folders_to_actually_trash:

                best_folder_path_associated = "Unknown" # type: Union[Path, str]
                for b_path, (b_info, del_list) in grouped_deletions.items():
                     if folder_to_delete in del_list:
                          best_folder_path_associated = b_info.path
                          break
                try:

                    if folder_to_delete.path.exists() and folder_to_delete.path.is_dir():
                         send2trash(str(folder_to_delete.path))
                         print(f"Moved to trash: '{folder_to_delete.path}'")
                         logger.warning(f"Moved to trash: {folder_to_delete.path} (preferred was {best_folder_path_associated})")
                         trashed_count += 1
                    elif not folder_to_delete.path.exists():
                         print(f"Skipped missing folder: '{folder_to_delete.path}'")
                         logger.warning(f"Skipped trashing missing folder: {folder_to_delete.path}")
                    else:

                         print(f"Skipped non-directory path: '{folder_to_delete.path}'")
                         logger.warning(f"Skipped trashing non-directory path: {folder_to_delete.path}")


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