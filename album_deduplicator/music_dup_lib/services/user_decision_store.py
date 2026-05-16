from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set

from .dto import AnalysisSnapshot


logger = logging.getLogger(__name__)
USER_DECISIONS_SCHEMA_VERSION = "1.0"
USER_DECISIONS_FILENAME = "album_decisions.json"


@dataclass(frozen=True)
class StoredUserDecision:
    cluster_id: str
    keeper_id: Optional[str]
    delete_folder_ids: Set[str]
    resolution_state: str


def resolve_user_decision_file() -> Path:
    override = os.getenv("ALBUM_DEDUP_USER_DATA_DIR", "").strip()
    if override:
        base_dir = Path(override).expanduser()
    elif os.name == "nt" and os.getenv("LOCALAPPDATA"):
        base_dir = Path(os.environ["LOCALAPPDATA"]) / "Music Automatic" / "Album Deduplicator"
    else:
        base_dir = Path.home() / ".local" / "share" / "music-automatic" / "album-deduplicator"
    return base_dir / "user_decisions" / USER_DECISIONS_FILENAME


class UserDecisionStore:
    def __init__(self, decision_file: Optional[Path] = None):
        self.decision_file = decision_file or resolve_user_decision_file()
        self._lock = threading.Lock()

    def save_decision(
        self,
        *,
        snapshot: AnalysisSnapshot,
        cluster_id: str,
        keeper_id: Optional[str],
        delete_folder_ids: Set[str],
        resolution_state: str,
    ) -> None:
        cluster = snapshot.clusters.get(cluster_id)
        if cluster is None:
            return

        folder_ids = sorted(cluster.folder_ids)
        allowed_delete_folder_ids = {
            folder_id
            for folder_id in folder_ids
            if folder_id != keeper_id
        }
        normalized_delete_folder_ids = sorted(
            folder_id for folder_id in delete_folder_ids if folder_id in allowed_delete_folder_ids
        )
        album_paths = {
            folder_id: str(snapshot.albums[folder_id].path)
            for folder_id in folder_ids
            if folder_id in snapshot.albums
        }
        record = {
            "cluster_id": cluster_id,
            "folder_ids": folder_ids,
            "keeper_id": keeper_id if keeper_id in folder_ids else None,
            "delete_folder_ids": normalized_delete_folder_ids,
            "resolution_state": "user_selected" if keeper_id else "skipped",
            "album_paths": album_paths,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            data = self._read_data_unlocked()
            decisions = data.setdefault("decisions", {})
            decisions[cluster_id] = record
            data["schema_version"] = USER_DECISIONS_SCHEMA_VERSION
            data["updated_at"] = record["updated_at"]
            self._write_data_unlocked(data)

    def clear_decision(self, cluster_id: str) -> None:
        with self._lock:
            data = self._read_data_unlocked()
            decisions = data.setdefault("decisions", {})
            if cluster_id not in decisions:
                return
            del decisions[cluster_id]
            data["schema_version"] = USER_DECISIONS_SCHEMA_VERSION
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_data_unlocked(data)

    def decisions_for_snapshot(self, snapshot: AnalysisSnapshot) -> Dict[str, StoredUserDecision]:
        with self._lock:
            data = self._read_data_unlocked()

        stored_decisions = data.get("decisions", {})
        if not isinstance(stored_decisions, dict):
            return {}

        restored: Dict[str, StoredUserDecision] = {}
        for cluster_id, cluster in snapshot.clusters.items():
            record = stored_decisions.get(cluster_id)
            if not isinstance(record, dict):
                continue
            if set(record.get("folder_ids") or []) != set(cluster.folder_ids):
                continue

            keeper_id = record.get("keeper_id")
            if keeper_id is None:
                continue
            if keeper_id not in cluster.folder_ids:
                continue

            allowed_delete_folder_ids = {
                folder_id
                for folder_id in cluster.folder_ids
                if folder_id != keeper_id
            }
            restored[cluster_id] = StoredUserDecision(
                cluster_id=cluster_id,
                keeper_id=keeper_id,
                delete_folder_ids={
                    folder_id
                    for folder_id in (record.get("delete_folder_ids") or [])
                    if folder_id in allowed_delete_folder_ids
                },
                resolution_state="user_selected" if keeper_id else "skipped",
            )
        return restored

    def _read_data_unlocked(self) -> dict:
        try:
            with self.decision_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {"schema_version": USER_DECISIONS_SCHEMA_VERSION, "decisions": {}}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read user decisions from %s: %s", self.decision_file, exc)
            return {"schema_version": USER_DECISIONS_SCHEMA_VERSION, "decisions": {}}
        if not isinstance(data, dict):
            return {"schema_version": USER_DECISIONS_SCHEMA_VERSION, "decisions": {}}
        if not isinstance(data.get("decisions"), dict):
            data["decisions"] = {}
        return data

    def _write_data_unlocked(self, data: dict) -> None:
        self.decision_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.decision_file.with_suffix(f"{self.decision_file.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        temp_path.replace(self.decision_file)
