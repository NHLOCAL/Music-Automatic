from pathlib import Path

from music_dup_lib.core.data_store import DataStore
from music_dup_lib.core.file_processor import FileProcessor
from music_dup_lib.core.folder_scanner import FolderScanner
from music_dup_lib.models import FolderComparisonResult, FolderInfo


def test_file_processor_switches_between_partial_and_full_hash(monkeypatch, tmp_path):
    sample = tmp_path / "track.mp3"
    sample.write_bytes(b"abc123")

    processor = FileProcessor(enable_hashing=True, full_hash_scan=False)
    monkeypatch.setattr(processor, "_calculate_partial_hash", lambda path: "partial")
    monkeypatch.setattr(processor, "_calculate_full_hash", lambda path: "full")
    assert processor._calculate_hash(sample) == "partial"

    processor = FileProcessor(enable_hashing=True, full_hash_scan=True)
    monkeypatch.setattr(processor, "_calculate_partial_hash", lambda path: "partial")
    monkeypatch.setattr(processor, "_calculate_full_hash", lambda path: "full")
    assert processor._calculate_hash(sample) == "full"


def test_folder_scanner_rescans_when_cached_hash_strategy_differs(monkeypatch, tmp_path):
    root = tmp_path / "album"
    root.mkdir()
    cache_file = tmp_path / "music_cache.json"
    comparison_cache = tmp_path / "comparison_cache.pkl"
    store = DataStore(music_cache_file=cache_file, comparison_cache_file=comparison_cache)
    store.save_data(
        {
            str(root): {
                "path": str(root),
                "folder_name": root.name,
                "parent_folder_name": root.parent.name,
                "files": [],
                "album_art_hash": None,
                "other_files": [],
                "file_hashes_present": False,
                "avg_bitrate": 0.0,
                "unique_artists": [],
                "unique_albums": [],
                "generic_filename_score": 0.0,
                "generic_title_score": 0.0,
                "hebrew_metadata_ratio": 0.0,
                "metadata_completeness_ratio": 0.0,
                "lossless_ratio": 0.0,
                "lyrics_ratio": 0.0,
                "quality_score": None,
                "quality_breakdown": {},
                "hashing_strategy": "partial",
            }
        }
    )

    scanner = FolderScanner(
        file_processor=FileProcessor(enable_hashing=True, full_hash_scan=True),
        data_store=store,
    )
    monkeypatch.setattr(scanner, "_walk_directories", lambda current_root: iter([root]))
    processed = []

    def fake_process_single_folder(folder_path: Path) -> FolderInfo:
        processed.append(folder_path)
        return FolderInfo(
            path=folder_path,
            folder_name=folder_path.name,
            parent_folder_name=folder_path.parent.name,
        )

    monkeypatch.setattr(scanner, "_process_single_folder", fake_process_single_folder)

    result = scanner.scan_folders([root])

    assert processed == [root]
    assert root in result
    saved_cache = store.load_data()
    assert saved_cache[str(root)]["hashing_strategy"] == "full"


def test_data_store_ignores_comparison_cache_with_different_hash_profile(tmp_path):
    store = DataStore(
        music_cache_file=tmp_path / "music_cache.json",
        comparison_cache_file=tmp_path / "comparison_cache.pkl",
    )
    result = FolderComparisonResult(
        folder1_path=Path("C:/music/a"),
        folder2_path=Path("D:/music/b"),
        weighted_score=98.0,
    )

    store.save_comparison_results([result], cache_profile="partial")

    assert len(store.load_comparison_results(cache_profile="partial")) == 1
    assert store.load_comparison_results(cache_profile="full") == {}
