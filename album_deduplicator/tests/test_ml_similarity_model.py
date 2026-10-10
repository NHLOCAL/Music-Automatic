from pathlib import Path
import tracemalloc

import numpy as np

from music_dup_lib.external.ml_similarity_model import MLSimilarityModel
from music_dup_lib.models import FolderComparisonResult, FolderInfo


class DummyPredictor:
    def __init__(self):
        self.calls = []
        self.n_jobs = -1

    def set_params(self, **kwargs):
        if "n_jobs" in kwargs:
            self.n_jobs = kwargs["n_jobs"]
        return self

    def predict(self, matrix):
        self.calls.append(matrix.copy())
        return np.asarray([101.0] * len(matrix), dtype=np.float64)


def test_ml_similarity_model_limits_runtime_threads():
    predictor = DummyPredictor()

    model = MLSimilarityModel.__new__(MLSimilarityModel)
    model.model = predictor
    model.max_prediction_threads = 3

    model._configure_model_runtime()

    assert predictor.n_jobs == 3


def test_ml_similarity_model_batches_numpy_predictions(monkeypatch):
    predictor = DummyPredictor()

    model = MLSimilarityModel.__new__(MLSimilarityModel)
    model.model = predictor
    model.model_loaded = True
    model.prediction_batch_size = 2
    model._folder_feature_cache = {}

    feature_rows = [
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
        [7.0, 8.0, 9.0],
    ]

    row_iter = iter(feature_rows)
    monkeypatch.setattr(model, "_build_feature_vector", lambda *args, **kwargs: next(row_iter))

    pair = FolderComparisonResult(folder1_path=Path("C:/music/A"), folder2_path=Path("D:/music/B"))
    pair_inputs = [
        (object(), object(), pair),
        (object(), object(), pair),
        (object(), object(), pair),
    ]

    scores = model.predict_similarities_for_pairs(pair_inputs)

    assert scores == [100.0, 100.0, 100.0]
    assert [call.shape for call in predictor.calls] == [(2, 3), (1, 3)]


def test_ml_feature_memory_is_bounded_by_prediction_batch():
    class BitratePredictor:
        def predict(self, matrix):
            return matrix[:, 0]

    model = MLSimilarityModel.__new__(MLSimilarityModel)
    model.model = BitratePredictor()
    model.model_loaded = True
    model.prediction_batch_size = 32
    model._folder_feature_cache = {}
    left = FolderInfo(path=Path("A"), folder_name="A", parent_folder_name="", avg_bitrate=44.0)
    right = FolderInfo(path=Path("B"), folder_name="B", parent_folder_name="", avg_bitrate=88.0)
    pair = FolderComparisonResult(folder1_path=left.path, folder2_path=right.path)
    pair_inputs = [(left, right, pair)] * 4096

    tracemalloc.start()
    try:
        scores = model.predict_similarities_for_pairs(pair_inputs)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert scores == [44.0] * 4096
    # 4096 full feature rows require many MB; 32 rows and scores fit comfortably.
    assert peak_bytes < 2_000_000


def test_ml_batches_preserve_invalid_pair_positions_and_sanitize_features():
    class BitratePredictor:
        def predict(self, matrix):
            assert np.isfinite(matrix).all()
            return matrix[:, 0]

    model = MLSimilarityModel.__new__(MLSimilarityModel)
    model.model = BitratePredictor()
    model.model_loaded = True
    model.prediction_batch_size = 2
    model._folder_feature_cache = {}
    right = FolderInfo(path=Path("B"), folder_name="B", parent_folder_name="")
    pair_inputs = []
    for index, bitrate in enumerate([12.0, 13.0, np.nan, 101.0, -5.0]):
        left = FolderInfo(path=Path(str(index)), folder_name=str(index), parent_folder_name="", avg_bitrate=bitrate)
        pair = FolderComparisonResult(folder1_path=left.path, folder2_path=right.path)
        if index == 1:
            pair.similarity_scores["additional_metadata_details"] = {"date": None}
        pair_inputs.append((left, right, pair))

    assert model.predict_similarities_for_pairs(pair_inputs) == [12.0, None, 0.0, 100.0, 0.0]


def test_ml_prediction_failure_retains_only_completed_batch_scores():
    class FailingPredictor:
        def predict(self, matrix):
            if matrix[0, 0] == 14.0:
                raise ValueError("Prediction unavailable")
            return matrix[:, 0]

    model = MLSimilarityModel.__new__(MLSimilarityModel)
    model.model = FailingPredictor()
    model.model_loaded = True
    model.prediction_batch_size = 2
    model._folder_feature_cache = {}
    right = FolderInfo(path=Path("B"), folder_name="B", parent_folder_name="")
    pair_inputs = []
    for index, bitrate in enumerate([12.0, 13.0, 14.0, 15.0, 16.0]):
        left = FolderInfo(path=Path(str(index)), folder_name=str(index), parent_folder_name="", avg_bitrate=bitrate)
        pair = FolderComparisonResult(folder1_path=left.path, folder2_path=right.path)
        pair_inputs.append((left, right, pair))

    assert model.predict_similarities_for_pairs(pair_inputs) == [12.0, 13.0, None, None, None]
