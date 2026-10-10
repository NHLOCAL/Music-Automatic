import json
import os
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]


def test_desktop_probe_loads_real_model_and_server():
    result = subprocess.run(
        [sys.executable, str(PROJECT / "scripts" / "desktop_backend.py"), "--self-test"],
        cwd=PROJECT, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT)},
    )
    assert result.returncode == 0, result.stderr
    probe = json.loads(result.stdout.strip().splitlines()[-1])
    assert len(probe["model_sha256"]) == 64
    assert len(probe["predictions"]) == 32


def test_frozen_runtime_separates_resources_from_writable_state(tmp_path):
    code = """
import sys
sys.frozen = True
from music_dup_lib import config
assert config.DATA_DIR == __import__('pathlib').Path(sys.argv[1]) / 'data'
assert config.ML_MODEL_FILE.is_file()
assert config.ARTIST_CSV_FILE.is_file()
assert config.ML_MODEL_FILE.parent != config.DATA_DIR
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], cwd=PROJECT,
        env={**os.environ, "ALBUM_DEDUP_USER_DATA_DIR": str(tmp_path)},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
