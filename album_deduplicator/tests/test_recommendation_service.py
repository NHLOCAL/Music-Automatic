from pathlib import Path

from music_dup_lib.models import FolderInfo
from music_dup_lib.services.dto import PairAnalysis, stable_id
from music_dup_lib.services.recommendation_service import RecommendationService


def make_folder(path_str: str, quality: float) -> FolderInfo:
    path = Path(path_str)
    return FolderInfo(
        path=path,
        folder_name=path.name,
        parent_folder_name=path.parent.name,
        quality_score=quality,
        avg_bitrate=320.0,
        unique_artists={"Artist"},
        unique_albums={"Album"},
        lossless_ratio=0.0,
        lyrics_ratio=0.0,
    )


def make_pair(folder1_path: Path, folder2_path: Path, score: float) -> PairAnalysis:
    folder1_id = stable_id("folder", str(folder1_path))
    folder2_id = stable_id("folder", str(folder2_path))
    pair_id = stable_id("pair", "|".join(sorted([folder1_id, folder2_id])))
    return PairAnalysis(
        pair_id=pair_id,
        folder1_id=folder1_id,
        folder2_id=folder2_id,
        folder1_path=folder1_path,
        folder2_path=folder2_path,
        algorithmic_score=score,
        ml_score=score,
        base_score=score,
        gemini_score=None,
        final_score=score,
        gemini_verdict=None,
        gemini_reason=None,
        gemini_error=None,
        is_identical_by_hash=score >= 100,
    )


def test_recommendation_prefers_preferred_root_and_marks_safe():
    keeper = make_folder("C:/preferred/Album", 91.0)
    duplicate = make_folder("D:/archive/Album", 97.0)
    folders = {keeper.path: keeper, duplicate.path: duplicate}

    service = RecommendationService(preferred_root=Path("C:/preferred"))
    albums = service.build_album_summaries(folders)
    pair = make_pair(keeper.path, duplicate.path, 99.0)

    clusters = service.build_clusters(folders, {pair.pair_id: pair}, albums)
    cluster = next(iter(clusters.values()))

    assert cluster.recommended_keeper_id == stable_id("folder", str(keeper.path))
    assert cluster.confidence_bucket == "safe"
    assert "preferred_root_keeper" in cluster.reason_codes


def test_recommendation_marks_review_when_keeper_is_not_unique():
    folder1 = make_folder("C:/music/A", 90.0)
    folder2 = make_folder("D:/music/B", 90.0)
    folders = {folder1.path: folder1, folder2.path: folder2}

    service = RecommendationService()
    albums = service.build_album_summaries(folders)
    pair = make_pair(folder1.path, folder2.path, 99.0)

    clusters = service.build_clusters(folders, {pair.pair_id: pair}, albums)
    cluster = next(iter(clusters.values()))

    assert cluster.recommended_keeper_id is None
    assert cluster.confidence_bucket == "review"
    assert "keeper_conflict" in cluster.reason_codes


def test_recommendation_marks_review_for_borderline_scores():
    folder1 = make_folder("C:/music/A", 90.0)
    folder2 = make_folder("D:/music/B", 88.0)
    folders = {folder1.path: folder1, folder2.path: folder2}

    service = RecommendationService()
    albums = service.build_album_summaries(folders)
    pair = make_pair(folder1.path, folder2.path, 90.0)

    clusters = service.build_clusters(folders, {pair.pair_id: pair}, albums)
    cluster = next(iter(clusters.values()))

    assert cluster.recommended_keeper_id == stable_id("folder", str(folder1.path))
    assert cluster.confidence_bucket == "review"
    assert "cluster_review" in cluster.reason_codes

