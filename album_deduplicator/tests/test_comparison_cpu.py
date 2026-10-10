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
