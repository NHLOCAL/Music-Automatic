from pathlib import Path

from music_dup_lib.performance_benchmark import (
    BenchmarkRecorder,
    format_seconds,
    render_stage_metrics,
    write_benchmark_report,
)


class DummyCounts:
    def __init__(self):
        self.folders = 3
        self.compared_pairs = 5
        self.safe_clusters = 1
        self.review_clusters = 2


class DummySnapshot:
    def __init__(self):
        self.counts = DummyCounts()


class DummyOptions:
    def __init__(self):
        self.folders = [Path("C:/music")]
        self.preferred_root = None
        self.bitrate_mode = "128"
        self.force_rescan = False
        self.clear_cache = False
        self.gemini_enabled = False
        self.disable_hash = False
        self.full_hash_scan = False


class DummyRunResult:
    def __init__(self):
        self.snapshot = DummySnapshot()
        self.wall_time_seconds = 12.5
        self.stage_metrics = []
        self.progress_metrics = []
        self.cprofile_text = "profile output"


def test_benchmark_recorder_sorts_stage_metrics_descending():
    recorder = BenchmarkRecorder()
    recorder.record_stage_duration("scan", 2.0)
    recorder.record_stage_duration("scoring", 1.0)
    recorder.record_stage_duration("scan", 0.5)

    metrics = recorder.build_stage_metrics()

    assert [metric.label for metric in metrics] == ["scan", "scoring"]
    assert metrics[0].duration_seconds == 2.5
    assert metrics[0].call_count == 2


def test_format_seconds_handles_minutes():
    assert format_seconds(12.34) == "12.34s"
    assert format_seconds(65.2) == "1m 05.20s"


def test_render_stage_metrics_includes_calls():
    recorder = BenchmarkRecorder()
    recorder.record_stage_duration("scan", 2.0)

    rendered = render_stage_metrics(recorder.build_stage_metrics())

    assert "scan" in rendered
    assert "calls=1" in rendered


def test_write_benchmark_report_creates_markdown(tmp_path):
    output_path = tmp_path / "benchmark.md"

    write_benchmark_report(output_path, DummyRunResult(), DummyOptions())

    content = output_path.read_text(encoding="utf-8")
    assert "# Album Deduplicator Benchmark Report" in content
    assert "profile output" in content
    assert "compared_pairs: 5" in content
