"""Measure comparison CPU separately from scanning, ML, progress events and disk writes.

Alternates old/new runs and resets string caches on every run. Optional music cache
input is read only; no music files are opened and no caches are rewritten.
"""
import argparse
import cProfile
import gc
import io
from itertools import zip_longest
import json
import logging
from pathlib import Path
import pstats
import random
import statistics
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from validate_performance import load_baseline, make_folder
from music_dup_lib.core.comparison_engine import ComparisonEngine
from music_dup_lib.core.folder_scanner import FolderScanner
from music_dup_lib.utils import cached_string_similarity


def synthetic_folders(workload, count, tracks):
    folders = [make_folder(index, tracks) for index in range(count)]
    if workload != "shared":
        for index, folder in enumerate(folders):
            artist = index % 30 if workload == "mixed" else index
            album = index % 100 if workload == "mixed" else index
            for track_index, track in enumerate(folder.files):
                track.artist = track.albumartist = f"Artist {artist}"
                track.album = f"Album {album}"
                track.title = f"Song {album}-{track_index}"
                track.size_mb += (index % 7) * 0.001
                track.duration += (index % 5) * 0.01
    return {folder.path: folder for folder in folders}


def cache_folders(path, count, seed):
    with path.open(encoding="utf-8") as handle:
        records = json.load(handle)
    eligible_keys = [key for key, value in records.items()
                     if isinstance(value, dict) and value.get("files") and "path" in value]
    keys = random.Random(seed).sample(eligible_keys, min(count, len(eligible_keys)))
    scanner = FolderScanner.__new__(FolderScanner)
    # Drop unselected records before preparing the sample; loading is outside timing.
    selected = [records[key] for key in keys]
    del records
    folders = [scanner._folder_info_from_dict(record) for record in selected]
    return {folder.path: folder for folder in folders}


def results(engine_class, folders):
    engine = engine_class()
    if hasattr(engine, "iter_similar_folders"):
        return engine.iter_similar_folders(folders)
    return iter(engine.find_similar_folders(folders))


def measure(workload, folders, baseline, repeats, profile):
    sentinel = object()
    count = 0
    for old, new in zip_longest(results(baseline, folders), results(ComparisonEngine, folders), fillvalue=sentinel):
        if old != new:
            raise AssertionError(f"Comparison result differs in {workload} at pair {count}")
        if list(old.similarity_scores) != list(new.similarity_scores):
            raise AssertionError("Score presentation order changed")
        if list(old.similarity_scores.get("additional_metadata_details", {})) != list(
                new.similarity_scores.get("additional_metadata_details", {})):
            raise AssertionError("Additional metadata presentation order changed")
        count += 1
    timings = [[], []]
    for repeat in range(repeats):
        for index in ((0, 1) if repeat % 2 == 0 else (1, 0)):
            gc.collect()
            cached_string_similarity.cache_clear()
            started = time.perf_counter()
            actual_count = sum(1 for _ in results((baseline, ComparisonEngine)[index], folders))
            timings[index].append(time.perf_counter() - started)
            assert actual_count == count
    before, after = map(statistics.median, timings)
    report = {"workload": workload, "folders": len(folders), "exactly_equal_pairs": count,
              "before_median_seconds": before, "after_median_seconds": after,
              "speedup": before / after, "before_samples_seconds": timings[0], "after_samples_seconds": timings[1]}
    if profile:
        recorder = cProfile.Profile()
        cached_string_similarity.cache_clear()
        recorder.runcall(lambda: sum(1 for _ in results(ComparisonEngine, folders)))
        output = io.StringIO()
        pstats.Stats(recorder, stream=output).sort_stats("tottime").print_stats(15)
        report["cpu_profile"] = output.getvalue()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="24e69ab")
    parser.add_argument("--folders", type=int, default=300)
    parser.add_argument("--tracks", type=int, default=12)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cache-file", type=Path)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--workloads", nargs="+", choices=["shared", "mixed", "diverse"],
                        default=["shared", "mixed", "diverse"])
    args = parser.parse_args()
    if args.folders < 2 or min(args.tracks, args.repeats) < 1:
        parser.error("Require at least two folders and positive tracks and repeats")
    if args.cache_only and args.cache_file is None:
        parser.error("--cache-only requires --cache-file")
    logging.disable(logging.CRITICAL)
    baseline = load_baseline("core/comparison_engine.py", args.baseline_ref).ComparisonEngine
    measurements = [] if args.cache_only else [
        measure(workload, synthetic_folders(workload, args.folders, args.tracks),
                baseline, args.repeats, args.profile) for workload in args.workloads]
    if args.cache_file:
        measurements.append(measure("cached_library_sample", cache_folders(args.cache_file, args.folders, args.seed),
                                    baseline, args.repeats, args.profile))
    print(json.dumps({"baseline_ref": args.baseline_ref, "repeats": args.repeats, "seed": args.seed,
                      "scope": "Comparison CPU only; current shared config/models/helpers; cache input is a historical snapshot",
                      "measurements": measurements}, indent=2))


if __name__ == "__main__":
    main()
