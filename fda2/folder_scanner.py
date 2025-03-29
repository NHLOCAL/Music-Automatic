# folder_scanner.py
import os
import logging
from pathlib import Path
import re
from typing import Any, List, Dict, Optional, Tuple
import concurrent.futures

import config
from models import FileInfo, FolderInfo
from file_processor import FileProcessor
from data_store import DataStore # To check cache
from utils import cached_string_similarity, contains_hebrew # For generic name checks
from itertools import combinations

logger = logging.getLogger(__name__)

class FolderScanner:
    """Scans directories, processes files, and aggregates folder information."""

    def __init__(self, file_processor: FileProcessor, data_store: DataStore,
                 force_rescan: bool = False):
        self.file_processor = file_processor
        self.data_store = data_store
        self.force_rescan = force_rescan
        # Load artist mappings (consider making this injectable or part of config)
        self.artists_map = self._load_artists_from_csv(config.ARTIST_CSV_FILE)

    def _load_artists_from_csv(self, csv_path: Path) -> Dict[str, str]:
        """Loads artist variations from a CSV file."""
        artists_map = {}
        if not csv_path.is_file():
            logger.warning(f"Artist CSV file not found: {csv_path}. No artist normalization will be applied.")
            return artists_map
        try:
            import csv
            with open(csv_path, mode='r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                for i, row in enumerate(reader):
                    if len(row) == 2:
                        key, value = row[0].strip(), row[1].strip()
                        if key: # Ensure key is not empty
                             artists_map[key.lower()] = value # Store key as lowercase for matching
                    elif row: # Log if row exists but is malformed
                         logger.warning(f"Skipping malformed row {i+1} in artist CSV: {row}")
        except ImportError:
             logger.error("CSV library not available, cannot load artist mappings.")
        except Exception as e:
            logger.error(f"Error reading artist CSV file {csv_path}: {e}", exc_info=True)
        logger.info(f"Loaded {len(artists_map)} artist mappings from {csv_path}.")
        return artists_map

    def scan_folders(self, root_paths: List[Path]) -> Dict[Path, FolderInfo]:
        """
        Scans root paths, processes folders concurrently, and returns folder data.
        Uses cached data unless force_rescan is True.
        """
        logger.info(f"Starting scan of root paths: {root_paths}")
        all_folders_to_process = []
        for root in root_paths:
            if not root.is_dir():
                logger.warning(f"Provided path is not a directory, skipping: {root}")
                continue
            logger.info(f"Scanning directory recursively: {root}")
            for potential_folder_path in self._walk_directories(root):
                 all_folders_to_process.append(potential_folder_path)

        logger.info(f"Found {len(all_folders_to_process)} potential folders to process.")

        processed_folders: Dict[Path, FolderInfo] = {}
        cached_data = self.data_store.load_data()

        futures = []
        # Determine max_workers safely
        max_workers = config.MAX_WORKERS if config.MAX_WORKERS else os.cpu_count()
        logger.info(f"Using up to {max_workers} workers for processing.")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for folder_path in all_folders_to_process:
                 folder_path_str = str(folder_path) # Use string for JSON key compatibility
                 # Check cache
                 if not self.force_rescan and folder_path_str in cached_data:
                     try:
                         # Reconstruct FolderInfo from cached dict
                         cached_folder_dict = cached_data[folder_path_str]
                         # Basic validation before assuming cache is valid
                         if isinstance(cached_folder_dict, dict) and 'path' in cached_folder_dict:
                              folder_info = self._folder_info_from_dict(cached_folder_dict)
                              # Optional: Add a quick validation (e.g., check if path still exists)
                              if folder_info.path.is_dir():
                                   processed_folders[folder_path] = folder_info
                                   logger.debug(f"Using cached data for: {folder_path}")
                                   continue # Skip submission to executor
                              else:
                                   logger.warning(f"Cached path no longer exists, rescanning: {folder_path}")
                         else:
                              logger.warning(f"Invalid cache format for {folder_path}, rescanning.")

                     except Exception as cache_err:
                          logger.warning(f"Error loading cached data for {folder_path}, rescanning. Error: {cache_err}")
                 # Submit for processing if not using cache or cache failed/forced
                 logger.debug(f"Submitting folder for processing: {folder_path}")
                 futures.append(executor.submit(self._process_single_folder, folder_path))

            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        folder_info = result
                        processed_folders[folder_info.path] = folder_info
                except Exception as e:
                    # Log error from future.result() if submit itself didn't catch it
                    # Finding which folder failed might be tricky here without extra tracking
                    logger.error(f"Error processing a folder: {e}", exc_info=True)


        logger.info(f"Scan complete. Processed {len(processed_folders)} folders.")

        # Update cache with newly processed/rescanned folders
        # Convert FolderInfo objects back to dictionaries for JSON serialization
        updated_cache_data = {str(path): self._folder_info_to_dict(info)
                               for path, info in processed_folders.items()}
        self.data_store.save_data(updated_cache_data)

        return processed_folders


    def _walk_directories(self, root_dir: Path):
        """Recursively yields directory paths."""
        yield root_dir
        try:
            for entry in os.scandir(root_dir):
                if entry.is_dir():
                    yield from self._walk_directories(Path(entry.path))
        except OSError as e:
            logger.error(f"Error scanning directory {root_dir}: {e}")


    def _process_single_folder(self, folder_path: Path) -> Optional[FolderInfo]:
        """Processes a single folder: finds music files, extracts info, aggregates."""
        logger.info(f"Processing folder: {folder_path}")
        music_files_info: List[FileInfo] = []
        try:
            all_entries = list(os.scandir(folder_path))
            potential_music_files = [
                Path(entry.path) for entry in all_entries
                if entry.is_file() and Path(entry.name).suffix.lower() in config.ALLOWED_EXTENSIONS
                   and entry.name.lower() not in config.IGNORED_FILES
            ]

            if len(potential_music_files) < config.MIN_FILES_PER_FOLDER:
                 logger.debug(f"Skipping folder {folder_path}: Found {len(potential_music_files)} music files (minimum required: {config.MIN_FILES_PER_FOLDER}).")
                 return None

            for file_path in potential_music_files:
                 file_info = self.file_processor.process_file(file_path)
                 if file_info:
                     music_files_info.append(file_info)
                 else:
                      logger.warning(f"Failed to process file, skipping: {file_path}")

            if len(music_files_info) < config.MIN_FILES_PER_FOLDER:
                 logger.debug(f"Skipping folder {folder_path}: Only {len(music_files_info)} files successfully processed (minimum required: {config.MIN_FILES_PER_FOLDER}).")
                 return None

            # Aggregate folder-level information
            folder_name = folder_path.name
            parent_folder_name = folder_path.parent.name

            album_art_hash = self.file_processor.get_folder_album_art_hash(folder_path)

            # Calculate derived metrics
            file_hashes_present = all(fi.file_hash is not None for fi in music_files_info)
            total_bitrate = sum(fi.bitrate for fi in music_files_info if fi.bitrate is not None)
            num_files_with_bitrate = sum(1 for fi in music_files_info if fi.bitrate is not None)
            avg_bitrate = total_bitrate / num_files_with_bitrate if num_files_with_bitrate > 0 else 0.0

            unique_artists = {fi.artist for fi in music_files_info if fi.artist}
            unique_albums = {fi.album for fi in music_files_info if fi.album}

            # Normalize artists based on CSV map if needed (apply to the set)
            normalized_artists = set()
            if self.artists_map:
                 for art in unique_artists:
                      normalized_artists.add(self.artists_map.get(art.lower(), art))
                 unique_artists = normalized_artists


            # Pre-calculate generic name scores
            filenames = [fi.filename for fi in music_files_info]
            titles = [fi.title for fi in music_files_info if fi.title]
            generic_filename_score = self._calculate_generic_score(filenames)
            generic_title_score = self._calculate_generic_score(titles) if titles else 0.0

            # Pre-calculate quality ratios
            total_files = len(music_files_info)
            hebrew_metadata_count = sum(1 for fi in music_files_info if contains_hebrew(fi.title) or contains_hebrew(fi.artist) or contains_hebrew(fi.album))
            metadata_completeness_count = sum(1 for fi in music_files_info if fi.metadata_complete)
            lossless_count = sum(1 for fi in music_files_info if fi.is_lossless)
            lyrics_count = sum(1 for fi in music_files_info if fi.has_lyrics)


            folder_info = FolderInfo(
                path=folder_path,
                folder_name=folder_name,
                parent_folder_name=parent_folder_name,
                files=music_files_info,
                album_art_hash=album_art_hash,
                file_hashes_present=file_hashes_present,
                avg_bitrate=avg_bitrate,
                unique_artists=unique_artists,
                unique_albums=unique_albums,
                generic_filename_score=generic_filename_score,
                generic_title_score=generic_title_score,
                # Ratios for quality calculation
                hebrew_metadata_ratio=hebrew_metadata_count / total_files if total_files else 0.0,
                metadata_completeness_ratio=metadata_completeness_count / total_files if total_files else 0.0,
                lossless_ratio=lossless_count / total_files if total_files else 0.0,
                lyrics_ratio=lyrics_count / total_files if total_files else 0.0
            )

            logger.info(f"Successfully processed folder: {folder_path} ({len(music_files_info)} files)")
            return folder_info

        except OSError as e:
            logger.error(f"OS error processing folder {folder_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing folder {folder_path}: {e}", exc_info=True)
            return None

    def _calculate_generic_score(self, names: List[str]) -> float:
        """Calculates average similarity between names in a list (for generic check)."""
        if len(names) < 2:
            return 0.0

        # Clean names: remove extension and digits for comparison
        cleaned_names = [re.sub(r'\d', '', Path(name).stem).strip() for name in names]
        # Filter out empty strings after cleaning
        cleaned_names = [name for name in cleaned_names if name]

        if len(cleaned_names) < 2:
             return 0.0

        total_similarity = 0.0
        pair_count = 0
        for name1, name2 in combinations(cleaned_names, 2):
            total_similarity += cached_string_similarity(name1, name2)
            pair_count += 1

        return total_similarity / pair_count if pair_count > 0 else 0.0

    # --- Cache Helper Methods ---
    # These are needed to convert complex objects (Path, Set) for JSON storage

    def _folder_info_to_dict(self, folder_info: FolderInfo) -> Dict[str, Any]:
        """Converts a FolderInfo object to a JSON-serializable dictionary."""
        return {
            "path": str(folder_info.path), # Convert Path to string
            "folder_name": folder_info.folder_name,
            "parent_folder_name": folder_info.parent_folder_name,
            "files": [self._file_info_to_dict(fi) for fi in folder_info.files],
            "album_art_hash": folder_info.album_art_hash,
            "file_hashes_present": folder_info.file_hashes_present,
            "avg_bitrate": folder_info.avg_bitrate,
            "unique_artists": sorted(list(folder_info.unique_artists)), # Convert set to sorted list
            "unique_albums": sorted(list(folder_info.unique_albums)), # Convert set to sorted list
            "generic_filename_score": folder_info.generic_filename_score,
            "generic_title_score": folder_info.generic_title_score,
            "hebrew_metadata_ratio": folder_info.hebrew_metadata_ratio,
            "metadata_completeness_ratio": folder_info.metadata_completeness_ratio,
            "lossless_ratio": folder_info.lossless_ratio,
            "lyrics_ratio": folder_info.lyrics_ratio,
            # Cache quality score if already calculated (optional)
            "quality_score": folder_info.quality_score,
            "quality_breakdown": folder_info.quality_breakdown,
        }

    def _file_info_to_dict(self, file_info: FileInfo) -> Dict[str, Any]:
        """Converts a FileInfo object to a JSON-serializable dictionary."""
        return {
            "filename": file_info.filename,
            "filepath": str(file_info.filepath), # Convert Path to string
            "extension": file_info.extension,
            "size_mb": file_info.size_mb,
            "file_hash": file_info.file_hash,
            "duration": file_info.duration,
            "bitrate": file_info.bitrate,
            "title": file_info.title,
            "artist": file_info.artist,
            "album": file_info.album,
            "albumartist": file_info.albumartist,
            "all_tags": file_info.all_tags,
            "metadata_complete": file_info.metadata_complete,
            "has_lyrics": file_info.has_lyrics,
            "is_lossless": file_info.is_lossless,
        }

    def _folder_info_from_dict(self, data: Dict[str, Any]) -> FolderInfo:
        """Reconstructs a FolderInfo object from a dictionary (loaded from cache)."""
        # Convert string path back to Path object
        path = Path(data["path"])
        # Convert lists back to sets for unique artists/albums
        unique_artists = set(data.get("unique_artists", []))
        unique_albums = set(data.get("unique_albums", []))

        return FolderInfo(
            path=path,
            folder_name=data["folder_name"],
            parent_folder_name=data["parent_folder_name"],
            files=[self._file_info_from_dict(fi_data) for fi_data in data.get("files", [])],
            album_art_hash=data.get("album_art_hash"),
            file_hashes_present=data.get("file_hashes_present", False),
            avg_bitrate=data.get("avg_bitrate", 0.0),
            unique_artists=unique_artists,
            unique_albums=unique_albums,
            generic_filename_score=data.get("generic_filename_score", 0.0),
            generic_title_score=data.get("generic_title_score", 0.0),
            hebrew_metadata_ratio=data.get("hebrew_metadata_ratio", 0.0),
            metadata_completeness_ratio=data.get("metadata_completeness_ratio", 0.0),
            lossless_ratio=data.get("lossless_ratio", 0.0),
            lyrics_ratio=data.get("lyrics_ratio", 0.0),
            quality_score=data.get("quality_score"), # Load if present
            quality_breakdown=data.get("quality_breakdown", {}), # Load if present
        )

    def _file_info_from_dict(self, data: Dict[str, Any]) -> FileInfo:
        """Reconstructs a FileInfo object from a dictionary."""
        return FileInfo(
            filename=data["filename"],
            filepath=Path(data["filepath"]), # Convert string back to Path
            extension=data["extension"],
            size_mb=data.get("size_mb", 0.0),
            file_hash=data.get("file_hash"),
            duration=data.get("duration"),
            bitrate=data.get("bitrate"),
            title=data.get("title"),
            artist=data.get("artist"),
            album=data.get("album"),
            albumartist=data.get("albumartist"),
            all_tags=data.get("all_tags", {}),
            metadata_complete=data.get("metadata_complete", False),
            has_lyrics=data.get("has_lyrics", False),
            is_lossless=data.get("is_lossless", False),
        )
