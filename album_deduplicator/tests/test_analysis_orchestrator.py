from pathlib import Path

from music_dup_lib.models import FolderComparisonResult, FolderInfo
from music_dup_lib.services.analysis_orchestrator import AnalysisOptions, AnalysisOrchestrator
from music_dup_lib.services.dto import AnalysisSnapshot


class DummyStore:
    def __init__(self):
        self.saved_results = None

    def load_comparison_results(self, cache_profile: str = "partial"):
        return {}

    def save_comparison_results(self, results_to_update, cache_profile: str = "partial"):
        self.saved_results = list(results_to_update)


def test_analysis_orchestrator_counts_all_compared_pairs(monkeypatch):
    store = DummyStore()
    orchestrator = AnalysisOrchestrator(data_store=store)

    folder_a = FolderInfo(path=Path("C:/music/A"), folder_name="A", parent_folder_name="music")
    folder_b = FolderInfo(path=Path("D:/music/B"), folder_name="B", parent_folder_name="music")
    comparison = FolderComparisonResult(
        folder1_path=folder_a.path,
        folder2_path=folder_b.path,
        weighted_score=40.0,
        similarity_scores={"title": 0.4},
    )

    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.FolderScanner.scan_folders",
        lambda self, folders: {folder_a.path: folder_a, folder_b.path: folder_b},
    )
    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.ComparisonEngine.find_similar_folders",
        lambda self, folders: [comparison],
    )
    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.RecommendationService.build_album_summaries",
        lambda self, folders: {},
    )
    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.RecommendationService.build_clusters",
        lambda self, folders, pairs, albums: {},
    )

    snapshot = orchestrator.run(
        AnalysisOptions(folders=[Path("C:/music"), Path("D:/music")]),
    )

    assert isinstance(snapshot, AnalysisSnapshot)
    assert snapshot.counts.compared_pairs == 1
    assert snapshot.pairs == {}
    assert store.saved_results is not None
    assert len(store.saved_results) == 1
    assert store.saved_results[0].similarity_scores == {}
