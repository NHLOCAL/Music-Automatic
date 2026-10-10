from pathlib import Path

import pytest

from music_dup_lib.services.recommendation_service import RecommendationService
from test_recommendation_service import make_folder


@pytest.mark.parametrize("enabled", [True, False])
def test_album_summaries_do_not_resolve_paths_without_active_preferences(monkeypatch, tmp_path, enabled):
    folder = make_folder(str(tmp_path / "album"), 91)
    service = RecommendationService(preferred_roots=[] if enabled else [tmp_path], use_preferred_roots=enabled)

    def forbidden(path):
        raise AssertionError("No preference match requires filesystem resolution")

    monkeypatch.setattr(service, "_normalize_path", forbidden)
    album = next(iter(service.build_album_summaries({folder.path: folder}).values()))
    assert album.in_preferred_root is False
    assert album.preferred_root_rank is None
    assert album.path == folder.path
    assert album.quality_score == 91


def test_album_preference_rank_is_calculated_once_per_folder(monkeypatch, tmp_path):
    folder = make_folder(str(tmp_path / "preferred" / "album"), 91)
    service = RecommendationService(preferred_roots=[tmp_path / "preferred"])
    original = service._normalize_path
    calls = []

    def counted(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(service, "_normalize_path", counted)
    album = next(iter(service.build_album_summaries({folder.path: folder}).values()))
    assert album.in_preferred_root is True
    assert album.preferred_root_rank == 0
    assert calls == [folder.path]
