from __future__ import annotations

import json
import os
import getpass
import re
import secrets
import socket
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from music_dup_lib import config

from .dto import AnalysisSnapshot, DeleteExecution, DeletePreviewItem


FEEDBACK_SCHEMA_VERSION = "1.0"
FEEDBACK_FILENAME = "user_feedback_events.jsonl"


@dataclass(frozen=True)
class FeedbackSummary:
    feedback_file_path: Path
    event_count: int
    size_bytes: int
    export_url: str = "/api/ml-feedback/export"


def resolve_user_feedback_file() -> Path:
    override = os.getenv("ALBUM_DEDUP_USER_DATA_DIR", "").strip()
    if override:
        base_dir = Path(override).expanduser()
    elif os.name == "nt" and os.getenv("LOCALAPPDATA"):
        base_dir = Path(os.environ["LOCALAPPDATA"]) / "Music Automatic" / "Album Deduplicator"
    else:
        base_dir = Path.home() / ".local" / "share" / "music-automatic" / "album-deduplicator"
    return base_dir / "user_feedback" / FEEDBACK_FILENAME


def sanitize_filename_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", str(value or "").strip())
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")[:40]
    return cleaned or fallback


def build_feedback_export_filename(now: Optional[datetime] = None) -> str:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    username = sanitize_filename_part(getpass.getuser(), "user")
    hostname = sanitize_filename_part(socket.gethostname(), "machine")
    random_id = secrets.token_hex(3)
    return f"ma-feedback_{timestamp}_{username}-{hostname}_{random_id}.jsonl"


class UserFeedbackLogger:
    def __init__(self, feedback_file: Optional[Path] = None):
        self.feedback_file = feedback_file or resolve_user_feedback_file()
        self._lock = threading.Lock()

    def summary(self) -> FeedbackSummary:
        if not self.feedback_file.exists():
            return FeedbackSummary(feedback_file_path=self.feedback_file, event_count=0, size_bytes=0)
        size_bytes = self.feedback_file.stat().st_size
        with self.feedback_file.open("r", encoding="utf-8") as handle:
            event_count = sum(1 for line in handle if line.strip())
        return FeedbackSummary(
            feedback_file_path=self.feedback_file,
            event_count=event_count,
            size_bytes=size_bytes,
        )

    def log_keep_all_decision(
        self,
        *,
        session_id: str,
        snapshot: AnalysisSnapshot,
        cluster_id: str,
    ) -> None:
        cluster = snapshot.clusters.get(cluster_id)
        if cluster is None:
            return
        self._append_event(
            {
                **self._base_event(session_id=session_id, event_type="decision_saved"),
                "label": "not_safe_to_delete",
                "evidence_strength": "medium",
                "decision": {
                    "keeper_folder_id": None,
                    "delete_folder_ids": [],
                    "source": "keep_all",
                },
                "cluster": self._cluster_payload(snapshot, cluster_id),
                "keeper": None,
                "target": None,
                "pairs": self._pair_payloads(snapshot, cluster.pair_ids),
                "model_policy": self._model_policy_payload(),
            }
        )

    def log_candidate_decision(
        self,
        *,
        session_id: str,
        snapshot: AnalysisSnapshot,
        cluster_id: str,
        keeper_id: str,
        delete_folder_ids: Iterable[str],
    ) -> None:
        cluster = snapshot.clusters.get(cluster_id)
        if cluster is None:
            return
        selected_ids = [folder_id for folder_id in delete_folder_ids if folder_id != keeper_id]
        for folder_id in selected_ids:
            self._append_event(
                {
                    **self._base_event(session_id=session_id, event_type="decision_saved"),
                    "label": "user_selected_candidate",
                    "evidence_strength": "medium",
                    "decision": {
                        "keeper_folder_id": keeper_id,
                        "delete_folder_ids": [folder_id],
                        "source": "delete_selection",
                    },
                    "cluster": self._cluster_payload(snapshot, cluster_id),
                    "keeper": self._album_payload(snapshot, keeper_id),
                    "target": self._album_payload(snapshot, folder_id),
                    "pairs": self._pair_payloads(
                        snapshot,
                        [
                            pair_id
                            for pair_id in cluster.pair_ids
                            if self._pair_involves(snapshot, pair_id, keeper_id, folder_id)
                        ]
                        or cluster.pair_ids,
                    ),
                    "model_policy": self._model_policy_payload(),
                }
            )

    def log_delete_execution(
        self,
        *,
        session_id: str,
        snapshot: AnalysisSnapshot,
        execution: DeleteExecution,
        preview_items: Iterable[DeletePreviewItem],
        source: str,
    ) -> None:
        items_by_folder_id = {item.folder_id: item for item in preview_items}
        for result in execution.results:
            if not result.success:
                continue
            preview_item = items_by_folder_id.get(result.folder_id)
            if preview_item is None:
                continue
            cluster = snapshot.clusters.get(preview_item.cluster_id)
            if cluster is None:
                continue
            self._append_event(
                {
                    **self._base_event(session_id=session_id, event_type="delete_executed"),
                    "label": "same_album_confirmed",
                    "evidence_strength": "strong",
                    "decision": {
                        "keeper_folder_id": preview_item.keeper_folder_id,
                        "delete_folder_ids": [preview_item.folder_id],
                        "source": source,
                        "selection_source": preview_item.selection_source,
                    },
                    "cluster": self._cluster_payload(snapshot, preview_item.cluster_id),
                    "keeper": self._album_payload(snapshot, preview_item.keeper_folder_id),
                    "target": self._album_payload(snapshot, preview_item.folder_id),
                    "execution": {
                        "success": True,
                        "message": result.message,
                        "size_mb": result.size_mb,
                    },
                    "pairs": self._pair_payloads(
                        snapshot,
                        [
                            pair_id
                            for pair_id in cluster.pair_ids
                            if self._pair_involves(snapshot, pair_id, preview_item.keeper_folder_id, preview_item.folder_id)
                        ]
                        or cluster.pair_ids,
                    ),
                    "model_policy": self._model_policy_payload(),
                }
            )

    def _append_event(self, event: dict) -> None:
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
            with self.feedback_file.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.write("\n")

    def _base_event(self, *, session_id: str, event_type: str) -> dict:
        return {
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "event_id": uuid.uuid4().hex,
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
        }

    def _cluster_payload(self, snapshot: AnalysisSnapshot, cluster_id: str) -> dict:
        cluster = snapshot.clusters[cluster_id]
        return {
            "cluster_id": cluster.cluster_id,
            "folder_ids": list(cluster.folder_ids),
            "pair_ids": list(cluster.pair_ids),
            "recommended_keeper_id": cluster.recommended_keeper_id,
            "confidence_bucket": cluster.confidence_bucket,
            "resolution_state": cluster.resolution_state,
            "deletable_folder_ids": list(cluster.deletable_folder_ids),
            "reason_codes": list(cluster.reason_codes),
        }

    def _album_payload(self, snapshot: AnalysisSnapshot, folder_id: Optional[str]) -> Optional[dict]:
        if folder_id is None:
            return None
        album = snapshot.albums.get(folder_id)
        if album is None:
            return None
        return {
            "folder_id": album.folder_id,
            "path": str(album.path),
            "name": album.name,
            "quality_score": album.quality_score,
            "avg_bitrate": album.avg_bitrate,
            "file_count": album.file_count,
            "in_preferred_root": album.in_preferred_root,
            "has_album_art": album.has_album_art,
            "lossless_ratio": album.lossless_ratio,
            "lyrics_ratio": album.lyrics_ratio,
            "total_size_mb": album.total_size_mb,
        }

    def _pair_payloads(self, snapshot: AnalysisSnapshot, pair_ids: Iterable[str]) -> list[dict]:
        payloads = []
        for pair_id in pair_ids:
            pair = snapshot.pairs.get(pair_id)
            if pair is None:
                continue
            payloads.append(
                {
                    "pair_id": pair.pair_id,
                    "folder1_id": pair.folder1_id,
                    "folder2_id": pair.folder2_id,
                    "folder1_path": str(pair.folder1_path),
                    "folder2_path": str(pair.folder2_path),
                    "algorithmic_score": pair.algorithmic_score,
                    "ml_score": pair.ml_score,
                    "base_score": pair.base_score,
                    "gemini_score": pair.gemini_score,
                    "final_score": pair.final_score,
                    "gemini_verdict": pair.gemini_verdict,
                    "is_identical_by_hash": pair.is_identical_by_hash,
                    "reason_codes": list(pair.reason_codes),
                    "similarity_scores": pair.similarity_scores,
                }
            )
        return payloads

    def _pair_involves(self, snapshot: AnalysisSnapshot, pair_id: str, folder1_id: str, folder2_id: str) -> bool:
        pair = snapshot.pairs.get(pair_id)
        if pair is None:
            return False
        return {pair.folder1_id, pair.folder2_id} == {folder1_id, folder2_id}

    def _model_policy_payload(self) -> dict:
        return {
            "review_min_similarity": config.REVIEW_MIN_SIMILARITY,
            "safe_delete_min_similarity": config.SAFE_DELETE_MIN_SIMILARITY,
            "base_score_algorithmic_weight": config.BASE_SCORE_ALGORITHMIC_WEIGHT,
            "base_score_ml_weight": config.BASE_SCORE_ML_WEIGHT,
            "final_score_base_weight": config.FINAL_SCORE_BASE_WEIGHT,
            "final_score_gemini_weight": config.FINAL_SCORE_GEMINI_WEIGHT,
        }
