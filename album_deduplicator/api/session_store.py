from __future__ import annotations

import logging
from collections import deque
import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

from music_dup_lib.services import (
    AnalysisOptions,
    AnalysisOrchestrator,
    AnalysisProgressEvent,
    AnalysisSnapshot,
    DeletionService,
    DeleteExecution,
    DeletePreview,
    UserFeedbackLogger,
)

logger = logging.getLogger(__name__)
MAX_SESSION_EVENTS = 256


class SessionEventBuffer:
    def __init__(self, maxlen: int = MAX_SESSION_EVENTS):
        self._events: deque[dict] = deque()
        self._maxlen = maxlen
        self._lock = threading.Lock()

    def put(self, event: dict) -> None:
        with self._lock:
            if event.get("event") == "progress":
                self._drop_latest_progress_locked()
            elif len(self._events) >= self._maxlen:
                self._drop_oldest_progress_locked()

            if len(self._events) >= self._maxlen:
                self._events.popleft()

            self._events.append(event)

    def get_nowait(self) -> dict:
        with self._lock:
            if not self._events:
                raise queue.Empty
            return self._events.popleft()

    def empty(self) -> bool:
        with self._lock:
            return not self._events

    def _drop_latest_progress_locked(self) -> None:
        for index in range(len(self._events) - 1, -1, -1):
            if self._events[index].get("event") == "progress":
                del self._events[index]
                return

    def _drop_oldest_progress_locked(self) -> None:
        for index, buffered_event in enumerate(self._events):
            if buffered_event.get("event") == "progress":
                del self._events[index]
                return


@dataclass
class SessionState:
    session_id: str
    options: AnalysisOptions
    status: str = "queued"
    progress: dict = field(
        default_factory=lambda: {
            "step": "queued",
            "stage": "queued",
            "message": "ממתין",
            "human_message": "ממתין לתחילת הניתוח.",
            "current": 0,
            "total": 1,
            "percent": 0.0,
            "warnings": [],
        }
    )
    snapshot: AnalysisSnapshot = field(default_factory=AnalysisSnapshot)
    decisions: Dict[str, Optional[str]] = field(default_factory=dict)
    preview: DeletePreview = field(default_factory=DeletePreview)
    error: Optional[str] = None
    events: SessionEventBuffer = field(default_factory=SessionEventBuffer)
    lock: threading.Lock = field(default_factory=threading.Lock)
    resolution_states: Dict[str, str] = field(default_factory=dict)
    deleted_folder_ids: Set[str] = field(default_factory=set)
    delete_selections: Dict[str, Set[str]] = field(default_factory=dict)


class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._orchestrator = AnalysisOrchestrator()
        self._deletion_service = DeletionService()
        self.feedback_logger = UserFeedbackLogger()
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
                resolution_states = {
                    cluster_id: "auto" if cluster.confidence_bucket == "safe" and cluster.recommended_keeper_id else "skipped"
                    for cluster_id, cluster in snapshot.clusters.items()
                }
                delete_selections = {
                    cluster_id: self._default_delete_selection(
                        cluster,
                        decisions.get(cluster_id),
                        set(),
                    )
                    for cluster_id, cluster in snapshot.clusters.items()
                }
                self._apply_resolution_states(snapshot, resolution_states, set())
                preview = self._deletion_service.build_preview(
                    clusters=snapshot.clusters,
                    albums=snapshot.albums,
                    decisions=decisions,
                    resolution_states=resolution_states,
                    delete_selections=delete_selections,
                )
                with session.lock:
                    session.snapshot = snapshot
                    session.decisions = decisions
                    session.resolution_states = resolution_states
                    session.delete_selections = delete_selections
                    session.preview = preview
                    session.status = "completed"
                    session.progress = {
                        "step": "completed",
                        "stage": "complete",
                        "message": "הניתוח הושלם",
                        "human_message": "הניתוח הסתיים. אפשר להתחיל לעבור על הקבוצות הבטוחות והקבוצות שדורשות סקירה.",
                        "current": 1,
                        "total": 1,
                        "percent": 100.0,
                        "warnings": snapshot.warnings.warnings,
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

    def apply_decisions(
        self,
        session_id: str,
        decisions: Dict[str, Optional[str]],
        delete_selections: Optional[Dict[str, Set[str]]] = None,
    ) -> DeletePreview:
        session = self._require_session(session_id)
        with session.lock:
            for cluster_id, keeper_id in decisions.items():
                previous_keeper_id = session.decisions.get(cluster_id)
                session.decisions[cluster_id] = keeper_id
                session.resolution_states[cluster_id] = "user_selected" if keeper_id else "skipped"
                cluster = session.snapshot.clusters.get(cluster_id)
                if cluster is None:
                    session.delete_selections[cluster_id] = set()
                    continue
                if keeper_id is None:
                    session.delete_selections[cluster_id] = set()
                    continue
                requested_selection = None
                if delete_selections and cluster_id in delete_selections:
                    requested_selection = delete_selections[cluster_id]
                elif previous_keeper_id == keeper_id and cluster_id in session.delete_selections:
                    requested_selection = session.delete_selections[cluster_id]
                session.delete_selections[cluster_id] = self._normalize_delete_selection(
                    cluster=cluster,
                    keeper_id=keeper_id,
                    requested_folder_ids=requested_selection,
                    deleted_folder_ids=session.deleted_folder_ids,
                )
            self._apply_resolution_states(session.snapshot, session.resolution_states, session.deleted_folder_ids)
            session.preview = self._deletion_service.build_preview(
                clusters=session.snapshot.clusters,
                albums=session.snapshot.albums,
                decisions=session.decisions,
                resolution_states=session.resolution_states,
                delete_selections=session.delete_selections,
                excluded_folder_ids=session.deleted_folder_ids,
            )
            return session.preview

    def get_preview(self, session_id: str) -> DeletePreview:
        session = self._require_session(session_id)
        return session.preview

    def execute_delete(self, session_id: str, folder_ids: list[str]) -> DeleteExecution:
        session = self._require_session(session_id)
        preview_items = list(session.preview.items)
        execution = self._deletion_service.execute(session.preview, folder_ids)
        removed_ids = {result.folder_id for result in execution.results if result.success}
        with session.lock:
            self.feedback_logger.log_delete_execution(
                session_id=session.session_id,
                snapshot=session.snapshot,
                execution=execution,
                preview_items=preview_items,
                source="bulk_delete",
            )
            session.deleted_folder_ids.update(removed_ids)
            for selection in session.delete_selections.values():
                selection.difference_update(removed_ids)
            session.preview = self._deletion_service.build_preview(
                clusters=session.snapshot.clusters,
                albums=session.snapshot.albums,
                decisions=session.decisions,
                resolution_states=session.resolution_states,
                delete_selections=session.delete_selections,
                excluded_folder_ids=session.deleted_folder_ids,
            )
            self._apply_resolution_states(session.snapshot, session.resolution_states, session.deleted_folder_ids)
        self._push_event(
            session,
            "delete_execution",
            {
                "moved_count": execution.moved_count,
                "failed_count": execution.failed_count,
                "total_size_mb": execution.total_size_mb,
            },
        )
        return execution

    def execute_single_delete(self, session_id: str, cluster_id: str, folder_id: str) -> DeleteExecution:
        session = self._require_session(session_id)
        with session.lock:
            cluster = session.snapshot.clusters.get(cluster_id)
            if cluster is None:
                raise KeyError(f"Unknown cluster id: {cluster_id}")
            keeper_id = (
                session.decisions[cluster_id]
                if cluster_id in session.decisions
                else cluster.recommended_keeper_id
            )
            if keeper_id is None:
                raise ValueError("לא ניתן למחוק בודד בלי keeper פעיל לקבוצה.")
            if folder_id == keeper_id:
                raise ValueError("לא ניתן למחוק את העותק שנבחר לשמירה.")
            if folder_id not in cluster.folder_ids:
                raise ValueError("התיקייה שנבחרה אינה חלק מהקבוצה.")
            preview_item = self._deletion_service.build_preview_item(
                cluster=cluster,
                albums=session.snapshot.albums,
                folder_id=folder_id,
                keeper_id=keeper_id,
                selection_source="user_selected",
            )

        preview_items = [preview_item]
        execution = self._deletion_service.execute(DeletePreview(items=preview_items), [folder_id])
        removed_ids = {result.folder_id for result in execution.results if result.success}
        with session.lock:
            self.feedback_logger.log_delete_execution(
                session_id=session.session_id,
                snapshot=session.snapshot,
                execution=execution,
                preview_items=preview_items,
                source="single_delete",
            )
            session.deleted_folder_ids.update(removed_ids)
            for selection in session.delete_selections.values():
                selection.difference_update(removed_ids)
            session.preview = self._deletion_service.build_preview(
                clusters=session.snapshot.clusters,
                albums=session.snapshot.albums,
                decisions=session.decisions,
                resolution_states=session.resolution_states,
                delete_selections=session.delete_selections,
                excluded_folder_ids=session.deleted_folder_ids,
            )
            self._apply_resolution_states(session.snapshot, session.resolution_states, session.deleted_folder_ids)
        self._push_event(
            session,
            "delete_execution",
            {
                "moved_count": execution.moved_count,
                "failed_count": execution.failed_count,
                "total_size_mb": execution.total_size_mb,
            },
        )
        return execution

    def _handle_progress(self, session: SessionState, event: AnalysisProgressEvent) -> None:
        total = max(event.total, 1)
        percent = round((event.current / total) * 100, 2)
        progress = {
            "step": event.step,
            "stage": event.stage,
            "message": event.message,
            "human_message": event.human_message,
            "current": event.current,
            "total": total,
            "percent": percent,
            "warnings": list(session.snapshot.warnings.warnings),
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

    def _apply_resolution_states(
        self,
        snapshot: AnalysisSnapshot,
        resolution_states: Dict[str, str],
        deleted_folder_ids: Set[str],
    ) -> None:
        for cluster_id, cluster in snapshot.clusters.items():
            if cluster.deletable_folder_ids and all(
                folder_id in deleted_folder_ids for folder_id in cluster.deletable_folder_ids
            ):
                cluster.resolution_state = "deleted"
                resolution_states[cluster_id] = "deleted"
            else:
                cluster.resolution_state = resolution_states.get(cluster_id, cluster.resolution_state)

    def _default_delete_selection(
        self,
        cluster,
        keeper_id: Optional[str],
        deleted_folder_ids: Set[str],
    ) -> Set[str]:
        if keeper_id is None:
            return set()
        return {
            folder_id
            for folder_id in cluster.folder_ids
            if folder_id != keeper_id and folder_id not in deleted_folder_ids
        }

    def _normalize_delete_selection(
        self,
        cluster,
        keeper_id: Optional[str],
        requested_folder_ids: Optional[Set[str]],
        deleted_folder_ids: Set[str],
    ) -> Set[str]:
        if keeper_id is None or keeper_id not in cluster.folder_ids:
            return set()
        allowed_folder_ids = self._default_delete_selection(cluster, keeper_id, deleted_folder_ids)
        if requested_folder_ids is None:
            return allowed_folder_ids
        return {folder_id for folder_id in requested_folder_ids if folder_id in allowed_folder_ids}
