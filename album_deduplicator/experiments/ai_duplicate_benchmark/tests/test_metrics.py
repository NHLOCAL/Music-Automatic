import json
import xml.etree.ElementTree as ET

import pytest

from album_deduplicator.experiments.ai_duplicate_benchmark.metrics import (
    build_summary, evaluate_cascade, model_metrics, paired_comparisons, wilson,
)
from album_deduplicator.experiments.ai_duplicate_benchmark.report import main, render_measurement_svg, write_report


def case(cid, label, **kwargs):
    return {"case_id": cid, "label": label, "provenance": "reviewed", **kwargs}


def row(cid, prediction, **kwargs):
    return {"case_id": cid, "model": "m", "repeat": 0, "status": "ok", "verdict": prediction,
            "cost_usd": .01, "latency_ms": 100, **kwargs}


def test_distinct_uncertain_truth_dangerous_fp_and_failures():
    cases = [case("d", "duplicate"), case("n", "different", tags=["hard"]), case("u", "uncertain"), case("f", "different")]
    rows = [row("d", "duplicate"), row("n", "uncertain"), row("u", "duplicate"), row("f", None, status="error", cost_usd=None)]
    m = model_metrics(cases, rows)
    assert m["duplicate_precision"] == {"value": .5, "numerator": 1, "denominator": 2}
    assert m["dangerous_duplicate_fp"]["uncertain"] == 1
    assert m["specificity_different_successful"]["value"] == 0
    assert m["multiclass_accuracy_successful"]["value"] == pytest.approx(1 / 3)
    assert m["end_to_end_accuracy"]["value"] == .25
    assert m["decisive_coverage"]["value"] == .5
    assert m["failure_rate"]["value"] == .25
    assert m["cost"]["total_usd"] is None
    assert m["cost"]["known_total_usd"] == .03
    assert m["cost"]["usd_per_1000_attempts"] is None
    assert m["case_level"]["unobserved_eligible_cases"] == 1
    assert m["tags"]["hard"]["confusion"][0]["prediction"] == "uncertain"


def test_repeats_do_not_inflate_confidence_sample_and_unknown_labels():
    cases = [case("n", "different"), case("p", None)]
    rows = [row("n", "different", repeat=i) for i in range(20)] + [row("p", "duplicate")]
    m = model_metrics(cases, rows)
    assert m["case_level"]["dangerous_fp_observed"]["denominator"] == 1
    assert m["case_level"]["dangerous_fp_wilson95"][1] > .79
    assert m["labeled_attempts"] == 20
    assert m["attempts"] == 21
    assert m["cost"]["usd_per_1000_cases"] == pytest.approx(105)


def test_case_level_any_repeat_fp_is_dangerous():
    m = model_metrics([case("n", "different")], [row("n", "different"), row("n", "duplicate", repeat=1)])
    assert m["case_level"]["dangerous_case_ids"] == ["n"]
    assert m["case_level"]["all_repeats_correct"]["value"] == 0


def test_paired_success_cohort_excludes_entire_case_with_failure():
    cases = [case("n", "different"), case("d", "duplicate")]
    rows = [row(cid, truth, model=model, repeat=repeat) for cid, truth in [("n", "different"), ("d", "duplicate")] for model in ("a", "b") for repeat in range(2)]
    rows[-1]["status"] = "error"
    p = paired_comparisons(cases, rows)[0]
    assert p["cohorts"]["identical_successful_cases"]["unique_cases"] == 1
    assert p["cohorts"]["all_paired_attempts"]["accuracy"]["b"]["value"] == .75
    assert p["cohorts"]["all_paired_attempts"]["case_discordance"]["first_only_all_correct"] == 1
    with pytest.raises(ValueError, match="Duplicate attempt"):
        paired_comparisons(cases, rows + [rows[0]])
    rows.append(row("n", None, model="a", repeat=2, status="error"))
    p = paired_comparisons(cases, rows)[0]
    assert p["cohorts"]["identical_successful_cases"]["unique_cases"] == 0
    assert p["unpaired_attempts"]["a"] == 1


def test_fixed_cascade_routes_negative_only_and_bills_failed_first_call():
    cases = [case("n", "different", split="test"), case("d", "duplicate", split="test"), case("c", "different", split="calibration")]
    rows = [row("n", "different", model="cheap", probabilities={"different": .98, "duplicate": .01, "uncertain": .01}), row("n", "duplicate", model="gemini"),
            row("d", None, model="cheap", status="error"), row("d", "duplicate", model="gemini"), row("c", "different", model="cheap")]
    cascade = evaluate_cascade(cases, rows, "cheap", "gemini")
    assert cascade["paired_attempts"] == 2
    assert cascade["cheap_routed_attempts"] == 1
    assert cascade["metrics"]["end_to_end_accuracy"]["value"] == 1
    assert cascade["metrics"]["cost"]["total_usd"] == .03
    assert cascade["metrics"]["latency"]["p50_s"] == pytest.approx(.15)


def test_empty_report_and_output_formats(tmp_path):
    summary = write_report([case("n", "different")], [], tmp_path)
    assert summary["models"] == {}
    assert "No measured responses" in (tmp_path / "report.md").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["dataset_cases"] == 1
    ET.parse(tmp_path / "quality.svg")
    ET.parse(tmp_path / "cost.svg")
    ET.parse(tmp_path / "latency.svg")
    assert wilson(0, 0) is None


def test_malformed_success_is_failure_and_unknown_case_rejected():
    m = model_metrics([case("n", "different")], [row("n", "nonsense")])
    assert m["failure_rate"]["value"] == 1
    with pytest.raises(ValueError, match="unknown"):
        build_summary([], [row("n", "different")])


def test_historical_labels_excluded_but_valid_unknown_cost_verdict_counted():
    cases = [case("n", "different", label_provenance="independent_metadata_review"),
             case("h", "duplicate", label_provenance="historical_gemini")]
    m = model_metrics(cases, [row("n", "different", status="missing_cost", cost_usd=None), row("h", "different")])
    assert m["end_to_end_accuracy"]["value"] == 1
    assert m["labeled_attempts"] == 1
    assert m["failure_rate"]["value"] == 0
    assert m["cost"]["unknown_attempts"] == 1


def test_split_results_remain_separate():
    cases = [case("c", "different", split="calibration"), case("t", "different", split="test")]
    summary = build_summary(cases, [row("c", "different"), row("t", "duplicate")])
    assert summary["split_models"]["calibration"]["m"]["end_to_end_accuracy"]["value"] == 1
    assert summary["split_models"]["test"]["m"]["end_to_end_accuracy"]["value"] == 0


def test_cli_reads_jsonl_and_measured_charts_escape_model_names(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    records = tmp_path / "records.jsonl"
    dataset.write_text(json.dumps(case("n", "different")) + "\n", encoding="utf-8")
    records.write_text(json.dumps(row("n", "different", model="a<b&c")) + "\n", encoding="utf-8")
    output = tmp_path / "out"
    assert main(["--dataset", str(dataset), "--records", str(records), "--output", str(output)]) == 0
    ET.parse(output / "cost.svg")
    ET.parse(output / "latency.svg")
    svg = (output / "cost.svg").read_text(encoding="utf-8")
    assert "a&lt;b&amp;c" in svg
    assert "10.0000 USD" in svg
    summary = build_summary([case("n", "different")], [row("n", "different", cost_usd=None)])
    assert "unavailable" in render_measurement_svg(summary, "cost")


def test_parsed_answer_reason_and_unique_tag_safety_counts(tmp_path):
    cases = [case("n", "different", split="test", category="real", tags=["hard"])]
    rows = [row("n", "duplicate", repeat=i, parsed_answer={"reason": "different edition | metadata mismatch"}) for i in range(3)]
    summary = write_report(cases, rows, tmp_path)
    m = summary["models"]["m"]
    assert m["errors"][0]["reason"] == "different edition | metadata mismatch"
    assert m["tags"]["hard"]["dangerous_unique_cases"] == 1
    assert m["tags"]["hard"]["dangerous_case_rate"]["denominator"] == 1
    assert m["tags"]["hard"]["attempts"] == 3
    assert summary["split_counts"]["test"]["reference_labels"]["different"] == 1
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Reference label" in report
    assert "Truth label" not in report
    assert "different edition \\| metadata mismatch" in report


def test_case_probability_scores_average_repeats_and_exclude_chat_scores():
    cases = [case("n", "different"), case("chat", "different"), case("failed", "different")]
    rows = [row("n", "duplicate", repeat=0, probabilities={"duplicate": 1, "different": 0, "uncertain": 0}),
            row("n", "different", repeat=1, probabilities={"duplicate": 0, "different": 1, "uncertain": 0}),
            row("chat", "different", confidence=.99, similarity_score=.01),
            row("failed", "different", probabilities={"duplicate": 0, "different": 1, "uncertain": 0}),
            row("failed", None, repeat=1, status="error")]
    p = model_metrics(cases, rows)["probability_diagnostics"]
    assert p["scored_unique_cases"] == 1
    assert p["excluded_unique_cases"] == 2
    assert p["mean_multiclass_brier"] == .5
    assert p["mean_negative_log_likelihood"] == pytest.approx(.69314718056)
    assert p["dangerous_probability_cases"][0]["mean_probabilities"]["duplicate"] == .5
    assert p["high_confidence_dangerous_cases"] == []


def test_high_probability_dangerous_case_not_repeat_count_and_optional_cascade():
    cases = [case("n", "different", split="test")]
    rows = [row("n", "duplicate", model="cheap", repeat=i, probabilities={"duplicate": .97, "different": .02, "uncertain": .01}) for i in range(3)]
    rows += [row("n", "different", model="gemini", repeat=i) for i in range(3)]
    summary = build_summary(cases, rows, cascade_pairs=[("cheap", "gemini")])
    p = summary["models"]["cheap"]["probability_diagnostics"]
    assert len(p["high_confidence_dangerous_cases"]) == 1
    assert p["high_confidence_dangerous_cases"][0]["mean_probabilities"]["duplicate"] == pytest.approx(.97)
    assert summary["cascades"][1]["metrics"]["end_to_end_accuracy"]["value"] == 1
    assert summary["cascades"][1]["cheap_routed_attempts"] == 0
