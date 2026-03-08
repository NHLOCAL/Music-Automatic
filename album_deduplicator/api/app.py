from __future__ import annotations

import asyncio
import json
import queue
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from music_dup_lib import config
from music_dup_lib.services import AnalysisOptions
from api.schemas import (
    AnalysisSessionCreateRequest,
    AnalysisSessionCreatedResponse,
    ClusterListResponse,
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
    FolderSummaryModel,
    ModeSummary,
    PairScoreBreakdownModel,
    ProgressState,
    RecommendationReasonModel,
    SessionStatusResponse,
    TrackInfoModel,
)
from api.session_store import SessionStore


store = SessionStore()


def create_app() -> FastAPI:
    app = FastAPI(title="Album Deduplicator API", version="2.0.0")
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
        )
        return _preview_model(preview)

    @app.get("/api/analysis-sessions/{session_id}/delete-preview", response_model=DeletePreviewResponse)
    def get_delete_preview(session_id: str) -> DeletePreviewResponse:
        _get_session_or_404(session_id)
        preview = store.get_preview(session_id)
        return _preview_model(preview)

    @app.post("/api/analysis-sessions/{session_id}/delete-executions", response_model=DeleteExecutionResponse)
    def execute_delete(session_id: str, payload: DeleteExecutionRequest) -> DeleteExecutionResponse:
        _get_session_or_404(session_id)
        execution = store.execute_delete(session_id, payload.folder_ids)
        return DeleteExecutionResponse(
            moved_count=execution.moved_count,
            failed_count=execution.failed_count,
            results=[
                DeleteExecutionItemModel(
                    folder_id=result.folder_id,
                    folder_path=str(result.folder_path),
                    success=result.success,
                    message=result.message,
                )
                for result in execution.results
            ],
        )

    return app


def _get_session_or_404(session_id: str):
    try:
        return store.get_session(session_id) or _raise_404(session_id)
    except KeyError:
        return _raise_404(session_id)


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
            tracks=[
                TrackInfoModel(
                    filename=file_info.filename,
                    title=file_info.title,
                    artist=file_info.artist,
                    album=file_info.album,
                    duration=file_info.duration,
                    size_mb=file_info.size_mb,
                    bitrate=file_info.bitrate,
                )
                for file_info in session.snapshot.folders[album.path].files
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
        reason_codes=cluster.reason_codes,
        reasons=[
            RecommendationReasonModel(code=reason.code, message=reason.message)
            for reason in cluster.reasons
        ],
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
            )
            for item in preview.items
        ],
        total_count=preview.total_count,
    )


app = create_app()
