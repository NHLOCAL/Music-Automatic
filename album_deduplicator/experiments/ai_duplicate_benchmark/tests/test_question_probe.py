import copy
import json

import pytest

from album_deduplicator.experiments.ai_duplicate_benchmark.client import BenchmarkError
from album_deduplicator.experiments.ai_duplicate_benchmark.question_probe import (
    ATOMIC_QUESTIONS, DEFAULT_MODELS, FROZEN_PROTOCOLS, PROTOCOL_HASH, gate_answers,
    probe_payload, run_probe, typed_answers,
)
from album_deduplicator.experiments.ai_duplicate_benchmark.runner import digest, read_jsonl


INPUT = {"album1": {"album": ["Album"], "tracks": []}, "album2": {"album": ["Album"], "tracks": []}}


def answers(questions=ATOMIC_QUESTIONS):
    chosen = {"release": "same", "content": "same", "evidence": "sufficient", "verdict": "duplicate"}
    return {name: {"type": "choice", "choice": chosen[name], "confidence": .97,
                   "probabilities": {label: .98 if label == chosen[name] else .02 / (len(question["criteria"]) - 1) for label in question["criteria"]}}
            for name, question in questions.items()}


class FakeClient:
    timeout = 120

    def __init__(self, *, cost=.00001, context=32768):
        self.cost, self.context, self.calls = cost, context, []

    def catalog(self):
        return {model: {"context_length": self.context, "pricing": {"prompt": "0.000001", "completion": "0", "request": "0"}} for model in DEFAULT_MODELS}

    def preflight(self):
        return {"limit": 2, "limit_reset": None, "limit_remaining": 2}

    def request(self, endpoint, payload):
        self.calls.append(copy.deepcopy(payload))
        return {"answers": answers(payload["questions"]), "model": payload["model"], "provider": "fixture", "id": "fixture", "usage": {"cost": self.cost}}


def cases():
    return [{"case_id": "c", "input": copy.deepcopy(INPUT), "label": "different", "review": "DO NOT SEND REFERENCE LABEL"}]


def test_atomic_fixed_gate_preserves_uncertainty_and_confidence():
    evidence = answers()
    assert gate_answers(evidence, INPUT, "atomic")["action"] == "duplicate"
    evidence["content"]["confidence"] = .79
    assert gate_answers(evidence, INPUT, "atomic")["action"] == "review"
    evidence = answers()
    evidence["evidence"].pop("confidence")
    assert gate_answers(evidence, INPUT, "atomic")["action"] == "review"
    evidence = answers()
    evidence["content"] = {"type": "choice", "choice": "different", "confidence": .99, "probabilities": {"same": .01, "different": .98, "unknown": .01}}
    assert gate_answers(evidence, INPUT, "atomic")["action"] == "review"
    evidence["verdict"] = {"type": "choice", "choice": "different", "confidence": .99, "probabilities": {"duplicate": .01, "different": .98, "uncertain": .01}}
    assert gate_answers(evidence, INPUT, "atomic")["action"] == "different"
    evidence["content"]["probabilities"] = {"same": .1, "different": .85, "unknown": .05}
    assert gate_answers(evidence, INPUT, "atomic")["action"] == "review"


def test_positive_gate_vetoes_explicit_volume_and_edition_conflicts():
    conflict = copy.deepcopy(INPUT)
    conflict["album1"]["album"] = ["Album Volume 1"]
    conflict["album2"]["album"] = ["Album Volume 2"]
    assert gate_answers(answers(), conflict, "atomic")["action"] == "review"
    conflict["album1"]["album"] = ["Album Live"]
    conflict["album2"]["album"] = ["Album Studio"]
    assert gate_answers(answers(), conflict, "atomic")["action"] == "review"


def test_actual_compact_albums_schema_and_optional_identity_fields():
    conflict = {"album1": {"albums": ["Release Vol1"]}, "album2": {"albums": ["Release Vol2"]}}
    assert gate_answers(answers(), conflict, "atomic")["action"] == "review"
    conflict = {"album1": {"albums": ["Release"], "edition": "live"}, "album2": {"albums": ["Release"], "editions": ["studio"]}}
    assert gate_answers(answers(), conflict, "atomic")["action"] == "review"
    conflict = {"album1": {"albums": ["Release"], "discnumber": "01"}, "album2": {"albums": ["Release"], "disc": 2}}
    assert gate_answers(answers(), conflict, "atomic")["action"] == "review"
    conflict["album2"]["disc"] = 1
    assert gate_answers(answers(), conflict, "atomic")["action"] == "duplicate"
    # Missing identity fields are not invented as conflicting values.
    missing = {"album1": {"albums": ["Release Vol1"], "edition": "live"}, "album2": {"albums": []}}
    assert gate_answers(answers(), missing, "atomic")["action"] == "duplicate"


def test_frozen_protocol_payload_contains_no_reference_label():
    payload = probe_payload(DEFAULT_MODELS[0], cases()[0]["input"], "atomic", "rules")
    assert payload["state"] == INPUT
    assert "DO NOT SEND" not in json.dumps(payload)
    assert "label" not in payload["state"]
    assert PROTOCOL_HASH == digest(FROZEN_PROTOCOLS)
    payload["questions"]["release"]["instructions"] = "changed"
    assert PROTOCOL_HASH == digest(FROZEN_PROTOCOLS)
    with pytest.raises(BenchmarkError, match="actual confidence"):
        malformed = answers()
        malformed["content"]["confidence"] = True
        typed_answers({"answers": malformed}, ATOMIC_QUESTIONS)


def test_shared_budget_prevents_any_paid_call(tmp_path):
    client = FakeClient()
    with pytest.raises(BenchmarkError, match="complete probe cost"):
        run_probe(client, cases(), tmp_path, "rules", repeats=2, budget=.00001)
    assert client.calls == []


def test_resume_no_duplicate_and_exact_payload_fingerprint(tmp_path):
    client = FakeClient()
    result = run_probe(client, cases(), tmp_path, "rules", repeats=2)
    assert len(client.calls) == 12
    assert len(read_jsonl(result["records_path"])) == 12
    run_probe(client, cases(), tmp_path, "rules", repeats=2)
    assert len(client.calls) == 12
    # A reference-label correction does not change inference inputs.
    relabeled = cases()
    relabeled[0]["label"] = "duplicate"
    run_probe(client, relabeled, tmp_path, "rules", repeats=2)
    assert len(client.calls) == 12
    changed = cases()
    changed[0]["input"]["album1"]["album"] = ["Other"]
    with pytest.raises(BenchmarkError, match="fingerprint mismatch"):
        run_probe(client, changed, tmp_path, "rules", repeats=2)
    records = read_jsonl(result["records_path"])
    assert all(record["confidence"] == .97 for record in records)
    assert all(record["full_response"]["answers"] == record["answers"] for record in records)
    assert len({record["input_hash"] for record in records}) == 1


def test_unknown_cost_stops_and_blocks_resume(tmp_path):
    client = FakeClient(cost=None)
    with pytest.raises(BenchmarkError, match="cost unknown"):
        run_probe(client, cases(), tmp_path, "rules", repeats=2)
    assert len(client.calls) == 1
    with pytest.raises(BenchmarkError, match="Previous probe cost unknown"):
        run_probe(client, cases(), tmp_path, "rules", repeats=2)
    assert len(client.calls) == 1


def test_shared_case_context_exclusion_applies_to_every_protocol_model(tmp_path):
    client = FakeClient(context=1500)
    result = run_probe(client, cases(), tmp_path, "rules", repeats=2)
    assert result["shared_excluded_case_ids"] == ["c"]
    assert client.calls == []
    assert len(read_jsonl(result["records_path"])) == 12
    assert all(record["status"] == "skipped_oversize" for record in read_jsonl(result["records_path"]))


def test_clef_requires_verified_tokenizer_before_network(tmp_path):
    client = FakeClient()
    with pytest.raises(BenchmarkError, match="verified full-payload tokenizer"):
        run_probe(client, cases(), tmp_path, "rules", models=["cloudflare/clef"])
    assert client.calls == []
