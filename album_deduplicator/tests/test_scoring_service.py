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
    monkeypatch.setattr(service.ml_model, "predict_similarities_for_pairs", lambda *args, **kwargs: [90.0])
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
    comparison = FolderComparisonResult(folder1_path=folder1.path, folder2_path=folder2.path, weighted_score=86.0)

    service = ScoringService(use_gemini=False)
    service.ml_model.model_loaded = False

    pairs, warnings = service.apply_scores(
        comparison_results=[comparison],
        all_folders={folder1.path: folder1, folder2.path: folder2},
        cached_results_map={},
    )

    pair = next(iter(pairs.values()))
    assert warnings.ml_unavailable is True
    assert pair.base_score == 86.0
    assert pair.final_score == 86.0
    assert pair.ml_score is None
    assert "algorithmic_only" in pair.reason_codes


def test_scoring_service_excludes_exact_review_threshold():
    folder1 = make_folder("C:/music/A")
    folder2 = make_folder("D:/music/B")
    comparison = FolderComparisonResult(folder1_path=folder1.path, folder2_path=folder2.path, weighted_score=60.0)

    service = ScoringService(use_gemini=False)
    service.ml_model.model_loaded = False

    pairs, _ = service.apply_scores(
        comparison_results=[comparison],
        all_folders={folder1.path: folder1, folder2.path: folder2},
        cached_results_map={},
    )

    assert pairs == {}


def test_scoring_service_keeps_exact_safe_threshold_in_review():
    folder1 = make_folder("C:/music/A")
    folder2 = make_folder("D:/music/B")
    comparison = FolderComparisonResult(folder1_path=folder1.path, folder2_path=folder2.path, weighted_score=90.0)

    service = ScoringService(use_gemini=False)
    service.ml_model.model_loaded = False

    pairs, _ = service.apply_scores(
        comparison_results=[comparison],
        all_folders={folder1.path: folder1, folder2.path: folder2},
        cached_results_map={},
    )

    pair = next(iter(pairs.values()))
    assert pair.final_score == 90.0
    assert "review_threshold" in pair.reason_codes
    assert "safe_threshold" not in pair.reason_codes


def test_scoring_service_skips_gemini_outside_review_band(monkeypatch):
    folder1 = make_folder("C:/music/A")
    folder2 = make_folder("D:/music/B")
    comparison = FolderComparisonResult(folder1_path=folder1.path, folder2_path=folder2.path, weighted_score=99.0)

    service = ScoringService(use_gemini=True)
    monkeypatch.setattr(service.ml_model, "model_loaded", True)
    monkeypatch.setattr(service.ml_model, "predict_similarities_for_pairs", lambda *args, **kwargs: [99.0])
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


def test_scoring_service_skips_ml_for_identical_hash_pairs(monkeypatch):
    folder1 = make_folder("C:/music/A")
    folder2 = make_folder("D:/music/B")
    comparison = FolderComparisonResult(
        folder1_path=folder1.path,
        folder2_path=folder2.path,
        weighted_score=100.0,
        is_identical_by_hash=True,
    )

    service = ScoringService(use_gemini=False)
    monkeypatch.setattr(service.ml_model, "model_loaded", True)
    monkeypatch.setattr(
        service.ml_model,
        "predict_similarities_for_pairs",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ML batch should not run")),
    )

    pairs, _ = service.apply_scores(
        comparison_results=[comparison],
        all_folders={folder1.path: folder1, folder2.path: folder2},
        cached_results_map={},
    )

    pair = next(iter(pairs.values()))
    assert pair.ml_score is None
    assert pair.base_score == 100.0
    assert pair.final_score == 100.0
    assert "identical_by_hash" in pair.reason_codes


def test_scoring_service_batches_ml_predictions(monkeypatch):
    folder1 = make_folder("C:/music/A")
    folder2 = make_folder("D:/music/B")
    folder3 = make_folder("E:/music/C")

    first = FolderComparisonResult(folder1_path=folder1.path, folder2_path=folder2.path, weighted_score=80.0)
    second = FolderComparisonResult(folder1_path=folder1.path, folder2_path=folder3.path, weighted_score=87.0)

    service = ScoringService(use_gemini=False)
    monkeypatch.setattr(service.ml_model, "model_loaded", True)

    seen_batch_sizes = []

    def fake_batch_predict(pair_inputs):
        seen_batch_sizes.append(len(pair_inputs))
        return [91.0, 84.0]

    monkeypatch.setattr(service.ml_model, "predict_similarities_for_pairs", fake_batch_predict)
    monkeypatch.setattr(service.ml_model, "prediction_batch_size", 32)

    pairs, _ = service.apply_scores(
        comparison_results=[first, second],
        all_folders={folder1.path: folder1, folder2.path: folder2, folder3.path: folder3},
        cached_results_map={},
    )

    assert seen_batch_sizes == [2]
    pair_values = sorted(pairs.values(), key=lambda item: item.folder2_path)
    assert [pair.ml_score for pair in pair_values] == [91.0, 84.0]


def test_scoring_service_discards_pairs_below_review_threshold_but_keeps_cache_entry(monkeypatch):
    folder1 = make_folder("C:/music/A")
    folder2 = make_folder("D:/music/B")
    comparison = FolderComparisonResult(
        folder1_path=folder1.path,
        folder2_path=folder2.path,
        weighted_score=58.0,
        similarity_scores={"title": 0.7, "album": 0.4, "additional_metadata_details": {"genre": 0.0}},
    )

    service = ScoringService(use_gemini=False)
    monkeypatch.setattr(service.ml_model, "model_loaded", True)
    monkeypatch.setattr(service.ml_model, "predict_similarities_for_pairs", lambda *args, **kwargs: [60.0])

    cached_results = []
    pairs, _ = service.apply_scores(
        comparison_results=[comparison],
        all_folders={folder1.path: folder1, folder2.path: folder2},
        cached_results_map={},
        cache_result_callback=cached_results.append,
    )

    assert pairs == {}
    assert len(cached_results) == 1
    assert cached_results[0].ml_similarity_score == 60.0
    assert cached_results[0].similarity_scores == {}
