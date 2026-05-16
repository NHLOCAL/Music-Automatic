from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)
GEMINI_SETTINGS_SCHEMA_VERSION = "1.0"
GEMINI_SETTINGS_FILENAME = "gemini_settings.json"


def resolve_user_data_dir() -> Path:
    override = os.getenv("ALBUM_DEDUP_USER_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt" and os.getenv("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "Music Automatic" / "Album Deduplicator"
    return Path.home() / ".local" / "share" / "music-automatic" / "album-deduplicator"


def resolve_gemini_settings_file() -> Path:
    return resolve_user_data_dir() / "settings" / GEMINI_SETTINGS_FILENAME


class GeminiSettingsStore:
    def __init__(self, settings_file: Optional[Path] = None):
        self.settings_file = settings_file or resolve_gemini_settings_file()
        self._lock = threading.Lock()

    def get_api_key(self) -> Optional[str]:
        with self._lock:
            data = self._read_data_unlocked()
        api_key = data.get("api_key")
        if not isinstance(api_key, str):
            return None
        api_key = api_key.strip()
        return api_key or None

    def has_api_key(self) -> bool:
        return self.get_api_key() is not None

    def save_api_key(self, api_key: str) -> None:
        normalized = api_key.strip()
        if not normalized:
            return

        with self._lock:
            data = self._read_data_unlocked()
            data["schema_version"] = GEMINI_SETTINGS_SCHEMA_VERSION
            data["api_key"] = normalized
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_data_unlocked(data)

    def _read_data_unlocked(self) -> dict:
        try:
            with self.settings_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {"schema_version": GEMINI_SETTINGS_SCHEMA_VERSION}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read Gemini settings from %s: %s", self.settings_file, exc)
            return {"schema_version": GEMINI_SETTINGS_SCHEMA_VERSION}
        return data if isinstance(data, dict) else {"schema_version": GEMINI_SETTINGS_SCHEMA_VERSION}

    def _write_data_unlocked(self, data: dict) -> None:
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.settings_file.with_suffix(f"{self.settings_file.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        temp_path.replace(self.settings_file)
