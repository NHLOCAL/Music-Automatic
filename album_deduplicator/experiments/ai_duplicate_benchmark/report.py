"""Readable, portable reports from measured responses only (standard library)."""
from __future__ import annotations

import html
import json
import argparse
from pathlib import Path

from .metrics import build_summary


def _metric(metric):
    if metric["value"] is None:
        return "unavailable (0 denominator)"
    return f'{metric["value"]:.1%} ({metric["numerator"]}/{metric["denominator"]})'


def _number(value, suffix=""):
    return "unknown" if value is None else f"{value:.4f}{suffix}"


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(summary):
    lines = ["# AI duplicate comparison benchmark", "", f'Dataset: {summary["dataset_cases"]} cases. Reference labels: `{json.dumps(summary["label_counts"], ensure_ascii=False)}`.', "",
             "## Evidence limitations", ""]
    lines.extend(f"- {warning}" for warning in summary["warnings"])
    lines.extend(["", f'Provenance: `{json.dumps(summary["provenance_counts"], ensure_ascii=False)}`.', "",
                  f'Categories: `{json.dumps(summary.get("category_counts", {}), ensure_ascii=False)}`.', "",
                  "| Dataset split | Cases | Reference labels | Provenance |", "| --- | ---: | --- | --- |"])
    for split, counts in summary.get("split_counts", {}).items():
        lines.append(f'| {_cell(split)} | {counts["cases"]} | {_cell(json.dumps(counts["reference_labels"], ensure_ascii=False))} | {_cell(json.dumps(counts["provenance"], ensure_ascii=False))} |')
    lines.extend(["", "Reference labels derived from metadata review or synthetic rule fixtures are not user-verified audio identity. Dataset case IDs are included in summary.json.", "",
                  "## Measured quality", "", "| Model | Calls | Labeled calls | Accuracy, successful | Accuracy, all labeled attempts | Duplicate precision | Duplicate recall, all attempts | Dangerous FP different / uncertain | Decisive coverage | Failures |",
                  "| --- | ---: | ---: | --- | --- | --- | --- | ---: | --- | --- |"])
    if not summary["models"]:
        lines.append("| No measured responses | 0 | 0 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |")
    for model, m in summary["models"].items():
        fp = m["dangerous_duplicate_fp"]
        values = [model, m["attempts"], m["labeled_attempts"], _metric(m["multiclass_accuracy_successful"]), _metric(m["end_to_end_accuracy"]),
                  _metric(m["duplicate_precision"]), _metric(m["duplicate_recall_end_to_end"]), f'{fp["different"]} / {fp["uncertain"]}', _metric(m["decisive_coverage"]), _metric(m["failure_rate"])]
        lines.append("| " + " | ".join(_cell(v) for v in values) + " |")
    lines.extend(["", "## Calibration and held-out cohorts", "", "Overall tables pool recorded cases. Use the held-out test cohort for evaluation after thresholds are fixed on calibration.", "",
                  "| Split | Model | Labeled attempts | End-to-end accuracy | Dangerous cases | 95% upper bound |", "| --- | --- | ---: | --- | --- | --- |"])
    for split, models in summary.get("split_models", {}).items():
        for model, m in models.items():
            c = m["case_level"]
            bound = c["dangerous_fp_wilson95"]
            lines.append(f'| {_cell(split)} | {_cell(model)} | {m["labeled_attempts"]} | {_metric(m["end_to_end_accuracy"])} | {_metric(c["dangerous_fp_observed"])} | {"unavailable" if bound is None else f"{bound[1]:.1%}"} |')
    lines.extend(["", "## Case safety and uncertainty", "", "Any duplicate prediction across repetitions makes a different/uncertain case dangerous. Missing and failed observations cannot establish safety. Wilson intervals use unique observed cases. Different specificity requires an exact different verdict; abstention is counted separately and does not count as a correct different classification.", "",
                  "| Model | Cases | Dangerous observed cases | 95% interval | Eligible unobserved cases | All repetitions correct | Different specificity | Abstention |", "| --- | ---: | --- | --- | ---: | --- | --- | --- |"])
    for model, m in summary["models"].items():
        c = m["case_level"]
        ci = c["dangerous_fp_wilson95"]
        values = [model, m["unique_cases"], _metric(c["dangerous_fp_observed"]), "unavailable" if ci is None else f"{ci[0]:.1%} to {ci[1]:.1%}", c["unobserved_eligible_cases"], _metric(c["all_repeats_correct"]), _metric(m["specificity_different_successful"]), _metric(m["abstention_rate"])]
        lines.append("| " + " | ".join(_cell(v) for v in values) + " |")
    lines.extend(["", "## Measured cost and latency", "", "Unknown charges are never counted as free. Per-case cost includes every repetition. Latency includes observed failed calls and is measured locally, not provider advertising.", "",
                  "| Model | Known USD subtotal | Unknown cost calls | USD / 1,000 calls | USD / 1,000 cases | Latency observations | p50 seconds | p95 seconds |", "| --- | ---: | ---: | --- | --- | ---: | --- | --- |"])
    for model, m in summary["models"].items():
        c, latency = m["cost"], m["latency"]
        values = [model, _number(c["known_total_usd"]), c["unknown_attempts"], _number(c["usd_per_1000_attempts"]), _number(c["usd_per_1000_cases"]), latency["observed_attempts"], _number(latency["p50_s"]), _number(latency["p95_s"])]
        lines.append("| " + " | ".join(_cell(v) for v in values) + " |")
    lines.extend(["", "## Paired comparison", "", "Successful-case comparisons share the same cases and repetitions. The all-paired cohort retains failures. Unpaired calls are disclosed and do not enter paired accuracy.", ""])
    for comparison in summary["paired_comparisons"]:
        a, b = comparison["models"]
        lines.extend([f"### {_cell(a)} vs {_cell(b)}", "", f'Unpaired calls: `{json.dumps(comparison["unpaired_attempts"], ensure_ascii=False)}`.', "", "| Cohort | Cases | Attempts | First accuracy | Second accuracy | First-only correct cases | Second-only correct cases |", "| --- | ---: | ---: | --- | --- | ---: | ---: |"])
        for name, c in comparison["cohorts"].items():
            d = c["case_discordance"]
            lines.append(f'| {name} | {c["unique_cases"]} | {c["attempts"]} | {_metric(c["accuracy"][a])} | {_metric(c["accuracy"][b])} | {d["first_only_all_correct"]} | {d["second_only_all_correct"]} |')
        lines.append("")
    lines.extend(["## Probability diagnostics", "", "Decision probabilities are self-reported diagnostics. Chat similarity scores are excluded. Average vectors across repetitions first, then weight every case once; a case with any failed or missing probability repetition is excluded. Brier is the sum across three classes (0 to 2); NLL uses natural logarithm. These scores do not establish calibration.", "",
                  "| Model | Scored cases | Excluded cases | Mean multiclass Brier | Mean NLL | Dangerous cases with mean duplicate probability at least 95% |", "| --- | ---: | ---: | --- | --- | --- |"])
    for model, m in summary["models"].items():
        p = m["probability_diagnostics"]
        dangerous = ", ".join(f'{record["case_id"]} ({record["mean_probabilities"]["duplicate"]:.1%})' for record in p["high_confidence_dangerous_cases"]) or "none observed"
        lines.append(f'| {_cell(model)} | {p["scored_unique_cases"]} | {p["excluded_unique_cases"]} | {_number(p["mean_multiclass_brier"])} | {_number(p["mean_negative_log_likelihood"])} | {_cell(dangerous)} |')
    if summary.get("cascades"):
        lines.extend(["", "## Fixed negative-routing cascades", "", "Confident different predictions route to the cheap model; every other prediction uses fallback. This is a simulation on paired recorded calls. Calibration and test cohorts remain separate and the threshold is not optimized here.", "",
                      "| Cheap / fallback | Split | Threshold | Paired calls | Cheap routed | Missing fallback | End-to-end accuracy | Dangerous cases | USD / 1,000 cases |", "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |"])
        for cascade in summary["cascades"]:
            policy, m = cascade["policy"], cascade["metrics"]
            lines.append(f'| {_cell(policy["cheap_model"])} / {_cell(policy["fallback_model"])} | {_cell(policy["split"])} | {policy["threshold"]:.0%} | {cascade["paired_attempts"]} | {cascade["cheap_routed_attempts"]} | {cascade["missing_fallback_attempts"]} | {_metric(m["end_to_end_accuracy"])} | {_metric(m["case_level"]["dangerous_fp_observed"])} | {_number(m["cost"]["usd_per_1000_cases"])} |')
    lines.extend(["", "## Error analysis", "", "Full confusion matrices and all error case IDs are in summary.json. Tag counts may overlap. Safety counts below use unique observed cases, not repetitions.", ""])
    for model, m in summary["models"].items():
        lines.extend([f"### {_cell(model)}", ""])
        if m["missing_dataset_case_ids"]:
            lines.extend([f'Missing dataset cases: {_cell(", ".join(m["missing_dataset_case_ids"]))}', ""])
        lines.extend(["| Tag | Attempts | Unique cases | Observed cases | Dangerous / observed different-or-uncertain cases | Dangerous case IDs |", "| --- | ---: | ---: | ---: | --- | --- |"])
        for tag, t in m["tags"].items():
            lines.append(f'| {_cell(tag)} | {t["attempts"]} | {t["unique_cases"]} | {t["observed_unique_cases"]} | {_metric(t["dangerous_case_rate"])} | {_cell(", ".join(t["dangerous_case_ids"]) or "none observed")} |')
        lines.extend(["", "| Case | Repeat | Reference label | Prediction | Model reason or recorded failure |", "| --- | --- | --- | --- | --- |"])
        for error in m["errors"]:
            lines.append("| " + " | ".join(_cell(error.get(key)) for key in ("case_id", "repeat", "label", "prediction", "reason")) + " |")
        lines.append("")
    lines.extend(["## Graphs", "", "![Measured accuracy and dangerous error bound](quality.svg)", "", "![Measured cost per thousand attempts](cost.svg)", "", "![Measured latency percentiles](latency.svg)", "",
                  "## Decision", "", "This POC does not establish a stable production replacement. Review dangerous errors first, then independent held-out labels, uncertainty bounds, failures, actual cost completeness and latency. A fixed cascade must use a threshold chosen on calibration cases and report held-out results separately.", ""])
    return "\n".join(lines)


def render_svg(summary):
    """Safety-oriented chart; absent metrics never become zero-length bars."""
    models = list(summary["models"].items())
    height = 100 + 80 * len(models)
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}" role="img" aria-label="Measured benchmark quality and dangerous case error bounds">',
                '<rect width="100%" height="100%" fill="#fff"/>', '<text x="20" y="28" font-family="sans-serif" font-size="18">Measured accuracy and dangerous FP upper 95% bound</text>',
                '<text x="20" y="52" font-family="sans-serif" font-size="12">Blue: end-to-end accuracy. Red: case-level dangerous FP upper bound. Unknown is shown explicitly.</text>']
    if not models:
        elements.append('<text x="20" y="82" font-family="sans-serif">No measured responses available</text>')
    for i, (model, m) in enumerate(models):
        y = 90 + i * 80
        elements.append(f'<text x="20" y="{y}" font-family="sans-serif" font-size="12">{html.escape(model)}</text>')
        bounds = m["case_level"]["dangerous_fp_wilson95"]
        for offset, color, value in [(8, "#2463eb", m["end_to_end_accuracy"]["value"]), (30, "#dc2626", bounds[1] if bounds else None)]:
            if value is not None:
                elements.append(f'<rect x="300" y="{y + offset}" width="{value * 480:.2f}" height="15" fill="{color}"/>')
            label = "unavailable" if value is None else f"{value:.1%}"
            elements.append(f'<text x="790" y="{y + offset + 12}" font-family="sans-serif" font-size="12">{label}</text>')
    return "\n".join(elements + ["</svg>"])


def render_measurement_svg(summary, kind):
    models = list(summary["models"].items())
    if kind == "cost":
        title = "Actual reported USD per 1,000 attempts"
        explanation = "Unknown billing produces an unavailable bar; known costs include failures and repetitions."
        series = [("USD / 1,000 attempts", "#7c3aed", lambda m: m["cost"]["usd_per_1000_attempts"])]
        unit = " USD"
    elif kind == "latency":
        title = "Observed latency p50 and p95"
        explanation = "Blue: p50. Orange: p95. Observed failed calls included; unavailable timings excluded."
        series = [("p50", "#2463eb", lambda m: m["latency"]["p50_s"]), ("p95", "#ea580c", lambda m: m["latency"]["p95_s"])]
        unit = " s"
    else:
        raise ValueError("Chart kind must be cost or latency")
    maximum = max([getter(m) or 0 for _, m in models for _, _, getter in series] + [0])
    scale = maximum or 1
    step = 38 + 24 * len(series)
    height = 105 + step * len(models)
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}" role="img" aria-label="{html.escape(title)}">',
                '<rect width="100%" height="100%" fill="#fff"/>', f'<text x="20" y="28" font-family="sans-serif" font-size="18">{html.escape(title)}</text>',
                f'<text x="20" y="52" font-family="sans-serif" font-size="12">{html.escape(explanation)}</text>']
    if not models:
        elements.append('<text x="20" y="82" font-family="sans-serif">No measured responses available</text>')
    for index, (model, metrics) in enumerate(models):
        y = 85 + index * step
        elements.append(f'<text x="20" y="{y}" font-family="sans-serif" font-size="12">{html.escape(model)}</text>')
        for i, (label, color, getter) in enumerate(series):
            value = getter(metrics)
            row_y = y + 10 + i * 24
            elements.append(f'<text x="180" y="{row_y + 12}" font-family="sans-serif" font-size="11">{html.escape(label)}</text>')
            if value is not None:
                elements.append(f'<rect x="320" y="{row_y}" width="{value / scale * 440:.2f}" height="15" fill="{color}"/>')
            rendered = "unavailable" if value is None else f"{value:.4f}{unit}"
            elements.append(f'<text x="775" y="{row_y + 12}" font-family="sans-serif" font-size="12">{rendered}</text>')
    return "\n".join(elements + ["</svg>"])


def write_report(cases, rows, output_dir, cascade_pairs=None, cascade_threshold=.95):
    summary = build_summary(list(cases), list(rows), cascade_pairs=cascade_pairs, cascade_threshold=cascade_threshold)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "report.md").write_text(render_markdown(summary), encoding="utf-8")
    (directory / "quality.svg").write_text(render_svg(summary), encoding="utf-8")
    for kind in ("cost", "latency"):
        (directory / f"{kind}.svg").write_text(render_measurement_svg(summary, kind), encoding="utf-8")
    return summary


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render measured duplicate benchmark responses into Markdown, JSON and SVG")
    parser.add_argument("--dataset", required=True, type=Path, help="Dataset JSONL path")
    parser.add_argument("--records", required=True, type=Path, help="Measured response JSONL path")
    parser.add_argument("--output", required=True, type=Path, help="Report output directory")
    args = parser.parse_args(argv)
    summary = write_report(read_jsonl(args.dataset), read_jsonl(args.records), args.output)
    print(json.dumps({"output": str(args.output.resolve()), "dataset_cases": summary["dataset_cases"], "models": list(summary["models"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
