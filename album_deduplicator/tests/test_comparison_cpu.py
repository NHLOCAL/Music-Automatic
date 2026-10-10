import logging
from pathlib import Path

from music_dup_lib.core.comparison_engine import ComparisonEngine
from test_comparison_engine import make_folder


def test_disabled_debug_does_not_format_pair_paths(monkeypatch, caplog):
    first, second = make_folder("a", 12), make_folder("b", 12)
    caplog.set_level(logging.INFO, logger="music_dup_lib.core.comparison_engine")
    original = Path.name.fget
    names = []

    def counted_name(path):
        names.append(str(path))
        return original(path)

    monkeypatch.setattr(Path, "name", property(counted_name))
    result = ComparisonEngine().compare_two_folders(first, second)
    assert result is not None
    assert names == []


def test_debug_still_reports_hash_and_boost_details(caplog):
    caplog.set_level(logging.DEBUG, logger="music_dup_lib.core.comparison_engine")
    result = ComparisonEngine().compare_two_folders(make_folder("a", 12), make_folder("b", 12))
    assert result is not None
    assert "not all music files have hashes" in caplog.text
    assert "Comparison Details (a vs b)" in caplog.text
    assert "Boosting score" in caplog.text


def test_track_ratio_calculation_avoids_repeated_min_max_calls(monkeypatch):
    from music_dup_lib.core import comparison_engine as module

    first, second = make_folder("a", 12), make_folder("b", 12)
    for track in second.files:
        track.size_mb += 0.01
        track.duration += 0.01
    calls = []

    def counted_min(*values):
        calls.append("min")
        return min(*values)

    def counted_max(*values):
        calls.append("max")
        return max(*values)

    monkeypatch.setattr(module, "min", counted_min, raising=False)
    monkeypatch.setattr(module, "max", counted_max, raising=False)
    result = ComparisonEngine().compare_two_folders(first, second)
    assert result is not None
    assert result.similarity_scores["file_size"] == 1.0
    assert result.similarity_scores["duration"] == 1.0
    assert len(calls) <= 3
