from __future__ import annotations

import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from music_dup_lib.services import (
    AnalysisOptions,
    AnalysisOrchestrator,
    AnalysisProgressEvent,
    AnalysisSnapshot,
    DeletionService,
    DeleteExecution,
    DeletePreview,
)

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    session_id: str
    options: AnalysisOptions
    status: str = "queued"
    progress: dict = field(
        default_factory=lambda: {
            "step": "queued",
            "message": "ממתין",
            "current": 0,
            "total": 1,
            "percent": 0.0,
        }
    )
    snapshot: AnalysisSnapshot = field(default_factory=AnalysisSnapshot)
    decisions: Dict[str, Optional[str]] = field(default_factory=dict)
    preview: DeletePreview = field(default_factory=DeletePreview)
    error: Optional[str] = None
    events: "queue.Queue[dict]" = field(default_factory=queue.Queue)
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._orchestrator = AnalysisOrchestrator()
        self._deletion_service = DeletionService()
        self._lock = threading.Lock()

    def create_session(self, options: AnalysisOptions) -> SessionState:
        session = SessionState(session_id=uuid.uuid4().hex, options=options)
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def start_analysis(self, session_id: str) -> None:
        session = self._require_session(session_id)

        def target() -> None:
            with session.lock:
                session.status = "running"
            self._push_event(session, "status", {"status": "running"})
            try:
                snapshot = self._orchestrator.run(
                    session.options,
                    progress_handler=lambda event: self._handle_progress(session, event),
                )
                decisions = {
                    cluster_id: cluster.recommended_keeper_id if cluster.confidence_bucket == "safe" else None
                    for cluster_id, cluster in snapshot.clusters.items()
                }
                preview = self._deletion_service.build_preview(
                    clusters=snapshot.clusters,
                    albums=snapshot.albums,
                    decisions=decisions,
                )
                with session.lock:
                    session.snapshot = snapshot
                    session.decisions = decisions
                    session.preview = preview
                    session.status = "completed"
                    session.progress = {
                        "step": "completed",
                        "message": "הניתוח הושלם",
                        "current": 1,
                        "total": 1,
                        "percent": 100.0,
                    }
                self._push_event(session, "completed", {"status": "completed"})
            except Exception as exc:
                logger.exception("Analysis session failed: %s", session_id)
                with session.lock:
                    session.status = "failed"
                    session.error = str(exc)
                self._push_event(session, "failed", {"status": "failed", "error": str(exc)})

        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def apply_decisions(self, session_id: str, decisions: Dict[str, Optional[str]]) -> DeletePreview:
        session = self._require_session(session_id)
        with session.lock:
            session.decisions.update(decisions)
            session.preview = self._deletion_service.build_preview(
                clusters=session.snapshot.clusters,
                albums=session.snapshot.albums,
                decisions=session.decisions,
            )
            return session.preview

    def get_preview(self, session_id: str) -> DeletePreview:
        session = self._require_session(session_id)
        return session.preview

    def execute_delete(self, session_id: str, folder_ids: list[str]) -> DeleteExecution:
        session = self._require_session(session_id)
        execution = self._deletion_service.execute(session.preview, folder_ids)
        removed_ids = set(folder_ids)
        with session.lock:
            session.preview.items = [item for item in session.preview.items if item.folder_id not in removed_ids]
        self._push_event(
            session,
            "delete_execution",
            {
                "moved_count": execution.moved_count,
                "failed_count": execution.failed_count,
            },
        )
        return execution

    def _handle_progress(self, session: SessionState, event: AnalysisProgressEvent) -> None:
        total = max(event.total, 1)
        percent = round((event.current / total) * 100, 2)
        progress = {
            "step": event.step,
            "message": event.message,
            "current": event.current,
            "total": total,
            "percent": percent,
        }
        with session.lock:
            session.progress = progress
        self._push_event(session, "progress", progress)

    def _push_event(self, session: SessionState, event_name: str, data: dict) -> None:
        session.events.put({"event": event_name, "data": data})

    def _require_session(self, session_id: str) -> SessionState:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Unknown session id: {session_id}")
        return session
