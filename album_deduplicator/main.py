import argparse
import logging
import sys
from pathlib import Path

from music_dup_lib import config, utils
from music_dup_lib.services import AnalysisOptions, AnalysisOrchestrator, DeletionService


def _print_progress(event):
    total = max(event.total, 1)
    percent = (event.current / total) * 100
    sys.stdout.write(f"\r[{event.step:<10}] {event.message} {percent:6.2f}%")
    sys.stdout.flush()
    if event.step == "complete":
        sys.stdout.write("\n")


def _print_cluster(snapshot, cluster):
    print(
        f"\n[{cluster.confidence_bucket.upper()}] Cluster {cluster.cluster_id} | "
        f"keeper={cluster.recommended_keeper_id or 'none'}"
    )
    for reason in cluster.reasons:
        print(f"  - {reason.message}")
    for folder_id in cluster.folder_ids:
        album = snapshot.albums[folder_id]
        quality = f"{album.quality_score:.1f}%" if album.quality_score is not None else "N/A"
        marker = "KEEP" if folder_id == cluster.recommended_keeper_id else "DROP"
        print(f"  {marker:<4} {album.name} | Q={quality} | {album.path}")
    for pair_id in cluster.pair_ids:
        pair = snapshot.pairs[pair_id]
        print(
            f"    pair {pair.pair_id}: final={pair.final_score:.2f} "
            f"base={pair.base_score:.2f} algo={pair.algorithmic_score:.2f} "
            f"ml={pair.ml_score if pair.ml_score is not None else 'n/a'}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Album Deduplicator CLI powered by the shared analysis orchestrator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("folders", nargs="+", metavar="FOLDER", help="One or more root folders to scan.")
    parser.add_argument("-l", "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=config.DEFAULT_LOG_LEVEL)
    parser.add_argument("-p", "--preferred-root", type=str, default=None, metavar="PREF_ROOT_PATH")
    parser.add_argument("-b", "--bitrate", choices=["128", "high"], default="128")
    parser.add_argument("-d", "--disable-hash", action="store_true")
    parser.add_argument("-r", "--force-rescan", action="store_true")
    parser.add_argument("-c", "--clear-comparison-cache", action="store_true")
    parser.add_argument("-g", "--gemini-analysis", action="store_true")
    parser.add_argument("--show-all", action="store_true", help="Print review clusters too.")
    args = parser.parse_args()

    utils.setup_logging(args.log_level, config.LOGS_DIR)
    logger = logging.getLogger(__name__)

    folders = [Path(folder).resolve() for folder in args.folders]
    invalid_paths = [str(folder) for folder in folders if not folder.is_dir()]
    if invalid_paths:
        print("Invalid input folders:")
        for folder in invalid_paths:
            print(f"  - {folder}")
        if len(invalid_paths) == len(folders):
            sys.exit(1)
        folders = [folder for folder in folders if folder.is_dir()]

    preferred_root = Path(args.preferred_root).resolve() if args.preferred_root else None
    if preferred_root and preferred_root not in folders:
        print("Preferred root must be one of the input folders.")
        sys.exit(1)

    orchestrator = AnalysisOrchestrator()
    snapshot = orchestrator.run(
        AnalysisOptions(
            folders=folders,
            preferred_root=preferred_root,
            bitrate_mode=args.bitrate,
            force_rescan=args.force_rescan,
            clear_cache=args.clear_comparison_cache,
            gemini_enabled=args.gemini_analysis,
            disable_hash=args.disable_hash,
        ),
        progress_handler=_print_progress,
    )

    print(
        f"\nScanned folders: {snapshot.counts.folders} | "
        f"Compared pairs: {snapshot.counts.compared_pairs} | "
        f"Safe clusters: {snapshot.counts.safe_clusters} | "
        f"Review clusters: {snapshot.counts.review_clusters}"
    )
    for warning in snapshot.warnings.warnings:
        print(f"Warning: {warning}")

    for cluster in snapshot.clusters.values():
        if cluster.confidence_bucket == "review" and not args.show_all:
            continue
        _print_cluster(snapshot, cluster)

    decisions = {
        cluster_id: cluster.recommended_keeper_id if cluster.confidence_bucket == "safe" else None
        for cluster_id, cluster in snapshot.clusters.items()
    }
    preview = DeletionService().build_preview(snapshot.clusters, snapshot.albums, decisions)
    if preview.total_count:
        print(f"\nSafe delete preview ({preview.total_count} folders):")
        for item in preview.items:
            print(f"  - delete {item.folder_path} | keep {item.keeper_folder_path}")
    else:
        print("\nNo folders qualified for safe delete preview.")

    logger.info("CLI analysis completed successfully.")


if __name__ == "__main__":
    main()

