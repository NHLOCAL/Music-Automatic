from copy import deepcopy
from music_dup_lib import config
from music_dup_lib.models import FileInfo, FolderInfo
from music_dup_lib.services.dto import AlbumCluster, AlbumSummary, AnalysisSnapshot, PairAnalysis
from music_dup_lib.services.user_decision_store import UserDecisionStore


def make_snapshot(tmp_path):
    folders = {}
    albums = {}
    for folder_id in ("keep", "drop"):
        path = tmp_path / folder_id
        path.mkdir()
        track = path / "track.mp3"
        track.write_bytes(b"original music")
        folders[path] = FolderInfo(
            path=path, folder_name=folder_id, parent_folder_name=tmp_path.name,
            files=[FileInfo(filename=track.name, filepath=track, extension=".mp3", size_mb=1.0,
                            file_hash="original", title="Original", artist="Artist", album="Album")],
        )
        albums[folder_id] = AlbumSummary(
            folder_id=folder_id, path=path, name=folder_id, quality_score=90.0,
            avg_bitrate=128.0, file_count=1, in_preferred_root=False,
            has_album_art=False, lossless_ratio=0.0, lyrics_ratio=0.0, total_size_mb=1.0,
        )
    pair = PairAnalysis(
        pair_id="pair", folder1_id="keep", folder2_id="drop",
        folder1_path=albums["keep"].path, folder2_path=albums["drop"].path,
        algorithmic_score=95.0, ml_score=95.0, base_score=95.0, gemini_score=None,
        final_score=95.0, gemini_verdict=None, gemini_reason=None, gemini_error=None,
        is_identical_by_hash=False,
    )
    cluster = AlbumCluster(
        cluster_id="cluster", folder_ids=["keep", "drop"], pair_ids=["pair"],
        recommended_keeper_id="keep", confidence_bucket="safe", reason_codes=[],
        reasons=[], deletable_folder_ids=["drop"], human_summary="Same album",
    )
    return AnalysisSnapshot(folders=folders, albums=albums, pairs={"pair": pair}, clusters={"cluster": cluster})


def save_decision(tmp_path, snapshot):
    store = UserDecisionStore(tmp_path / "decisions.json")
    store.save_decision(snapshot=snapshot, cluster_id="cluster", keeper_id="keep",
                        delete_folder_ids={"drop"}, resolution_state="user_selected")
    return store


def test_unchanged_album_evidence_restores_selection(tmp_path):
    snapshot = make_snapshot(tmp_path)
    store = save_decision(tmp_path, snapshot)
    restored = store.decisions_for_snapshot(deepcopy(snapshot))
    assert restored["cluster"].delete_folder_ids == {"drop"}


def test_warm_cache_without_diagnostic_details_restores_selection(tmp_path):
    snapshot = make_snapshot(tmp_path)
    snapshot.pairs["pair"].similarity_scores = {"title": 0.95, "duration": 1.0}
    snapshot.pairs["pair"].reason_codes = ["ml_blended", "safe_threshold"]
    store = save_decision(tmp_path, snapshot)
    warm_snapshot = deepcopy(snapshot)
    warm_snapshot.pairs["pair"].similarity_scores = {}
    assert store.decisions_for_snapshot(warm_snapshot)["cluster"].delete_folder_ids == {"drop"}


def test_changed_diagnostic_reason_does_not_invalidate_selection(tmp_path):
    snapshot = make_snapshot(tmp_path)
    snapshot.pairs["pair"].reason_codes = ["ml_blended", "safe_threshold"]
    store = save_decision(tmp_path, snapshot)
    snapshot.pairs["pair"].reason_codes = ["safe_threshold"]
    snapshot.pairs["pair"].gemini_reason = "An equivalent diagnostic explanation"
    assert store.decisions_for_snapshot(snapshot)["cluster"].delete_folder_ids == {"drop"}


def test_changed_music_hash_at_same_paths_requires_review(tmp_path):
    snapshot = make_snapshot(tmp_path)
    store = save_decision(tmp_path, snapshot)
    snapshot.folders[snapshot.albums["drop"].path].files[0].file_hash = "new music"
    assert store.decisions_for_snapshot(snapshot) == {}


def test_changed_metadata_at_same_paths_requires_review(tmp_path):
    snapshot = make_snapshot(tmp_path)
    store = save_decision(tmp_path, snapshot)
    snapshot.folders[snapshot.albums["drop"].path].files[0].title = "Different song"
    assert store.decisions_for_snapshot(snapshot) == {}


def test_changed_file_with_unchanged_snapshot_requires_review(tmp_path):
    snapshot = make_snapshot(tmp_path)
    store = save_decision(tmp_path, snapshot)
    (snapshot.albums["drop"].path / "track.mp3").write_bytes(b"replaced music content")
    assert store.decisions_for_snapshot(snapshot) == {}


def test_changed_similarity_evidence_requires_review(tmp_path):
    snapshot = make_snapshot(tmp_path)
    store = save_decision(tmp_path, snapshot)
    snapshot.pairs["pair"].final_score = 55.0
    snapshot.clusters["cluster"].confidence_bucket = "review"
    assert store.decisions_for_snapshot(snapshot) == {}


def test_changed_scoring_policy_requires_review(tmp_path, monkeypatch):
    snapshot = make_snapshot(tmp_path)
    store = save_decision(tmp_path, snapshot)
    monkeypatch.setattr(config, "SAFE_DELETE_MIN_SIMILARITY", 98.0)
    assert store.decisions_for_snapshot(snapshot) == {}


def test_legacy_decision_without_evidence_requires_review(tmp_path):
    import json

    snapshot = make_snapshot(tmp_path)
    store = UserDecisionStore(tmp_path / "decisions.json")
    store.decision_file.write_text(json.dumps({"decisions": {"cluster": {
        "folder_ids": ["keep", "drop"], "keeper_id": "keep", "delete_folder_ids": ["drop"],
    }}}), encoding="utf-8")
    assert store.decisions_for_snapshot(snapshot) == {}
