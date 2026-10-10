import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from album_deduplicator.experiments.ai_duplicate_benchmark.client import BenchmarkError
from album_deduplicator.experiments.ai_duplicate_benchmark.suite import select_cohort, aggregate_records, planned_cost, run_suite


class SuiteTests(unittest.TestCase):
    def test_shared_cohort_uses_largest_payload(self):
        cases=[{'case_id':'a','input':{'album1':{},'album2':{}}},
               {'case_id':'b','input':{'album1':{'album':'large'},'album2':{}}}]
        models=['cloudflare/clef','x']
        catalog={m:{'context_length':64000,'pricing':{'prompt':'0','completion':'0'}} for m in models}
        def count(text): return 1800 if 'large' in text and 'messages' in text else 1000
        cohort,excluded=select_cohort(cases,models,catalog,'rules',count)
        self.assertEqual([c['case_id'] for c in cohort],['a'])
        self.assertEqual([c['case_id'] for c in excluded],['b'])

    def test_aggregation_rejects_duplicates(self):
        row={'case_id':'a','model':'x','repeat':0}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            first=Path(d)/'one.jsonl'
            second=Path(d)/'two.jsonl'
            first.write_text('{"case_id":"a","model":"x","repeat":0}\n')
            second.write_text(first.read_text())
            with self.assertRaisesRegex(BenchmarkError,'Duplicate'):
                aggregate_records([first,second])

    def test_planned_cost_counts_every_model_repeat(self):
        models=['x','y']
        catalog={m:{'context_length':64000,'pricing':{'prompt':'0','completion':'0','request':'.1'}} for m in models}
        cases=[{'case_id':'a','input':{'album1':{},'album2':{}}}]
        per_model=planned_cost(cases,models,catalog,'rules',repeats=3)
        self.assertAlmostEqual(sum(per_model.values()),.66)

    def test_suite_blocks_uncapped_key_before_process_launch(self):
        class Fake:
            def catalog(self): return {'x':{'context_length':64000,'pricing':{'prompt':'0','completion':'0'}}}
            def preflight(self): return {'limit':None}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            with patch('subprocess.Popen') as launch:
                with self.assertRaisesRegex(BenchmarkError,'dedicated key cap'):
                    run_suite(Fake(),[{'case_id':'a','input':{'album1':{},'album2':{}}}],
                        Path(d),'rules',['x'],full_context=True)
            launch.assert_not_called()

    def test_suite_aggregate_budget_block_before_process_launch(self):
        class Fake:
            def catalog(self): return {m:{'context_length':64000,'pricing':{'prompt':'0','completion':'0','request':'1'}} for m in ('x','y')}
            def preflight(self): raise AssertionError('budget must be checked first')
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            with patch('subprocess.Popen') as launch:
                with self.assertRaisesRegex(BenchmarkError,'aggregate planned cost'):
                    run_suite(Fake(),[{'case_id':'a','input':{'album1':{},'album2':{}}}],
                        Path(d),'rules',['x','y'],full_context=True)
            launch.assert_not_called()


if __name__ == '__main__': unittest.main()
