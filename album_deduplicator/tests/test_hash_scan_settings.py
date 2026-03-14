from pathlib import Path

from music_dup_lib import config
from music_dup_lib.core import file_processor as file_processor_module
from music_dup_lib.core.data_store import DataStore
from music_dup_lib.core.file_processor import FileProcessor
from music_dup_lib.core.folder_scanner import FolderScanCandidate, FolderScanner
from music_dup_lib.models import FileInfo, FolderComparisonResult, FolderInfo


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
    candidate = FolderScanCandidate(
        path=root,
        music_file_paths=[root / "01.mp3", root / "02.mp3", root / "03.mp3"],
        other_file_paths=[],
        album_art_file_paths=[],
    )
    monkeypatch.setattr(scanner, "_iter_folder_candidates", lambda roots: iter([candidate]))
    processed = []

    def fake_process_folder_candidate(scan_candidate: FolderScanCandidate) -> FolderInfo:
        processed.append(scan_candidate.path)
        return FolderInfo(
            path=scan_candidate.path,
            folder_name=scan_candidate.path.name,
            parent_folder_name=scan_candidate.path.parent.name,
        )

    monkeypatch.setattr(scanner, "_process_folder_candidate", fake_process_folder_candidate)

    result = scanner.scan_folders([root])

    assert processed == [root]
    assert root in result
    saved_cache = store.load_data()
    assert saved_cache[str(root)]["hashing_strategy"] == "full"


def test_folder_scanner_skips_cache_rewrite_when_everything_comes_from_cache(monkeypatch, tmp_path):
    root = tmp_path / "album"
    root.mkdir()
    cache_file = tmp_path / "music_cache.json"
    comparison_cache = tmp_path / "comparison_cache.pkl"
    store = DataStore(music_cache_file=cache_file, comparison_cache_file=comparison_cache)
    cached_entry = {
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
    store.save_data(cached_entry)

    scanner = FolderScanner(
        file_processor=FileProcessor(enable_hashing=True, full_hash_scan=False),
        data_store=store,
    )
    candidate = FolderScanCandidate(
        path=root,
        music_file_paths=[root / "01.mp3", root / "02.mp3", root / "03.mp3"],
        other_file_paths=[],
        album_art_file_paths=[],
    )
    monkeypatch.setattr(scanner, "_iter_folder_candidates", lambda roots: iter([candidate]))

    save_calls = []
    monkeypatch.setattr(
        store,
        "save_data",
        lambda *args, **kwargs: save_calls.append((args, kwargs)),
    )

    result = scanner.scan_folders([root])

    assert root in result
    assert save_calls == []


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


def test_data_store_save_comparison_results_reuses_supplied_existing_map(monkeypatch, tmp_path):
    store = DataStore(
        music_cache_file=tmp_path / "music_cache.json",
        comparison_cache_file=tmp_path / "comparison_cache.pkl",
    )
    existing_result = FolderComparisonResult(
        folder1_path=Path("C:/music/existing-a"),
        folder2_path=Path("C:/music/existing-b"),
        weighted_score=88.0,
    )
    new_result = FolderComparisonResult(
        folder1_path=Path("C:/music/new-a"),
        folder2_path=Path("C:/music/new-b"),
        weighted_score=91.0,
    )

    monkeypatch.setattr(
        store,
        "load_comparison_results",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cache reload should be skipped")),
    )

    store.save_comparison_results(
        [new_result],
        cache_profile="partial",
        existing_results_map={
            frozenset({str(existing_result.folder1_path), str(existing_result.folder2_path)}): existing_result,
        },
    )

    reloaded_store = DataStore(
        music_cache_file=tmp_path / "music_cache.json",
        comparison_cache_file=tmp_path / "comparison_cache.pkl",
    )
    saved_results = reloaded_store.load_comparison_results(cache_profile="partial")
    assert len(saved_results) == 2


def test_folder_scanner_only_processes_leaf_album_candidates(monkeypatch, tmp_path):
    root = tmp_path / "music"
    root.mkdir()
    nested_parent = root / "Artist"
    nested_parent.mkdir()
    leaf_album = nested_parent / "Album"
    leaf_album.mkdir()
    non_album = root / "Singles"
    non_album.mkdir()

    for index in range(config.MIN_FILES_PER_FOLDER):
        (leaf_album / f"{index + 1:02d}.mp3").write_bytes(b"stub")
    (non_album / "track.mp3").write_bytes(b"stub")

    scanner = FolderScanner(
        file_processor=FileProcessor(enable_hashing=False),
        data_store=DataStore(
            music_cache_file=tmp_path / "music_cache.json",
            comparison_cache_file=tmp_path / "comparison_cache.pkl",
        ),
    )

    def fake_process_file(filepath: Path) -> FileInfo:
        return FileInfo(
            filename=filepath.name,
            filepath=filepath,
            extension=filepath.suffix.lower(),
            size_mb=1.0,
            title=filepath.stem,
            artist="Artist",
            album="Album",
            metadata_complete=True,
        )

    monkeypatch.setattr(scanner.file_processor, "process_file", fake_process_file)
    monkeypatch.setattr(scanner.file_processor, "process_other_file_info", lambda filepath: None)
    monkeypatch.setattr(scanner.file_processor, "get_folder_album_art_hash", lambda *args, **kwargs: None)

    result = scanner.scan_folders([root])

    assert set(result.keys()) == {leaf_album}


def test_get_folder_album_art_hash_uses_supplied_music_files_without_iterdir(monkeypatch, tmp_path):
    folder = tmp_path / "album"
    folder.mkdir()
    music_files = [folder / "01.mp3", folder / "02.mp3", folder / "03.mp3"]
    for music_file in music_files:
        music_file.write_bytes(b"stub")

    processor = FileProcessor(enable_hashing=False)
    calls = []

    monkeypatch.setattr(
        file_processor_module.Path,
        "iterdir",
        lambda self: (_ for _ in ()).throw(AssertionError("iterdir should not be used")),
    )
    monkeypatch.setattr(
        processor,
        "_extract_embedded_art_hash",
        lambda path: calls.append(path.name) or None,
    )

    assert processor.get_folder_album_art_hash(folder, music_files=music_files, album_art_files=[]) is None
    assert calls == ["01.mp3", "02.mp3", "03.mp3"]


def test_extract_metadata_reuses_single_detailed_mutagen_open(monkeypatch, tmp_path):
    audio_file = tmp_path / "track.mp3"
    audio_file.write_bytes(b"stub")
    processor = FileProcessor(enable_hashing=False)
    calls = []

    class FakeInfo:
        bitrate = 320000
        length = 245.0

    class FakeEasyAudio(dict):
        def __init__(self):
            super().__init__({"title": ["Song"], "artist": ["Artist"], "album": ["Album"]})
            self.info = FakeInfo()

    class FakeDetailedAudio(dict):
        def __init__(self):
            super().__init__({"TPE2": ["Album Artist"], "USLT::eng": ["lyrics"]})

    def fake_mutagen_file(filepath, easy=False):
        calls.append("easy" if easy else "detailed")
        return FakeEasyAudio() if easy else FakeDetailedAudio()

    monkeypatch.setattr(file_processor_module, "MutagenFile", fake_mutagen_file)

    metadata = processor._extract_metadata(audio_file)

    assert metadata["albumartist"] == "Album Artist"
    assert metadata["all_tags"]["lyrics"] == "[Present]"
    assert calls == ["easy", "detailed"]
