"""Paid benchmark runner with immutable attempts and conservative accounting."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
import uuid

from .client import (BenchmarkError, OpenRouterClient, DEFAULT_MODELS, DECISION_MODELS, PROMPT_VERSION,
                     build_payload, compact, estimate_cost, parse_response)

HERE = Path(__file__).resolve().parent
DEFAULT_RULES = HERE.parents[1] / 'music_dup_lib/external/gemini_system_instruction.txt'
CLEF_TOKENIZER_SHA256 = '06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523'
TRUNCATING_MODELS = {'cloudflare/clef', 'cloudflare/clef-flash'}


def load_tokenizer(path):
    """Only the verified common official Clef/Flash tokenizer, never remote code."""
    path = Path(path)
    try:
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha256 != CLEF_TOKENIZER_SHA256:
            raise BenchmarkError('Tokenizer hash does not match verified official Cloudflare Clef/Flash tokenizer')
        from tokenizers import Tokenizer
        tokenizer = Tokenizer.from_file(str(path))
        tokenizer.no_truncation()
        tokenizer.no_padding()
    except ImportError:
        raise BenchmarkError('Optional tokenizers package is required for --tokenizer; install in isolated experiment venv') from None
    except (OSError,ValueError):
        raise BenchmarkError('Cannot load local tokenizer file') from None
    return (lambda text: len(tokenizer.encode(text,add_special_tokens=True).ids)), {
        'sha256':sha256,'source':'https://huggingface.co/Cloudflare/clef-flash/blob/41318bf2106d135c7a92da745fec4b255279b4de/tokenizer.json',
        'covers':['cloudflare/clef-flash','cloudflare/clef'],
        'method':'complete JSON decision payload tokens plus 64 framing tokens; limit <=1800',
    }


def digest(value):
    return hashlib.sha256(compact(value).encode('utf-8')).hexdigest()


def read_jsonl(path):
    rows = []
    if Path(path).exists():
        for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
            if line.strip():
                try: rows.append(json.loads(line))
                except ValueError: raise BenchmarkError(f'Invalid JSONL at line {number}') from None
    return rows


def append_record(path, record):
    with Path(path).open('a',encoding='utf-8',newline='\n') as handle:
        handle.write(compact(record) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_benchmark(client, cases, output, rules, models=DEFAULT_MODELS, *, repeats=3,
                  budget=2, seed=42, max_tokens=256, context_budget=1900, limit=None,
                  tokenizer_path=None, full_context=False):
    if not 0 < budget <= 2 or repeats < 1 or max_tokens < 1:
        raise BenchmarkError('Invalid repeats, output cap or budget (maximum $2)')
    if not models or len(models) != len(set(models)): raise BenchmarkError('Models must be a nonempty unique list')
    if full_context and TRUNCATING_MODELS.intersection(models):
        raise BenchmarkError('Known truncating Clef/Flash models cannot use --full-context')
    count_tokens, tokenizer_metadata = load_tokenizer(tokenizer_path) if tokenizer_path else (None,None)
    lane = 'full_context' if full_context else 'tokenized_compact' if count_tokens else 'conservative_bytes'
    transport_timeout = getattr(client,'timeout',60)
    if limit is not None:
        if limit < 1: raise BenchmarkError('Case limit must be positive')
        cases = cases[:limit]
    if not cases: raise BenchmarkError('Dataset is empty')
    ids = [c['case_id'] for c in cases]
    if len(ids) != len(set(ids)): raise BenchmarkError('Dataset case IDs must be unique')
    for case in cases: build_payload(models[0],case['input'],rules,max_tokens)
    output = Path(output)
    output.mkdir(parents=True,exist_ok=True)
    fingerprint = digest({'cases':cases,'models':list(models),'rules':rules,'repeats':repeats,
        'budget':budget,'seed':seed,'max_tokens':max_tokens,'context_budget':context_budget,
        'lane':lane,'tokenizer':tokenizer_metadata,'version':2,'prompt_version':PROMPT_VERSION,
        'transport_timeout_seconds':transport_timeout})
    manifest_path, records_path = output/'manifest.json', output/'records.jsonl'
    inflight_path, lock_path = output/'inflight.json', output/'run.lock'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('fingerprint') != fingerprint:
            raise BenchmarkError('Resume fingerprint mismatch: dataset, rules or settings changed')
    else:
        if records_path.exists(): raise BenchmarkError('Records exist without a manifest; refusing unsafe resume')
        manifest = {'fingerprint':fingerprint,'created_at':utc_now(),'models':list(models),
            'dataset_hash':digest(cases),'rules_hash':digest(rules),'repeats':repeats,'budget_usd':budget,
            'seed':seed,'max_tokens':max_tokens,'context_budget':context_budget,'case_count':len(cases),
            'lane':lane,'tokenizer':tokenizer_metadata,'prompt_version':PROMPT_VERSION,
            'transport_timeout_seconds':transport_timeout}
        manifest_path.write_text(compact(manifest)+'\n',encoding='utf-8')
    records = read_jsonl(records_path)
    for record in records:
        if record.get('run_fingerprint') != fingerprint: raise BenchmarkError('Record fingerprint mismatch')
    recorded_ids = {r['attempt_id'] for r in records}
    if inflight_path.exists():
        inflight = json.loads(inflight_path.read_text(encoding='utf-8'))
        if inflight.get('attempt_id') not in recorded_ids:
            raise BenchmarkError('Interrupted billable attempt has unknown cost; reconcile in OpenRouter before a new run')
        inflight_path.unlink()
    if any(r['status'] not in ('ok','skipped_oversize') and r.get('cost_usd') is None for r in records):
        raise BenchmarkError('Previous attempt has unknown cost; further paid calls blocked')
    spent = sum(r.get('cost_usd') or 0 for r in records)
    completed = {(r['case_id'],r['model'],r['repeat']) for r in records}
    catalog = client.catalog()
    missing = [m for m in models if m not in catalog]
    if missing: raise BenchmarkError('Models missing from live catalog: ' + ', '.join(missing))
    if not 64 < context_budget <= 1900:
        raise BenchmarkError('Shared state byte cap must be between 65 and 1900 to protect Clef truncation')
    shared_context = min(int(catalog[m].get('context_length') or 1900) for m in models)
    # One byte per token upper bound includes all rules and complete structured schema.
    estimates = {}
    size_records = {}
    oversize = set()
    for case in cases:
        sizes = []
        for model in models:
            payload = build_payload(model,case['input'],rules,max_tokens,catalog[model]['pricing'])
            tokens = len(compact(payload).encode('utf-8')) + 64
            sizes.append(tokens)
            estimates[(case['case_id'],model)] = estimate_cost(catalog[model],tokens,max_tokens)
        state_bytes = len(compact(case['input']).encode('utf-8'))
        clef_tokens = None
        if count_tokens:
            # Both Clef variants have byte-identical tokenizers. Count the complete
            # decision payload (including criteria and system rules), even if only
            # chat models happen to be selected for the shared comparison lane.
            guard_payload = build_payload('cloudflare/clef',case['input'],rules,max_tokens)
            clef_tokens = count_tokens(compact(guard_payload)) + 64
        size_records[case['case_id']] = {'state_bytes':state_bytes,'clef_guard_tokens':clef_tokens,
            'conservative_full_payload_tokens':max(sizes),'lane':lane}
        shared_exceeded = (clef_tokens > min(context_budget,1800)) if count_tokens else (state_bytes + 64 > context_budget)
        if ((not full_context and shared_exceeded) or max(sizes) + max_tokens > shared_context):
            oversize.add(case['case_id'])
    tasks = [(case, model, repeat) for repeat in range(repeats) for case in cases for model in models]
    random.Random(seed).shuffle(tasks)
    remaining = sum(estimates[(c['case_id'],m)] for c,m,r in tasks
                    if (c['case_id'],m,r) not in completed and c['case_id'] not in oversize)
    if spent + remaining > budget:
        raise BenchmarkError(f'Conservative planned cost ${spent + remaining:.6f} exceeds budget ${budget:.2f}; reduce cases/repeats')
    # A dedicated provider-side cap is required in addition to local bounds.
    if hasattr(client,'preflight') and any(c['case_id'] not in oversize for c in cases):
        key = client.preflight()
        cap, reset = key.get('limit'), key.get('limit_reset')
        if cap is None or not 0 < float(cap) <= 2 or reset is not None:
            raise BenchmarkError('Paid run requires a dedicated API key capped at $2 with no limit reset')
        if key.get('limit_remaining') is not None and remaining > float(key['limit_remaining']):
            raise BenchmarkError('Dedicated API key remaining balance is below conservative planned cost')
    try:
        lockfd = os.open(lock_path,os.O_CREAT | os.O_EXCL | os.O_WRONLY,0o600)
    except FileExistsError:
        raise BenchmarkError('Run lock exists; confirm no runner is active before removing stale lock') from None
    os.close(lockfd)
    try:
        for case,model,repeat in tasks:
            if (case['case_id'],model,repeat) in completed: continue
            payload = build_payload(model,case['input'],rules,max_tokens,catalog[model]['pricing'])
            record = {'attempt_id':str(uuid.uuid4()),'run_fingerprint':fingerprint,
                'case_id':case['case_id'],'model':model,'requested_model':model,'repeat':repeat,
                'input_hash':digest(case['input']),'rules_hash':digest(rules),'prompt_hash':digest(payload),
                'timestamp':utc_now(),'endpoint':'decisions' if model in DECISION_MODELS else 'chat',
                'resolved_model':None,'provider':None,'response_id':None,'parsed_response':None,
                'usage':None,'cost_usd':None,'verdict':None,'probabilities':None,'confidence':None,
                'latency_ms':None,'status':'skipped_oversize' if case['case_id'] in oversize else 'pending'}
            record['input_size'] = size_records[case['case_id']]
            record['lane'] = lane
            record['tokenizer_sha256'] = tokenizer_metadata.get('sha256') if tokenizer_metadata else None
            record['transport_timeout_seconds'] = transport_timeout
            if record['status'] == 'skipped_oversize':
                record['skip_reason'] = 'Complete payload exceeds shared conservative input/output token cap'
                append_record(records_path,record)
                continue
            worst_cost = estimates[(case['case_id'],model)]
            if spent + worst_cost > budget: raise BenchmarkError('Next attempt exceeds remaining budget')
            inflight_path.write_text(compact(record)+'\n',encoding='utf-8')
            start = time.perf_counter()
            try:
                response = client.request_model(model,case['input'],rules,max_tokens=max_tokens)
                record.update({'parsed_response':response,'resolved_model':response.get('model'),
                               'provider':response.get('provider'),'response_id':response.get('id'),
                               'usage':response.get('usage')})
                # Persist actual reported cost even if the verdict shape is malformed.
                raw_cost = (response.get('usage') or {}).get('cost')
                if raw_cost is not None:
                    import math
                    actual = float(raw_cost)
                    if math.isfinite(actual) and actual >= 0: record['cost_usd'] = actual
                record.update(parse_response(response,model in DECISION_MODELS))
                record['status'] = 'ok' if record['cost_usd'] is not None else 'missing_cost'
            except (BenchmarkError,ValueError,TypeError) as exc:
                record['status'] = 'error'
                record['error'] = str(exc) if isinstance(exc,BenchmarkError) else 'Malformed model response'
            record['latency_ms'] = (time.perf_counter() - start) * 1000
            append_record(records_path,record)
            inflight_path.unlink()
            spent += record['cost_usd'] or 0
            if record['cost_usd'] is None:
                raise BenchmarkError('Attempt cost is unknown; record saved and further paid calls blocked')
            if record['cost_usd'] > worst_cost:
                raise BenchmarkError('Actual attempt cost exceeded conservative bound; further paid calls blocked')
        return {'records_path':str(records_path),'cost_usd':spent,'case_count':len(cases),
                'skipped_case_count':len(oversize),'fingerprint':fingerprint}
    finally:
        lock_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('catalog','preflight','provision','run'))
    parser.add_argument('--dataset',type=Path)
    parser.add_argument('--output',type=Path,default=HERE/'outputs/run')
    parser.add_argument('--env',type=Path,default=HERE/'.env')
    parser.add_argument('--rules',type=Path,default=DEFAULT_RULES)
    parser.add_argument('--models',nargs='+',default=list(DEFAULT_MODELS))
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--budget',type=float,default=2)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--max-tokens',type=int,default=256)
    parser.add_argument('--context-budget',type=int,default=1900)
    parser.add_argument('--tokenizer',type=Path,help='Verified official Clef/Flash tokenizer.json for shared compact lane')
    parser.add_argument('--full-context',action='store_true',help='Complete-input lane, excludes known truncating Clef/Flash models')
    parser.add_argument('--timeout',type=float,default=120,help='HTTP transport timeout in seconds')
    args = parser.parse_args(argv)
    client = OpenRouterClient(env_path=args.env,timeout=args.timeout)
    try:
        if args.command == 'catalog':
            catalog = client.catalog()
            result = {m:catalog.get(m) for m in args.models}
        elif args.command == 'preflight': result = client.preflight()
        elif args.command == 'provision': result = client.provision_key(args.env,args.budget)
        else:
            if args.dataset is None: raise BenchmarkError('--dataset is required')
            result = run_benchmark(client,read_jsonl(args.dataset),args.output,
                args.rules.read_text(encoding='utf-8-sig'),args.models,repeats=args.repeats,
                budget=args.budget,seed=args.seed,max_tokens=args.max_tokens,
                context_budget=args.context_budget,limit=args.limit,
                tokenizer_path=args.tokenizer,full_context=args.full_context)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (BenchmarkError,OSError,ValueError,KeyError) as exc:
        print(str(exc) if isinstance(exc,BenchmarkError) else 'Invalid local input or inaccessible file',file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
