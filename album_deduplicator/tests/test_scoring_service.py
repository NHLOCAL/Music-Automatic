from pathlib import Path

from music_dup_lib.models import FileInfo, FolderComparisonResult, FolderInfo
from music_dup_lib.services.scoring_service import ScoringService


def make_folder(path_str: str) -> FolderInfo:
    path = Path(path_str)
    files = [
        FileInfo(
            filename=f"track-{index}.mp3",
            filepath=path / f"track-{index}.mp3",
            extension=".mp3",
            size_mb=5.0,
            duration=180.0,
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
        for index in range(3)
    ]
    return FolderInfo(
        path=path,
        folder_name=path.name,
        parent_folder_name=path.parent.name,
        files=files,
        album_art_hash="art",
        file_hashes_present=True,
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


def test_scoring_service_blends_algorithmic_ml_and_gemini(monkeypatch):
    folder1 = make_folder("C:/music/A")
    folder2 = make_folder("D:/music/B")
    comparison = FolderComparisonResult(
        folder1_path=folder1.path,
        folder2_path=folder2.path,
        weighted_score=80.0,
        similarity_scores={"title": 0.9},
    )

    service = ScoringService(use_gemini=True)
    monkeypatch.setattr(service.ml_model, "model_loaded", True)
    monkeypatch.setattr(service.ml_model, "predict_similarity_for_pair", lambda *args, **kwargs: 90.0)
    monkeypatch.setattr(
        service,
        "_resolve_gemini",
        lambda **kwargs: ("duplicate", 100.0, "ok", None),
    )

    pairs, warnings = service.apply_scores(
        comparison_results=[comparison],
        all_folders={folder1.path: folder1, folder2.path: folder2},
        cached_results_map={},
    )

    pair = next(iter(pairs.values()))
    assert warnings.ml_unavailable is False
    assert pair.base_score == 85.5
    assert round(pair.final_score, 3) == 87.675
    assert pair.gemini_score == 100.0
    assert "ml_blended" in pair.reason_codes
    assert "gemini_reviewed" in pair.reason_codes


def test_scoring_service_falls_back_to_algorithmic_when_ml_missing():
    folder1 = make_folder("C:/music/A")
    folder2 = make_folder("D:/music/B")
    comparison = FolderComparisonResult(folder1_path=folder1.path, folder2_path=folder2.path, weighted_score=82.0)

    service = ScoringService(use_gemini=False)
    service.ml_model.model_loaded = False

    pairs, warnings = service.apply_scores(
        comparison_results=[comparison],
        all_folders={folder1.path: folder1, folder2.path: folder2},
        cached_results_map={},
    )

    pair = next(iter(pairs.values()))
    assert warnings.ml_unavailable is True
    assert pair.base_score == 82.0
    assert pair.final_score == 82.0
    assert pair.ml_score is None
    assert "algorithmic_only" in pair.reason_codes


def test_scoring_service_skips_gemini_outside_review_band(monkeypatch):
    folder1 = make_folder("C:/music/A")
    folder2 = make_folder("D:/music/B")
    comparison = FolderComparisonResult(folder1_path=folder1.path, folder2_path=folder2.path, weighted_score=99.0)

    service = ScoringService(use_gemini=True)
    monkeypatch.setattr(service.ml_model, "model_loaded", True)
    monkeypatch.setattr(service.ml_model, "predict_similarity_for_pair", lambda *args, **kwargs: 99.0)
    monkeypatch.setattr(
        service,
        "_resolve_gemini",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("Gemini should not run")),
    )

    pairs, _ = service.apply_scores(
        comparison_results=[comparison],
        all_folders={folder1.path: folder1, folder2.path: folder2},
        cached_results_map={},
    )

    pair = next(iter(pairs.values()))
    assert pair.gemini_score is None
    assert pair.final_score == 99.0

