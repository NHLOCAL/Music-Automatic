"""Install silently, then exercise installed runtime without Python on PATH."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import wave
import re

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from desktop_backend import model_probe


def cleanup_temporary(directory):
    # NSIS may briefly leave its self-removal helper holding a directory handle.
    deadline = time.monotonic() + 30
    while True:
        try:
            directory.cleanup()
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.3)


def verify_desktop(install_dir, env, root, version):
    from websockets.sync.client import connect

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        debug_port = sock.getsockname()[1]
    desktop = subprocess.Popen(
        [str(install_dir / "Music Automatic.exe"),
         f"--remote-debugging-port={debug_port}", "--remote-debugging-address=127.0.0.1"],
        env=env, cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 90
        target = None
        while target is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json", timeout=2) as response:
                    targets = json.load(response)
                target = next((item for item in targets if item.get("type") == "page"
                               and item.get("url", "").startswith("http://127.0.0.1:")), None)
            except OSError:
                pass
            assert desktop.poll() is None, "Desktop exited before the renderer loaded"
            assert time.monotonic() < deadline, "Desktop renderer did not load"
            time.sleep(0.3)
        with connect(target["webSocketDebuggerUrl"]) as connection:
            for request_id in range(1, 100):
                connection.send(json.dumps({
                    "id": request_id, "method": "Runtime.evaluate",
                    "params": {
                        "expression": "JSON.stringify({runtime: window.albumDeduplicator?.runtime, rendered: !!document.querySelector('#root')?.children.length})",
                        "returnByValue": True,
                    },
                }))
                while True:
                    result = json.loads(connection.recv(timeout=5))
                    if result.get("id") == request_id:
                        break
                value = json.loads(result["result"]["result"]["value"])
                if value.get("rendered") and value.get("runtime"):
                    assert value["runtime"]["version"] == version, value
                    assert value["runtime"]["backendBaseUrl"] == target["url"].rstrip("/"), value
                    break
                time.sleep(0.3)
            else:
                raise AssertionError("React UI or preload bridge did not initialize")
            connection.send(json.dumps({"id": 100, "method": "Browser.close"}))
        desktop.wait(timeout=20)
    finally:
        if desktop.poll() is None:
            subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32" / "taskkill.exe"),
                            "/pid", str(desktop.pid), "/t", "/f"], check=True)
            desktop.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", type=Path)
    parser.add_argument("--installer-dir", type=Path)
    parser.add_argument("--backend", type=Path)
    parser.add_argument("--version", help="Override the expected build version")
    args = parser.parse_args()
    version = args.version or subprocess.check_output(
        ["node", str(PROJECT / "frontend" / "electron" / "app-version.cjs")],
        text=True,
    ).strip()
    if args.installer_dir:
        installers = list(args.installer_dir.glob("*setup*.exe"))
        if len(installers) != 1:
            parser.error("Expected exactly one installer in installer-dir")
        args.installer = installers[0]
    if not args.installer and not args.backend:
        parser.error("Provide --installer, --installer-dir or --backend")
    expected = model_probe()
    with ExitStack() as cleanup:
        temporary = tempfile.TemporaryDirectory(prefix="album clean ")
        cleanup.callback(cleanup_temporary, temporary)
        root = Path(temporary.name)
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("PYTHON") and key != "ALBUM_DEDUP_PYTHON"}
        env.update(PATH=str(Path(os.environ["SystemRoot"]) / "System32"),
                   ALBUM_DEDUP_USER_DATA_DIR=str(root / "user"),
                   ALBUM_DEDUP_VERSION=version)
        if args.installer:
            install_dir = root / "installed"
            subprocess.run([str(args.installer.resolve()), "/S", f"/D={install_dir}"],
                           env=env, check=True, timeout=180)
            uninstallers = list(install_dir.glob("Uninstall*.exe"))
            assert len(uninstallers) == 1, "Installed uninstaller is missing"
            cleanup.callback(subprocess.run,
                             [str(uninstallers[0]), "/S", f"_?={install_dir}"],
                             env=env, timeout=120, check=True)
            executable = install_dir / "resources" / "backend" / "album-deduplicator-api.exe"
            for relative in ("data/singer-list.csv",
                             "music_dup_lib/external/gemini_system_instruction.txt"):
                assert (executable.parent / "_internal" / relative).read_bytes() == (PROJECT / relative).read_bytes(), relative
        else:
            executable = args.backend.resolve()
        result = subprocess.run([str(executable), "--self-test"], cwd=root,
                                env=env, capture_output=True, text=True,
                                timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        actual = json.loads(result.stdout.strip().splitlines()[-1])
        assert expected == actual, "Frozen model predictions differ from source runtime"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with (root / "backend.log").open("w", encoding="utf-8") as log:
            child = subprocess.Popen([str(executable), "--port", str(port)],
                                     cwd=root, env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 90
                while True:
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                            health = json.load(response)
                        assert health["status"] == "ok"
                        assert health["version"] == version
                        break
                    except OSError:
                        if child.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError((root / "backend.log").read_text(encoding="utf-8"))
                        time.sleep(0.3)
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/openapi.json") as response:
                    assert "/api/analysis-sessions" in json.load(response)["paths"]
                if args.installer:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
                        html = response.read().decode("utf-8")
                    assert '<div id="root">' in html, "Renderer HTML is missing"
                    assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
                    assert assets, "Renderer assets are missing"
                    for asset in assets:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}{asset}") as response:
                            assert response.read(), f"Empty renderer asset: {asset}"
                music = root / "music"
                for album in ("copy one", "copy two"):
                    folder = music / album
                    folder.mkdir(parents=True)
                    for track in range(3):
                        with wave.open(str(folder / f"song {track}.wav"), "wb") as audio:
                            audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                            audio.writeframes(bytes([track, 0]) * 8000)
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/analysis-sessions",
                    data=json.dumps({"folders": [str(music)], "force_rescan": True}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request) as response:
                    session_id = json.load(response)["session_id"]
                deadline = time.monotonic() + 60
                while True:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/analysis-sessions/{session_id}") as response:
                        session = json.load(response)
                    assert session["status"] != "failed", session
                    if session["status"] == "completed":
                        assert not session["degraded_flags"]["ml_unavailable"], session
                        assert session["counts"]["folders"] == 2, session
                        assert session["counts"]["compared_pairs"] == 1, session
                        break
                    assert time.monotonic() < deadline, session
                    time.sleep(0.3)
            finally:
                child.terminate()
                child.wait(timeout=15)
        if args.installer:
            verify_desktop(install_dir, env, root, version)
        checks = "API, duplicate scan, model hash and 32 identical predictions"
        if args.installer:
            checks += ", installed desktop renderer and preload bridge"
    print(f"Bundle verified without Python/PYTHONPATH: {checks}")


if __name__ == "__main__":
    main()
