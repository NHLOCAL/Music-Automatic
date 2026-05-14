from __future__ import annotations

import asyncio
import json
import os
import queue
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from mutagen._util import MutagenError
from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3, HeaderNotFoundError as MP3HeaderNotFoundError

from music_dup_lib import config
from music_dup_lib.services import AnalysisOptions
from music_dup_lib.services.user_feedback_logger import build_feedback_export_filename
from api.schemas import (
    AnalysisSessionCreateRequest,
    AnalysisSessionCreatedResponse,
    ClusterListResponse,
    ComparisonHighlightModel,
    ClusterSummaryModel,
    CountsResponse,
    DecisionItem,
    DecisionsRequest,
    DeleteExecutionItemModel,
    DeleteExecutionRequest,
    DeleteExecutionResponse,
    DeletePreviewItemModel,
    DeletePreviewResponse,
    DegradedFlags,
    FeedbackSummaryResponse,
    FolderSummaryModel,
    ModeSummary,
    OpenExplorerRequest,
    PairScoreBreakdownModel,
    ProgressState,
    RecommendationReasonModel,
    SingleDeleteRequest,
    SessionStatusResponse,
    TrackInfoModel,
)
from api.session_store import SessionStore


store = SessionStore()


def _resolve_app_version() -> str:
    env_version = os.getenv("ALBUM_DEDUP_VERSION", "").strip()
    if env_version:
        return env_version

    package_json_path = Path(__file__).resolve().parent.parent / "frontend" / "package.json"
    try:
        package_data = json.loads(package_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "0.1.0"

    version = package_data.get("version")
    return version.strip() if isinstance(version, str) and version.strip() else "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(title="Album Deduplicator API", version=_resolve_app_version())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.API_DEV_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def serve_frontend() -> FileResponse:
            return FileResponse(frontend_dist / "index.html")

    @app.get("/api/health")
    def healthcheck() -> dict:
        return {"status": "ok", "app": app.title, "version": app.version}

    @app.post("/api/analysis-sessions", response_model=AnalysisSessionCreatedResponse)
    def create_analysis_session(payload: AnalysisSessionCreateRequest) -> AnalysisSessionCreatedResponse:
        folders = [Path(folder).resolve() for folder in payload.folders]
        invalid_paths = [str(folder) for folder in folders if not folder.is_dir()]
        if not folders:
            raise HTTPException(status_code=400, detail="At least one folder is required.")
        if invalid_paths:
            raise HTTPException(status_code=400, detail=f"Invalid folder paths: {', '.join(invalid_paths)}")

        preferred_root = Path(payload.preferred_root).resolve() if payload.preferred_root else None
        if preferred_root and preferred_root not in folders:
            raise HTTPException(status_code=400, detail="preferred_root must be one of the input folders.")

        session = store.create_session(
            AnalysisOptions(
                folders=folders,
                preferred_root=preferred_root,
                bitrate_mode=payload.bitrate_mode,
                force_rescan=payload.force_rescan,
                clear_cache=payload.clear_cache,
                gemini_enabled=payload.gemini_enabled,
                full_hash_scan=payload.full_hash_scan,
            )
        )
        store.start_analysis(session.session_id)
        return AnalysisSessionCreatedResponse(session_id=session.session_id, status="queued")

    @app.get("/api/analysis-sessions/{session_id}", response_model=SessionStatusResponse)
    def get_analysis_session(session_id: str) -> SessionStatusResponse:
        session = _get_session_or_404(session_id)
        return SessionStatusResponse(
            session_id=session.session_id,
            status=session.status,
            progress=ProgressState(**session.progress),
            mode_summary=ModeSummary(
                ml_default_enabled=True,
                gemini_enabled=session.options.gemini_enabled,
                review_threshold=config.REVIEW_MIN_SIMILARITY,
                safe_delete_threshold=config.SAFE_DELETE_MIN_SIMILARITY,
            ),
            degraded_flags=DegradedFlags(
                ml_unavailable=session.snapshot.warnings.ml_unavailable,
                gemini_unavailable=session.snapshot.warnings.gemini_unavailable,
                warnings=session.snapshot.warnings.warnings,
            ),
            counts=CountsResponse(
                folders=session.snapshot.counts.folders,
                compared_pairs=session.snapshot.counts.compared_pairs,
                safe_clusters=session.snapshot.counts.safe_clusters,
                review_clusters=session.snapshot.counts.review_clusters,
            ),
            error=session.error,
        )

    @app.get("/api/analysis-sessions/{session_id}/events")
    async def stream_analysis_events(session_id: str) -> StreamingResponse:
        session = _get_session_or_404(session_id)

        async def event_generator():
            while True:
                try:
                    event = session.events.get_nowait()
                    payload = json.dumps(event["data"], ensure_ascii=False)
                    yield f"event: {event['event']}\ndata: {payload}\n\n"
                except queue.Empty:
                    if session.status in {"completed", "failed"} and session.events.empty():
                        final_payload = json.dumps({"status": session.status}, ensure_ascii=False)
                        yield f"event: end\ndata: {final_payload}\n\n"
                        break
                    await asyncio.sleep(0.25)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/api/analysis-sessions/{session_id}/clusters", response_model=ClusterListResponse)
    def get_clusters(
        session_id: str,
        bucket: Literal["safe", "review", "all"] = Query(default="all"),
    ) -> ClusterListResponse:
        session = _get_session_or_404(session_id)
        clusters = [
            _cluster_model(session, cluster_id)
            for cluster_id in session.snapshot.clusters
            if bucket == "all" or session.snapshot.clusters[cluster_id].confidence_bucket == bucket
        ]
        return ClusterListResponse(clusters=clusters)

    @app.post("/api/analysis-sessions/{session_id}/decisions", response_model=DeletePreviewResponse)
    def save_decisions(session_id: str, payload: DecisionsRequest) -> DeletePreviewResponse:
        _get_session_or_404(session_id)
        preview = store.apply_decisions(
            session_id,
            {decision.cluster_id: decision.keeper_id for decision in payload.decisions},
            {
                decision.cluster_id: set(decision.delete_folder_ids or [])
                for decision in payload.decisions
                if decision.delete_folder_ids is not None
            },
        )
        return _preview_model(preview)

    @app.get("/api/analysis-sessions/{session_id}/delete-preview", response_model=DeletePreviewResponse)
    def get_delete_preview(session_id: str) -> DeletePreviewResponse:
        _get_session_or_404(session_id)
        preview = store.get_preview(session_id)
        return _preview_model(preview)

    @app.get("/api/ml-feedback/summary", response_model=FeedbackSummaryResponse)
    def get_feedback_summary() -> FeedbackSummaryResponse:
        summary = store.feedback_logger.summary()
        return FeedbackSummaryResponse(
            feedback_file_path=str(summary.feedback_file_path),
            event_count=summary.event_count,
            size_bytes=summary.size_bytes,
            export_url=summary.export_url,
        )

    @app.get("/api/ml-feedback/export")
    def export_feedback() -> FileResponse:
        summary = store.feedback_logger.summary()
        if not summary.feedback_file_path.exists():
            raise HTTPException(status_code=404, detail="No ML feedback data has been collected yet.")
        return FileResponse(
            summary.feedback_file_path,
            media_type="application/x-ndjson; charset=utf-8",
            filename=build_feedback_export_filename(),
        )

    @app.delete("/api/ml-feedback", response_model=FeedbackSummaryResponse)
    def clear_feedback_history() -> FeedbackSummaryResponse:
        summary = store.feedback_logger.clear()
        return FeedbackSummaryResponse(
            feedback_file_path=str(summary.feedback_file_path),
            event_count=summary.event_count,
            size_bytes=summary.size_bytes,
            export_url=summary.export_url,
        )

    @app.post("/api/analysis-sessions/{session_id}/delete-executions", response_model=DeleteExecutionResponse)
    def execute_delete(session_id: str, payload: DeleteExecutionRequest) -> DeleteExecutionResponse:
        _get_session_or_404(session_id)
        execution = store.execute_delete(session_id, payload.folder_ids)
        return DeleteExecutionResponse(
            moved_count=execution.moved_count,
            failed_count=execution.failed_count,
            total_size_mb=execution.total_size_mb,
            results=[
                DeleteExecutionItemModel(
                    folder_id=result.folder_id,
                    folder_path=str(result.folder_path),
                    success=result.success,
                    message=result.message,
                    size_mb=result.size_mb,
                )
                for result in execution.results
            ],
        )

    @app.post("/api/analysis-sessions/{session_id}/delete-single", response_model=DeleteExecutionResponse)
    def delete_single(session_id: str, payload: SingleDeleteRequest) -> DeleteExecutionResponse:
        _get_session_or_404(session_id)
        try:
            execution = store.execute_single_delete(session_id, payload.cluster_id, payload.folder_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return DeleteExecutionResponse(
            moved_count=execution.moved_count,
            failed_count=execution.failed_count,
            total_size_mb=execution.total_size_mb,
            results=[
                DeleteExecutionItemModel(
                    folder_id=result.folder_id,
                    folder_path=str(result.folder_path),
                    success=result.success,
                    message=result.message,
                    size_mb=result.size_mb,
                )
                for result in execution.results
            ],
        )

    @app.post("/api/system/open-explorer")
    def open_explorer(payload: OpenExplorerRequest) -> dict:
        path = Path(payload.path).resolve()
        if not path.exists():
            raise HTTPException(status_code=400, detail="Path does not exist.")
        if not hasattr(os, "startfile"):
            raise HTTPException(status_code=501, detail="Explorer integration is only available on Windows.")
        os.startfile(str(path))
        return {"status": "opened", "path": str(path)}

    @app.get("/api/analysis-sessions/{session_id}/albums/{folder_id}/cover")
    def get_album_cover(session_id: str, folder_id: str):
        session = _get_session_or_404(session_id)
        album, folder_info = _get_album_context_or_404(session, folder_id)
        cover_file = _find_cover_file(album.path)
        if cover_file:
            return FileResponse(cover_file)

        embedded_art = _read_embedded_album_art(folder_info)
        if embedded_art is None:
            raise HTTPException(status_code=404, detail="Album cover is not available.")

        content, media_type = embedded_art
        return Response(content=content, media_type=media_type)

    @app.get("/api/analysis-sessions/{session_id}/albums/{folder_id}/tracks/{track_index}/stream")
    def stream_track(session_id: str, folder_id: str, track_index: int):
        session = _get_session_or_404(session_id)
        _album, folder_info = _get_album_context_or_404(session, folder_id)
        if track_index < 0 or track_index >= len(folder_info.files):
            raise HTTPException(status_code=404, detail="Track not found.")

        track_path = folder_info.files[track_index].filepath.resolve()
        if not track_path.is_file():
            raise HTTPException(status_code=404, detail="Track file is missing.")
        return FileResponse(track_path)

    return app


def _get_session_or_404(session_id: str):
    session = store.get_session(session_id)
    if session is None:
        _raise_404(session_id)
    return session


def _raise_404(session_id: str):
    raise HTTPException(status_code=404, detail=f"Unknown session id: {session_id}")


def _cluster_model(session, cluster_id: str) -> ClusterSummaryModel:
    cluster = session.snapshot.clusters[cluster_id]
    albums = [
        FolderSummaryModel(
            folder_id=album.folder_id,
            path=str(album.path),
            name=album.name,
            quality_score=album.quality_score,
            avg_bitrate=album.avg_bitrate,
            file_count=album.file_count,
            in_preferred_root=album.in_preferred_root,
            has_album_art=album.has_album_art,
            lossless_ratio=album.lossless_ratio,
            lyrics_ratio=album.lyrics_ratio,
            total_size_mb=album.total_size_mb,
            is_deleted=album.folder_id in session.deleted_folder_ids,
            album_art_preview_url=(
                f"/api/analysis-sessions/{session.session_id}/albums/{album.folder_id}/cover"
                if album.has_album_art
                else None
            ),
            tracks=[
                TrackInfoModel(
                    track_index=index,
                    filename=file_info.filename,
                    filepath=str(file_info.filepath),
                    title=file_info.title,
                    artist=file_info.artist,
                    album=file_info.album,
                    duration=file_info.duration,
                    size_mb=file_info.size_mb,
                    bitrate=file_info.bitrate,
                    stream_url=(
                        f"/api/analysis-sessions/{session.session_id}/albums/{album.folder_id}/tracks/{index}/stream"
                    ),
                )
                for index, file_info in enumerate(session.snapshot.folders[album.path].files)
            ],
        )
        for album in (session.snapshot.albums[folder_id] for folder_id in cluster.folder_ids)
    ]
    pairs = [
        PairScoreBreakdownModel(
            pair_id=pair.pair_id,
            folder1_id=pair.folder1_id,
            folder2_id=pair.folder2_id,
            algorithmic_score=pair.algorithmic_score,
            ml_score=pair.ml_score,
            base_score=pair.base_score,
            gemini_score=pair.gemini_score,
            final_score=pair.final_score,
            gemini_verdict=pair.gemini_verdict,
            gemini_reason=pair.gemini_reason,
            gemini_error=pair.gemini_error,
            is_identical_by_hash=pair.is_identical_by_hash,
            similarity_scores=pair.similarity_scores,
            reason_codes=pair.reason_codes,
        )
        for pair in (session.snapshot.pairs[pair_id] for pair_id in cluster.pair_ids)
    ]
    return ClusterSummaryModel(
        cluster_id=cluster.cluster_id,
        confidence_bucket=cluster.confidence_bucket,
        recommended_keeper_id=cluster.recommended_keeper_id,
        selected_delete_folder_ids=sorted(session.delete_selections.get(cluster_id, set())),
        human_summary=cluster.human_summary,
        resolution_state=cluster.resolution_state,
        recommended_keeper_reason=cluster.recommended_keeper_reason,
        reason_codes=cluster.reason_codes,
        reasons=[
            RecommendationReasonModel(code=reason.code, message=reason.message)
            for reason in cluster.reasons
        ],
        comparison_highlights=[
            ComparisonHighlightModel(
                id=highlight.id,
                label=highlight.label,
                album_id=highlight.album_id,
                tone=highlight.tone,
                value=highlight.value,
            )
            for highlight in cluster.comparison_highlights
        ],
        technical_summary=cluster.technical_summary,
        deletable_folder_ids=cluster.deletable_folder_ids,
        albums=albums,
        pairs=pairs,
    )


def _preview_model(preview) -> DeletePreviewResponse:
    return DeletePreviewResponse(
        items=[
            DeletePreviewItemModel(
                folder_id=item.folder_id,
                folder_path=str(item.folder_path),
                folder_name=item.folder_name,
                keeper_folder_id=item.keeper_folder_id,
                keeper_folder_name=item.keeper_folder_name,
                keeper_folder_path=str(item.keeper_folder_path),
                cluster_id=item.cluster_id,
                estimated_size_mb=item.estimated_size_mb,
                selection_source=item.selection_source,
            )
            for item in preview.items
        ],
        total_count=preview.total_count,
        total_size_mb=preview.total_size_mb,
        auto_selected_count=preview.auto_selected_count,
        manual_selected_count=preview.manual_selected_count,
    )


def _get_album_context_or_404(session, folder_id: str):
    album = session.snapshot.albums.get(folder_id)
    if album is None:
        raise HTTPException(status_code=404, detail=f"Unknown album id: {folder_id}")

    folder_info = session.snapshot.folders.get(album.path)
    if folder_info is None:
        raise HTTPException(status_code=404, detail="Album content is unavailable.")
    return album, folder_info


def _find_cover_file(folder_path: Path) -> Path | None:
    for filename in sorted(config.ALBUM_ART_FILES):
        cover_file = folder_path / filename
        if cover_file.is_file():
            return cover_file.resolve()
    return None


def _read_embedded_album_art(folder_info) -> tuple[bytes, str] | None:
    for file_info in folder_info.files[:5]:
        art_payload = _read_embedded_art_from_track(file_info.filepath)
        if art_payload is not None:
            return art_payload
    return None


def _read_embedded_art_from_track(track_path: Path) -> tuple[bytes, str] | None:
    try:
        ext = track_path.suffix.lower()
        if ext == ".mp3":
            audio = MP3(track_path, ID3=ID3)
            if audio.tags:
                pictures = audio.tags.getall("APIC")
                if pictures:
                    picture = pictures[0]
                    return picture.data, picture.mime or "image/jpeg"
        if ext == ".flac":
            audio = FLAC(track_path)
            if audio.pictures:
                picture = audio.pictures[0]
                return picture.data, picture.mime or "image/jpeg"
    except (ID3NoHeaderError, MP3HeaderNotFoundError, MutagenError, OSError):
        return None
    return None


app = create_app()
