"""Independent model processes over a frozen shared cohort and capped total budget."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from .client import BenchmarkError, DEFAULT_MODELS, OpenRouterClient, PROMPT_VERSION, build_payload, compact, estimate_cost
from .runner import HERE, DEFAULT_RULES, TRUNCATING_MODELS, digest, load_tokenizer, read_jsonl, utc_now


def select_cohort(cases, models, catalog, rules, count_tokens=None, *, full_context=False, max_tokens=256):
    if full_context and TRUNCATING_MODELS.intersection(models):
        raise BenchmarkError('Known truncating Clef/Flash models cannot use full-context lane')
    if not full_context and count_tokens is None:
        raise BenchmarkError('Shared suite requires verified --tokenizer')
    if not cases or not models or len(models)!=len(set(models)):
        raise BenchmarkError('Cases and unique models are required')
    if len({c['case_id'] for c in cases}) != len(cases): raise BenchmarkError('Duplicate dataset case IDs')
    missing=[m for m in models if m not in catalog]
    if missing: raise BenchmarkError('Models missing from catalog: '+', '.join(missing))
    context=min(int(catalog[m]['context_length']) for m in models)
    cohort,excluded=[],[]
    for case in cases:
        sizes=[]
        exact=[]
        for model in models:
            payload=compact(build_payload(model,case['input'],rules,max_tokens,catalog[model]['pricing']))
            sizes.append(len(payload.encode('utf-8'))+64)
            if count_tokens is not None: exact.append(count_tokens(payload)+64)
        # Also protect each child's shared Clef guard, even in a chat-only compact suite.
        if not full_context:
            exact.append(count_tokens(compact(build_payload('cloudflare/clef',case['input'],rules,max_tokens)))+64)
        reason=None
        if max(sizes)+max_tokens>context: reason='full payload exceeds common conservative catalog context'
        elif not full_context and max(exact)>1800: reason='largest full payload exceeds shared 1800 token guard'
        if reason:
            excluded.append(dict(case,exclusion={'reason':reason,'max_guard_tokens':max(exact) if exact else None}))
        else: cohort.append(case)
    return cohort,excluded


def planned_cost(cases,models,catalog,rules,*,repeats=3,max_tokens=256):
    if repeats<1: raise BenchmarkError('Repeats must be positive')
    return {model:sum(estimate_cost(catalog[model],len(compact(build_payload(model,c['input'],rules,
        max_tokens,catalog[model]['pricing'])).encode('utf-8'))+64,max_tokens) for c in cases)*repeats for model in models}


def aggregate_records(paths):
    rows=[]
    seen=set()
    for path in paths:
        for row in read_jsonl(path):
            key=(row['case_id'],row['model'],row['repeat'])
            if key in seen: raise BenchmarkError('Duplicate model/case/repeat key in aggregate records')
            seen.add(key)
            rows.append(row)
    return rows


def freeze_file(path,content):
    if path.exists():
        if path.read_text(encoding='utf-8') != content:
            raise BenchmarkError('Frozen suite data or configuration changed; use a new output directory')
    else:
        with path.open('x',encoding='utf-8',newline='\n') as handle: handle.write(content)


def run_suite(client,cases,output,rules,models=DEFAULT_MODELS,*,tokenizer_path=None,
              full_context=False,repeats=3,budget=2,max_tokens=256,seed=42,env_path=HERE/'.env',rules_path=DEFAULT_RULES):
    if not 0<budget<=2: raise BenchmarkError('Total suite budget must be at most $2')
    count,tokenizer_meta=load_tokenizer(tokenizer_path) if tokenizer_path else (None,None)
    catalog=client.catalog()
    cohort,excluded=select_cohort(cases,models,catalog,rules,count,full_context=full_context,max_tokens=max_tokens)
    if not cohort: raise BenchmarkError('No complete cases fit shared cohort')
    bounds=planned_cost(cohort,models,catalog,rules,repeats=repeats,max_tokens=max_tokens)
    total=sum(bounds.values())
    if total>budget: raise BenchmarkError(f'Conservative aggregate planned cost ${total:.6f} exceeds suite budget ${budget:.2f}')
    key=client.preflight()
    cap=key.get('limit')
    if cap is None or not 0<float(cap)<=2 or key.get('limit_reset') is not None:
        raise BenchmarkError('Suite requires dedicated key cap <=$2 without reset')
    if key.get('limit_remaining') is not None and total>float(key['limit_remaining']):
        raise BenchmarkError('Aggregate planned cost exceeds dedicated key remaining balance')
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    cohort_path=output/'cohort.jsonl'
    freeze_file(cohort_path,''.join(compact(c)+'\n' for c in cohort))
    freeze_file(output/'excluded.jsonl',''.join(compact(c)+'\n' for c in excluded))
    config={'cohort_hash':digest(cohort),'excluded_hash':digest(excluded),'rules_hash':digest(rules),
        'models':list(models),'repeats':repeats,'budget_usd':budget,'seed':seed,'max_tokens':max_tokens,
        'lane':'full_context' if full_context else 'tokenized_compact','tokenizer':tokenizer_meta,
        'prompt_version':PROMPT_VERSION,'concurrency':len(models),'concurrency_note':
        'One sequential runner per model; parallel execution measures concurrent request latency, not dedicated throughput'}
    transport_timeout = getattr(client,'timeout',120)
    config['transport_timeout_seconds'] = transport_timeout
    freeze_file(output/'suite-manifest.json',compact(config)+'\n')
    processes=[]
    expected=len(cohort)*len(models)*repeats
    print(compact({'stage':'starting','cases':len(cohort),'excluded':len(excluded),'models':len(models),
        'requests':expected,'conservative_cost_usd':total,'concurrency':len(models)}),flush=True)
    for index,model in enumerate(models):
        model_output=output/'models'/f'{index:02d}-{model.replace("/","_")}'
        args=[sys.executable,'-m','album_deduplicator.experiments.ai_duplicate_benchmark.runner','run',
            '--dataset',str(cohort_path),'--output',str(model_output),'--env',str(Path(env_path).resolve()),
            '--rules',str(Path(rules_path).resolve()),'--models',model,'--repeats',str(repeats),
            '--budget',str(budget),'--max-tokens',str(max_tokens),'--seed',str(seed),
            '--timeout',str(transport_timeout)]
        if full_context: args.append('--full-context')
        else: args.extend(['--tokenizer',str(Path(tokenizer_path).resolve())])
        process=subprocess.Popen(args,cwd=HERE.parents[2],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        processes.append({'model':model,'process':process,'output':model_output})
    last_progress=time.monotonic()
    try:
        while any(item['process'].poll() is None for item in processes):
            if time.monotonic()-last_progress>=30:
                completed=sum(len(read_jsonl(item['output']/'records.jsonl')) for item in processes)
                print(compact({'stage':'progress','records':completed,'expected':expected,
                    'running_models':sum(item['process'].poll() is None for item in processes)}),flush=True)
                last_progress=time.monotonic()
            time.sleep(1)
    except KeyboardInterrupt:
        for item in processes:
            if item['process'].poll() is None: item['process'].terminate()
        for item in processes: item['process'].wait()
        raise
    states=[]
    for item in processes:
        child_output,_=item['process'].communicate()
        (item['output']/'runner-output.txt').write_text(child_output,encoding='utf-8')
        states.append({'model':item['model'],'exit_code':item['process'].returncode})
    rows=aggregate_records([item['output']/'records.jsonl' for item in processes])
    allowed={(c['case_id'],m,r) for c in cohort for m in models for r in range(repeats)}
    if any((r['case_id'],r['model'],r['repeat']) not in allowed for r in rows):
        raise BenchmarkError('Aggregate contains records outside frozen cohort')
    freeze_file(output/'records.jsonl',''.join(compact(row)+'\n' for row in rows))
    from .report import write_report
    summary=write_report(cohort,rows,output)
    result={'timestamp':utc_now(),'models':states,'records':len(rows),'expected_records':expected,
        'known_cost_usd':sum(r.get('cost_usd') or 0 for r in rows),'unknown_cost_attempts':
        sum(r.get('cost_usd') is None and r.get('status')!='skipped_oversize' for r in rows),
        'complete':all(s['exit_code']==0 for s in states) and len(rows)==expected,
        'summary_path':str(output/'summary.json'),'report_path':str(output/'report.md')}
    (output/'suite-result.json').write_text(compact(result)+'\n',encoding='utf-8')
    print(compact(result),flush=True)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--tokenizer',type=Path)
    parser.add_argument('--full-context',action='store_true')
    parser.add_argument('--env',type=Path,default=HERE/'.env')
    parser.add_argument('--rules',type=Path,default=DEFAULT_RULES)
    parser.add_argument('--models',nargs='+',default=list(DEFAULT_MODELS))
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--budget',type=float,default=2)
    parser.add_argument('--max-tokens',type=int,default=256)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--timeout',type=float,default=120)
    args=parser.parse_args(argv)
    try:
        result=run_suite(OpenRouterClient(env_path=args.env,timeout=args.timeout),read_jsonl(args.dataset),args.output,
            args.rules.read_text(encoding='utf-8-sig'),args.models,tokenizer_path=args.tokenizer,
            full_context=args.full_context,repeats=args.repeats,budget=args.budget,
            max_tokens=args.max_tokens,seed=args.seed,env_path=args.env,rules_path=args.rules)
        return 0 if result['complete'] else 2
    except (BenchmarkError,OSError,ValueError,KeyError) as exc:
        print(str(exc) if isinstance(exc,BenchmarkError) else 'Invalid local suite input or unavailable process',file=sys.stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())
