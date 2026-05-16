import argparse
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from music_dup_lib import config, utils
from music_dup_lib.performance_benchmark import (  # noqa: E402
    format_seconds,
    render_stage_metrics,
    run_benchmark,
    write_benchmark_report,
)
from music_dup_lib.services import AnalysisOptions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a benchmark/profile analysis over the shared album deduplicator pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("folders", nargs="+", metavar="FOLDER", help="One or more root folders to scan.")
    parser.add_argument("-p", "--preferred-root", type=str, default=None, metavar="PREF_ROOT_PATH")
    parser.add_argument("-b", "--bitrate", choices=["128", "high"], default="128")
    parser.add_argument("-l", "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")
    parser.add_argument("--force-rescan", action="store_true")
    parser.add_argument("--clear-comparison-cache", action="store_true")
    parser.add_argument("--disable-hash", action="store_true")
    parser.add_argument("--full-hash-scan", action="store_true")
    parser.add_argument("--gemini-analysis", action="store_true")
    parser.add_argument("--top-functions", type=int, default=30)
    parser.add_argument("--sort-by", choices=["cumtime", "tottime", "calls"], default="cumtime")
    parser.add_argument("--report-path", type=str, default=None, help="Optional output markdown path.")
    args = parser.parse_args()

    utils.setup_logging(args.log_level, config.LOGS_DIR)

    folders = [Path(folder).resolve() for folder in args.folders]
    invalid_paths = [str(folder) for folder in folders if not folder.is_dir()]
    if invalid_paths:
        print("Invalid input folders:")
        for folder in invalid_paths:
            print(f"  - {folder}")
        return 1

    preferred_root = Path(args.preferred_root).resolve() if args.preferred_root else None
    if preferred_root and preferred_root not in folders:
        print("Preferred root must be one of the input folders.")
        return 1

    options = AnalysisOptions(
        folders=folders,
        preferred_root=preferred_root,
        bitrate_mode=args.bitrate,
        force_rescan=args.force_rescan,
        clear_cache=args.clear_comparison_cache,
        gemini_enabled=args.gemini_analysis,
        disable_hash=args.disable_hash,
        full_hash_scan=args.full_hash_scan,
    )
    run_result = run_benchmark(
        options,
        sort_by=args.sort_by,
        top_functions=args.top_functions,
    )

    print(f"Wall time: {format_seconds(run_result.wall_time_seconds)}")
    print(
        "Counts: "
        f"folders={run_result.snapshot.counts.folders}, "
        f"compared_pairs={run_result.snapshot.counts.compared_pairs}, "
        f"safe_clusters={run_result.snapshot.counts.safe_clusters}, "
        f"review_clusters={run_result.snapshot.counts.review_clusters}"
    )
    print("\nStage timings:")
    print(render_stage_metrics(run_result.stage_metrics))
    print("\nTop cProfile functions:")
    print(run_result.cprofile_text.rstrip())

    report_path = Path(args.report_path) if args.report_path else (
        config.LOGS_DIR
        / "benchmarks"
        / f"benchmark-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    )
    write_benchmark_report(report_path, run_result, options)
    print(f"\nReport written to: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
