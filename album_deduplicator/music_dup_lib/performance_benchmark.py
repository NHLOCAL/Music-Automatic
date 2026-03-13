from __future__ import annotations

import cProfile
import io
import pstats
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional
from unittest.mock import patch

from .core.data_store import DataStore
from .core.folder_scanner import FolderScanner
from .core.comparison_engine import ComparisonEngine
from .services.analysis_orchestrator import AnalysisOptions, AnalysisOrchestrator
from .services.recommendation_service import RecommendationService
from .services.scoring_service import ScoringService


@dataclass(slots=True)
class StageMetric:
    label: str
    duration_seconds: float
    call_count: int


@dataclass(slots=True)
class ProgressMetric:
    step: str
    stage: str
    message: str
    current: int
    total: int
    elapsed_seconds: float


@dataclass(slots=True)
class BenchmarkRunResult:
    snapshot: object
    wall_time_seconds: float
    stage_metrics: List[StageMetric]
    progress_metrics: List[ProgressMetric]
    cprofile_text: str


class BenchmarkRecorder:
    def __init__(self) -> None:
        self._stage_totals: Dict[str, float] = {}
        self._stage_calls: Dict[str, int] = {}
        self._run_start = time.perf_counter()
        self.progress_metrics: List[ProgressMetric] = []

    def record_stage_duration(self, label: str, duration_seconds: float) -> None:
        self._stage_totals[label] = self._stage_totals.get(label, 0.0) + duration_seconds
        self._stage_calls[label] = self._stage_calls.get(label, 0) + 1

    def record_progress_event(self, event: object) -> None:
        self.progress_metrics.append(
            ProgressMetric(
                step=getattr(event, "step", ""),
                stage=getattr(event, "stage", ""),
                message=getattr(event, "message", ""),
                current=getattr(event, "current", 0),
                total=getattr(event, "total", 0),
                elapsed_seconds=time.perf_counter() - self._run_start,
            )
        )

    def build_stage_metrics(self) -> List[StageMetric]:
        return [
            StageMetric(
                label=label,
                duration_seconds=self._stage_totals[label],
                call_count=self._stage_calls[label],
            )
            for label in sorted(self._stage_totals, key=self._stage_totals.get, reverse=True)
        ]


def format_seconds(seconds: float) -> str:
    if seconds >= 60:
        minutes, remainder = divmod(seconds, 60.0)
        return f"{int(minutes)}m {remainder:05.2f}s"
    return f"{seconds:.2f}s"


def render_stage_metrics(stage_metrics: Iterable[StageMetric]) -> str:
    lines = []
    for metric in stage_metrics:
        lines.append(
            f"{metric.label:<28} {format_seconds(metric.duration_seconds):>10}  calls={metric.call_count}"
        )
    return "\n".join(lines)


def render_progress_metrics(progress_metrics: Iterable[ProgressMetric]) -> str:
    lines = []
    for metric in progress_metrics:
        total = max(metric.total, 1)
        percent = (metric.current / total) * 100
        lines.append(
            f"{format_seconds(metric.elapsed_seconds):>10}  "
            f"{metric.step:<10} {percent:6.2f}%  {metric.message}"
        )
    return "\n".join(lines)


def _make_timed_method(
    label: str,
    recorder: BenchmarkRecorder,
    original: Callable[..., object],
) -> Callable[..., object]:
    def wrapped(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            recorder.record_stage_duration(label, time.perf_counter() - started)

    return wrapped


def run_benchmark(
    options: AnalysisOptions,
    *,
    sort_by: str = "cumtime",
    top_functions: int = 30,
) -> BenchmarkRunResult:
    recorder = BenchmarkRecorder()
    orchestrator = AnalysisOrchestrator()
    profiler = cProfile.Profile()

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                DataStore,
                "load_data",
                new=_make_timed_method("data_store.load_data", recorder, DataStore.load_data),
            )
        )
        stack.enter_context(
            patch.object(
                DataStore,
                "save_data",
                new=_make_timed_method("data_store.save_data", recorder, DataStore.save_data),
            )
        )
        stack.enter_context(
            patch.object(
                DataStore,
                "load_comparison_results",
                new=_make_timed_method(
                    "data_store.load_comparison_results",
                    recorder,
                    DataStore.load_comparison_results,
                ),
            )
        )
        stack.enter_context(
            patch.object(
                DataStore,
                "save_comparison_results",
                new=_make_timed_method(
                    "data_store.save_comparison_results",
                    recorder,
                    DataStore.save_comparison_results,
                ),
            )
        )
        stack.enter_context(
            patch.object(
                FolderScanner,
                "scan_folders",
                new=_make_timed_method("scanner.scan_folders", recorder, FolderScanner.scan_folders),
            )
        )
        stack.enter_context(
            patch.object(
                FolderScanner,
                "_process_folder_candidate",
                new=_make_timed_method(
                    "scanner.process_folder_candidate",
                    recorder,
                    FolderScanner._process_folder_candidate,
                ),
            )
        )
        stack.enter_context(
            patch.object(
                ComparisonEngine,
                "find_similar_folders",
                new=_make_timed_method(
                    "comparison.find_similar_folders",
                    recorder,
                    ComparisonEngine.find_similar_folders,
                ),
            )
        )
        stack.enter_context(
            patch.object(
                ComparisonEngine,
                "compare_two_folders",
                new=_make_timed_method(
                    "comparison.compare_two_folders",
                    recorder,
                    ComparisonEngine.compare_two_folders,
                ),
            )
        )
        stack.enter_context(
            patch.object(
                ScoringService,
                "apply_scores",
                new=_make_timed_method("scoring.apply_scores", recorder, ScoringService.apply_scores),
            )
        )
        stack.enter_context(
            patch.object(
                RecommendationService,
                "build_album_summaries",
                new=_make_timed_method(
                    "recommendation.build_album_summaries",
                    recorder,
                    RecommendationService.build_album_summaries,
                ),
            )
        )
        stack.enter_context(
            patch.object(
                RecommendationService,
                "build_clusters",
                new=_make_timed_method(
                    "recommendation.build_clusters",
                    recorder,
                    RecommendationService.build_clusters,
                ),
            )
        )

        started = time.perf_counter()
        profiler.enable()
        try:
            snapshot = orchestrator.run(options, progress_handler=recorder.record_progress_event)
        finally:
            profiler.disable()
        wall_time_seconds = time.perf_counter() - started

    stats_stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stats_stream).sort_stats(sort_by)
    stats.print_stats(top_functions)

    return BenchmarkRunResult(
        snapshot=snapshot,
        wall_time_seconds=wall_time_seconds,
        stage_metrics=recorder.build_stage_metrics(),
        progress_metrics=recorder.progress_metrics,
        cprofile_text=stats_stream.getvalue(),
    )


def write_benchmark_report(
    output_path: Path,
    run_result: BenchmarkRunResult,
    options: AnalysisOptions,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Album Deduplicator Benchmark Report",
        "",
        "## Options",
        "",
        f"- folders: {', '.join(str(folder) for folder in options.folders)}",
        f"- preferred_root: {options.preferred_root}",
        f"- bitrate_mode: {options.bitrate_mode}",
        f"- force_rescan: {options.force_rescan}",
        f"- clear_cache: {options.clear_cache}",
        f"- gemini_enabled: {options.gemini_enabled}",
        f"- disable_hash: {options.disable_hash}",
        f"- full_hash_scan: {options.full_hash_scan}",
        "",
        "## Summary",
        "",
        f"- wall_time: {format_seconds(run_result.wall_time_seconds)}",
        f"- scanned_folders: {run_result.snapshot.counts.folders}",
        f"- compared_pairs: {run_result.snapshot.counts.compared_pairs}",
        f"- safe_clusters: {run_result.snapshot.counts.safe_clusters}",
        f"- review_clusters: {run_result.snapshot.counts.review_clusters}",
        "",
        "## Stage Timings",
        "",
        "```text",
        render_stage_metrics(run_result.stage_metrics),
        "```",
        "",
        "## Progress Timeline",
        "",
        "```text",
        render_progress_metrics(run_result.progress_metrics),
        "```",
        "",
        "## cProfile",
        "",
        "```text",
        run_result.cprofile_text.rstrip(),
        "```",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
