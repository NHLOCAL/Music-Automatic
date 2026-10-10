"""Frozen question protocols, independent of reference labels; isolated paid probe."""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import time
import uuid

from .client import BenchmarkError, OpenRouterClient, build_payload, compact, estimate_cost
from .runner import DEFAULT_RULES, HERE, TRUNCATING_MODELS, append_record, digest, load_tokenizer, read_jsonl, utc_now

PROTOCOL_VERSION = 2
DEFAULT_MODELS = ("microsoft/microsoft-decision-1", "typesafe/jev-1.13")
PROTOCOLS = ("baseline", "improved_single", "atomic")
IMPROVED_VERDICT = {
    "type": "choice", "instructions": "Using only album1 and album2 metadata, classify whether these are duplicate albums under the defined policy. Never infer missing track identities. Artist/title aliases, translation, ordering, encoding and file formats can differ without changing identity. Explicit different editions, volumes or set discs are different. Ignore script scores as proof. Missing or conflicting evidence is uncertain.",
    "criteria": {
        "duplicate": "Same artist, same release and same recorded content, supported by complete identifying track evidence. No edition, volume or disc conflict. Generic track numbers and equal durations alone do not prove identity.",
        "different": "Explicit distinct releases, editions (Deluxe/Live/Studio), volumes or set discs, or clear unique recorded content on otherwise complete track lists.",
        "uncertain": "Insufficient or conflicting identity evidence; generic titles/durations alone; missing tracks/durations; subset or incomplete-copy relationship without proof of exact recorded identity; material unexplained duration differences.",
    },
}
ATOMIC_QUESTIONS = {
    "release": {"type": "choice", "instructions": "Compare album1 and album2 release identity from artist, album, edition, volume and set-disc metadata only. Do not infer missing identity or consult another question's answer.", "criteria": {
        "same": "Evidence supports the same artist and release; title aliases or translations are acceptable; no explicit edition, volume or set-disc conflict.",
        "different": "Explicit distinct artists/releases or conflicting editions (Deluxe/Live/Studio), volumes or set discs.",
        "unknown": "Release identity is missing, ambiguous or conflicting without a clear explicit distinct release.",
    }},
    "content": {"type": "choice", "instructions": "Compare album1 and album2 recorded content using their full track metadata. Names can be translated or reordered. Never invent missing track identities or durations. Answer this question independently.", "criteria": {
        "same": "Complete identifying track content matches, allowing reordered/translated names and minor timing noise. Generic track numbers with equal durations alone are insufficient.",
        "different": "Complete, identifying track evidence establishes unique different recordings or tracks on either album, not merely renaming or formatting.",
        "unknown": "Generic or missing titles/durations, incomplete or subset copy relationship, or unexplained material timing differences prevent establishing exact recorded identity.",
    }},
    "evidence": {"type": "choice", "instructions": "Is album1 and album2 metadata sufficient to establish album and recorded-content identity for a duplicate decision? Judge evidence sufficiency independently of other answers.", "criteria": {
        "sufficient": "Clear artist/release identity and complete identifying track evidence, without unresolved contradictions or missing essential information.",
        "insufficient": "Generic matching names/durations alone, missing/conflicting identity, incomplete content or unexplained material timing differences leave identity unresolved.",
    }},
    "verdict": IMPROVED_VERDICT,
}
FROZEN_PROTOCOLS = {"version": PROTOCOL_VERSION, "improved_single": {"verdict": IMPROVED_VERDICT}, "atomic": ATOMIC_QUESTIONS,
                    "veto_schema_fields": {"release_names": ["albums", "album", "folder_name"],
                                           "explicit_identity": [["edition", "editions"], ["volume", "volumes"], ["disc", "discs", "discnumber"]]},
                    "policy": {"version": 2, "positive": {"duplicate": .95, "same_release": .9, "same_content": .9, "sufficient": .9, "each_confidence": .8},
                               "contradiction": {"duplicate_verdict_confidence": .8, "different_release_or_content": .95, "action": "review"},
                               "negative": {"different_release_or_content": .95}, "fallback": "review"}}
PROTOCOL_HASH = digest(FROZEN_PROTOCOLS)


def probe_payload(model, album_input, protocol, rules, pricing=None):
    if protocol not in PROTOCOLS:
        raise BenchmarkError("Unknown question protocol")
    payload = build_payload(model, album_input, rules, pricing=pricing)
    if "questions" not in payload:
        raise BenchmarkError("Question probe requires a Decisions model")
    if protocol != "baseline":
        payload["questions"] = copy.deepcopy(FROZEN_PROTOCOLS[protocol])
    return payload


def typed_answers(response, questions):
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise BenchmarkError("Missing or unexpected typed question answers")
    result = {}
    for name, question in questions.items():
        answer = answers[name]
        if not isinstance(answer, dict) or answer.get("type") != "choice" or answer.get("choice") not in question["criteria"]:
            raise BenchmarkError("Malformed typed choice answer")
        probabilities, confidence = answer.get("probabilities"), answer.get("confidence")
        valid = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1
        if not isinstance(probabilities, dict) or set(probabilities) != set(question["criteria"]) or not all(valid(v) for v in probabilities.values()) or abs(sum(probabilities.values()) - 1) > .02 or not valid(confidence):
            raise BenchmarkError("Missing or invalid actual confidence/probabilities")
        result[name] = copy.deepcopy(answer)
    return result


def explicit_identity_conflict(album_input):
    """Conservative metadata-only veto; no reference labels or learned patterns."""
    texts = []
    for album in (album_input["album1"], album_input["album2"]):
        names = album.get("albums") or album.get("album") or []
        if isinstance(names, str):
            names = [names]
        texts.append(" ".join(str(name) for name in names) + " " + str(album.get("folder_name", "")))
    volume_pattern = r"\b(?:vol(?:ume)?\.?|part|disc|cd)\s*(\d+)\b|(?:חלק|כרך|דיסק)\s*(\d+)"
    volumes = [{a or b for a, b in re.findall(volume_pattern, text, flags=re.I)} for text in texts]
    if all(volumes) and volumes[0] != volumes[1]:
        return True
    editions = [{token.lower().replace("remastered", "remaster") for token in re.findall(r"\b(?:deluxe|live|studio|remaster(?:ed)?)\b", text, flags=re.I)} for text in texts]
    # Only explicitly conflicting described editions, not absent edition tags.
    if all(editions) and editions[0] != editions[1]:
        return True
    def explicit_values(album, fields):
        values = []
        for field in fields:
            value = album.get(field)
            if value is not None:
                values.extend(value if isinstance(value, list) else [value])
        normalized = set()
        for value in values:
            text = str(value).strip().casefold().replace("remastered", "remaster")
            if text:
                normalized.add(str(int(text)) if text.isdecimal() else text)
        return normalized
    for fields in FROZEN_PROTOCOLS["veto_schema_fields"]["explicit_identity"]:
        a, b = (explicit_values(album_input[name], fields) for name in ("album1", "album2"))
        if a and b and a != b:
            return True
    return False


def gate_answers(answers, album_input, protocol):
    """A fixed routing policy; never multiply correlated confidence signals."""
    questions = {"verdict": IMPROVED_VERDICT} if protocol != "atomic" else ATOMIC_QUESTIONS
    try:
        parsed = typed_answers({"answers": answers}, questions)
    except BenchmarkError:
        return {"action": "review", "verdict": "uncertain", "policy_reason": "missing_or_invalid_typed_evidence"}
    v = parsed["verdict"]
    if protocol != "atomic":
        if v["choice"] == "different" and v["probabilities"]["different"] >= .95 and v["confidence"] >= .8:
            return {"action": "different", "verdict": "different", "policy_reason": "single_confident_different"}
        if v["choice"] == "duplicate" and v["probabilities"]["duplicate"] >= .95 and v["confidence"] >= .8 and not explicit_identity_conflict(album_input):
            return {"action": "duplicate", "verdict": "duplicate", "policy_reason": "single_confident_duplicate"}
        return {"action": "review", "verdict": "uncertain", "policy_reason": "single_gate_not_met"}
    release, content, evidence = (parsed[key] for key in ("release", "content", "evidence"))
    different_dimension = any(answer["choice"] == "different" and answer["probabilities"]["different"] >= .95 for answer in (release, content))
    if different_dimension and v["choice"] == "duplicate" and v["confidence"] >= .8:
        return {"action": "review", "verdict": "uncertain", "policy_reason": "confident_verdict_dimension_contradiction"}
    if different_dimension:
        return {"action": "different", "verdict": "different", "policy_reason": "explicit_confident_different_dimension"}
    positive = (v["choice"] == "duplicate" and v["probabilities"]["duplicate"] >= .95
                and release["choice"] == "same" and release["probabilities"]["same"] >= .9
                and content["choice"] == "same" and content["probabilities"]["same"] >= .9
                and evidence["choice"] == "sufficient" and evidence["probabilities"]["sufficient"] >= .9
                and all(answer["confidence"] >= .8 for answer in parsed.values())
                and not explicit_identity_conflict(album_input))
    return {"action": "duplicate" if positive else "review", "verdict": "duplicate" if positive else "uncertain",
            "policy_reason": "all_positive_gates_met" if positive else "atomic_gate_not_met"}


def run_probe(client, cases, output, rules, models=DEFAULT_MODELS, *, repeats=2, budget=.5, tokenizer_path=None, seed=42):
    if not math.isfinite(budget) or not 0 < budget <= 2 or repeats < 1 or not cases or not models or len(set(models)) != len(models):
        raise BenchmarkError("Invalid dataset, models, repetitions or budget (maximum $2)")
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise BenchmarkError("Duplicate dataset case IDs")
    count_tokens, tokenizer_metadata = load_tokenizer(tokenizer_path) if tokenizer_path else (None, None)
    if TRUNCATING_MODELS.intersection(models) and count_tokens is None:
        raise BenchmarkError("Clef question probes require verified full-payload tokenizer to prevent truncation")
    catalog = client.catalog()
    if any(model not in catalog for model in models):
        raise BenchmarkError("Requested decision model missing from live catalog")
    payloads, estimates, excluded = {}, {}, set()
    for case in cases:
        for model in models:
            context = int(catalog[model].get("context_length") or 0)
            if context < 1:
                raise BenchmarkError("Unknown model context length")
            for protocol in PROTOCOLS:
                payload = probe_payload(model, case["input"], protocol, rules, catalog[model]["pricing"])
                key = (case["case_id"], model, protocol)
                payloads[key] = payload
                conservative_tokens = len(compact(payload).encode("utf-8")) + 64
                estimates[key] = estimate_cost(catalog[model], conservative_tokens, 1024)
                if conservative_tokens + 1024 > context:
                    excluded.add(case["case_id"])
                if model in TRUNCATING_MODELS and count_tokens(compact(payload)) + 64 > 1800:
                    excluded.add(case["case_id"])
    inputs = [{"case_id": case["case_id"], "input": case["input"]} for case in cases]
    settings = {"inputs": inputs, "models": list(models), "protocol_hash": PROTOCOL_HASH, "rules": rules,
                "payload_hashes": {"/".join(key): digest(payload) for key, payload in payloads.items()},
                "repeats": repeats, "budget": budget, "seed": seed, "tokenizer": tokenizer_metadata,
                "timeout": getattr(client, "timeout", 60)}
    fingerprint = digest(settings)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path, records_path, inflight_path, lock_path = (output / name for name in ("manifest.json", "records.jsonl", "inflight.json", "run.lock"))
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8"))["fingerprint"] != fingerprint:
            raise BenchmarkError("Question probe resume fingerprint mismatch")
    elif records_path.exists():
        raise BenchmarkError("Records exist without probe manifest")
    else:
        manifest_path.write_text(compact({"fingerprint": fingerprint, "created_at": utc_now(), "protocols": FROZEN_PROTOCOLS,
            "protocol_hash": PROTOCOL_HASH, "input_hash": digest(inputs), "rules_hash": digest(rules), "models": list(models),
            "repeats": repeats, "budget_usd": budget, "shared_excluded_case_ids": sorted(excluded), "settings": settings}) + "\n", encoding="utf-8")
    records = read_jsonl(records_path)
    if any(record.get("run_fingerprint") != fingerprint for record in records):
        raise BenchmarkError("Probe record fingerprint mismatch")
    completed = {(record["case_id"], record["model"], record["protocol"], record["repeat"]) for record in records}
    if len(completed) != len(records):
        raise BenchmarkError("Duplicate recorded probe attempt")
    if inflight_path.exists():
        inflight = json.loads(inflight_path.read_text(encoding="utf-8"))
        if inflight.get("attempt_id") not in {record["attempt_id"] for record in records}:
            raise BenchmarkError("Interrupted probe has unknown billing; reconcile before further calls")
        inflight_path.unlink()
    if any(record.get("cost_usd") is None and record["status"] != "skipped_oversize" for record in records):
        raise BenchmarkError("Previous probe cost unknown; further calls blocked")
    spent = sum(record.get("cost_usd") or 0 for record in records)
    tasks = [(case, model, protocol, repeat) for repeat in range(repeats) for case in cases for model in models for protocol in PROTOCOLS]
    random.Random(seed).shuffle(tasks)
    remaining = sum(estimates[(case["case_id"], model, protocol)] for case, model, protocol, repeat in tasks
                    if (case["case_id"], model, protocol, repeat) not in completed and case["case_id"] not in excluded)
    if spent + remaining > budget:
        raise BenchmarkError("Conservative complete probe cost exceeds budget; no paid calls made")
    if remaining:
        key = client.preflight()
        if key.get("limit") is None or not 0 < float(key["limit"]) <= 2 or key.get("limit_reset") is not None:
            raise BenchmarkError("Probe requires a dedicated non-resetting API key capped at $2")
        if key.get("limit_remaining") is None or remaining > float(key["limit_remaining"]):
            raise BenchmarkError("Key remaining balance below conservative complete probe cost")
    try:
        lockfd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise BenchmarkError("Question probe already locked") from None
    os.close(lockfd)
    try:
        for case, model, protocol, repeat in tasks:
            if (case["case_id"], model, protocol, repeat) in completed:
                continue
            payload = payloads[(case["case_id"], model, protocol)]
            record = {"attempt_id": str(uuid.uuid4()), "run_fingerprint": fingerprint, "case_id": case["case_id"], "model": model,
                      "protocol": protocol, "protocol_version": PROTOCOL_VERSION, "protocol_hash": PROTOCOL_HASH, "repeat": repeat,
                      "timestamp": utc_now(), "input_hash": digest(case["input"]), "prompt_hash": digest(payload),
                      "questions": payload["questions"], "answers": None, "full_response": None, "cost_usd": None,
                      "latency_ms": None, "status": "pending", "action": "review", "verdict": "uncertain", "confidence": None}
            if case["case_id"] in excluded:
                record.update(status="skipped_oversize", cost_usd=0, policy_reason="shared_complete_payload_limit")
                append_record(records_path, record)
                continue
            worst_cost = estimates[(case["case_id"], model, protocol)]
            if spent + worst_cost > budget:
                raise BenchmarkError("Next probe attempt exceeds remaining budget")
            inflight_path.write_text(compact(record) + "\n", encoding="utf-8")
            started = time.perf_counter()
            try:
                response = client.request("/api/alpha/decisions", payload)
                record.update(full_response=response, response_id=response.get("id"), resolved_model=response.get("model"), provider=response.get("provider"), usage=response.get("usage"))
                raw_cost = (response.get("usage") or {}).get("cost")
                if raw_cost is not None and not isinstance(raw_cost, bool):
                    cost = float(raw_cost)
                    if math.isfinite(cost) and cost >= 0:
                        record["cost_usd"] = cost
                answers = typed_answers(response, payload["questions"])
                record["answers"] = answers
                v = answers["verdict"]
                record.update(raw_verdict=v["choice"], confidence=v["confidence"], probabilities=v["probabilities"], parsed_answer=v)
                record.update(gate_answers(answers, case["input"], protocol))
                record["status"] = "ok" if record["cost_usd"] is not None else "missing_cost"
            except (BenchmarkError, ValueError, TypeError) as exc:
                record.update(status="error", error=str(exc) if isinstance(exc, BenchmarkError) else "Malformed decision response")
            record["latency_ms"] = (time.perf_counter() - started) * 1000
            append_record(records_path, record)
            inflight_path.unlink()
            spent += record["cost_usd"] or 0
            if record["cost_usd"] is None:
                raise BenchmarkError("Probe cost unknown; record saved and further calls blocked")
            if record["cost_usd"] > worst_cost:
                raise BenchmarkError("Actual probe cost exceeded conservative estimate; further calls blocked")
        return {"records_path": str(records_path), "cost_usd": spent, "case_count": len(cases), "shared_excluded_case_ids": sorted(excluded), "fingerprint": fingerprint, "protocol_hash": PROTOCOL_HASH}
    finally:
        lock_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--budget", type=float, default=.5)
    parser.add_argument("--env", type=Path, default=HERE / ".env")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        result = run_probe(OpenRouterClient(env_path=args.env, timeout=args.timeout), read_jsonl(args.dataset), args.output,
                           args.rules.read_text(encoding="utf-8-sig"), args.models, repeats=args.repeats, budget=args.budget, tokenizer_path=args.tokenizer)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (BenchmarkError, OSError, ValueError, KeyError) as exc:
        print(str(exc) if isinstance(exc, BenchmarkError) else "Invalid local probe input", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
