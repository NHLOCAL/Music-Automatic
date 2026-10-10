"""Freeze the server and native ML dependencies using the build interpreter."""
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]


def main():
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--name", "album-deduplicator-api",
        "--distpath", str(PROJECT / "build" / "backend"),
        "--workpath", str(PROJECT / "build" / "pyinstaller"),
        "--specpath", str(PROJECT / "build"),
        "--paths", str(PROJECT),
        "--collect-submodules", "music_dup_lib",
        "--collect-submodules", "api",
        "--add-data", f"{PROJECT / 'data' / 'lgbm_regressor_model.joblib'}:data",
        "--add-data", f"{PROJECT / 'data' / 'singer-list.csv'}:data",
        "--add-data", f"{PROJECT / 'music_dup_lib' / 'external' / 'gemini_system_instruction.txt'}:music_dup_lib/external",
    ]
    # joblib unpickles sklearn/LightGBM dynamically; collect their native DLLs too.
    for package in ("lightgbm", "sklearn", "google.genai", "uvicorn", "mutagen", "send2trash"):
        command.extend(["--collect-all", package])
    command.append(str(PROJECT / "scripts" / "desktop_backend.py"))
    subprocess.run(command, cwd=PROJECT, check=True)


if __name__ == "__main__":
    main()
