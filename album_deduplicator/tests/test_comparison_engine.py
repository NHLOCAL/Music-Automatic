from pathlib import Path

from music_dup_lib.core.comparison_engine import ComparisonEngine
from music_dup_lib.models import FileInfo, FolderComparisonResult, FolderInfo


def make_folder(path_str: str, track_count: int) -> FolderInfo:
    path = Path(path_str)
    files = [
        FileInfo(
            filename=f"{index:02d} Track {index}.mp3",
            filepath=path / f"{index:02d} Track {index}.mp3",
            extension=".mp3",
            size_mb=5.0 + index,
            duration=180.0 + index,
            bitrate=320,
            title=f"Song {index}",
            artist="Artist",
            album="Album",
            albumartist="Artist",
            all_tags={"title": f"Song {index}", "artist": "Artist", "album": "Album"},
            metadata_complete=True,
            has_lyrics=True,
            is_lossless=False,
        )
        for index in range(track_count)
    ]
    return FolderInfo(
        path=path,
        folder_name=path.name,
        parent_folder_name=path.parent.name,
        files=files,
        album_art_hash="art",
        other_files=[{"name": "cover.jpg", "size_bytes": 2048, "hash": "cover-hash"}],
        file_hashes_present=False,
        avg_bitrate=320.0,
        unique_artists={"Artist"},
        unique_albums={"Album"},
        generic_filename_score=0.1,
        generic_title_score=0.1,
        hebrew_metadata_ratio=1.0,
        metadata_completeness_ratio=1.0,
        lossless_ratio=0.0,
        lyrics_ratio=1.0,
    )


def test_comparison_engine_only_compares_matching_music_file_counts():
    engine = ComparisonEngine(enable_hashing=False)
    folder_a = make_folder("C:/music/A", 3)
    folder_b = make_folder("D:/music/B", 3)
    folder_c = make_folder("E:/music/C", 4)

    seen_pairs = []
    progress_events = []

    def fake_compare(folder1, folder2):
        seen_pairs.append((folder1.path, folder2.path))
        return FolderComparisonResult(
            folder1_path=folder1.path,
            folder2_path=folder2.path,
            weighted_score=42.0,
        )

    engine.compare_two_folders = fake_compare  # type: ignore[method-assign]

    results = engine.find_similar_folders(
        {
            folder_a.path: folder_a,
            folder_b.path: folder_b,
            folder_c.path: folder_c,
        },
        progress_callback=lambda current, total: progress_events.append((current, total)),
    )

    assert seen_pairs == [(folder_a.path, folder_b.path)]
    assert len(results) == 1
    assert progress_events == [(1, 1)]


def test_comparison_engine_reuses_prepared_folder_cache(monkeypatch):
    engine = ComparisonEngine(enable_hashing=False)
    folder_a = make_folder("C:/music/A", 3)
    folder_b = make_folder("D:/music/B", 3)

    normalize_calls = []

    def counting_normalize(filename: str) -> str:
        normalize_calls.append(filename)
        return filename.lower()

    monkeypatch.setattr(
        "music_dup_lib.core.comparison_engine.normalize_filename_for_sort",
        counting_normalize,
    )

    first_result = engine.compare_two_folders(folder_a, folder_b)
    second_result = engine.compare_two_folders(folder_a, folder_b)

    assert first_result is not None
    assert second_result is not None
    assert first_result.weighted_score == second_result.weighted_score
    assert first_result.similarity_scores == second_result.similarity_scores
    assert len(normalize_calls) == len(folder_a.files) + len(folder_b.files)
