from pathlib import Path

from music_dup_lib.core.folder_scanner import FolderScanner


class DummyFileProcessor:
    hashing_strategy = "partial"


class DummyDataStore:
    def load_data(self):
        return {}


def create_album(folder_path: Path) -> None:
    folder_path.mkdir(parents=True)
    for index in range(1, 4):
        (folder_path / f"{index:02d}.mp3").write_bytes(b"")


def test_folder_scanner_skips_recycle_bin_descendants(tmp_path):
    music_album = tmp_path / "Music" / "Album"
    recycle_album = tmp_path / "$Recycle.Bin" / "S-1-5-21-user" / "Deleted Album"
    create_album(music_album)
    create_album(recycle_album)

    scanner = FolderScanner(DummyFileProcessor(), DummyDataStore())

    candidates = list(scanner._iter_folder_candidates([tmp_path]))

    assert [candidate.path for candidate in candidates] == [music_album]


def test_folder_scanner_skips_music_folder_with_subdirectory_until_delete_flow_is_safe(tmp_path):
    music_album = tmp_path / "Music" / "Album"
    create_album(music_album)
    (music_album / "Scans").mkdir()
    (music_album / "Scans" / "cover.jpg").write_bytes(b"")

    scanner = FolderScanner(DummyFileProcessor(), DummyDataStore())

    candidates = list(scanner._iter_folder_candidates([tmp_path]))

    assert [candidate.path for candidate in candidates] == []
