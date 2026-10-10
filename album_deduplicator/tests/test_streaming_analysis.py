from copy import deepcopy
from pathlib import Path

from music_dup_lib.models import FileInfo, FolderComparisonResult, FolderInfo
from music_dup_lib.services.scoring_service import ScoringService


def test_scoring_stream_is_bounded_and_matches_list(monkeypatch):
    folders = {}
    for name in ("a", "b", "c"):
        path = Path(name)
        folders[path] = FolderInfo(
            path=path, folder_name=name, parent_folder_name="",
            files=[FileInfo(filename="song.mp3", filepath=path / "song.mp3",
                            extension=".mp3", size_mb=1)],
        )
    comparisons = [
        FolderComparisonResult(Path("a"), Path("b"), {"title": 0.8}, weighted_score=81),
        FolderComparisonResult(Path("b"), Path("c"), {"title": 1.0}, weighted_score=100,
                               is_identical_by_hash=True),
        FolderComparisonResult(Path("a"), Path("c"), {"title": 0.1}, weighted_score=10),
    ]
    service = ScoringService()
    service.ml_model.model_loaded = True
    service.ml_model.prediction_batch_size = 2
    monkeypatch.setattr(service.ml_model, "predict_similarities_for_pairs",
                        lambda pairs: [item[2].weighted_score for item in pairs])
    expected_cache = []
    expected = service.apply_scores(deepcopy(comparisons), deepcopy(folders), {},
                                    cache_result_callback=expected_cache.append)
    consumed = []
    scored_chunks = []

    def stream():
        for comparison in deepcopy(comparisons):
            consumed.append(comparison)
            yield comparison

    def predict(pairs):
        scored_chunks.append(len(consumed))
        assert len(consumed) <= 2  # First inference must happen before the last pair is produced
        return [item[2].weighted_score for item in pairs]

    # The last low-scoring pair already has its ML score, so only the first batch predicts
    comparisons[-1].ml_similarity_score = 10
    monkeypatch.setattr(service.ml_model, "predict_similarities_for_pairs", predict)
    actual_cache = []
    progress = []
    actual = service.apply_scores(stream(), deepcopy(folders), {}, total_pairs=3,
                                  quality_folder_paths=set(folders),
                                  progress_callback=lambda *args: progress.append(args),
                                  cache_result_callback=actual_cache.append)
    assert actual == expected
    assert actual_cache == expected_cache
    assert scored_chunks == [2]
    assert service.compared_pairs_count == 3
    assert [event[2:] for event in progress if event[0] == "scoring"] == [(1, 3), (2, 3), (3, 3)]


def test_empty_scoring_stream_does_not_calculate_singleton_quality():
    path = Path("singleton")
    folder = FolderInfo(path, "singleton", "", files=[
        FileInfo("song.mp3", path / "song.mp3", ".mp3", 1),
    ])
    service = ScoringService()
    pairs, _warnings = service.apply_scores(iter(()), {path: folder}, {}, total_pairs=0,
                                            quality_folder_paths=set())
    assert pairs == {}
    assert folder.quality_score is None
    assert service.compared_pairs_count == 0


def test_scoring_keeps_unchanged_warm_cache_without_rewriting():
    first, second = Path("a"), Path("b")
    folders = {path: FolderInfo(path, path.name, "", files=[
        FileInfo("song.mp3", path / "song.mp3", ".mp3", 1),
    ]) for path in (first, second)}
    cached = FolderComparisonResult(first, second, weighted_score=85, ml_similarity_score=86)
    updates = []
    service = ScoringService()
    service.ml_model.model_loaded = False
    pairs, _ = service.apply_scores([deepcopy(cached)], folders,
                                    {frozenset(map(str, folders)): cached},
                                    cache_result_callback=updates.append)
    assert len(pairs) == 1
    assert updates == []


def test_orchestrator_stream_progress_is_monotonic_and_bounded(monkeypatch):
    from music_dup_lib.services.analysis_orchestrator import AnalysisOptions, AnalysisOrchestrator
    from music_dup_lib.services.dto import AnalysisSnapshot

    folders = {Path(str(index)): FolderInfo(Path(str(index)), str(index), "", files=[
        FileInfo("song.mp3", Path(str(index)) / "song.mp3", ".mp3", 1),
    ]) for index in range(100)}
    first, second = list(folders)[:2]

    def comparisons(self, all_folders, progress_callback=None, cached_results_map=None):
        for index in range(1, 4951):
            progress_callback(index, 4950)
            yield FolderComparisonResult(first, second, weighted_score=10)

    class Store:
        def load_comparison_results(self, **kwargs):
            return {}

    monkeypatch.setattr("music_dup_lib.services.analysis_orchestrator.FolderScanner.scan_folders",
                        lambda self, roots: folders)
    monkeypatch.setattr("music_dup_lib.services.analysis_orchestrator.ComparisonEngine.iter_similar_folders",
                        comparisons)
    monkeypatch.setattr("music_dup_lib.services.scoring_service.MLSimilarityModel.__init__",
                        lambda self: (setattr(self, "model_loaded", False),
                                      setattr(self, "prediction_batch_size", 256)) and None)
    events = []
    snapshot = AnalysisOrchestrator(Store()).run(AnalysisOptions([Path("library")]), events.append)
    assert isinstance(snapshot, AnalysisSnapshot)
    assert snapshot.counts.compared_pairs == 4950
    matching = [event.current for event in events if event.step == "matching"]
    assert matching == sorted(matching)
    assert matching[-1] == 4950
    assert len(matching) <= 1002


def test_warm_analysis_matches_forced_analysis_after_file_change(monkeypatch, tmp_path):
    import os
    import wave
    from music_dup_lib.core.data_store import DataStore
    from music_dup_lib.services.analysis_orchestrator import AnalysisOptions, AnalysisOrchestrator

    def write_track(path, sample):
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(8000)
            handle.writeframes(sample * 800)

    monkeypatch.setattr("music_dup_lib.services.scoring_service.MLSimilarityModel.__init__",
                        lambda self: (setattr(self, "model_loaded", False),
                                      setattr(self, "prediction_batch_size", 2)) and None)
    for name in ("a", "b"):
        album = tmp_path / name
        album.mkdir()
        for index in range(3):
            write_track(album / f"{index}.wav", b"\x00\x01")
    store = DataStore(tmp_path / "music.json", tmp_path / "pairs.pkl")
    orchestrator = AnalysisOrchestrator(store)
    initial = orchestrator.run(AnalysisOptions([tmp_path], full_hash_scan=True))
    assert next(iter(initial.pairs.values())).is_identical_by_hash
    changed = tmp_path / "b" / "0.wav"
    previous = changed.stat()
    write_track(changed, b"\x01\x02")
    os.utime(changed, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1000000000))
    warm = orchestrator.run(AnalysisOptions([tmp_path], full_hash_scan=True))
    forced = orchestrator.run(AnalysisOptions([tmp_path], full_hash_scan=True, force_rescan=True))
    assert not any(pair.is_identical_by_hash for pair in warm.pairs.values())
    assert warm == forced
