"""Offline semantic validation and synthetic performance comparison against a local tag.

Only reads Git source and the local ML model. It never scans music or opens caches.
Baseline modules intentionally use today's shared models, configuration and helpers
to isolate the comparison, ML batching and scoring changes being measured.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import gc
import itertools
import json
import logging
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
import types
import warnings

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from music_dup_lib.core.comparison_engine import ComparisonEngine
from music_dup_lib.external.ml_similarity_model import MLSimilarityModel
from music_dup_lib.models import FileInfo, FolderComparisonResult, FolderInfo
from music_dup_lib.services.scoring_service import ScoringService


def load_baseline(relative_path: str, ref: str) -> types.ModuleType:
    module_name = "music_dup_lib." + relative_path.replace("/", ".").removesuffix(".py") + "_performance_baseline"
    source = subprocess.check_output(
        ["git", "show", f"{ref}:album_deduplicator/music_dup_lib/{relative_path}"],
        cwd=PROJECT_DIR.parent, text=True, encoding="utf-8",
    )
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    exec(compile(source, module_name, "exec"), module.__dict__)
    return module


def make_folder(index: int, track_count: int) -> FolderInfo:
    path = Path("synthetic_library") / f"Album {index}"
    files = [FileInfo(
        filename=f"{track:02d} Track {track}.mp3", filepath=path / f"{track:02d} Track {track}.mp3",
        extension=".mp3", size_mb=5.0 + track, duration=180.0 + track, bitrate=320,
        title=f"Song {track}", artist="Artist", album="Album", albumartist="Artist",
        all_tags={"date": "1999", "genre": "Pop"}, metadata_complete=True, has_lyrics=True,
    ) for track in range(track_count)]
    return FolderInfo(
        path=path, folder_name=path.name, parent_folder_name=path.parent.name, files=files,
        album_art_hash="art", other_files=[{"name": "cover.jpg", "size_bytes": 2048, "hash": "cover"}],
        avg_bitrate=320.0, unique_artists={"Artist"}, unique_albums={"Album"},
        generic_filename_score=0.1, generic_title_score=0.1,
        hebrew_metadata_ratio=1.0, metadata_completeness_ratio=1.0, lyrics_ratio=1.0,
    )


def randomized_folders(count: int, tracks: int, seed: int) -> list[FolderInfo]:
    rng = random.Random(seed)
    folders = [make_folder(index, rng.choice([0, 1, 3, tracks])) for index in range(count)]
    for folder in folders:
        folder.generic_filename_score = rng.choice([0.0, 0.5, 0.9])
        folder.generic_title_score = rng.choice([0.0, 0.5, 0.9])
        folder.file_hashes_present = rng.choice([True, False])
        folder.other_files = rng.choice([[], [{"name": "cover.jpg", "size_bytes": rng.choice([0, 10, 100]),
                                              "hash": rng.choice([None, "a", "b"])}]])
        for track in folder.files:
            track.size_mb = rng.choice([0.0, 1.0, 1.05, 2.0])
            track.duration = rng.choice([None, 0.0, 180.0, 188.0, 220.0])
            track.file_hash = rng.choice([None, "a", "b"])
            track.title = rng.choice([None, "", "Song", " SONG ", "שיר"])
            track.all_tags = {"date": rng.choice([None, " 1999 ", "2001"]),
                              "genre": rng.choice([None, "", "Pop"]), "tracknumber": rng.choice([1, 2])}
    return folders


def validate_parity(old_compare, old_ml, old_scoring, args) -> dict:
    folders = randomized_folders(args.validation_folders, args.tracks, args.seed)
    cases = 0
    for hashing in (True, False):
        baseline, current = old_compare(hashing), ComparisonEngine(hashing)
        for left, right in itertools.permutations(folders, 2):
            expected = baseline.compare_two_folders(left, right)
            actual = current.compare_two_folders(left, right)
            assert (asdict(expected) if expected else None) == (asdict(actual) if actual else None)
            if expected:
                assert list(expected.similarity_scores) == list(actual.similarity_scores)
            cases += 1

    current_model = MLSimilarityModel()
    if not current_model.model_loaded:
        raise RuntimeError("A working local ML model is required for exact prediction validation")
    baseline_model = old_ml.__new__(old_ml)
    baseline_model.model = current_model.model
    baseline_model.model_loaded = True
    baseline_model._folder_feature_cache = {}
    baseline_model.prediction_batch_size = current_model.prediction_batch_size = args.batch_size
    rng = random.Random(args.seed + 1)
    inputs = []
    for _ in range(args.validation_folders * 2):
        left, right = rng.sample(folders, 2)
        pair = FolderComparisonResult(left.path, right.path, similarity_scores={
            "file_size": rng.random(), "additional_metadata_details": {"date": rng.random()}})
        assert baseline_model._build_feature_vector(left, right, pair) == current_model._build_feature_vector(left, right, pair)
        inputs.append((left, right, pair))
    assert baseline_model.predict_similarities_for_pairs(inputs) == current_model.predict_similarities_for_pairs(inputs)

    # Use the stable list pipeline versus the current iterator pipeline, with identical
    # config, local model and quality calculation, and no remote Gemini calls.
    subset = folders[:min(len(folders), 24)]
    baseline_folders = deepcopy({folder.path: folder for folder in subset})
    folder_map = deepcopy(baseline_folders)
    baseline_service = old_scoring(use_gemini=False)
    baseline_service.ml_model = old_ml.__new__(old_ml)
    baseline_service.ml_model.model = current_model.model
    baseline_service.ml_model.model_loaded = True
    baseline_service.ml_model._folder_feature_cache = {}
    baseline_service.ml_model.prediction_batch_size = args.batch_size
    expected_pairs, expected_warnings = baseline_service.apply_scores(
        old_compare().find_similar_folders(baseline_folders), baseline_folders, {})
    counts = Counter(len(folder.files) for folder in subset if folder.files)
    total = sum(count * (count - 1) // 2 for count in counts.values())
    paths = {folder.path for folder in subset if folder.files and counts[len(folder.files)] > 1}
    current_service = ScoringService(use_gemini=False)
    current_service.ml_model.prediction_batch_size = args.batch_size
    actual_pairs, actual_warnings = current_service.apply_scores(
        ComparisonEngine().iter_similar_folders(folder_map), folder_map, {},
        total_pairs=total, quality_folder_paths=paths)
    assert {key: asdict(value) for key, value in expected_pairs.items()} == {
        key: asdict(value) for key, value in actual_pairs.items()}
    assert asdict(expected_warnings) == asdict(actual_warnings)
    return {"comparison_cases": cases, "ml_feature_prediction_cases": len(inputs),
            "real_model_loaded": True, "streaming_scoring": True, "scoring_candidates": total,
            "retained_scoring_pairs": len(actual_pairs)}


def peak_allocations(run) -> int:
    gc.collect()
    tracemalloc.start()
    try:
        run()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class BitratePredictor:
    """Measure real feature preparation independently of native model allocations."""
    def predict(self, matrix):
        return matrix[:, 0]


def benchmark(old_compare, old_ml, args) -> tuple[dict, dict]:
    folder_map = {folder.path: folder for folder in
                  [make_folder(index, args.tracks) for index in range(args.benchmark_folders)]}
    baseline_times, current_times = [], []
    for repetition in range(args.repeats):
        runs = [(old_compare, baseline_times), (ComparisonEngine, current_times)]
        if repetition % 2:
            runs.reverse()
        for engine_class, timings in runs:
            gc.collect()
            start = time.perf_counter()
            results = engine_class().find_similar_folders(folder_map)
            timings.append(time.perf_counter() - start)
            del results
    baseline_peak = peak_allocations(lambda: old_compare().find_similar_folders(folder_map))
    current_peak = peak_allocations(lambda: sum(1 for _ in ComparisonEngine().iter_similar_folders(folder_map)))
    comparison = {"folders": args.benchmark_folders, "tracks": args.tracks,
                  "pairs": args.benchmark_folders * (args.benchmark_folders - 1) // 2,
                  "baseline_median_seconds": statistics.median(baseline_times),
                  "current_median_seconds": statistics.median(current_times),
                  "baseline_peak_bytes": baseline_peak, "current_peak_bytes": current_peak}
    left, right = make_folder(0, args.tracks), make_folder(1, args.tracks)
    inputs = [(left, right, FolderComparisonResult(left.path, right.path))] * args.ml_pairs

    def run_features(model_class):
        model = model_class.__new__(model_class)
        model.model = BitratePredictor()
        model.model_loaded = True
        model.prediction_batch_size = args.batch_size
        model._folder_feature_cache = {}
        assert model.predict_similarities_for_pairs(inputs) == [100.0] * args.ml_pairs

    ml_memory = {"pairs": args.ml_pairs, "batch_size": args.batch_size,
                 "baseline_peak_bytes": peak_allocations(lambda: run_features(old_ml)),
                 "current_peak_bytes": peak_allocations(lambda: run_features(MLSimilarityModel))}
    return comparison, ml_memory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="album-deduplicator-v0.1.1")
    parser.add_argument("--seed", type=int, default=42)
    for name, default in [("validation-folders", 100), ("benchmark-folders", 200),
                          ("tracks", 12), ("ml-pairs", 4096), ("batch-size", 32), ("repeats", 5)]:
        parser.add_argument(f"--{name}", type=int, default=default)
    args = parser.parse_args()
    if min(args.validation_folders, args.benchmark_folders) < 2 or min(
            args.tracks, args.ml_pairs, args.batch_size, args.repeats) < 1:
        parser.error("At least two folders and positive tracks, pairs, batch size and repeats are required")
    logging.disable(logging.CRITICAL)
    warnings.filterwarnings("ignore", message="X does not have valid feature names")
    old_compare = load_baseline("core/comparison_engine.py", args.baseline_ref).ComparisonEngine
    old_ml = load_baseline("external/ml_similarity_model.py", args.baseline_ref).MLSimilarityModel
    old_scoring = load_baseline("services/scoring_service.py", args.baseline_ref).ScoringService
    parity = validate_parity(old_compare, old_ml, old_scoring, args)
    comparison, ml_memory = benchmark(old_compare, old_ml, args)
    print(json.dumps({"baseline_ref": args.baseline_ref, "seed": args.seed,
                      "measurement_scope": "Synthetic Python allocations; excludes native memory and real library IO",
                      "baseline_dependencies": "Current shared configuration, models and helpers",
                      "parity": parity, "comparison": comparison, "ml_feature_memory": ml_memory}, indent=2))


if __name__ == "__main__":
    main()
