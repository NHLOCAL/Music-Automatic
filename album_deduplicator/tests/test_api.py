import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app, store
from music_dup_lib.models import FileInfo, FolderInfo
from music_dup_lib.services import AnalysisOptions, DeletionService
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


def test_api_session_flow(monkeypatch, tmp_path):
    def fake_start_analysis(session_id: str):
        session = store.get_session(session_id)
        session.snapshot = build_snapshot()
        session.decisions = {
            next(iter(session.snapshot.clusters.values())).cluster_id: next(
                iter(session.snapshot.clusters.values())
            ).recommended_keeper_id
        }
        session.preview = DeletionService().build_preview(
            session.snapshot.clusters,
            session.snapshot.albums,
            session.decisions,
            resolution_states={next(iter(session.snapshot.clusters.values())).cluster_id: "auto"},
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
    session.preview = DeletionService().build_preview(
        session.snapshot.clusters,
        session.snapshot.albums,
        session.decisions,
        resolution_states=session.resolution_states,
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
    session.preview = DeletionService().build_preview(
        session.snapshot.clusters,
        session.snapshot.albums,
        session.decisions,
        resolution_states=session.resolution_states,
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


def test_api_open_explorer(monkeypatch, tmp_path):
    api_app_module = importlib.import_module("api.app")
    opened = {}
    monkeypatch.setattr(api_app_module.os, "startfile", lambda path: opened.setdefault("path", path), raising=False)

    client = TestClient(app)
    response = client.post("/api/system/open-explorer", json={"path": str(tmp_path)})

    assert response.status_code == 200
    assert response.json()["status"] == "opened"
    assert opened["path"] == str(tmp_path.resolve())
