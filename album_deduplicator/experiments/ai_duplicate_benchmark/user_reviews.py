"""Human reference overlays; notes are data and never become model inputs."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
from pathlib import Path

from .runner import digest, read_jsonl

DEFAULT_USER_REVIEWS = Path(__file__).with_name('reviews') / 'user_review_decisions.json'


def validate_export(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('decisions'), list) or not payload['decisions']:
        raise ValueError('User review export must contain nonempty decisions')
    if not isinstance(payload.get('source'), str) or not payload['source'].strip():
        raise ValueError('User review export needs source attribution')
    try:
        timestamp = dt.datetime.fromisoformat(payload['exported_at'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            raise ValueError()
    except (KeyError, AttributeError, TypeError, ValueError):
        raise ValueError('User review export needs an ISO timestamp with timezone') from None
    decisions = {}
    for row in payload['decisions']:
        if not isinstance(row, dict) or not isinstance(row.get('case_id'), str) or not row['case_id'].strip():
            raise ValueError('User review case_id must be a nonempty string')
        if row['case_id'] in decisions:
            raise ValueError('Duplicate case_id in user review export')
        if row.get('verdict') not in ('duplicate', 'different', 'uncertain'):
            raise ValueError('User review verdict must be duplicate, different or uncertain')
        if not isinstance(row.get('note', ''), str):
            raise ValueError('Review notes must be plain text data')
        decisions[row['case_id']] = {'verdict': row['verdict'], 'note': row.get('note', '')}
    return {'source': payload['source'], 'exported_at': payload['exported_at'],
            'export_sha256': digest(payload), 'decisions': decisions}


def load_user_reviews(path=DEFAULT_USER_REVIEWS):
    return validate_export(json.loads(Path(path).read_text(encoding='utf-8-sig')))


def apply_user_reviews(cases, export, *, require_exact=True):
    cases = copy.deepcopy(list(cases))
    ids = [case['case_id'] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case_id in reference dataset')
    supplied = set(export['decisions'])
    if supplied - set(ids) or (require_exact and supplied != set(ids)):
        raise ValueError('User review case IDs do not match the reference dataset')
    for case in cases:
        if case['case_id'] not in supplied:
            continue
        previous_user = case.get('user_review')
        if previous_user and previous_user.get('export_sha256') == export['export_sha256']:
            continue
        history = list(case.get('reference_history', []))
        history.append({'label': case.get('label'),
                        'label_provenance': case.get('label_provenance'),
                        'review': copy.deepcopy(case.get('review')),
                        'user_review': copy.deepcopy(previous_user),
                        'source': copy.deepcopy(case.get('source'))})
        review = dict(export['decisions'][case['case_id']],
                      provenance='user_review', source=export['source'],
                      exported_at=export['exported_at'], export_sha256=export['export_sha256'])
        case.update(label=review['verdict'], label_provenance='user_review',
                    review=copy.deepcopy(review), user_review=review,
                    reference_history=history)
    return cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, type=Path)
    parser.add_argument('--decisions', type=Path, default=DEFAULT_USER_REVIEWS)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    original = read_jsonl(args.dataset)
    cases = apply_user_reviews(original, load_user_reviews(args.decisions))
    if args.output.resolve() == args.dataset.resolve():
        raise ValueError('Write overlays to a separate output to preserve the original references')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases), encoding='utf-8')
    print(json.dumps({'cases': len(cases), 'provenance': 'user_review',
                      'changed_labels': sum(a.get('label') != b.get('label') for a, b in zip(original, cases))}))
    return 0


if __name__ == '__main__': raise SystemExit(main())
