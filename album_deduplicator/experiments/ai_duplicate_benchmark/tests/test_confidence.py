import unittest

from album_deduplicator.experiments.ai_duplicate_benchmark.confidence import (
    apply_thresholds,fit_thresholds,evaluate_policy,evaluate_agreement,
)


MS='microsoft/microsoft-decision-1'
CLEF='cloudflare/clef'


def row(case_id,model=MS,repeat=0,probabilities=None):
    return {'case_id':case_id,'model':model,'repeat':repeat,'status':'ok','verdict':'duplicate',
            'probabilities':probabilities,'confidence':.99,'cost_usd':.01}


class ConfidenceTests(unittest.TestCase):
    def test_missing_probability_reviews_despite_confidence(self):
        self.assertEqual(apply_thresholds(row('a'),{'positive_threshold':.9,'negative_threshold':.9,'margin':0}), 'review')

    def test_fit_never_uses_test_labels(self):
        cases=[{'case_id':'a','group_id':'one','split':'calibration','label':'duplicate'},
               {'case_id':'b','group_id':'two','split':'test','label':'different'}]
        rows=[row('a',probabilities={'duplicate':.96,'different':.02,'uncertain':.02}),
              row('b',probabilities={'duplicate':.99,'different':.005,'uncertain':.005})]
        one=fit_thresholds(cases,rows,MS,repeats=1)
        cases[1]['label']='duplicate'
        two=fit_thresholds(cases,rows,MS,repeats=1)
        self.assertEqual(one,two)

    def test_review_not_counted_as_correct_uncertain(self):
        cases=[{'case_id':'a','split':'test','label':'uncertain'}]
        result=evaluate_policy(cases,[row('a')],MS,{'reject_all':True},repeats=1)
        self.assertEqual(result['coverage']['numerator'],0)
        self.assertEqual(result['correct_auto_decisions'],0)
        self.assertEqual(result['true_uncertain_review'],1)

    def test_false_negative_constraint_rejects_unsafe_auto_negative(self):
        cases=[{'case_id':'a','split':'calibration','label':'duplicate'}]
        rows=[row('a',probabilities={'duplicate':.001,'different':.998,'uncertain':.001})]
        config=fit_thresholds(cases,rows,MS,repeats=1)
        self.assertTrue(config['reject_all'])

    def test_repeated_case_not_three_independent_samples(self):
        cases=[{'case_id':'a','split':'test','label':'different'}]
        rows=[row('a',repeat=r,probabilities={'duplicate':.99,'different':.005,'uncertain':.005}) for r in range(3)]
        result=evaluate_policy(cases,rows,MS,{'positive_threshold':.9,'negative_threshold':.9,'margin':0})
        self.assertEqual(result['unsafe_positive_attempts'],3)
        self.assertEqual(result['unsafe_positive_unique_cases'],1)
        self.assertEqual(result['auto_positive_precision_unique_cases']['denominator'],1)

    def test_agreement_requires_both_and_tracks_cost(self):
        cases=[{'case_id':'a','split':'test','label':'duplicate'}]
        rows=[row('a',model=MS,probabilities={'duplicate':.99,'different':.005,'uncertain':.005}),
              row('a',model=CLEF,probabilities={'duplicate':.1,'different':.8,'uncertain':.1})]
        result=evaluate_agreement(cases,rows,[MS,CLEF],repeats=1)
        self.assertEqual(result['coverage']['numerator'],0)
        self.assertAlmostEqual(result['known_cost_usd'],.02)

    def test_native_confidence_is_not_chosen_probability(self):
        r=row('a',probabilities={'duplicate':.992,'different':.005,'uncertain':.003})
        r['confidence']=.987839
        cfg={'positive_threshold':.99,'negative_threshold':.99,'margin':.3}
        self.assertEqual(apply_thresholds(r,cfg),'duplicate')
        self.assertEqual(apply_thresholds(r,dict(cfg,score_kind='provider_confidence')),'review')

    def test_family_overlap_blocks_fitting(self):
        from album_deduplicator.experiments.ai_duplicate_benchmark.client import BenchmarkError
        cases=[{'case_id':'a','group_id':'same','split':'calibration','label':'duplicate'},
               {'case_id':'b','group_id':'same','split':'test','label':'duplicate'}]
        with self.assertRaisesRegex(BenchmarkError,'family overlap'):
            fit_thresholds(cases,[],MS)

    def test_native_agreement_reviews_missing_confidence_and_reports_shared_errors(self):
        cases=[{'case_id':'a','split':'test','label':'different'}]
        rows=[row('a',model=m,probabilities={'duplicate':.99,'different':.005,'uncertain':.005}) for m in (MS,CLEF)]
        rows[0]['confidence']=None
        result=evaluate_agreement(cases,rows,[MS,CLEF],repeats=1,score_kind='provider_confidence')
        self.assertEqual(result['coverage']['numerator'],0)
        self.assertEqual(result['shared_unsafe_raw_positive_attempts'],1)
        self.assertAlmostEqual(result['known_cost_usd'],.02)


if __name__=='__main__': unittest.main()
