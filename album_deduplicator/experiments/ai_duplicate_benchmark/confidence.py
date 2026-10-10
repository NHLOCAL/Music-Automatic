"""Offline selective decision policies. Confidence measures concentration, not truth."""
from __future__ import annotations

import argparse
from collections import defaultdict
import itertools
import json
import math
from pathlib import Path

from .client import BenchmarkError, DECISION_MODELS
from .metrics import LABELS, _probabilities, ratio, successful, truth_label, verdict, wilson
from .runner import digest, read_jsonl

THRESHOLDS = (.8,.9,.95,.98,.99)
MARGINS = (0,.1,.2,.3)


def _confidence(row):
    value=row.get('confidence') if row else None
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=1 else None


def apply_thresholds(row, config):
    if config.get('reject_all') or not row or not successful(row): return 'review'
    probabilities=_probabilities(row)
    if probabilities is None: return 'review'
    pos=probabilities['duplicate']
    neg=probabilities['different']
    if config.get('score_kind','probability')=='provider_confidence':
        confidence=_confidence(row)
        if confidence is None: return 'review'
        positive_score=confidence if pos==max(probabilities.values()) else -1
        negative_score=confidence if neg==max(probabilities.values()) else -1
    else:
        positive_score,negative_score=pos,neg
    if (positive_score>=config['positive_threshold'] and
            pos-max(neg,probabilities['uncertain'])>=config.get('margin',0)):
        return 'duplicate'
    if negative_score>=config['negative_threshold']: return 'different'
    return 'review'


def _indexed(rows,models):
    index={}
    for row in rows:
        if row.get('model') not in models: continue
        key=(row['case_id'],row['model'],row.get('repeat',0))
        if key in index: raise BenchmarkError('Duplicate case/model/repeat records in confidence analysis')
        index[key]=row
    return index


def _cases(cases,split):
    return [c for c in cases if (split is None or c.get('split')==split) and truth_label(c) in LABELS]


def _measure(cases,rows,models,action,split,repeats):
    selected=_cases(cases,split)
    index=_indexed(rows,models)
    attempts=[]
    flags=[]
    for case in selected:
        case_rows=[]
        for repeat in range(repeats):
            inputs=[index.get((case['case_id'],model,repeat)) for model in models]
            decided=action(inputs)
            item={'case_id':case['case_id'],'repeat':repeat,'truth':truth_label(case),'action':decided,
                'success':all(r is not None and successful(r) for r in inputs),
                'known_cost_usd':sum(r.get('cost_usd') or 0 for r in inputs if r),
                'unknown_cost_calls':sum(r is not None and r.get('cost_usd') is None for r in inputs),
                'missing_calls':sum(r is None for r in inputs)}
            attempts.append(item)
            case_rows.append(item)
        flags.append({'case_id':case['case_id'],'truth':truth_label(case),
            'any_unsafe_positive':any(r['action']=='duplicate' and r['truth']!='duplicate' for r in case_rows),
            'any_duplicate_negative':any(r['action']=='different' and r['truth']=='duplicate' for r in case_rows),
            'any_positive':any(r['action']=='duplicate' for r in case_rows),
            'any_review':any(r['action']=='review' for r in case_rows),
            'fully_automated':all(r['action']!='review' for r in case_rows),
            'any_failed_call':any(not r['success'] for r in case_rows)})
    positive=[r for r in attempts if r['action']=='duplicate']
    negative=[r for r in attempts if r['action']=='different']
    auto=positive+negative
    unsafe=sum(r['truth']!='duplicate' for r in positive)
    missed=sum(r['truth']=='duplicate' for r in negative)
    positive_cases=[f for f in flags if f['any_positive']]
    truepositive_cases=sum(f['truth']=='duplicate' for f in positive_cases)
    nonduplicate=[f for f in flags if f['truth']!='duplicate']
    duplicate=[f for f in flags if f['truth']=='duplicate']
    unsafe_cases=sum(f['any_unsafe_positive'] for f in flags)
    missed_cases=sum(f['any_duplicate_negative'] for f in flags)
    return {'split':split,'unique_cases':len(selected),'attempts':len(attempts),'repeats':repeats,
        'successful_decisions':sum(r['success'] for r in attempts),
        'coverage':ratio(len(auto),len(attempts)),'fully_automated_cases':sum(f['fully_automated'] for f in flags),
        'auto_positive_precision':ratio(len(positive)-unsafe,len(positive)),
        'auto_positive_precision_unique_cases':dict(ratio(truepositive_cases,len(positive_cases)),
            wilson_95=wilson(truepositive_cases,len(positive_cases))),
        'unsafe_positive_attempts':unsafe,'unsafe_positive_unique_cases':unsafe_cases,
        'unsafe_positive_different':sum(r['truth']=='different' for r in positive),
        'unsafe_positive_uncertain':sum(r['truth']=='uncertain' for r in positive),
        'unsafe_positive_unique_case_rate':dict(ratio(unsafe_cases,len(nonduplicate)),wilson_95=wilson(unsafe_cases,len(nonduplicate))),
        'safe_negative_falsemisses':missed,'duplicate_negative_unique_cases':missed_cases,
        'duplicate_negative_unique_case_rate':dict(ratio(missed_cases,len(duplicate)),wilson_95=wilson(missed_cases,len(duplicate))),
        'negative_on_uncertain':sum(r['truth']=='uncertain' for r in negative),
        'correct_auto_decisions':sum(r['action']==r['truth'] for r in auto),
        'review_attempts':sum(r['action']=='review' for r in attempts),
        'true_uncertain_review':sum(r['action']=='review' and r['truth']=='uncertain' for r in attempts),
        'duplicate_review':sum(r['action']=='review' and r['truth']=='duplicate' for r in attempts),
        'different_review':sum(r['action']=='review' and r['truth']=='different' for r in attempts),
        'known_cost_usd':sum(r['known_cost_usd'] for r in attempts),
        'unknown_cost_calls':sum(r['unknown_cost_calls'] for r in attempts),
        'missing_calls':sum(r['missing_calls'] for r in attempts),
        'case_flags':flags,'attempt_actions':attempts,
        'interpretation':'Review is safe deferral, never a correct prediction of uncertain. Repetitions do not increase independent case count. Intervals are descriptive on selected metadata cases.'}


def evaluate_policy(cases,rows,model,config,*,split='test',repeats=3):
    if model not in DECISION_MODELS:
        raise BenchmarkError('Confidence policy requires a supported decision model')
    return _measure(cases,rows,[model],lambda items:apply_thresholds(items[0],config),split,repeats)


def fit_thresholds(cases,rows,model,*,repeats=3,score_kind='probability'):
    if score_kind not in ('probability','provider_confidence'): raise BenchmarkError('Unknown confidence score kind')
    calibration=_cases(cases,'calibration')
    calibration_families={c.get('group_id',c['case_id']) for c in calibration}
    test_families={c.get('group_id',c['case_id']) for c in _cases(cases,'test')}
    if calibration_families & test_families:
        raise BenchmarkError('Calibration/test family overlap; threshold fitting blocked')
    base={'score_kind':score_kind,'calibration_cases':len(calibration),
        'calibration_hash':digest(calibration),'fit_constraints':
        'Zero unsafe positive attempts and zero duplicate cases routed negative on calibration only'}
    if not calibration: return dict(base,reject_all=True,reason='No labeled calibration families')
    accepted=[]
    for positive,negative,margin in itertools.product(THRESHOLDS,THRESHOLDS,MARGINS):
        config={'score_kind':score_kind,'positive_threshold':positive,'negative_threshold':negative,'margin':margin}
        metrics=evaluate_policy(calibration,rows,model,config,split='calibration',repeats=repeats)
        if metrics['unsafe_positive_attempts']==0 and metrics['safe_negative_falsemisses']==0:
            accepted.append((metrics['coverage']['numerator'],positive+negative,margin,config,metrics))
    if not accepted: return dict(base,reject_all=True,reason='No finite-grid configuration met safety constraints')
    # Prefer higher automation, then more conservative score thresholds and margin.
    best=max(accepted,key=lambda item:item[:3])
    return dict(base,**best[3],reject_all=best[0]==0,calibration_coverage=best[4]['coverage'],
        calibration_auto_positive_precision=best[4]['auto_positive_precision'])


def evaluate_agreement(cases,rows,models,*,threshold=.9,negative_threshold=.9,split='test',repeats=3,score_kind='probability'):
    if len(models)<2 or len(set(models))!=len(models): raise BenchmarkError('Agreement needs distinct models')
    if any(model not in DECISION_MODELS for model in models): raise BenchmarkError('Agreement confidence requires supported decision models')
    if score_kind not in ('probability','provider_confidence'): raise BenchmarkError('Unknown confidence score kind')
    config={'positive_threshold':threshold,'negative_threshold':negative_threshold,'margin':0,'score_kind':score_kind}
    def action(items):
        actions=[apply_thresholds(r,config) for r in items]
        return actions[0] if len(set(actions))==1 and actions[0]!='review' else 'review'
    result=_measure(cases,rows,models,action,split,repeats)
    index=_indexed(rows,models)
    shared_positive=shared_negative=0
    for case in _cases(cases,split):
        for repeat in range(repeats):
            matched=[index.get((case['case_id'],model,repeat)) for model in models]
            if not all(r and successful(r) for r in matched): continue
            raw=[verdict(r) for r in matched]
            shared_positive+=int(all(v=='duplicate' for v in raw) and truth_label(case)!='duplicate')
            shared_negative+=int(all(v=='different' for v in raw) and truth_label(case)=='duplicate')
    result.update(score_kind=score_kind,shared_unsafe_raw_positive_attempts=shared_positive,
        shared_duplicate_raw_negative_attempts=shared_negative,
        agreement_note='Cross-model agreement is not independent evidence; matching mistakes can persist. Native-confidence mode reviews when any native confidence is missing.')
    return result


def confidence_diagnostics(cases,rows,model):
    ids={c['case_id'] for c in _cases(cases,None)}
    pairs=[]
    for row in rows:
        if row.get('model')!=model or row.get('case_id') not in ids or not successful(row): continue
        p=_probabilities(row)
        conf=_confidence(row)
        if p is not None and conf is not None:
            chosen=p[verdict(row)]
            expected=(3*max(p.values())-1)/2
            pairs.append({'case_id':row['case_id'],'repeat':row.get('repeat',0),
                'provider_confidence':conf,'p_chosen':chosen,'three_choice_concentration':expected,
                'confidence_minus_p_chosen':conf-chosen,'confidence_minus_concentration':conf-expected})
    return {'matched_attempts':len(pairs),'unique_cases':len({r['case_id'] for r in pairs}),
        'mean_provider_confidence':sum(r['provider_confidence'] for r in pairs)/len(pairs) if pairs else None,
        'mean_p_chosen':sum(r['p_chosen'] for r in pairs)/len(pairs) if pairs else None,
        'mean_absolute_confidence_vs_concentration':sum(abs(r['confidence_minus_concentration']) for r in pairs)/len(pairs) if pairs else None,
        'definition':'TypeSafe confidence=(p_max-1/n)/(1-1/n); for three options (3*p_max-1)/2. Concentration is not probability of correctness, and confidence is not multiplied by p_choice.',
        'source':'https://docs.typesafe.ai/confidence','attempts':pairs}


def write_confidence_report(cases,rows,output_dir,*,repeats=3):
    available={r.get('model') for r in rows}
    models=[m for m in DECISION_MODELS if m in available and m!='cloudflare/clef-omni']
    result={'dataset_hash':digest(cases),'records_hash':digest(rows),'unique_cases':len(cases),
        'repeats':repeats,'models':{},'agreement':{},'warnings':[
        'Native decision confidence and probabilities are not calibrated correctness guarantees',
        'Threshold selection uses calibration families only; test labels never tune settings',
        'Review is reported as safe_deferral, not rewarded as accurate uncertain',
        'Small curated metadata-only reference set; descriptive case intervals do not imply production safety']}
    for model in models:
        entry={'diagnostics':confidence_diagnostics(cases,rows,model),'policies':{},'risk_coverage_grid':[]}
        entry['raw']=_measure(cases,rows,[model],lambda items:
            verdict(items[0]) if items[0] and successful(items[0]) and verdict(items[0])!='uncertain' else 'review','test',repeats)
        for kind in ('probability','provider_confidence'):
            config=fit_thresholds(cases,rows,model,repeats=repeats,score_kind=kind)
            entry['policies'][kind]={'frozen_config':config,
                'calibration':evaluate_policy(cases,rows,model,config,split='calibration',repeats=repeats),
                'test':evaluate_policy(cases,rows,model,config,split='test',repeats=repeats)}
            for threshold in THRESHOLDS:
                config={'score_kind':kind,'positive_threshold':threshold,'negative_threshold':threshold,'margin':0}
                metrics=evaluate_policy(cases,rows,model,config,split='test',repeats=repeats)
                entry['risk_coverage_grid'].append({'score_kind':kind,'threshold':threshold,
                    'coverage':metrics['coverage'],'positive_precision':metrics['auto_positive_precision'],
                    'unsafe_positive_cases':metrics['unsafe_positive_unique_cases'],
                    'duplicate_negative_cases':metrics['duplicate_negative_unique_cases']})
        result['models'][model]=entry
    for pair in itertools.combinations(models,2):
        for kind in ('probability','provider_confidence'):
            name=' + '.join(pair)+(f' [{kind}]' if kind!='probability' else '')
            result['agreement'][name]={'models':pair,'score_kind':kind,'positive_threshold':.9,'negative_threshold':.9,
                'test':evaluate_agreement(cases,rows,pair,repeats=repeats,score_kind=kind)}
    output=Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    (output/'confidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    def pct(metric):
        value=metric.get('value')
        return f'{100*value:.1f}%' if value is not None else 'n/a'
    text=['# Decision confidence research','',
        'Native confidence measures probability concentration, not correctness. With three options, the TypeSafe definition is `(3*p_max-1)/2`. A confidence of 0.95 is not the same score as a chosen-option probability of 0.95. [Definition](https://docs.typesafe.ai/confidence)','',
        'Fit uses calibration families only and requires zero unsafe positives and zero duplicates routed negative. Thresholds are frozen before the test split is evaluated. Review is safe deferral, not a correct uncertain prediction. Repetitions do not enlarge the independent sample size.','',
        '| Model | Score | Test auto coverage | Positive precision | Unsafe positive cases | Duplicate negative cases | Correct auto / attempts |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for model,entry in result['models'].items():
        for kind,value in [('raw',{'test':entry['raw']}),*entry['policies'].items()]:
            m=value['test']
            text.append(f"| {model} | {kind} | {pct(m['coverage'])} | {pct(m['auto_positive_precision'])} | {m['unsafe_positive_unique_cases']} | {m['duplicate_negative_unique_cases']} | {m['correct_auto_decisions']}/{m['attempts']} |")
    for model,entry in result['models'].items():
        text += ['',f'## {model}','',f"Frozen configs: `{json.dumps({k:v['frozen_config'] for k,v in entry['policies'].items()},ensure_ascii=False)}`",'',
            '| Score | Threshold | Test auto coverage | Positive precision | Unsafe positive cases | Duplicate negative cases |',
            '| --- | --- | --- | --- | --- | --- |']
        for row in entry['risk_coverage_grid']:
            text.append(f"| {row['score_kind']} | {row['threshold']} | {pct(row['coverage'])} | {pct(row['positive_precision'])} | {row['unsafe_positive_cases']} | {row['duplicate_negative_cases']} |")
    text += ['','## Cross-model agreement','',
        'Each matching case/repeat uses both models. Probability mode requires both `p_duplicate >= 0.9` for positives or both `p_different >= 0.9` for negatives. Native-confidence mode requires both selected-class confidence scores >=0.9 and reviews missing confidence. Otherwise review. Agreement is not independent evidence; models may share mistakes. Cost includes both recorded calls and lists unknown costs separately in JSON.','',
        '| Models | Test auto coverage | Positive precision | Unsafe positive cases | Duplicate negative cases | Known cost USD |',
        '| --- | --- | --- | --- | --- | --- |']
    for name,value in result['agreement'].items():
        m=value['test']
        text.append(f"| {name} | {pct(m['coverage'])} | {pct(m['auto_positive_precision'])} | {m['unsafe_positive_unique_cases']} | {m['duplicate_negative_unique_cases']} | {m['known_cost_usd']:.6f} |")
    text += ['','Case flags and Wilson intervals use each distinct case once. The risk/coverage grid is diagnostic and must not be used to select a new threshold from test labels. Small metadata-only reference sets cannot establish production precision.']
    (output/'confidence.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',required=True,type=Path)
    parser.add_argument('--records',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    result=write_confidence_report(read_jsonl(args.dataset),read_jsonl(args.records),args.output)
    print(json.dumps({'models':list(result['models']),'unique_cases':result['unique_cases'],'output':str(args.output)}))
    return 0


if __name__=='__main__': raise SystemExit(main())
