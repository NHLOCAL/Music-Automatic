import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app, store
from api.session_store import SessionEventBuffer, SessionStore
from music_dup_lib import config
from music_dup_lib.models import FileInfo, FolderInfo
from music_dup_lib.services import AnalysisOptions, DeletionService
from music_dup_lib.services.user_decision_store import UserDecisionStore
from music_dup_lib.services.dto import (
    AlbumCluster,
    AlbumSummary,
    AnalysisCounts,
    AnalysisSnapshot,
    PairAnalysis,
    RecommendationReason,
    stable_id,
)


def make_folder(path_str: str, quality: float) -> FolderInfo:
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
                bitrate=320,
                title="Track",
                artist="Artist",
                album="Album",
                albumartist="Artist",
                all_tags={"title": "Track"},
                metadata_complete=True,
            )
        ],
        quality_score=quality,
        avg_bitrate=320.0,
        unique_artists={"Artist"},
        unique_albums={"Album"},
        album_art_hash="art",
        lossless_ratio=0.0,
        lyrics_ratio=0.0,
    )


def build_snapshot():
    folder1 = make_folder("C:/music/keep", 95.0)
    folder2 = make_folder("D:/music/drop", 80.0)
    folder1_id = stable_id("folder", str(folder1.path))
    folder2_id = stable_id("folder", str(folder2.path))
    pair_id = stable_id("pair", "|".join(sorted([folder1_id, folder2_id])))
    cluster_id = stable_id("cluster", "|".join(sorted([folder1_id, folder2_id])))

    pair = PairAnalysis(
        pair_id=pair_id,
        folder1_id=folder1_id,
        folder2_id=folder2_id,
        folder1_path=folder1.path,
        folder2_path=folder2.path,
        algorithmic_score=98.0,
        ml_score=99.0,
        base_score=98.55,
        gemini_score=None,
        final_score=98.55,
        gemini_verdict=None,
        gemini_reason=None,
        gemini_error=None,
        is_identical_by_hash=False,
        reason_codes=["ml_blended", "safe_threshold"],
    )
    albums = {
        folder1_id: AlbumSummary(
            folder_id=folder1_id,
            path=folder1.path,
            name=folder1.path.name,
            quality_score=folder1.quality_score,
            avg_bitrate=folder1.avg_bitrate,
            file_count=len(folder1.files),
            in_preferred_root=True,
            has_album_art=True,
            lossless_ratio=0.0,
            lyrics_ratio=0.0,
            total_size_mb=5.0,
        ),
        folder2_id: AlbumSummary(
            folder_id=folder2_id,
            path=folder2.path,
            name=folder2.path.name,
            quality_score=folder2.quality_score,
            avg_bitrate=folder2.avg_bitrate,
            file_count=len(folder2.files),
            in_preferred_root=False,
            has_album_art=True,
            lossless_ratio=0.0,
            lyrics_ratio=0.0,
            total_size_mb=5.0,
        ),
    }
    clusters = {
        cluster_id: AlbumCluster(
            cluster_id=cluster_id,
            folder_ids=[folder1_id, folder2_id],
            pair_ids=[pair_id],
            recommended_keeper_id=folder1_id,
            confidence_bucket="safe",
            reason_codes=["preferred_root_keeper", "cluster_safe"],
            reasons=[RecommendationReason(code="preferred_root_keeper", message="root preferred")],
            deletable_folder_ids=[folder2_id],
            human_summary="נמצאו עותקים כמעט זהים. מומלץ לשמור את keep.",
            resolution_state="auto",
            recommended_keeper_reason="root preferred",
            technical_summary="1 זוג הושווה.",
        )
    }
    return AnalysisSnapshot(
        folders={folder1.path: folder1, folder2.path: folder2},
        albums=albums,
        pairs={pair_id: pair},
        clusters=clusters,
        counts=AnalysisCounts(folders=2, compared_pairs=1, safe_clusters=1, review_clusters=0),
    )


def build_media_snapshot(tmp_path: Path):
    album_path = tmp_path / "album"
    album_path.mkdir()
    track_path = album_path / "track.mp3"
    cover_path = album_path / "cover.jpg"
    track_path.write_bytes(b"stub-audio")
    cover_path.write_bytes(b"stub-cover")

    folder_info = FolderInfo(
        path=album_path,
        folder_name=album_path.name,
        parent_folder_name=album_path.parent.name,
        files=[
            FileInfo(
                filename=track_path.name,
                filepath=track_path,
                extension=".mp3",
                size_mb=5.0,
                duration=180.0,
                bitrate=320,
                title="Track",
                artist="Artist",
                album="Album",
                albumartist="Artist",
                all_tags={"title": "Track"},
                metadata_complete=True,
            )
        ],
        quality_score=96.0,
        avg_bitrate=320.0,
        unique_artists={"Artist"},
        unique_albums={"Album"},
        album_art_hash="art",
        lossless_ratio=0.0,
        lyrics_ratio=0.0,
    )
    folder_id = stable_id("folder", str(album_path))
    snapshot = AnalysisSnapshot(
        folders={album_path: folder_info},
        albums={
            folder_id: AlbumSummary(
                folder_id=folder_id,
                path=album_path,
                name=album_path.name,
                quality_score=96.0,
                avg_bitrate=320.0,
                file_count=1,
                in_preferred_root=True,
                has_album_art=True,
                lossless_ratio=0.0,
                lyrics_ratio=0.0,
                total_size_mb=5.0,
            )
        },
        counts=AnalysisCounts(folders=1, compared_pairs=0, safe_clusters=0, review_clusters=0),
    )
    return snapshot, folder_id, track_path, cover_path


def test_api_session_flow(monkeypatch, tmp_path):
    def fake_start_analysis(session_id: str):
        session = store.get_session(session_id)
        session.snapshot = build_snapshot()
        cluster = next(iter(session.snapshot.clusters.values()))
        session.decisions = {cluster.cluster_id: cluster.recommended_keeper_id}
        session.delete_selections = {cluster.cluster_id: set(cluster.deletable_folder_ids)}
        session.preview = DeletionService().build_preview(
            session.snapshot.clusters,
            session.snapshot.albums,
            session.decisions,
            resolution_states={next(iter(session.snapshot.clusters.values())).cluster_id: "auto"},
            delete_selections=session.delete_selections,
        )
        session.resolution_states = {next(iter(session.snapshot.clusters.values())).cluster_id: "auto"}
        session.status = "completed"
        session.progress = {
            "step": "completed",
            "stage": "complete",
            "message": "הניתוח הושלם",
            "human_message": "הניתוח הסתיים. אפשר להתחיל לעבור על הקבוצות.",
            "current": 1,
            "total": 1,
            "percent": 100.0,
            "warnings": [],
        }

    monkeypatch.setattr(store, "start_analysis", fake_start_analysis)
    music_root = tmp_path / "music"
    archive_root = tmp_path / "archive"
    music_root.mkdir()
    archive_root.mkdir()

    client = TestClient(app)
    response = client.post(
        "/api/analysis-sessions",
        json={
            "folders": [str(music_root), str(archive_root)],
            "preferred_root": str(music_root),
            "force_rescan": False,
            "clear_cache": False,
            "bitrate_mode": "128",
            "gemini_enabled": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_api_session_flow_accepts_full_hash_scan(monkeypatch, tmp_path):
    seen = {}

    def fake_start_analysis(session_id: str):
        session = store.get_session(session_id)
        seen["full_hash_scan"] = session.options.full_hash_scan
        seen["disable_hash"] = session.options.disable_hash
        session.status = "completed"

    monkeypatch.setattr(store, "start_analysis", fake_start_analysis)
    music_root = tmp_path / "music"
    archive_root = tmp_path / "archive"
    music_root.mkdir()
    archive_root.mkdir()

    client = TestClient(app)
    response = client.post(
        "/api/analysis-sessions",
        json={
            "folders": [str(music_root), str(archive_root)],
            "preferred_root": str(music_root),
            "force_rescan": False,
            "clear_cache": False,
            "full_hash_scan": True,
            "bitrate_mode": "128",
            "gemini_enabled": False,
        },
    )

    assert response.status_code == 200
    assert seen == {"full_hash_scan": True, "disable_hash": False}


def test_api_session_flow_saves_and_uses_gemini_api_key(monkeypatch, tmp_path):
    seen = {}

    def fake_start_analysis(session_id: str):
        session = store.get_session(session_id)
        seen["gemini_enabled"] = session.options.gemini_enabled
        seen["gemini_api_key"] = session.options.gemini_api_key
        session.status = "completed"

    monkeypatch.setattr(store, "start_analysis", fake_start_analysis)
    monkeypatch.setattr(store.gemini_settings_store, "settings_file", tmp_path / "gemini_settings.json")
    music_root = tmp_path / "music"
    music_root.mkdir()

    client = TestClient(app)
    response = client.post(
        "/api/analysis-sessions",
        json={
            "folders": [str(music_root)],
            "force_rescan": False,
            "clear_cache": False,
            "bitrate_mode": "128",
            "gemini_enabled": True,
            "gemini_api_key": "gemini-secret",
        },
    )

    assert response.status_code == 200
    assert seen == {"gemini_enabled": True, "gemini_api_key": "gemini-secret"}
    settings_response = client.get("/api/settings/gemini")
    assert settings_response.status_code == 200
    assert settings_response.json() == {"has_api_key": True}


def test_api_session_flow_reuses_saved_gemini_api_key(monkeypatch, tmp_path):
    seen = {}

    def fake_start_analysis(session_id: str):
        session = store.get_session(session_id)
        seen["gemini_api_key"] = session.options.gemini_api_key
        session.status = "completed"

    monkeypatch.setattr(store, "start_analysis", fake_start_analysis)
    monkeypatch.setattr(store.gemini_settings_store, "settings_file", tmp_path / "gemini_settings.json")
    store.gemini_settings_store.save_api_key("saved-secret")
    music_root = tmp_path / "music"
    music_root.mkdir()

    client = TestClient(app)
    response = client.post(
        "/api/analysis-sessions",
        json={
            "folders": [str(music_root)],
            "force_rescan": False,
            "clear_cache": False,
            "bitrate_mode": "128",
            "gemini_enabled": True,
        },
    )

    assert response.status_code == 200
    assert seen == {"gemini_api_key": "saved-secret"}


def test_api_session_flow_accepts_preferred_root_order(monkeypatch, tmp_path):
    seen = {}

    def fake_start_analysis(session_id: str):
        session = store.get_session(session_id)
        seen["preferred_roots"] = session.options.preferred_roots
        seen["preferred_root"] = session.options.preferred_root
        session.status = "completed"

    monkeypatch.setattr(store, "start_analysis", fake_start_analysis)
    root_1 = tmp_path / "root-1"
    root_2 = tmp_path / "root-2"
    root_3 = tmp_path / "root-3"
    root_1.mkdir()
    root_2.mkdir()
    root_3.mkdir()

    client = TestClient(app)
    response = client.post(
        "/api/analysis-sessions",
        json={
            "folders": [str(root_1), str(root_2), str(root_3)],
            "preferred_roots": [str(root_2), str(root_3), str(root_1)],
            "force_rescan": False,
            "clear_cache": False,
            "bitrate_mode": "128",
            "gemini_enabled": False,
        },
    )

    assert response.status_code == 200
    assert seen["preferred_roots"] == [root_2.resolve(), root_3.resolve(), root_1.resolve()]
    assert seen["preferred_root"] == root_2.resolve()


def test_api_session_flow_can_disable_preferred_root_order(monkeypatch, tmp_path):
    seen = {}

    def fake_start_analysis(session_id: str):
        session = store.get_session(session_id)
        seen["use_preferred_roots"] = session.options.use_preferred_roots
        seen["preferred_roots"] = session.options.preferred_roots
        session.status = "completed"

    monkeypatch.setattr(store, "start_analysis", fake_start_analysis)
    root_1 = tmp_path / "root-1"
    root_2 = tmp_path / "root-2"
    root_1.mkdir()
    root_2.mkdir()

    client = TestClient(app)
    response = client.post(
        "/api/analysis-sessions",
        json={
            "folders": [str(root_1), str(root_2)],
            "preferred_roots": [str(root_2), str(root_1)],
            "use_preferred_roots": False,
            "force_rescan": False,
            "clear_cache": False,
            "bitrate_mode": "128",
            "gemini_enabled": False,
        },
    )

    assert response.status_code == 200
    assert seen["use_preferred_roots"] is False
    assert seen["preferred_roots"] == [root_2.resolve(), root_1.resolve()]


def test_api_cluster_decisions_and_delete_execution(monkeypatch):
    session = store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    session.snapshot = build_snapshot()
    cluster = next(iter(session.snapshot.clusters.values()))
    session.decisions = {cluster.cluster_id: cluster.recommended_keeper_id}
    session.resolution_states = {cluster.cluster_id: "auto"}
    session.delete_selections = {cluster.cluster_id: set(cluster.deletable_folder_ids)}
    session.preview = DeletionService().build_preview(
        session.snapshot.clusters,
        session.snapshot.albums,
        session.decisions,
        resolution_states=session.resolution_states,
        delete_selections=session.delete_selections,
    )
    session.status = "completed"

    monkeypatch.setattr(
        store,
        "execute_delete",
        lambda session_id, folder_ids: type(
            "Execution",
            (),
                {
                    "moved_count": len(folder_ids),
                    "failed_count": 0,
                    "total_size_mb": 5.0,
                    "results": [
                        type(
                            "Result",
                            (),
                            {
                                "folder_id": folder_ids[0],
                                "folder_path": Path("D:/music/drop"),
                                "success": True,
                                "message": "ok",
                                "size_mb": 5.0,
                            },
                        )()
                    ],
                },
        )(),
    )

    client = TestClient(app)
    status_response = client.get(f"/api/analysis-sessions/{session.session_id}")
    assert status_response.status_code == 200
    assert status_response.json()["counts"]["safe_clusters"] == 1
    assert status_response.json()["progress"]["stage"] == "queued"

    clusters_response = client.get(f"/api/analysis-sessions/{session.session_id}/clusters?bucket=safe")
    assert clusters_response.status_code == 200
    assert len(clusters_response.json()["clusters"]) == 1
    assert clusters_response.json()["clusters"][0]["human_summary"]
    assert clusters_response.json()["clusters"][0]["selected_keeper_id"] == cluster.recommended_keeper_id
    assert clusters_response.json()["clusters"][0]["selected_delete_folder_ids"] == [cluster.deletable_folder_ids[0]]
    assert clusters_response.json()["clusters"][0]["albums"][0]["album_art_preview_url"].endswith("/cover")
    assert clusters_response.json()["clusters"][0]["albums"][0]["tracks"][0]["stream_url"].endswith("/stream")
    assert clusters_response.json()["clusters"][0]["albums"][0]["tracks"][0]["filepath"].endswith("track.mp3")

    preview_response = client.get(f"/api/analysis-sessions/{session.session_id}/delete-preview")
    assert preview_response.status_code == 200
    assert preview_response.json()["total_count"] == 1
    assert preview_response.json()["total_size_mb"] == 5.0

    decisions_response = client.post(
        f"/api/analysis-sessions/{session.session_id}/decisions",
        json={"decisions": [{"cluster_id": cluster.cluster_id, "keeper_id": None}]},
    )
    assert decisions_response.status_code == 200
    assert decisions_response.json()["total_count"] == 0

    session.preview = DeletionService().build_preview(
        session.snapshot.clusters,
        session.snapshot.albums,
        {cluster.cluster_id: cluster.recommended_keeper_id},
        resolution_states={cluster.cluster_id: "auto"},
        delete_selections={cluster.cluster_id: set(cluster.deletable_folder_ids)},
    )
    delete_response = client.post(
        f"/api/analysis-sessions/{session.session_id}/delete-executions",
        json={"folder_ids": [cluster.deletable_folder_ids[0]]},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["moved_count"] == 1


def test_api_delete_single_updates_preview(monkeypatch):
    session = store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    session.snapshot = build_snapshot()
    cluster = next(iter(session.snapshot.clusters.values()))
    session.decisions = {cluster.cluster_id: cluster.recommended_keeper_id}
    session.resolution_states = {cluster.cluster_id: "user_selected"}
    session.delete_selections = {cluster.cluster_id: set(cluster.deletable_folder_ids)}
    session.preview = DeletionService().build_preview(
        session.snapshot.clusters,
        session.snapshot.albums,
        session.decisions,
        resolution_states=session.resolution_states,
        delete_selections=session.delete_selections,
    )
    session.status = "completed"

    monkeypatch.setattr(
        "music_dup_lib.services.deletion_service.send2trash",
        lambda path: None,
    )
    monkeypatch.setattr(Path, "exists", lambda self: True)

    client = TestClient(app)
    response = client.post(
        f"/api/analysis-sessions/{session.session_id}/delete-single",
        json={"cluster_id": cluster.cluster_id, "folder_id": cluster.deletable_folder_ids[0]},
    )

    assert response.status_code == 200
    assert response.json()["moved_count"] == 1
    preview_response = client.get(f"/api/analysis-sessions/{session.session_id}/delete-preview")
    assert preview_response.json()["total_count"] == 0


def test_successful_bulk_delete_writes_ml_feedback_event(monkeypatch, tmp_path):
    feedback_file = tmp_path / "feedback" / "user_feedback_events.jsonl"
    store.feedback_logger.feedback_file = feedback_file
    session = store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    session.snapshot = build_snapshot()
    cluster = next(iter(session.snapshot.clusters.values()))
    drop_id = cluster.deletable_folder_ids[0]
    session.decisions = {cluster.cluster_id: cluster.recommended_keeper_id}
    session.resolution_states = {cluster.cluster_id: "auto"}
    session.delete_selections = {cluster.cluster_id: {drop_id}}
    session.preview = DeletionService().build_preview(
        session.snapshot.clusters,
        session.snapshot.albums,
        session.decisions,
        resolution_states=session.resolution_states,
        delete_selections=session.delete_selections,
    )
    session.status = "completed"

    monkeypatch.setattr(
        "music_dup_lib.services.deletion_service.send2trash",
        lambda path: None,
    )
    monkeypatch.setattr(Path, "exists", lambda self: True)

    client = TestClient(app)
    response = client.post(
        f"/api/analysis-sessions/{session.session_id}/delete-executions",
        json={"folder_ids": [drop_id]},
    )

    assert response.status_code == 200
    events = [json.loads(line) for line in feedback_file.read_text(encoding="utf-8").splitlines()]
    assert len(events) == 1
    event = events[0]
    assert event["schema_version"] == "1.0"
    assert event["event_type"] == "delete_executed"
    assert event["label"] == "same_album_confirmed"
    assert event["evidence_strength"] == "strong"
    assert event["session_id"] == session.session_id
    assert event["cluster"]["cluster_id"] == cluster.cluster_id
    assert event["keeper"]["folder_id"] == cluster.recommended_keeper_id
    assert event["target"]["folder_id"] == drop_id
    assert event["pairs"][0]["final_score"] == 98.55
    assert event["model_policy"]["base_score_ml_weight"] == config.BASE_SCORE_ML_WEIGHT


def test_keep_all_decision_does_not_write_ml_feedback_event(tmp_path):
    feedback_file = tmp_path / "feedback" / "user_feedback_events.jsonl"
    store.feedback_logger.feedback_file = feedback_file
    session = store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    session.snapshot = build_snapshot()
    cluster = next(iter(session.snapshot.clusters.values()))
    session.decisions = {cluster.cluster_id: cluster.recommended_keeper_id}
    session.resolution_states = {cluster.cluster_id: "auto"}
    session.delete_selections = {cluster.cluster_id: set(cluster.deletable_folder_ids)}

    store.apply_decisions(session.session_id, {cluster.cluster_id: None}, {cluster.cluster_id: set()})

    assert not feedback_file.exists()


def test_keeper_selection_does_not_write_candidate_feedback_events(tmp_path):
    feedback_file = tmp_path / "feedback" / "user_feedback_events.jsonl"
    store.feedback_logger.feedback_file = feedback_file
    session = store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    session.snapshot = build_snapshot()
    cluster = next(iter(session.snapshot.clusters.values()))
    drop_id = cluster.deletable_folder_ids[0]

    store.apply_decisions(
        session.session_id,
        {cluster.cluster_id: cluster.recommended_keeper_id},
        {cluster.cluster_id: {drop_id}},
    )

    assert not feedback_file.exists()


def test_user_decision_is_saved_to_local_decision_store(tmp_path):
    decision_store = UserDecisionStore(tmp_path / "decisions" / "album_decisions.json")
    local_store = SessionStore(decision_store=decision_store)
    session = local_store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    session.snapshot = build_snapshot()
    cluster = next(iter(session.snapshot.clusters.values()))
    keeper_id = cluster.recommended_keeper_id
    drop_id = cluster.deletable_folder_ids[0]

    local_store.apply_decisions(
        session.session_id,
        {cluster.cluster_id: keeper_id},
        {cluster.cluster_id: {drop_id}},
    )

    saved = json.loads(decision_store.decision_file.read_text(encoding="utf-8"))
    saved_decision = saved["decisions"][cluster.cluster_id]
    assert saved["schema_version"] == "1.0"
    assert saved_decision["keeper_id"] == keeper_id
    assert saved_decision["delete_folder_ids"] == [drop_id]
    assert saved_decision["folder_ids"] == sorted(cluster.folder_ids)


def test_saved_user_decision_is_reapplied_after_rescan(tmp_path):
    decision_store = UserDecisionStore(tmp_path / "decisions" / "album_decisions.json")
    initial_store = SessionStore(decision_store=decision_store)
    first_session = initial_store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    first_session.snapshot = build_snapshot()
    cluster = next(iter(first_session.snapshot.clusters.values()))
    keeper_id = cluster.recommended_keeper_id
    drop_id = cluster.deletable_folder_ids[0]
    initial_store.apply_decisions(
        first_session.session_id,
        {cluster.cluster_id: keeper_id},
        {cluster.cluster_id: {drop_id}},
    )

    rescanned_store = SessionStore(decision_store=decision_store)
    rescanned_store._orchestrator.run = lambda options, progress_handler=None: build_snapshot()
    next_session = rescanned_store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )

    rescanned_store.run_analysis_sync(next_session.session_id)

    assert next_session.status == "completed"
    assert next_session.decisions[cluster.cluster_id] == keeper_id
    assert next_session.delete_selections[cluster.cluster_id] == {drop_id}
    assert next_session.resolution_states[cluster.cluster_id] == "user_selected"
    assert next_session.preview.total_count == 1


def test_saved_null_decision_does_not_override_safe_auto_selection(tmp_path):
    decision_store = UserDecisionStore(tmp_path / "decisions" / "album_decisions.json")
    snapshot = build_snapshot()
    cluster = next(iter(snapshot.clusters.values()))
    decision_store.decision_file.parent.mkdir(parents=True)
    decision_store.decision_file.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "decisions": {
                    cluster.cluster_id: {
                        "cluster_id": cluster.cluster_id,
                        "folder_ids": sorted(cluster.folder_ids),
                        "keeper_id": None,
                        "delete_folder_ids": [],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rescanned_store = SessionStore(decision_store=decision_store)
    rescanned_store._orchestrator.run = lambda options, progress_handler=None: snapshot
    next_session = rescanned_store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )

    rescanned_store.run_analysis_sync(next_session.session_id)

    assert next_session.status == "completed"
    assert next_session.decisions[cluster.cluster_id] == cluster.recommended_keeper_id
    assert next_session.resolution_states[cluster.cluster_id] == "auto"
    assert next_session.preview.total_count == 1


def test_keep_all_clears_saved_user_decision(tmp_path):
    decision_store = UserDecisionStore(tmp_path / "decisions" / "album_decisions.json")
    local_store = SessionStore(decision_store=decision_store)
    session = local_store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    session.snapshot = build_snapshot()
    cluster = next(iter(session.snapshot.clusters.values()))
    drop_id = cluster.deletable_folder_ids[0]

    local_store.apply_decisions(
        session.session_id,
        {cluster.cluster_id: cluster.recommended_keeper_id},
        {cluster.cluster_id: {drop_id}},
    )
    local_store.apply_decisions(session.session_id, {cluster.cluster_id: None}, {cluster.cluster_id: set()})

    saved = json.loads(decision_store.decision_file.read_text(encoding="utf-8"))
    assert cluster.cluster_id not in saved["decisions"]


def test_restored_non_recommended_keeper_is_exposed_in_cluster_response(tmp_path):
    decision_store = UserDecisionStore(tmp_path / "decisions" / "album_decisions.json")
    local_store = SessionStore(decision_store=decision_store)
    session = local_store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    session.snapshot = build_snapshot()
    cluster = next(iter(session.snapshot.clusters.values()))
    manual_keeper_id = cluster.deletable_folder_ids[0]
    manual_delete_id = cluster.recommended_keeper_id
    session.decisions = {cluster.cluster_id: manual_keeper_id}
    session.resolution_states = {cluster.cluster_id: "user_selected"}
    session.delete_selections = {cluster.cluster_id: {manual_delete_id}}
    session.preview = DeletionService().build_preview(
        session.snapshot.clusters,
        session.snapshot.albums,
        session.decisions,
        resolution_states=session.resolution_states,
        delete_selections=session.delete_selections,
    )
    session.status = "completed"

    client = TestClient(app)
    original_store = app_module_store = importlib.import_module("api.app").store
    importlib.import_module("api.app").store = local_store
    try:
        response = client.get(f"/api/analysis-sessions/{session.session_id}/clusters?bucket=all")
    finally:
        importlib.import_module("api.app").store = original_store

    assert app_module_store is original_store
    assert response.status_code == 200
    cluster_response = response.json()["clusters"][0]
    assert cluster_response["recommended_keeper_id"] == cluster.recommended_keeper_id
    assert cluster_response["selected_keeper_id"] == manual_keeper_id
    assert cluster_response["selected_delete_folder_ids"] == [manual_delete_id]


def test_feedback_summary_and_export_endpoint(tmp_path):
    feedback_file = tmp_path / "feedback" / "user_feedback_events.jsonl"
    store.feedback_logger.feedback_file = feedback_file
    feedback_file.parent.mkdir(parents=True, exist_ok=True)
    feedback_file.write_text(
        json.dumps({"schema_version": "1.0", "event_type": "delete_executed"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    client = TestClient(app)
    summary_response = client.get("/api/ml-feedback/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["event_count"] == 1
    assert summary["export_url"] == "/api/ml-feedback/export"
    assert summary["feedback_file_path"] == str(feedback_file)

    export_response = client.get("/api/ml-feedback/export")
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("application/x-ndjson")
    assert "ma-feedback_" in export_response.headers["content-disposition"]
    assert export_response.headers["content-disposition"].endswith(".jsonl\"")
    assert export_response.content == feedback_file.read_bytes()

    clear_response = client.delete("/api/ml-feedback")
    assert clear_response.status_code == 200
    assert clear_response.json()["event_count"] == 0
    assert clear_response.json()["size_bytes"] == 0
    assert not feedback_file.exists()


def test_api_delete_single_respects_explicit_keep_all():
    session = store.create_session(
        AnalysisOptions(
            folders=[Path("C:/music"), Path("D:/archive")],
            preferred_root=Path("C:/music"),
            bitrate_mode="128",
        )
    )
    session.snapshot = build_snapshot()
    cluster = next(iter(session.snapshot.clusters.values()))
    session.decisions = {cluster.cluster_id: None}
    session.resolution_states = {cluster.cluster_id: "skipped"}
    session.delete_selections = {cluster.cluster_id: set()}
    session.status = "completed"

    client = TestClient(app)
    response = client.post(
        f"/api/analysis-sessions/{session.session_id}/delete-single",
        json={"cluster_id": cluster.cluster_id, "folder_id": cluster.deletable_folder_ids[0]},
    )

    assert response.status_code == 400
    assert "keeper פעיל" in response.json()["detail"]


def test_api_open_explorer(monkeypatch, tmp_path):
    api_app_module = importlib.import_module("api.app")
    opened = {}
    monkeypatch.setattr(api_app_module.os, "startfile", lambda path: opened.setdefault("path", path), raising=False)

    client = TestClient(app)
    response = client.post("/api/system/open-explorer", json={"path": str(tmp_path)})

    assert response.status_code == 200
    assert response.json()["status"] == "opened"
    assert opened["path"] == str(tmp_path.resolve())


def test_api_album_cover_and_track_stream_endpoints(tmp_path):
    snapshot, folder_id, track_path, cover_path = build_media_snapshot(tmp_path)
    session = store.create_session(
        AnalysisOptions(
            folders=[tmp_path],
            preferred_root=tmp_path,
            bitrate_mode="128",
        )
    )
    session.snapshot = snapshot
    session.status = "completed"

    client = TestClient(app)

    cover_response = client.get(f"/api/analysis-sessions/{session.session_id}/albums/{folder_id}/cover")
    assert cover_response.status_code == 200
    assert cover_response.content == cover_path.read_bytes()

    stream_response = client.get(f"/api/analysis-sessions/{session.session_id}/albums/{folder_id}/tracks/0/stream")
    assert stream_response.status_code == 200
    assert stream_response.content == track_path.read_bytes()


def test_session_event_buffer_coalesces_progress_and_stays_bounded():
    buffer = SessionEventBuffer(maxlen=3)

    buffer.put({"event": "status", "data": {"status": "running"}})
    buffer.put({"event": "progress", "data": {"current": 1}})
    buffer.put({"event": "progress", "data": {"current": 2}})
    buffer.put({"event": "progress", "data": {"current": 3}})
    buffer.put({"event": "completed", "data": {"status": "completed"}})

    events = []
    while not buffer.empty():
        events.append(buffer.get_nowait())

    assert events == [
        {"event": "status", "data": {"status": "running"}},
        {"event": "progress", "data": {"current": 3}},
        {"event": "completed", "data": {"status": "completed"}},
    ]
