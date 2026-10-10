import hashlib
import os
from pathlib import Path

import pytest

from music_dup_lib.core.data_store import DataStore
from music_dup_lib.core.file_processor import FileProcessor
from music_dup_lib.core.folder_scanner import FolderScanner
from music_dup_lib.models import FolderComparisonResult
from music_dup_lib import config
from music_dup_lib.core import folder_scanner as scanner_module


def make_album(path):
    path.mkdir()
    for number in range(3):
        (path / f"{number}.mp3").write_bytes(b"sample")


@pytest.mark.parametrize("changed_file", ["0.mp3", "notes.txt", "cover.jpg"])
def test_warm_scan_invalidates_changed_music_other_and_cover_files(tmp_path, changed_file):
    album = tmp_path / "album"
    make_album(album)
    (album / "notes.txt").write_bytes(b"notes")
    (album / "cover.jpg").write_bytes(b"not an image")
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    scanner = FolderScanner(FileProcessor(enable_hashing=True), store)
    scanner.scan_folders([album])
    before = store.load_data()[str(album)]
    (album / changed_file).write_bytes(b"changed content with a different size")

    result = scanner.scan_folders([album])
    after = store.load_data()[str(album)]

    assert before.get("cache_signature") != after.get("cache_signature")
    assert scanner.cache_signatures[str(album)] == after["cache_signature"]
    if changed_file == "0.mp3":
        assert result[album].files[0].file_hash == hashlib.sha256(b"changed content with a different size").hexdigest()
    if changed_file == "notes.txt":
        assert result[album].other_files[0]["size_bytes"] == 37


def test_warm_scan_invalidates_added_and_removed_files(tmp_path):
    album = tmp_path / "album"
    make_album(album)
    scanner = FolderScanner(FileProcessor(False), DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl"))
    scanner.scan_folders([album])
    (album / "3.mp3").write_bytes(b"extra")
    assert len(scanner.scan_folders([album])[album].files) == 4
    (album / "0.mp3").unlink()
    assert [file.filename for file in scanner.scan_folders([album])[album].files] == ["1.mp3", "2.mp3", "3.mp3"]


def test_warm_scan_detects_same_size_change_through_nanosecond_mtime(tmp_path):
    album = tmp_path / "album"
    make_album(album)
    scanner = FolderScanner(FileProcessor(True), DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl"))
    scanner.scan_folders([album])
    track = album / "0.mp3"
    old_stat = track.stat()
    track.write_bytes(b"edited")
    os.utime(track, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns + 1000000000))
    assert scanner.scan_folders([album])[album].files[0].file_hash == hashlib.sha256(b"edited").hexdigest()


@pytest.mark.parametrize("context_change", ["artist_map", "version", "hash_chunks"])
def test_cache_signature_changes_when_extraction_context_changes(monkeypatch, tmp_path, context_change):
    album = tmp_path / "album"
    make_album(album)
    scanner = FolderScanner(FileProcessor(True), DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl"))
    scanner.scan_folders([album])
    original = scanner.cache_signatures[str(album)]
    if context_change == "artist_map":
        scanner.artists_map["test singer"] = "Corrected Singer"
    elif context_change == "version":
        monkeypatch.setattr(scanner_module, "FOLDER_CACHE_SIGNATURE_VERSION", scanner_module.FOLDER_CACHE_SIGNATURE_VERSION + 1)
    else:
        monkeypatch.setattr(config, "HASH_NUM_RANDOM_CHUNKS", config.HASH_NUM_RANDOM_CHUNKS + 1)
    scanner.scan_folders([album])
    assert scanner.cache_signatures[str(album)] != original


def test_legacy_folder_cache_is_rescanned_once_then_reused(monkeypatch, tmp_path):
    album = tmp_path / "album"
    make_album(album)
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    store.save_data({str(album): {"path": str(album), "folder_name": "old", "parent_folder_name": "old", "files": [], "hashing_strategy": "none"}}, merge=False)
    scanner = FolderScanner(FileProcessor(False), store)
    assert len(scanner.scan_folders([album])[album].files) == 3

    def forbidden_processing(candidate):
        raise AssertionError("Unchanged fingerprint should reuse the newly written cache")

    monkeypatch.setattr(scanner, "_process_folder_candidate", forbidden_processing)
    assert len(scanner.scan_folders([album])[album].files) == 3


def test_comparison_cache_only_reuses_pairs_with_current_signatures(tmp_path):
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    ab = FolderComparisonResult(Path("a"), Path("b"), weighted_score=90)
    ac = FolderComparisonResult(Path("a"), Path("c"), weighted_score=80)
    signatures = {"a": "a-v1", "b": "b-v1", "c": "c-v1"}
    store.save_comparison_results([ab, ac], folder_signatures=signatures)

    reused = store.load_comparison_results(folder_signatures={"a": "a-v1", "b": "b-v1", "c": "c-v2"})
    assert set(reused) == {frozenset({"a", "b"})}
    assert reused[frozenset({"a", "b"})].weighted_score == 90
    assert store.load_comparison_results(folder_signatures={"a": "a-v1"}) == {}


def test_comparison_cache_without_fingerprints_is_ignored_when_validation_requested(tmp_path):
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    ab = FolderComparisonResult(Path("a"), Path("b"), weighted_score=90)
    store.save_comparison_results([ab])
    assert len(store.load_comparison_results()) == 1
    assert store.load_comparison_results(folder_signatures={"a": "current-a", "b": "current-b"}) == {}


@pytest.mark.parametrize("changed_input", ["weights", "model", "prompt", "quality", "bitrate"])
def test_comparison_cache_invalidates_changed_scoring_inputs(monkeypatch, tmp_path, changed_input):
    model = tmp_path / "model.joblib"
    prompt = tmp_path / "prompt.txt"
    model.write_bytes(b"model-v1")
    prompt.write_text("prompt-v1", encoding="utf-8")
    monkeypatch.setattr(config, "ML_MODEL_FILE", model)
    monkeypatch.setattr(config, "GEMINI_SYSTEM_INST_FILE", prompt)
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    signatures = {"a": "1", "b": "1"}
    pair = FolderComparisonResult(Path("a"), Path("b"), weighted_score=90, ml_similarity_score=95)
    store.save_comparison_results([pair], folder_signatures=signatures)
    assert len(store.load_comparison_results(folder_signatures=signatures)) == 1
    if changed_input == "weights":
        monkeypatch.setattr(config, "SIMILARITY_WEIGHTS", {"file_hash": 1.0})
    elif changed_input == "model":
        model.write_bytes(b"model-v2-with-different-size")
    elif changed_input == "prompt":
        prompt.write_text("a new prompt", encoding="utf-8")
    elif changed_input == "quality":
        monkeypatch.setattr(config, "QUALITY_WEIGHTS", {"bitrate_score": 1.0})
    if changed_input == "bitrate":
        assert store.load_comparison_results(folder_signatures=signatures, scoring_profile="high") == {}
    else:
        assert store.load_comparison_results(folder_signatures=signatures) == {}


def test_comparison_cache_merge_retains_only_pairs_valid_for_new_signatures(tmp_path):
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    ab = FolderComparisonResult(Path("a"), Path("b"), weighted_score=90)
    ac = FolderComparisonResult(Path("a"), Path("c"), weighted_score=80)
    store.save_comparison_results([ab, ac], folder_signatures={"a": "1", "b": "1", "c": "1"})
    changed_ac = FolderComparisonResult(Path("a"), Path("c"), weighted_score=20)
    current = {"a": "1", "b": "1", "c": "2"}
    store.save_comparison_results([changed_ac], folder_signatures=current)
    reloaded = store.load_comparison_results(folder_signatures=current)
    assert len(reloaded) == 2
    assert reloaded[frozenset({"a", "b"})].weighted_score == 90
    assert reloaded[frozenset({"a", "c"})].weighted_score == 20


def test_failed_music_cache_serialization_preserves_previous_valid_cache(tmp_path):
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    store.save_data({"existing": {"files": ["keep"]}}, merge=False)
    previous = store.music_cache_file.read_bytes()
    store.save_data({"bad": {"not-json": {1, 2}}}, merge=False)
    assert store.music_cache_file.read_bytes() == previous
    assert set(tmp_path.iterdir()) == {store.music_cache_file}


def test_failed_comparison_cache_serialization_preserves_previous_valid_cache(tmp_path):
    store = DataStore(tmp_path / "music.json", tmp_path / "comparisons.pkl")
    good = FolderComparisonResult(Path("a"), Path("b"), weighted_score=90)
    store.save_comparison_results([good])
    previous = store.comparison_cache_file.read_bytes()
    bad = FolderComparisonResult(Path("c"), Path("d"), weighted_score=lambda: 90)
    store.save_comparison_results([bad])
    assert store.comparison_cache_file.read_bytes() == previous
    assert set(tmp_path.iterdir()) == {store.comparison_cache_file}
