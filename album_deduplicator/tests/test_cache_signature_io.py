import hashlib
import json
import os
import threading
from pathlib import Path

import pytest

from music_dup_lib.core.data_store import DataStore
from music_dup_lib.core.file_processor import FileProcessor
from music_dup_lib.core.folder_scanner import FolderScanCandidate, FolderScanner


def setup_candidate(tmp_path):
    album = tmp_path / "album"
    album.mkdir()
    for name in ("0.mp3", "1.mp3", "2.mp3", "notes.txt", "cover.jpg"):
        (album / name).write_bytes(b"sample")
    scanner = FolderScanner(FileProcessor(False), DataStore(tmp_path / "music.json", tmp_path / "pairs.pkl"))
    return scanner, scanner._build_folder_candidate(album, [path.name for path in album.iterdir()])


def reference_signature(candidate, context):
    digest = hashlib.sha256(context)
    for category, paths in (("music", candidate.music_file_paths), ("other", candidate.other_file_paths),
                            ("art", candidate.album_art_file_paths)):
        for path in paths:
            result = path.stat()
            record = (category, path.name, result.st_size, result.st_mtime_ns, result.st_mode)
            digest.update(json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return digest.hexdigest()


def test_signature_keeps_existing_format_and_reads_every_file(monkeypatch, tmp_path):
    scanner, candidate = setup_candidate(tmp_path)
    context = scanner._signature_context()
    expected = reference_signature(candidate, context)
    original = Path.stat
    calls = []

    def counted(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", counted)
    assert scanner._candidate_signature(candidate, context) == expected
    assert calls == candidate.music_file_paths + candidate.other_file_paths + candidate.album_art_file_paths


def test_signature_enumerates_fresh_metadata_each_time(tmp_path):
    scanner, candidate = setup_candidate(tmp_path)
    context = scanner._signature_context()
    before = scanner._candidate_signature(candidate, context)
    track = candidate.music_file_paths[0]
    previous = track.stat()
    track.write_bytes(b"edited")
    os.utime(track, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1000000000))
    after = scanner._candidate_signature(candidate, context)
    assert after != before
    assert after == reference_signature(candidate, context)


def test_signature_does_not_trust_a_file_missing_from_directory_snapshot(tmp_path):
    scanner, candidate = setup_candidate(tmp_path)
    candidate.other_file_paths[0].unlink()
    assert scanner._candidate_signature(candidate, scanner._signature_context()) is None


def test_unreadable_file_cannot_validate_cache(monkeypatch, tmp_path):
    scanner, candidate = setup_candidate(tmp_path)
    original = Path.stat

    def denied(path, *args, **kwargs):
        if path == candidate.music_file_paths[0]:
            raise PermissionError("no file access")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", denied)
    assert scanner._candidate_signature(candidate, scanner._signature_context()) is None


def test_signature_still_follows_file_symlink_targets(tmp_path):
    scanner, candidate = setup_candidate(tmp_path)
    track = candidate.music_file_paths[0]
    target = tmp_path / "target.mp3"
    target.write_bytes(b"first")
    track.unlink()
    try:
        track.symlink_to(target)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or privileges")
    context = scanner._signature_context()
    before = scanner._candidate_signature(candidate, context)
    assert before == reference_signature(candidate, context)
    target.write_bytes(b"changed target content")
    after = scanner._candidate_signature(candidate, context)
    assert after != before
    assert after == reference_signature(candidate, context)


def test_warm_signature_checks_use_bounded_scan_workers_and_keep_folder_order(monkeypatch, tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    for name in ("a", "b", "c"):
        album = root / name
        album.mkdir()
        for index in range(3):
            (album / f"{index}.mp3").write_bytes(b"sample")
    scanner = FolderScanner(FileProcessor(False), DataStore(tmp_path / "music.json", tmp_path / "pairs.pkl"))
    expected_order = [candidate.path for candidate in scanner._iter_folder_candidates([root])]
    scanner.scan_folders([root])
    original = scanner._candidate_signature
    caller = threading.get_ident()
    worker_ids = []

    def counted(candidate, context):
        worker_ids.append(threading.get_ident())
        return original(candidate, context)

    monkeypatch.setattr(scanner, "_candidate_signature", counted)
    actual = scanner.scan_folders([root])
    assert list(actual) == expected_order
    assert len(worker_ids) == 3
    assert all(worker != caller for worker in worker_ids)
    assert len(set(worker_ids)) <= scanner._resolve_max_workers()


@pytest.mark.parametrize("extension", [".exe", ".com", ".cmd", ".bat"])
def test_signature_keeps_executable_file_mode_bits(tmp_path, extension):
    scanner, candidate = setup_candidate(tmp_path)
    extra = candidate.path / ("notes" + extension)
    extra.write_bytes(b"additional file")
    candidate = scanner._build_folder_candidate(candidate.path, [path.name for path in candidate.path.iterdir()])
    context = scanner._signature_context()
    assert scanner._candidate_signature(candidate, context) == reference_signature(candidate, context)


def test_signature_rechecks_content_changed_through_another_hard_link(tmp_path):
    scanner, candidate = setup_candidate(tmp_path)
    target = tmp_path / "alias.mp3"
    try:
        os.link(candidate.music_file_paths[0], target)
    except OSError:
        pytest.skip("Creating hard links is unavailable in this environment")
    context = scanner._signature_context()
    before = scanner._candidate_signature(candidate, context)
    target.write_bytes(b"modified through a different hard link")
    after = scanner._candidate_signature(candidate, context)
    assert before != after
    assert after == reference_signature(candidate, context)


def test_validation_does_not_queue_unbounded_futures(monkeypatch, tmp_path):
    scanner, _ = setup_candidate(tmp_path)
    candidates = [FolderScanCandidate(tmp_path / str(index), [], [], []) for index in range(20)]
    monkeypatch.setattr(scanner, "_iter_folder_candidates", lambda roots: iter(candidates))
    monkeypatch.setattr(scanner, "_candidate_signature", lambda candidate, context: str(candidate.path))
    pending = [0]
    peaks = []

    class Future:
        def __init__(self, value):
            self.value = value

        def result(self):
            pending[0] -= 1
            return self.value

    class Executor:
        def submit(self, fn, *args):
            pending[0] += 1
            peaks.append(pending[0])
            return Future(fn(*args))

    actual = list(scanner._iter_validated_candidates([tmp_path], Executor(), 3))
    assert [candidate for candidate, _ in actual] == candidates
    assert max(peaks) == 3
    assert pending[0] == 0


def test_single_worker_validation_does_not_add_future_overhead(tmp_path):
    scanner, candidate = setup_candidate(tmp_path)
    expected = scanner._candidate_signature(candidate, scanner._signature_context())

    class Executor:
        def submit(self, *args):
            raise AssertionError("Single-worker mode should validate directly")

    actual = list(scanner._iter_validated_candidates([candidate.path], Executor(), 1))
    assert len(actual) == 1
    assert actual[0][1] == expected
