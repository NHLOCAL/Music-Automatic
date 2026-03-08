import concurrent.futures
import logging
import os
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .. import config
from ..models import FileInfo, FolderInfo
from ..utils import cached_string_similarity, contains_hebrew
from .data_store import DataStore
from .file_processor import FileProcessor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FolderScanCandidate:
    path: Path
    music_file_paths: List[Path]
    other_file_paths: List[Path]
    album_art_file_paths: List[Path]


class FolderScanner:
    def __init__(self, file_processor: FileProcessor, data_store: DataStore, force_rescan: bool = False):
        self.file_processor = file_processor
        self.data_store = data_store
        self.force_rescan = force_rescan
        self.artists_map = self._load_artists_from_csv(config.ARTIST_CSV_FILE)

    def _load_artists_from_csv(self, csv_path: Path) -> Dict[str, str]:
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
                        if key:
                            artists_map[key.lower()] = value
                    elif row:
                        logger.warning(f"Skipping malformed row {i + 1} in artist CSV: {row}")
        except ImportError:
            logger.error("CSV library not available, cannot load artist mappings.")
        except Exception as e:
            logger.error(f"Error reading artist CSV file {csv_path}: {e}", exc_info=True)
        logger.info(f"Loaded {len(artists_map)} artist mappings from {csv_path}.")
        return artists_map

    def scan_folders(self, root_paths: List[Path]) -> Dict[Path, FolderInfo]:
        logger.info(f"Starting scan of root paths: {root_paths}")
        processed_folders: Dict[Path, FolderInfo] = {}
        cached_data = self.data_store.load_data()
        cache_to_persist = dict(cached_data)
        candidates_found = 0
        futures: Dict[concurrent.futures.Future[Optional[FolderInfo]], FolderScanCandidate] = {}

        max_workers = self._resolve_max_workers()
        max_pending_tasks = max_workers * max(1, config.SCAN_MAX_PENDING_TASKS_MULTIPLIER)
        logger.info(f"Using up to {max_workers} workers for processing.")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for candidate in self._iter_folder_candidates(root_paths):
                candidates_found += 1
                cached_folder = self._load_cached_folder(candidate.path, cached_data)
                if cached_folder is not None:
                    processed_folders[candidate.path] = cached_folder
                    continue

                logger.debug(f"Submitting folder for processing: {candidate.path}")
                future = executor.submit(self._process_folder_candidate, candidate)
                futures[future] = candidate

                if len(futures) >= max_pending_tasks:
                    self._drain_completed_futures(
                        futures=futures,
                        processed_folders=processed_folders,
                        cache_to_persist=cache_to_persist,
                        wait_for_all=False,
                    )

            self._drain_completed_futures(
                futures=futures,
                processed_folders=processed_folders,
                cache_to_persist=cache_to_persist,
                wait_for_all=True,
            )

        logger.info(
            f"Scan complete. Found {candidates_found} candidate folders and processed {len(processed_folders)} folders."
        )
        self.data_store.save_data(cache_to_persist, merge=False)
        return processed_folders

    def _resolve_max_workers(self) -> int:
        if config.SCAN_MAX_WORKERS:
            return max(1, config.SCAN_MAX_WORKERS)
        if config.MAX_WORKERS:
            return max(1, config.MAX_WORKERS)
        cpu_count = os.cpu_count() or 1
        if cpu_count == 1:
            return 1
        return max(2, min(8, cpu_count // 2))

    def _iter_folder_candidates(self, root_paths: Iterable[Path]) -> Iterable[FolderScanCandidate]:
        for root in root_paths:
            if not root.is_dir():
                logger.warning(f"Provided path is not a directory, skipping: {root}")
                continue
            logger.info(f"Scanning directory recursively: {root}")
            try:
                for current_dir, subdirs, filenames in os.walk(root):
                    if subdirs:
                        continue
                    candidate = self._build_folder_candidate(Path(current_dir), filenames)
                    if candidate is not None:
                        yield candidate
            except OSError as e:
                logger.error(f"Error scanning directory {root}: {e}")

    def _build_folder_candidate(self, folder_path: Path, filenames: Iterable[str]) -> Optional[FolderScanCandidate]:
        music_file_paths: List[Path] = []
        other_file_paths: List[Path] = []
        album_art_file_paths: List[Path] = []

        for filename in filenames:
            lowered = filename.lower()
            entry_path = folder_path / filename
            suffix = entry_path.suffix.lower()

            if suffix in config.ALLOWED_EXTENSIONS and lowered not in config.IGNORED_FILES:
                music_file_paths.append(entry_path)
                continue

            if lowered in config.ALBUM_ART_FILES:
                album_art_file_paths.append(entry_path)
                continue

            other_file_paths.append(entry_path)

        if len(music_file_paths) < config.MIN_FILES_PER_FOLDER:
            return None

        music_file_paths.sort(key=lambda path: path.name.lower())
        other_file_paths.sort(key=lambda path: path.name.lower())
        album_art_file_paths.sort(key=lambda path: path.name.lower())

        return FolderScanCandidate(
            path=folder_path,
            music_file_paths=music_file_paths,
            other_file_paths=other_file_paths,
            album_art_file_paths=album_art_file_paths,
        )

    def _load_cached_folder(self, folder_path: Path, cached_data: Dict[str, Any]) -> Optional[FolderInfo]:
        folder_path_str = str(folder_path)
        if self.force_rescan or folder_path_str not in cached_data:
            return None

        try:
            cached_folder_dict = cached_data[folder_path_str]
            if not isinstance(cached_folder_dict, dict) or 'path' not in cached_folder_dict:
                logger.warning(f"Invalid cache format for {folder_path}, rescanning.")
                return None

            cached_hash_strategy = cached_folder_dict.get("hashing_strategy", "partial")
            if cached_hash_strategy != self.file_processor.hashing_strategy:
                logger.info(
                    "Rescanning %s because cache hash strategy %s does not match requested %s.",
                    folder_path,
                    cached_hash_strategy,
                    self.file_processor.hashing_strategy,
                )
                return None

            folder_info = self._folder_info_from_dict(cached_folder_dict)
            if folder_info.path.is_dir():
                logger.debug(f"Using cached data for: {folder_path}")
                return folder_info

            logger.warning(f"Cached path no longer exists, rescanning: {folder_path}")
            return None
        except Exception as cache_err:
            logger.warning(f"Error loading cached data for {folder_path}, rescanning. Error: {cache_err}")
            return None

    def _drain_completed_futures(
        self,
        futures: Dict[concurrent.futures.Future[Optional[FolderInfo]], FolderScanCandidate],
        processed_folders: Dict[Path, FolderInfo],
        cache_to_persist: Dict[str, Any],
        wait_for_all: bool,
    ) -> None:
        if not futures:
            return

        return_when = concurrent.futures.ALL_COMPLETED if wait_for_all else concurrent.futures.FIRST_COMPLETED
        done, _ = concurrent.futures.wait(tuple(futures.keys()), return_when=return_when)

        for future in done:
            candidate = futures.pop(future)
            try:
                result = future.result()
                if result:
                    processed_folders[result.path] = result
                    cache_to_persist[str(result.path)] = self._folder_info_to_dict(result)
            except Exception as e:
                logger.error(f"Error processing folder {candidate.path}: {e}", exc_info=True)

    def _process_folder_candidate(self, candidate: FolderScanCandidate) -> Optional[FolderInfo]:
        folder_path = candidate.path
        logger.info(f"Processing folder: {folder_path}")
        music_files_info: List[FileInfo] = []
        other_files_list: List[Dict[str, Any]] = []

        try:
            for file_path in candidate.music_file_paths:
                file_info = self.file_processor.process_file(file_path)
                if file_info:
                    music_files_info.append(file_info)
                else:
                    logger.warning(f"Failed to process music file, skipping: {file_path}")

            if len(music_files_info) < config.MIN_FILES_PER_FOLDER:
                logger.debug(
                    f"Skipping folder {folder_path}: Only {len(music_files_info)} music files successfully processed "
                    f"(minimum required: {config.MIN_FILES_PER_FOLDER})."
                )
                return None

            for other_file_path in candidate.other_file_paths:
                other_file_details = self.file_processor.process_other_file_info(other_file_path)
                if other_file_details:
                    other_files_list.append(other_file_details)
                    logger.debug(f"Collected other file: {other_file_path.name} in {folder_path.name}")

            album_art_hash = self.file_processor.get_folder_album_art_hash(
                folder_path,
                music_files=candidate.music_file_paths,
                album_art_files=candidate.album_art_file_paths,
            )

            file_hashes_present = all(fi.file_hash is not None for fi in music_files_info)
            total_bitrate = sum(fi.bitrate for fi in music_files_info if fi.bitrate is not None)
            num_files_with_bitrate = sum(1 for fi in music_files_info if fi.bitrate is not None)
            avg_bitrate = total_bitrate / num_files_with_bitrate if num_files_with_bitrate > 0 else 0.0

            unique_artists = {fi.artist for fi in music_files_info if fi.artist}
            unique_albums = {fi.album for fi in music_files_info if fi.album}

            normalized_artists = set()
            if self.artists_map:
                for artist in unique_artists:
                    normalized_artists.add(self.artists_map.get(artist.lower(), artist))
                unique_artists = normalized_artists

            filenames = [fi.filename for fi in music_files_info]
            titles = [fi.title for fi in music_files_info if fi.title]
            generic_filename_score = self._calculate_generic_score(filenames)
            generic_title_score = self._calculate_generic_score(titles) if titles else 0.0

            total_files = len(music_files_info)
            hebrew_metadata_count = sum(
                1
                for fi in music_files_info
                if contains_hebrew(fi.title) or contains_hebrew(fi.artist) or contains_hebrew(fi.album)
            )
            metadata_completeness_count = sum(1 for fi in music_files_info if fi.metadata_complete)
            lossless_count = sum(1 for fi in music_files_info if fi.is_lossless)
            lyrics_count = sum(1 for fi in music_files_info if fi.has_lyrics)

            folder_info = FolderInfo(
                path=folder_path,
                folder_name=folder_path.name,
                parent_folder_name=folder_path.parent.name,
                files=music_files_info,
                album_art_hash=album_art_hash,
                other_files=other_files_list,
                file_hashes_present=file_hashes_present,
                avg_bitrate=avg_bitrate,
                unique_artists=unique_artists,
                unique_albums=unique_albums,
                generic_filename_score=generic_filename_score,
                generic_title_score=generic_title_score,
                hebrew_metadata_ratio=hebrew_metadata_count / total_files if total_files else 0.0,
                metadata_completeness_ratio=metadata_completeness_count / total_files if total_files else 0.0,
                lossless_ratio=lossless_count / total_files if total_files else 0.0,
                lyrics_ratio=lyrics_count / total_files if total_files else 0.0,
            )

            logger.info(
                f"Successfully processed folder: {folder_path} "
                f"({len(music_files_info)} music files, {len(other_files_list)} other files)"
            )
            return folder_info
        except OSError as e:
            logger.error(f"OS error processing folder {folder_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing folder {folder_path}: {e}", exc_info=True)
            return None

    def _calculate_generic_score(self, names: List[str]) -> float:
        if len(names) < 2:
            return 0.0

        cleaned_names = [re.sub(r'\d', '', Path(name).stem).strip() for name in names]
        cleaned_names = [name for name in cleaned_names if name]
        if len(cleaned_names) < 2:
            return 0.0

        total_similarity = 0.0
        pair_count = 0
        for name1, name2 in combinations(cleaned_names, 2):
            total_similarity += cached_string_similarity(name1, name2)
            pair_count += 1

        return total_similarity / pair_count if pair_count > 0 else 0.0

    def _folder_info_to_dict(self, folder_info: FolderInfo) -> Dict[str, Any]:
        return {
            "path": str(folder_info.path),
            "folder_name": folder_info.folder_name,
            "parent_folder_name": folder_info.parent_folder_name,
            "files": [self._file_info_to_dict(fi) for fi in folder_info.files],
            "album_art_hash": folder_info.album_art_hash,
            "other_files": folder_info.other_files,
            "file_hashes_present": folder_info.file_hashes_present,
            "avg_bitrate": folder_info.avg_bitrate,
            "unique_artists": sorted(list(folder_info.unique_artists)),
            "unique_albums": sorted(list(folder_info.unique_albums)),
            "generic_filename_score": folder_info.generic_filename_score,
            "generic_title_score": folder_info.generic_title_score,
            "hebrew_metadata_ratio": folder_info.hebrew_metadata_ratio,
            "metadata_completeness_ratio": folder_info.metadata_completeness_ratio,
            "lossless_ratio": folder_info.lossless_ratio,
            "lyrics_ratio": folder_info.lyrics_ratio,
            "hashing_strategy": self.file_processor.hashing_strategy,
            "quality_score": folder_info.quality_score,
            "quality_breakdown": folder_info.quality_breakdown,
        }

    def _file_info_to_dict(self, file_info: FileInfo) -> Dict[str, Any]:
        return {
            "filename": file_info.filename,
            "filepath": str(file_info.filepath),
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
        path = Path(data["path"])
        unique_artists = set(data.get("unique_artists", []))
        unique_albums = set(data.get("unique_albums", []))

        return FolderInfo(
            path=path,
            folder_name=data["folder_name"],
            parent_folder_name=data["parent_folder_name"],
            files=[self._file_info_from_dict(fi_data) for fi_data in data.get("files", [])],
            album_art_hash=data.get("album_art_hash"),
            other_files=data.get("other_files", []),
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
            quality_score=data.get("quality_score"),
            quality_breakdown=data.get("quality_breakdown", {}),
        )

    def _file_info_from_dict(self, data: Dict[str, Any]) -> FileInfo:
        return FileInfo(
            filename=data["filename"],
            filepath=Path(data["filepath"]),
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
