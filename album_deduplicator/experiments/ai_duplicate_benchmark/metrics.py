"""Offline benchmark statistics. Repeated calls are not independent truth samples."""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
import math

LABELS = ("duplicate", "different", "uncertain")


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def wilson(successes, total, z=1.959963984540054):
    """95% Wilson interval; None for no independent cases."""
    if not total:
        return None
    p = successes / total
    divisor = 1 + z * z / total
    center = (p + z * z / (2 * total)) / divisor
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / divisor
    return [max(0.0, center - radius), min(1.0, center + radius)]


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lo = math.floor(position)
    hi = math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def verdict(row):
    parsed = row.get("parsed_answer") or row.get("parsed_response") or {}
    return row.get("verdict") or parsed.get("verdict")


def reason(row):
    parsed = row.get("parsed_answer") or row.get("parsed_response") or {}
    return row.get("reason") or parsed.get("reason") or row.get("error")


def successful(row):
    return row.get("status") in ("ok", "success", "missing_cost") and verdict(row) in LABELS


def truth_label(case):
    """Historical/model-inferred labels must not quietly enter quality scores."""
    source = str(case.get("label_provenance", case.get("provenance", "unspecified"))).lower()
    if any(word in source for word in ("model_inferred", "historical", "gemini", "pending_review")):
        return None
    return case.get("label") if case.get("label") in LABELS else None


def _number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _probabilities(row):
    probabilities = row.get("probabilities") or (row.get("parsed_answer") or row.get("parsed_response") or {}).get("probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != set(LABELS):
        return None
    if not all(_number(probabilities[label]) and probabilities[label] <= 1 for label in LABELS):
        return None
    total = sum(probabilities.values())
    if not total or abs(total - 1) > .02:
        return None
    return {label: probabilities[label] / total for label in LABELS}


def probability_diagnostics(case_map, by_case, threshold=.95):
    """Equal case weights, with all repeated attempts required for scoring.

    Self-reported decision probabilities are diagnostic, not calibration proof.
    Chat similarity scores never become probabilities here.
    """
    scored = []
    for cid, attempts in by_case.items():
        vectors = [_probabilities(row) if successful(row) else None for row in attempts]
        if any(vector is None for vector in vectors):
            continue
        mean = {label: sum(vector[label] for vector in vectors) / len(vectors) for label in LABELS}
        label = case_map[cid]["label"]
        brier = sum((mean[prediction] - int(prediction == label)) ** 2 for prediction in LABELS)
        nll = -math.log(max(mean[label], 1e-15))
        dangerous = label in ("different", "uncertain") and any(verdict(row) == "duplicate" for row in attempts)
        scored.append({"case_id": cid, "reference_label": label, "repetitions": len(attempts), "mean_probabilities": mean,
                       "multiclass_brier": brier, "negative_log_likelihood": nll, "dangerous": dangerous})
    dangerous = sorted([record for record in scored if record["dangerous"]], key=lambda record: -record["mean_probabilities"]["duplicate"])
    return {"scored_unique_cases": len(scored), "excluded_unique_cases": len(by_case) - len(scored),
            "mean_multiclass_brier": sum(record["multiclass_brier"] for record in scored) / len(scored) if scored else None,
            "mean_negative_log_likelihood": sum(record["negative_log_likelihood"] for record in scored) / len(scored) if scored else None,
            "method": "Average valid probability vectors across all recorded repetitions before scoring each case once. Any failed/missing/invalid probability repetition excludes that case. Vectors within 0.02 of sum 1 are normalized. Brier sums squared errors across three classes (range 0 to 2). NLL uses natural logarithm and epsilon 1e-15.",
            "interpretation": "Self-reported decision probabilities are diagnostics, not calibrated confidence. Chat similarity scores are excluded. Repetitions are not independent samples.",
            "high_confidence_threshold": threshold,
            "high_confidence_dangerous_cases": [record for record in dangerous if record["mean_probabilities"]["duplicate"] >= threshold],
            "dangerous_probability_cases": dangerous, "cases": scored}


def model_metrics(cases, rows):
    case_map = {case["case_id"]: case for case in cases}
    labeled = [r for r in rows if r.get("case_id") in case_map and truth_label(case_map[r["case_id"]]) in LABELS]
    good = [r for r in labeled if successful(r)]
    confusion = {truth: {prediction: 0 for prediction in LABELS} for truth in LABELS}
    for row in good:
        confusion[case_map[row["case_id"]]["label"]][verdict(row)] += 1
    tp = confusion["duplicate"]["duplicate"]
    fp_different = confusion["different"]["duplicate"]
    fp_uncertain = confusion["uncertain"]["duplicate"]
    fp = fp_different + fp_uncertain
    predicted_duplicate = tp + fp
    actual_duplicate = sum(confusion["duplicate"].values())
    precision = ratio(tp, predicted_duplicate)
    recall = ratio(tp, actual_duplicate)
    f1 = 2 * tp / (2 * tp + fp + actual_duplicate - tp) if 2 * tp + fp + actual_duplicate - tp else None
    correct = sum(confusion[label][label] for label in LABELS)
    by_case = defaultdict(list)
    for row in labeled:
        by_case[row["case_id"]].append(row)
    eligible = [cid for cid in by_case if case_map[cid]["label"] in ("different", "uncertain")]
    observed_eligible = [cid for cid in eligible if any(successful(r) for r in by_case[cid])]
    dangerous = [cid for cid in eligible if any(successful(r) and verdict(r) == "duplicate" for r in by_case[cid])]
    all_correct = [cid for cid, attempts in by_case.items() if all(successful(r) and verdict(r) == case_map[cid]["label"] for r in attempts)]
    costs = [r["cost_usd"] for r in rows if _number(r.get("cost_usd"))]
    known_total = sum(costs)
    complete_cost = len(costs) == len(rows)
    attempted_cases = len({r.get("case_id") for r in rows})
    latency = []
    for row in rows:
        value = row.get("latency_s")
        if value is None and _number(row.get("latency_ms")):
            value = row["latency_ms"] / 1000
        if _number(value):
            latency.append(value)
    tag_rows = defaultdict(list)
    for row in labeled:
        for tag in case_map[row["case_id"]].get("tags", []):
            tag_rows[tag].append(row)
    tags = {}
    for tag, attempts in sorted(tag_rows.items()):
        matrix = Counter((case_map[r["case_id"]]["label"], verdict(r) if successful(r) else "failure") for r in attempts)
        tag_cases = {r["case_id"] for r in attempts}
        tag_observed_cases = {r["case_id"] for r in attempts if successful(r)}
        tag_observed_nonduplicate = {r["case_id"] for r in attempts if successful(r) and case_map[r["case_id"]]["label"] in ("different", "uncertain")}
        tag_dangerous = {r["case_id"] for r in attempts if successful(r) and verdict(r) == "duplicate" and case_map[r["case_id"]]["label"] != "duplicate"}
        tags[tag] = {"attempts": len(attempts), "confusion": [{"label": key[0], "prediction": key[1], "count": count} for key, count in sorted(matrix.items())],
                     "unique_cases": len(tag_cases), "observed_unique_cases": len(tag_observed_cases),
                     "observed_nonduplicate_cases": len(tag_observed_nonduplicate), "dangerous_unique_cases": len(tag_dangerous),
                     "dangerous_case_rate": ratio(len(tag_dangerous), len(tag_observed_nonduplicate)),
                     "dangerous_fp_wilson95": wilson(len(tag_dangerous), len(tag_observed_nonduplicate)),
                     "dangerous_case_ids": sorted(tag_dangerous)}
    return {
        "attempts": len(rows), "labeled_attempts": len(labeled), "unique_cases": len(by_case), "unique_attempted_cases": attempted_cases,
        "missing_dataset_case_ids": sorted(set(case_map) - {r.get("case_id") for r in rows}),
        "successful_labeled_attempts": len(good), "confusion": confusion,
        "multiclass_accuracy_successful": ratio(correct, len(good)),
        "end_to_end_accuracy": ratio(correct, len(labeled)),
        "duplicate_precision": precision, "duplicate_recall_successful": recall,
        "duplicate_recall_end_to_end": ratio(tp, sum(case_map[r["case_id"]]["label"] == "duplicate" for r in labeled)), "duplicate_f1_successful": f1,
        "dangerous_duplicate_fp": {"different": fp_different, "uncertain": fp_uncertain,
                                  "rate_successful_nonduplicate": ratio(fp, sum(sum(confusion[label].values()) for label in ("different", "uncertain")))},
        "specificity_different_successful": ratio(confusion["different"]["different"], sum(confusion["different"].values())),
        "decisive_coverage": ratio(sum(successful(r) and verdict(r) != "uncertain" for r in rows), len(rows)),
        "abstention_rate": ratio(sum(successful(r) and verdict(r) == "uncertain" for r in rows), len(rows)),
        "failure_rate": ratio(sum(not successful(r) for r in rows), len(rows)),
        "case_level": {"rule": "Any duplicate prediction on a different/uncertain case is dangerous; all repetitions must be correct for case accuracy",
                       "dangerous_case_ids": sorted(dangerous), "dangerous_fp_observed": ratio(len(dangerous), len(observed_eligible)),
                       "dangerous_fp_wilson95": wilson(len(dangerous), len(observed_eligible)), "eligible_cases": len(eligible),
                       "unobserved_eligible_cases": len(eligible) - len(observed_eligible),
                       "all_repeats_correct": ratio(len(all_correct), len(by_case)), "accuracy_wilson95": wilson(len(all_correct), len(by_case))},
        "cost": {"known_total_usd": known_total, "known_attempts": len(costs), "unknown_attempts": len(rows) - len(costs),
                 "total_usd": known_total if complete_cost else None,
                 "usd_per_1000_attempts": known_total * 1000 / len(rows) if rows and complete_cost else None,
                 "usd_per_1000_cases": known_total * 1000 / attempted_cases if attempted_cases and complete_cost else None},
        "latency": {"observed_attempts": len(latency), "p50_s": percentile(latency, .5), "p95_s": percentile(latency, .95)},
        "tags": tags,
        "probability_diagnostics": probability_diagnostics(case_map, by_case),
        "errors": [{"case_id": r["case_id"], "repeat": r.get("repeat"), "label": case_map[r["case_id"]]["label"],
                    "prediction": verdict(r) if successful(r) else "failure", "reason": reason(r)}
                   for r in labeled if not successful(r) or verdict(r) != case_map[r["case_id"]]["label"]],
    }


def paired_comparisons(cases, rows):
    """Do not hide failed calls by reporting only intersection accuracy."""
    labels = {c["case_id"]: truth_label(c) for c in cases}
    models = sorted({r["model"] for r in rows})
    index = {}
    for row in rows:
        key = (row["model"], row["case_id"], row.get("repeat", 0))
        if key in index:
            raise ValueError(f"Duplicate attempt key: {key}")
        index[key] = row
    result = []
    for a, b in combinations(models, 2):
        keys_a = {(cid, repeat) for model, cid, repeat in index if model == a and labels.get(cid) in LABELS}
        keys_b = {(cid, repeat) for model, cid, repeat in index if model == b and labels.get(cid) in LABELS}
        common = sorted(keys_a & keys_b, key=str)
        success_cases = {cid for cid, _ in common
                         if {rep for c, rep in keys_a if c == cid} == {rep for c, rep in keys_b if c == cid}
                         and all(successful(index[(m, c, rep)]) for c, rep in common if c == cid for m in (a, b))}
        cohorts = {"all_paired_attempts": common, "identical_successful_cases": [k for k in common if k[0] in success_cases]}
        entry = {"models": [a, b], "unpaired_attempts": {a: len(keys_a - keys_b), b: len(keys_b - keys_a)}, "cohorts": {}}
        for name, keys in cohorts.items():
            scores = {}
            for m in (a, b):
                scores[m] = ratio(sum(successful(index[(m, cid, rep)]) and verdict(index[(m, cid, rep)]) == labels[cid] for cid, rep in keys), len(keys))
            a_only = b_only = 0
            for cid in {k[0] for k in keys}:
                winners = [all(successful(index[(m, c, rep)]) and verdict(index[(m, c, rep)]) == labels[c] for c, rep in keys if c == cid) for m in (a, b)]
                a_only += winners == [True, False]
                b_only += winners == [False, True]
            entry["cohorts"][name] = {"attempts": len(keys), "unique_cases": len({k[0] for k in keys}), "accuracy": scores,
                                         "case_discordance": {"first_only_all_correct": a_only, "second_only_all_correct": b_only}}
        result.append(entry)
    return result


def evaluate_cascade(cases, rows, cheap_model, fallback_model, threshold=.95, split="test"):
    """Fixed policy: route confident cheap different verdicts, else use fallback.

    Threshold must be selected on calibration data before held-out evaluation.
    Cost is the simulated routed bill; latency assumes sequential calls.
    """
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be within [0, 1]")
    selected = {c["case_id"] for c in cases if c.get("split") == split}
    index = {(r["model"], r["case_id"], r.get("repeat", 0)): r for r in rows}
    if len(index) != len(rows):
        raise ValueError("Duplicate attempt key in cascade records")
    keys = sorted({(r["case_id"], r.get("repeat", 0)) for r in rows if r["model"] == cheap_model and r["case_id"] in selected}, key=str)
    simulated = []
    missing = 0
    cheap_routed = 0
    for cid, repeat in keys:
        cheap = index[(cheap_model, cid, repeat)]
        fallback = index.get((fallback_model, cid, repeat))
        if fallback is None:
            missing += 1
            continue
        probs = _probabilities(cheap) or {}
        confidence = probs.get("different")
        routed = successful(cheap) and verdict(cheap) == "different" and _number(confidence) and confidence >= threshold
        chosen = dict(cheap if routed else fallback)
        chosen["model"] = f"cascade:{cheap_model}->{fallback_model}"
        costs = [cheap.get("cost_usd")] if routed else [cheap.get("cost_usd"), fallback.get("cost_usd")]
        chosen["cost_usd"] = sum(costs) if all(_number(v) for v in costs) else None
        def seconds(row):
            value = row.get("latency_s")
            if value is None and _number(row.get("latency_ms")):
                value = row["latency_ms"] / 1000
            return value if _number(value) else None
        latencies = [seconds(cheap)] if routed else [seconds(cheap), seconds(fallback)]
        chosen["latency_s"] = sum(latencies) if all(_number(v) for v in latencies) else None
        chosen.pop("latency_ms", None)
        cheap_routed += routed
        simulated.append(chosen)
    return {"policy": {"cheap_model": cheap_model, "fallback_model": fallback_model, "threshold": threshold, "split": split},
            "paired_attempts": len(simulated), "missing_fallback_attempts": missing, "cheap_routed_attempts": cheap_routed,
            "metrics": model_metrics([c for c in cases if c["case_id"] in selected], simulated)}


def build_summary(cases, rows, cascade_pairs=None, cascade_threshold=.95):
    if len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate dataset case_id")
    known_ids = {c["case_id"] for c in cases}
    if any(r.get("case_id") not in known_ids for r in rows):
        raise ValueError("Result references unknown dataset case_id")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)
    split_metrics = {}
    for split in sorted({str(c.get("split", "unspecified")) for c in cases}):
        cohort = [c for c in cases if str(c.get("split", "unspecified")) == split]
        cohort_ids = {c["case_id"] for c in cohort}
        split_metrics[split] = {model: model_metrics(cohort, [r for r in attempts if r["case_id"] in cohort_ids])
                                for model, attempts in sorted(grouped.items())}
    split_counts = {}
    for split in sorted({str(c.get("split", "unspecified")) for c in cases}):
        cohort = [c for c in cases if str(c.get("split", "unspecified")) == split]
        split_counts[split] = {"cases": len(cohort), "reference_labels": dict(Counter(truth_label(c) or "unlabeled" for c in cohort)),
                              "provenance": dict(Counter(str(c.get("label_provenance", c.get("provenance", "unspecified"))) for c in cohort))}
    return {"schema_version": 1, "dataset_cases": len(cases), "label_counts": dict(Counter(truth_label(c) or "unlabeled" for c in cases)),
            "dataset_case_ids": sorted(known_ids), "split_counts": split_counts,
            "category_counts": dict(Counter(str(c.get("category", "unspecified")) for c in cases)),
            "provenance_counts": dict(Counter(str(c.get("label_provenance", c.get("provenance", "unspecified"))) for c in cases)),
            "warnings": ["Labels inferred by a model are not independently verified ground truth.",
                         "Zero observed dangerous errors does not establish safety; inspect the case-level confidence bound and corpus provenance.",
                         "No stable replacement recommendation without robust independent ground truth and adequate held-out coverage.",
                         "Repeated calls are correlated. Confidence intervals count unique cases, not calls.",
                         "Wilson bounds assume independent cases; shared albums or groups can make these exploratory bounds optimistic.",
                         "Quality scores use accepted labels only; billing, coverage and failures include all recorded calls, including unlabeled cases.",
                         "End-to-end attempt accuracy includes recorded failures; absent dataset cases are listed separately and cannot be assessed.",
                         "Different specificity counts only different verdicts; uncertain labels remain a separate class."],
            "models": {model: model_metrics(cases, attempts) for model, attempts in sorted(grouped.items())},
            "split_models": split_metrics,
            "cascades": [evaluate_cascade(cases, rows, cheap_model, fallback_model, threshold=cascade_threshold, split=split)
                         for cheap_model, fallback_model in (cascade_pairs or []) for split in ("calibration", "test")],
            "paired_comparisons": paired_comparisons(cases, rows)}
