import json
from pathlib import Path
import subprocess
import sys


def test_cpu_benchmark_validates_each_workload_against_the_requested_commit():
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(project / "tools/benchmark_comparison_cpu.py"),
         "--baseline-ref", "24e69ab", "--folders", "8", "--tracks", "3", "--repeats", "1"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert {item["workload"] for item in report["measurements"]} == {"shared", "mixed", "diverse"}
    for item in report["measurements"]:
        assert item["exactly_equal_pairs"] == 28
        assert item["before_median_seconds"] > 0
        assert item["after_median_seconds"] > 0


def test_cache_sample_benchmark_preserves_input_file(tmp_path):
    project = Path(__file__).resolve().parents[1]
    records = {str(index): {"path": str(tmp_path / str(index)), "folder_name": str(index),
                           "parent_folder_name": "library", "files": [
        {"filename": "track.mp3", "filepath": str(tmp_path / str(index) / "track.mp3"),
         "extension": ".mp3", "size_mb": 1}]} for index in range(4)}
    cache = tmp_path / "sample.json"
    cache.write_text(json.dumps(records), encoding="utf-8")
    before = cache.read_bytes(), cache.stat().st_mtime_ns
    completed = subprocess.run(
        [sys.executable, str(project / "tools/benchmark_comparison_cpu.py"),
         "--cache-only", "--cache-file", str(cache), "--folders", "4", "--repeats", "1"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert (cache.read_bytes(), cache.stat().st_mtime_ns) == before
    measurements = json.loads(completed.stdout)["measurements"]
    assert len(measurements) == 1
    assert measurements[0]["workload"] == "cached_library_sample"
    assert measurements[0]["exactly_equal_pairs"] == 6
