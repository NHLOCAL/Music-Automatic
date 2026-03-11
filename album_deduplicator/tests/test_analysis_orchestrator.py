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

    def fake_ml_model_init(self):
        self.model_loaded = False
        self.prediction_batch_size = 256

    monkeypatch.setattr(
        "music_dup_lib.services.scoring_service.MLSimilarityModel.__init__",
        fake_ml_model_init,
    )

    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.FolderScanner.scan_folders",
        lambda self, folders: {folder_a.path: folder_a, folder_b.path: folder_b},
    )
    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.ComparisonEngine.find_similar_folders",
        lambda self, folders, progress_callback=None: [comparison],
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


def test_analysis_orchestrator_emits_matching_progress(monkeypatch):
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
    progress_events = []

    def fake_ml_model_init(self):
        self.model_loaded = False
        self.prediction_batch_size = 256

    monkeypatch.setattr(
        "music_dup_lib.services.scoring_service.MLSimilarityModel.__init__",
        fake_ml_model_init,
    )

    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.FolderScanner.scan_folders",
        lambda self, folders: {folder_a.path: folder_a, folder_b.path: folder_b},
    )

    def fake_find_similar_folders(self, folders, progress_callback=None):
        if progress_callback is not None:
            progress_callback(1, 1)
        return [comparison]

    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.ComparisonEngine.find_similar_folders",
        fake_find_similar_folders,
    )
    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.RecommendationService.build_album_summaries",
        lambda self, folders: {},
    )
    monkeypatch.setattr(
        "music_dup_lib.services.analysis_orchestrator.RecommendationService.build_clusters",
        lambda self, folders, pairs, albums: {},
    )

    orchestrator.run(
        AnalysisOptions(folders=[Path("C:/music"), Path("D:/music")]),
        progress_handler=progress_events.append,
    )

    assert any(event.stage == "matching" and event.current == 1 and event.total == 1 for event in progress_events)
