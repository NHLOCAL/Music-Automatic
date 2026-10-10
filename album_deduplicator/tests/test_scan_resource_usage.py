import hashlib
import logging
import os
import tracemalloc
from pathlib import Path

import pytest

from music_dup_lib.core import file_processor as processor_module
from music_dup_lib.core.data_store import DataStore
from music_dup_lib.core.file_processor import FileProcessor
from music_dup_lib.core.folder_scanner import FolderScanner
from music_dup_lib.models import FileInfo


@pytest.mark.parametrize("music_file", [True, False])
def test_file_processing_reads_filesystem_metadata_once(monkeypatch, tmp_path, music_file):
    track = tmp_path / ("track.mp3" if music_file else "notes.txt")
    track.write_bytes(b"sample content")
    processor = FileProcessor(enable_hashing=True)
    monkeypatch.setattr(processor, "_extract_metadata", lambda path: {"all_tags": {}})
    original_stat = Path.stat
    reads = []

    def counted_stat(path, *args, **kwargs):
        if path == track:
            reads.append(path)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", counted_stat)
    result = processor.process_file(track) if music_file else processor.process_other_file_info(track)

    assert result is not None
    expected_hash = hashlib.sha256(b"sample content").hexdigest()
    assert (result.file_hash if music_file else result["hash"]) == expected_hash
    assert (result.size_mb if music_file else result["size_bytes"]) == (
        14 / (1024 * 1024) if music_file else 14
    )
    assert len(reads) == 1


@pytest.mark.parametrize("name", ["missing.mp3", "directory.mp3"])
def test_file_processing_still_rejects_missing_files_and_directories(tmp_path, name):
    path = tmp_path / name
    if name.startswith("directory"):
        path.mkdir()
    processor = FileProcessor(enable_hashing=False)
    assert processor.process_file(path) is None
    assert processor.process_other_file_info(path) is None


def test_disabled_debug_logging_does_not_render_track_metadata(monkeypatch, tmp_path):
    track = tmp_path / "track.mp3"
    track.write_bytes(b"content")
    processor = FileProcessor(enable_hashing=False)
    monkeypatch.setattr(processor, "_extract_metadata", lambda path: {"title": "Song", "all_tags": {}})
    monkeypatch.setattr(processor_module.logger, "level", logging.INFO)

    def forbidden_repr(self):
        raise AssertionError("Disabled debug logging should not render every track's tags")

    monkeypatch.setattr(FileInfo, "__repr__", forbidden_repr)
    result = processor.process_file(track)
    assert result is not None
    assert result.title == "Song"


def test_scan_does_not_duplicate_large_folder_cache_when_no_candidates(monkeypatch, tmp_path):
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    cached_records = {str(index): {} for index in range(10000)}
    monkeypatch.setattr(store, "load_data", lambda: cached_records)
    scanner = FolderScanner(FileProcessor(enable_hashing=False), store)

    tracemalloc.start()
    try:
        result = scanner.scan_folders([])
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert result == {}
    assert not store.music_cache_file.exists()
    # A shallow copy of this cache alone exceeds 200 KB on supported CPython.
    assert peak < 100000


def test_scan_updates_preserve_cache_for_other_roots_and_unchanged_rescans(tmp_path):
    album = tmp_path / "album"
    album.mkdir()
    for number in range(3):
        (album / f"{number}.mp3").write_bytes(b"sample")
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    outside_record = {"path": "outside-root", "unrelated": ["preserve"]}
    store.save_data({"outside-root": outside_record}, merge=False)

    scanner = FolderScanner(FileProcessor(enable_hashing=True), store, force_rescan=True)
    result = scanner.scan_folders([album])
    assert list(result) == [album]
    persisted = store.load_data()
    assert persisted["outside-root"] == outside_record
    assert len(persisted[str(album)]["files"]) == 3
    assert persisted[str(album)]["files"][0]["file_hash"] == hashlib.sha256(b"sample").hexdigest()

    os.utime(store.music_cache_file, ns=(1000000000, 1000000000))
    scanner.scan_folders([album])
    assert store.music_cache_file.stat().st_mtime_ns == 1000000000
    assert store.load_data() == persisted


def test_generic_repeated_track_names_avoid_quadratic_comparisons(monkeypatch, tmp_path):
    import music_dup_lib.core.folder_scanner as scanner_module

    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    scanner = FolderScanner(FileProcessor(enable_hashing=False), store)
    original_similarity = scanner_module.cached_string_similarity
    comparisons = []

    def counted_similarity(first, second):
        comparisons.append((first, second))
        return original_similarity(first, second)

    monkeypatch.setattr(scanner_module, "cached_string_similarity", counted_similarity)
    score = scanner._calculate_generic_score([f"track {index:03}.mp3" for index in range(100)])

    assert score == 1.0
    assert len(comparisons) <= 1
