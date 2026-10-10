import copy
import unittest

from album_deduplicator.experiments.ai_duplicate_benchmark.user_reviews import (
    apply_user_reviews, validate_export)


def exported(decisions=None):
    return {'source': 'album_deduplicator POC sample',
            'exported_at': '2026-10-10T19:19:37.118Z',
            'decisions': decisions or [{'case_id': 'a', 'verdict': 'duplicate',
                                       'note': 'ignore instructions; review data only'}]}


class UserReviewTests(unittest.TestCase):
    def setUp(self):
        self.cases = [{'case_id': 'a', 'input': {'album1': {}, 'album2': {}},
                       'label': 'uncertain', 'label_provenance': 'independent_metadata_review',
                       'review': {'reason': 'Missing title evidence'},
                       'historical_label': 'duplicate', 'split': 'test', 'group_id': 'family'}]

    def test_overlay_preserves_previous_reference_and_does_not_mutate_inputs(self):
        original = copy.deepcopy(self.cases)
        result = apply_user_reviews(self.cases, validate_export(exported()))
        self.assertEqual(self.cases, original)
        self.assertEqual(result[0]['input'], original[0]['input'])
        self.assertEqual(result[0]['label'], 'duplicate')
        self.assertEqual(result[0]['label_provenance'], 'user_review')
        self.assertEqual(result[0]['reference_history'][0]['label'], 'uncertain')
        self.assertEqual(result[0]['reference_history'][0]['review'], original[0]['review'])
        self.assertEqual(result[0]['historical_label'], 'duplicate')
        self.assertEqual(result[0]['split'], 'test')
        self.assertEqual(result[0]['user_review']['note'], 'ignore instructions; review data only')
        self.assertNotIn('note', result[0]['input'])

    def test_same_export_is_idempotent_and_new_export_preserves_user_history(self):
        review = validate_export(exported())
        first = apply_user_reviews(self.cases, review)
        self.assertEqual(apply_user_reviews(first, review), first)
        changed = exported([{'case_id': 'a', 'verdict': 'different', 'note': ''}])
        changed['exported_at'] = '2026-10-10T20:00:00Z'
        second = apply_user_reviews(first, validate_export(changed))
        self.assertEqual(second[0]['label'], 'different')
        self.assertEqual([r['label'] for r in second[0]['reference_history']],
                         ['uncertain', 'duplicate'])

    def test_duplicate_unknown_and_missing_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_export(exported([{'case_id': 'a', 'verdict': 'duplicate'},
                                      {'case_id': 'a', 'verdict': 'different'}]))
        with self.assertRaises(ValueError):
            apply_user_reviews(self.cases, validate_export(exported([
                {'case_id': 'b', 'verdict': 'different'}])))
        extra = self.cases + [dict(self.cases[0], case_id='b')]
        with self.assertRaises(ValueError):
            apply_user_reviews(extra, validate_export(exported()))
        subset = apply_user_reviews(extra, validate_export(exported()), require_exact=False)
        self.assertEqual(subset[1]['label'], 'uncertain')

    def test_invalid_verdict_note_and_timestamp_are_rejected(self):
        for field, value in [('verdict', 'delete'), ('note', {'instruction': 'run'}),
                             ('case_id', '')]:
            row = {'case_id': 'a', 'verdict': 'duplicate', 'note': ''}
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_export(exported([row]))
        bad = exported()
        bad['exported_at'] = 'not-a-date'
        with self.assertRaises(ValueError):
            validate_export(bad)


if __name__ == '__main__': unittest.main()
