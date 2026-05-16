from pathlib import Path

from music_dup_lib import config
from music_dup_lib.models import FileInfo, FolderInfo
from music_dup_lib.services.dto import PairAnalysis, stable_id
from music_dup_lib.services.recommendation_service import RecommendationService


def make_folder(
    path_str: str,
    quality: float,
    bitrate: float = 320.0,
    has_art: bool = False,
) -> FolderInfo:
    path = Path(path_str)
    return FolderInfo(
        path=path,
        folder_name=path.name,
        parent_folder_name=path.parent.name,
        files=[
            FileInfo(
                filename="track.mp3",
                filepath=path / "track.mp3",
                extension=".mp3",
                size_mb=5.0,
                duration=180.0,
                bitrate=int(bitrate),
            )
        ],
        quality_score=quality,
        avg_bitrate=bitrate,
        unique_artists={"Artist"},
        unique_albums={"Album"},
        album_art_hash="art" if has_art else None,
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
    assert cluster.human_summary
    assert cluster.resolution_state == "auto"


def test_recommendation_prefers_equivalent_preferred_root_when_quality_ties():
    keeper = make_folder("C:/library/../library/preferred/Album", 91.0)
    duplicate = make_folder("D:/archive/Album", 91.0)
    folders = {keeper.path: keeper, duplicate.path: duplicate}

    service = RecommendationService(preferred_root=Path("C:/library/preferred"))
    albums = service.build_album_summaries(folders)
    pair = make_pair(keeper.path, duplicate.path, 100.0)

    clusters = service.build_clusters(folders, {pair.pair_id: pair}, albums)
    cluster = next(iter(clusters.values()))

    assert cluster.recommended_keeper_id == stable_id("folder", str(keeper.path))
    assert cluster.confidence_bucket == "safe"
    assert "preferred_root_keeper" in cluster.reason_codes
    assert "keeper_conflict" not in cluster.reason_codes


def test_recommendation_uses_preferred_root_order_between_multiple_roots():
    higher_priority = make_folder("D:/archive/Album", 88.0)
    lower_priority = make_folder("E:/backup/Album", 96.0)
    unrelated = make_folder("F:/old/Album", 99.0)
    folders = {
        higher_priority.path: higher_priority,
        lower_priority.path: lower_priority,
        unrelated.path: unrelated,
    }

    service = RecommendationService(
        preferred_roots=[
            Path("C:/primary"),
            Path("D:/archive"),
            Path("E:/backup"),
        ]
    )
    albums = service.build_album_summaries(folders)
    pair_ab = make_pair(higher_priority.path, lower_priority.path, 100.0)
    pair_ac = make_pair(higher_priority.path, unrelated.path, 100.0)
    pair_bc = make_pair(lower_priority.path, unrelated.path, 100.0)

    clusters = service.build_clusters(
        folders,
        {
            pair_ab.pair_id: pair_ab,
            pair_ac.pair_id: pair_ac,
            pair_bc.pair_id: pair_bc,
        },
        albums,
    )
    cluster = next(iter(clusters.values()))

    assert cluster.recommended_keeper_id == stable_id("folder", str(higher_priority.path))
    assert cluster.confidence_bucket == "safe"
    assert "preferred_root_keeper" in cluster.reason_codes
    assert "keeper_conflict" not in cluster.reason_codes


def test_recommendation_can_disable_preferred_root_order():
    lower_quality_preferred = make_folder("D:/archive/Album", 88.0)
    higher_quality_backup = make_folder("E:/backup/Album", 96.0)
    folders = {
        lower_quality_preferred.path: lower_quality_preferred,
        higher_quality_backup.path: higher_quality_backup,
    }

    service = RecommendationService(
        preferred_roots=[Path("D:/archive"), Path("E:/backup")],
        use_preferred_roots=False,
    )
    albums = service.build_album_summaries(folders)
    pair = make_pair(lower_quality_preferred.path, higher_quality_backup.path, 100.0)

    clusters = service.build_clusters(folders, {pair.pair_id: pair}, albums)
    cluster = next(iter(clusters.values()))

    assert cluster.recommended_keeper_id == stable_id("folder", str(higher_quality_backup.path))
    assert "quality_keeper" in cluster.reason_codes
    assert "preferred_root_keeper" not in cluster.reason_codes


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
    assert "נדרשת בדיקה ידנית" in cluster.human_summary


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


def test_recommendation_marks_ui_safe_tab_for_scores_above_90():
    folder1 = make_folder("C:/music/A", 90.0)
    folder2 = make_folder("D:/music/B", 88.0)
    folders = {folder1.path: folder1, folder2.path: folder2}

    service = RecommendationService()
    albums = service.build_album_summaries(folders)
    pair = make_pair(folder1.path, folder2.path, config.SAFE_DELETE_MIN_SIMILARITY + 0.01)

    clusters = service.build_clusters(folders, {pair.pair_id: pair}, albums)
    cluster = next(iter(clusters.values()))

    assert cluster.recommended_keeper_id == stable_id("folder", str(folder1.path))
    assert cluster.confidence_bucket == "safe"
    assert "cluster_safe" in cluster.reason_codes


def test_recommendation_excludes_exact_review_threshold_from_clusters():
    folder1 = make_folder("C:/music/A", 90.0)
    folder2 = make_folder("D:/music/B", 88.0)
    folders = {folder1.path: folder1, folder2.path: folder2}

    service = RecommendationService()
    albums = service.build_album_summaries(folders)
    pair = make_pair(folder1.path, folder2.path, 60.0)

    clusters = service.build_clusters(folders, {pair.pair_id: pair}, albums)

    assert clusters == {}


def test_recommendation_builds_human_highlights_for_quality_and_art():
    keeper = make_folder("C:/music/Best", 95.0, bitrate=320.0, has_art=True)
    duplicate = make_folder("D:/music/Worse", 82.0, bitrate=192.0, has_art=False)
    folders = {keeper.path: keeper, duplicate.path: duplicate}

    service = RecommendationService(preferred_root=Path("C:/music"))
    albums = service.build_album_summaries(folders)
    pair = make_pair(keeper.path, duplicate.path, 98.0)

    clusters = service.build_clusters(folders, {pair.pair_id: pair}, albums)
    cluster = next(iter(clusters.values()))

    labels = {highlight.label for highlight in cluster.comparison_highlights}
    assert "איכות גבוהה יותר" in labels
    assert "ביטרייט גבוה יותר" in labels
    assert "כולל עטיפת אלבום" in labels
    assert cluster.recommended_keeper_reason is not None


def test_recommendation_requires_full_pairwise_validation_for_safe_clusters():
    folder_a = make_folder("C:/music/A", 80.0)
    folder_b = make_folder("C:/music/B", 96.0)
    folder_c = make_folder("D:/music/C", 85.0)
    folders = {
        folder_a.path: folder_a,
        folder_b.path: folder_b,
        folder_c.path: folder_c,
    }

    service = RecommendationService()
    albums = service.build_album_summaries(folders)
    pair_ab = make_pair(folder_a.path, folder_b.path, 98.0)
    pair_bc = make_pair(folder_b.path, folder_c.path, 97.0)

    clusters = service.build_clusters(
        folders,
        {pair_ab.pair_id: pair_ab, pair_bc.pair_id: pair_bc},
        albums,
    )
    cluster = next(iter(clusters.values()))

    assert cluster.recommended_keeper_id == stable_id("folder", str(folder_b.path))
    assert cluster.confidence_bucket == "review"
    assert "pairwise_validation_incomplete" in cluster.reason_codes
    assert "לא כל הזוגות בתוך הקבוצה אומתו ישירות" in cluster.human_summary
    assert "חסר עוד זוג אחד" in cluster.technical_summary
