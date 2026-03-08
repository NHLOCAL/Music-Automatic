from pathlib import Path

import numpy as np

from music_dup_lib.external.ml_similarity_model import MLSimilarityModel
from music_dup_lib.models import FolderComparisonResult


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
