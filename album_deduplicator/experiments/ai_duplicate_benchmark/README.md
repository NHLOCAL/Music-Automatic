# Album AI comparison POC

This opt-in experiment compares duplicate decisions, dangerous false positives,
actual billed cost and response time. The stable application never imports it.
It reads JSON snapshots and writes only benchmark outputs. It does not scan,
rename, merge or delete music files.

## Environment and credentials

Use Python 3.12. Create an experiment-local virtual environment and install
`requirements.txt`. The current workstation uses the installed Python 3.12
runtime with an isolated `.venv` sharing existing `tokenizers` and `pytest`
packages. No MCP or heavyweight inference installation is required: API calls
use the Python standard library and local tokenization uses `tokenizers`.

Run commands below from the repository root in PowerShell 7. Activate
`album_deduplicator/experiments/ai_duplicate_benchmark/.venv/Scripts/Activate.ps1`
first, or use that environment's `python.exe` explicitly.

Create a **dedicated OpenRouter key** with a maximum **$2 total** credit limit,
**no reset**, and **seven-day expiry**. Save it only as `OPENROUTER_API_KEY` in
the experiment-local `.env` (see `.env.example`). Restrict its Windows ACL to
the current user. `.env`, `.venv` and local outputs are ignored by Git. Never
paste the key into a report, command-line argument or chat. An existing
`OPENROUTER_MANAGEMENT_KEY` environment variable permits `runner provision`;
it is not saved. Key creation is an explicit administrative operation.

```powershell
python -m album_deduplicator.experiments.ai_duplicate_benchmark.runner preflight
python -m album_deduplicator.experiments.ai_duplicate_benchmark.runner catalog
```

The live catalog includes both standard models and
`/api/v1/models?output_modalities=decisions`. Clef Flash, Clef,
GPT-6 Luna Decisions, Jev and Microsoft-Decision-1 use `/api/alpha/decisions`; Gemini Flash-Lite,
Qwen Flash use `/api/v1/chat/completions`. Each response records the
requested and resolved model, provider and request ID.

## Reference data

```powershell
python -m album_deduplicator.experiments.ai_duplicate_benchmark.dataset build --cache album_deduplicator/data/comparison_results_cache.json.bak --music album_deduplicator/data/music_data.json --output album_deduplicator/logs/ai-duplicate-benchmark/candidates.jsonl --limit 100
```

The local cache contains historical Gemini judgments, **not verified truth**.
Only independently reviewed cases receive reference labels. Historical
judgments remain separate and are never sent to a model. Built-in reviews are
bound to exact source hashes; changed snapshots require fresh reviews.
Pending cases retain null labels and do not enter quality metrics.

The initial real sample has 36 metadata-reviewed cases: 14 duplicate, 16
different, six uncertain. Seven cases were corroborated by a second agent.
Metadata review does not verify audio identity or user decisions. No real
user feedback log was found; test feedback fixtures are excluded.

The common input preserves complete tracklists, filenames, durations and
identity tags, including edition and disc identifiers. Repeated values use
defaults, aligned columns and explicit references, without cutting tracks.
Absolute music paths, reference labels and historical AI scores are excluded.
Bitrate and file size are omitted from the identity-only comparison. Album art
is not transmitted in this text-only lane. The existing application can use
art, so this is a controlled model comparison rather than complete production
pipeline validation.

Album families stay together across calibration and test. Results are
stratified by case tags and split; a hand-picked hard sample does not estimate
library-wide prevalence. Explicit Deluxe/standard comparisons are a current
coverage gap and must be added before relying on edition safety claims.

## Uniform benchmark and long cases

Clef and Clef Flash can truncate input around 2,000 tokens. Download the
[official tokenizer](https://huggingface.co/Cloudflare/clef/blob/main/tokenizer.json)
to `album_deduplicator/logs/ai-duplicate-benchmark/tokenizers/clef.json`.
Both official models publish the same tokenizer; the runner checks its SHA256
and disables local truncation. The complete decision payload including rules
and schema must fit the conservative 1,800-token guard. This protects against
documented truncation, but provider-side preprocessing remains an external
implementation detail. Without the tokenizer, a stricter byte guard applies.

```powershell
python -m album_deduplicator.experiments.ai_duplicate_benchmark.runner run --dataset album_deduplicator/logs/ai-duplicate-benchmark/reviewed.jsonl --output album_deduplicator/logs/ai-duplicate-benchmark/common --tokenizer album_deduplicator/logs/ai-duplicate-benchmark/tokenizers/clef.json --repeats 3 --budget 2
```

`reviewed.jsonl` is the subset of the candidate file with a non-null label.
The same complete input is used for every model. All models skip the same
oversized cases. Use a separate `--full-context` run for long cases with
explicit `--models` excluding `cloudflare/clef` and `cloudflare/clef-flash`.
Do not combine lanes into an unqualified ranking.

Calls run sequentially in seeded randomized order, with three repetitions,
the current system instruction and a bounded chat output. Time measures a
complete API request, excluding preflight and tokenization. Decision models
produce probabilities; chat similarity scores are not confidence probabilities.
The runner records actual `usage.cost`, enforces provider price caps and the
provider-side key budget, and never substitutes a price estimate for billing.
HTTP or parsing errors have their own records. There are no automatic retries.
An unknown bill or interrupted request stops the run until reconciled.
Resume requires an identical dataset, prompt, model list and configuration.

For a parallel suite, replace `runner run` with `suite` and omit `--budget`
if using its default $2 cap. The suite freezes `cohort.jsonl` and
`excluded.jsonl` for all selected models before starting a separate sequential
runner per model. Calls are randomized within each model. Its manifest records
concurrency; timings measure concurrent API latency rather than dedicated
throughput. Clef Omni is excluded from the requested comparison. Microsoft was
added after the first suite began and uses the identical frozen cohort in a
separate run. Its request timings are therefore not simultaneous with every
other model. Original smoke and failed-attempt ledgers remain separate.
Llama 3.1 and Clef Omni were removed at the user's request. Their earlier
calls remain in the accounting audit but do not enter the comparison or any
recommendation. Only the requested decision models, Gemini 3.1 Flash-Lite and
the recent Qwen 3.7 Flash are benchmark defaults.

## Reports and tests

```powershell
python -m album_deduplicator.experiments.ai_duplicate_benchmark.report --dataset album_deduplicator/logs/ai-duplicate-benchmark/reviewed.jsonl --records album_deduplicator/logs/ai-duplicate-benchmark/common/records.jsonl --output album_deduplicator/logs/ai-duplicate-benchmark/common/report
python -m pytest album_deduplicator/experiments/ai_duplicate_benchmark/tests -q --basetemp album_deduplicator/logs/ai-duplicate-benchmark/test-tmp
```

Outputs include Markdown tables, JSON metrics and SVG quality, cost and speed
graphs, error examples, paired cohorts and an offline negative-routing cascade.
False duplicate decisions on both `different` and `uncertain` references are
dangerous. Reports disclose abstention, failures, unavailable bills and missing
cases. Repeated requests are not additional independent truth samples. Wilson
intervals use unique cases and may still be optimistic for correlated families.
No threshold is tuned on the test split. A candidate cascade requires a larger
user-verified holdout before any change to stable behavior.

TLS validation stays enabled. HTTP 418 or certificate errors can indicate
Netfree filtering but do not establish its cause. Sandbox DNS restrictions and
browser connection failures are reported separately from confirmed filtering.

## Confidence and question research

`confidence.py` evaluates probability and native-confidence thresholds as
separate policies. It fits a finite grid on calibration families only, freezes
the policy and then measures review coverage, dangerous positives and missed
duplicates on test families. A review action does not earn an accuracy point.
Cross-model agreement reports shared errors and the cost of both models;
agreement does not establish statistical independence.

```powershell
python -m album_deduplicator.experiments.ai_duplicate_benchmark.confidence --dataset album_deduplicator/logs/ai-duplicate-benchmark/comparison/cases.jsonl --records album_deduplicator/logs/ai-duplicate-benchmark/comparison/records.jsonl --output album_deduplicator/logs/ai-duplicate-benchmark/confidence-research
```

Native `confidence` measures distribution concentration and is preserved
separately from the full probability vector. Missing native confidence stays
missing and causes confidence-based deferral. TypeSafe defines Choice
confidence as `(p_max - 1/n) / (1 - 1/n)`, so for three choices a confidence of
0.95 is not the same threshold as a chosen-option probability of 0.95.
See [the official definition](https://docs.typesafe.ai/confidence) and
[atomic questions](https://docs.typesafe.ai/primitives).

`question_probe.py` compares the existing question, explicit identity criteria,
and independent release/content/evidence questions. Its versioned questions
and routing policy are hashed before requests. Labels never enter requests.
Raw model classification and the policy's duplicate/different/review action are
recorded separately. Question answers are combined in code; contradictory or
invalid answers defer. The default current models are Microsoft Decision 1 and
Jev 1.13, with two repetitions and a $0.50 local cap under the $2 provider cap.

```powershell
python -m album_deduplicator.experiments.ai_duplicate_benchmark.dataset build --cache album_deduplicator/data/comparison_results_cache.json.bak --music album_deduplicator/data/music_data.json --reviews album_deduplicator/experiments/ai_duplicate_benchmark/reviews/confidence_holdout.json --output album_deduplicator/logs/ai-duplicate-benchmark/confidence-research/fresh-cases.jsonl --limit 20
python -m album_deduplicator.experiments.ai_duplicate_benchmark.question_probe --dataset album_deduplicator/logs/ai-duplicate-benchmark/confidence-research/fresh-cases.jsonl --output album_deduplicator/logs/ai-duplicate-benchmark/confidence-research/new-probe --repeats 2 --budget 0.5
```

The fresh review envelope binds both source snapshot hashes; mismatches block
dataset construction. Its 20 album families exclude the previous reviewed
families and their transitive aliases. This is metadata-only evidence. More
questions and higher cutoffs can remove all positive approvals, producing zero
dangerous positives while making automation unhelpful. Always inspect positive
approval counts, reference uncertainty, stable family coverage and intervals.

API contracts: [Decisions guide](https://openrouter.ai/blog/insights/what-is-jev/),
[key creation](https://openrouter.ai/docs/api/api-reference/api-keys/create-keys),
[Clef models and input limit](https://openrouter.ai/cloudflare).
