from __future__ import annotations

import importlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
NPM_COMMAND = "npm.cmd" if sys.platform == "win32" else "npm"

IMPORT_NAMES = {
    "google-genai": "google.genai",
    "pillow": "PIL",
    "send2trash": "send2trash",
}


def normalize_requirement(line: str) -> str | None:
    cleaned = line.strip()
    if not cleaned or cleaned.startswith("#") or cleaned.startswith("-"):
        return None
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
        if separator in cleaned:
            cleaned = cleaned.split(separator, 1)[0]
            break
    return cleaned.strip()


def check_python_dependencies() -> list[str]:
    missing: list[str] = []
    requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()

    for line in requirements:
        package_name = normalize_requirement(line)
        if not package_name:
            continue

        try:
            importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(package_name)
            continue

        import_name = IMPORT_NAMES.get(package_name.lower(), package_name.replace("-", "_"))
        try:
            importlib.import_module(import_name)
        except Exception as exc:
            missing.append(f"{package_name} (import failed: {exc})")

    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if pip_check.returncode != 0:
        details = (pip_check.stdout + pip_check.stderr).strip()
        missing.append(f"pip dependency conflict: {details}")

    return missing


def check_frontend_dependencies() -> list[str]:
    problems: list[str] = []

    try:
        subprocess.run(
            [NPM_COMMAND, "--version"],
            cwd=FRONTEND_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ["npm is not available on PATH"]

    package_json = FRONTEND_ROOT / "package.json"
    node_modules = FRONTEND_ROOT / "node_modules"
    if not package_json.exists():
        return ["frontend/package.json is missing"]
    if not node_modules.exists():
        return ["frontend/node_modules is missing; run npm install in album_deduplicator/frontend"]

    npm_ls = subprocess.run(
        [NPM_COMMAND, "ls", "--depth=0", "--json"],
        cwd=FRONTEND_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    output = npm_ls.stdout or npm_ls.stderr
    try:
        report = json.loads(output)
    except json.JSONDecodeError:
        report = {}

    missing = []
    for problem in report.get("problems", []):
        if isinstance(problem, str):
            missing.append(problem)

    if npm_ls.returncode != 0 and not missing:
        details = (npm_ls.stderr or npm_ls.stdout).strip()
        missing.append(details or "npm dependency check failed")

    problems.extend(missing)
    return problems


def main() -> int:
    python_problems = check_python_dependencies()
    frontend_problems = check_frontend_dependencies()

    if not python_problems and not frontend_problems:
        print("Dependency check passed.")
        return 0

    print("Dependency check failed.", file=sys.stderr)

    if python_problems:
        print("\nPython dependencies:", file=sys.stderr)
        for problem in python_problems:
            print(f"  - {problem}", file=sys.stderr)
        print(f"\nInstall Python dependencies with:\n  {sys.executable} -m pip install -r requirements.txt", file=sys.stderr)

    if frontend_problems:
        print("\nFrontend dependencies:", file=sys.stderr)
        for problem in frontend_problems:
            print(f"  - {problem}", file=sys.stderr)
        print("\nInstall frontend dependencies with:\n  cd frontend\n  npm install", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
