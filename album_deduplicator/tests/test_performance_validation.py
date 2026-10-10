import json
from pathlib import Path
import subprocess
import sys


def test_offline_performance_validation_checks_stable_parity_without_cache_writes():
    project_dir = Path(__file__).resolve().parents[1]
    cache_paths = [project_dir / "data" / name for name in
                   ["music_data.json", "comparison_results_cache.pkl"]]
    cache_state_before = [(path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None
                          for path in cache_paths]
    result = subprocess.run(
        [sys.executable, str(project_dir / "tools" / "validate_performance.py"),
         "--validation-folders", "6", "--benchmark-folders", "8", "--tracks", "2",
         "--ml-pairs", "32", "--batch-size", "4", "--repeats", "1"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert [(path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None
            for path in cache_paths] == cache_state_before
    report = json.loads(result.stdout)
    assert report["parity"]["comparison_cases"] == 60
    assert report["parity"]["streaming_scoring"] is True
    assert report["comparison"]["pairs"] == 28
    assert report["ml_feature_memory"]["pairs"] == 32
    for measurement in [report["comparison"], report["ml_feature_memory"]]:
        assert measurement["baseline_peak_bytes"] > 0
        assert measurement["current_peak_bytes"] > 0
