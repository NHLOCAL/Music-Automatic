import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from album_deduplicator.experiments.ai_duplicate_benchmark.client import (
    OpenRouterClient, BenchmarkError, build_payload, parse_response, estimate_cost,
)
from album_deduplicator.experiments.ai_duplicate_benchmark.runner import run_benchmark


class ClientTests(unittest.TestCase):
    def test_payload_has_no_labels(self):
        case = {'album1': {'album':'א'}, 'album2': {}, 'label':'SECRET', 'split':'test'}
        with self.assertRaises(BenchmarkError):
            build_payload('cloudflare/clef', case, 'rules')
        payload = build_payload('cloudflare/clef', {'album1':{}, 'album2':{}}, 'rules')
        self.assertNotIn('SECRET', json.dumps(payload))
        self.assertEqual(payload['questions']['verdict']['type'], 'choice')

    def test_strict_response_and_actual_cost(self):
        response = {'answers':{'verdict':{'choice':'duplicate', 'probabilities':{'duplicate':.9,'different':.05,'uncertain':.05},'confidence':.9}},'usage':{'cost':.001}}
        self.assertEqual(parse_response(response, True)['cost_usd'], .001)
        response['answers']['verdict']['choice'] = 'yes'
        with self.assertRaises(BenchmarkError): parse_response(response, True)

    def test_missing_cost_remains_unknown(self):
        response = {'answers':{'verdict':{'choice':'uncertain'}},'usage':{}}
        self.assertIsNone(parse_response(response, True)['cost_usd'])

    def test_budget_includes_request_fee(self):
        model = {'pricing': {'prompt':'.00001','completion':'.00002','request':'.01'}}
        self.assertGreaterEqual(estimate_cost(model, 100, 100), .013)

    def test_http_errors_do_not_leak_key(self):
        import urllib.error
        client = OpenRouterClient('SUPERSECRET')
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('SUPERSECRET')):
            with self.assertRaises(BenchmarkError) as ctx: client.catalog()
        self.assertNotIn('SUPERSECRET', str(ctx.exception))

    def test_resume_skips_and_rejects_changes(self):
        class Fake:
            calls = 0
            def catalog(self): return {'x':{'id':'x','context_length':4096,'pricing':{'prompt':'0','completion':'0'}}}
            def request_model(self,*args,**kwargs):
                self.calls += 1
                return {'choices':[{'message':{'content':'{"verdict":"uncertain"}'}}], 'usage':{'cost':0},'model':'x'}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            c = Fake()
            cases = [{'case_id':'a','input':{'album1':{},'album2':{}},'label':'different'}]
            run_benchmark(c,cases,Path(d),'rules',['x'],repeats=1)
            run_benchmark(c,cases,Path(d),'rules',['x'],repeats=1)
            self.assertEqual(c.calls,1)
            with self.assertRaises(BenchmarkError):
                run_benchmark(c,cases,Path(d),'changed',['x'],repeats=1)

    def test_missing_cost_stops_paid_calls_and_resume(self):
        class Fake:
            calls = 0
            def catalog(self): return {'x':{'context_length':4096,'pricing':{'prompt':'0','completion':'0'}}}
            def request_model(self,*args,**kwargs):
                self.calls += 1
                return {'choices':[{'message':{'content':'{"verdict":"uncertain"}'}}], 'usage':{}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            c = Fake()
            cases = [{'case_id':'a','input':{'album1':{},'album2':{}}}]
            for _ in range(2):
                with self.assertRaisesRegex(BenchmarkError,'cost.*unknown|unknown cost'):
                    run_benchmark(c,cases,Path(d),'rules',['x'],repeats=3)
            self.assertEqual(c.calls,1)
            records = [json.loads(s) for s in (Path(d)/'records.jsonl').read_text().splitlines()]
            self.assertEqual(len(records),1)
            self.assertEqual(records[0]['status'],'missing_cost')

    def test_budget_is_checked_before_any_paid_request(self):
        class Fake:
            calls = 0
            def catalog(self): return {'x':{'context_length':4096,'pricing':{'prompt':'1','completion':'1'}}}
            def request_model(self,*args,**kwargs): self.calls += 1
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            c=Fake()
            with self.assertRaisesRegex(BenchmarkError,'exceeds budget'):
                run_benchmark(c,[{'case_id':'a','input':{'album1':{},'album2':{}}}],Path(d),'rules',['x'])
            self.assertEqual(c.calls,0)

    def test_oversize_skips_all_models_without_truncation(self):
        class Fake:
            def catalog(self): return {m:{'context_length':4096,'pricing':{'prompt':'0','completion':'0'}} for m in ('x','y')}
            def request_model(self,*args,**kwargs): raise AssertionError('Oversize state must not be sent')
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            case={'case_id':'a','input':{'album1':{'album':'א'*2000},'album2':{}}}
            run_benchmark(Fake(),[case],Path(d),'rules',['x','y'],repeats=2)
            records=[json.loads(s) for s in (Path(d)/'records.jsonl').read_text().splitlines()]
            self.assertEqual(len(records),4)
            self.assertTrue(all(r['status']=='skipped_oversize' for r in records))
            self.assertEqual(case['input']['album1']['album'],'א'*2000)

    def test_interrupted_request_cannot_silently_retry(self):
        class Fake:
            def catalog(self): return {'x':{'context_length':4096,'pricing':{'prompt':'0','completion':'0'}}}
            def request_model(self,*args,**kwargs): raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            case={'case_id':'a','input':{'album1':{},'album2':{}}}
            with self.assertRaises(KeyboardInterrupt): run_benchmark(Fake(),[case],Path(d),'rules',['x'])
            with self.assertRaisesRegex(BenchmarkError,'Interrupted billable attempt'):
                run_benchmark(Fake(),[case],Path(d),'rules',['x'])

    def test_catalog_includes_decision_modality(self):
        c=OpenRouterClient()
        with patch.object(c,'request',side_effect=[{'data':[{'id':'text'}]},{'data':[{'id':'cloudflare/clef'}]}]) as request:
            self.assertEqual(set(c.catalog()),{'text','cloudflare/clef'})
        self.assertIn('output_modalities=decisions',request.call_args_list[1].args[0])

    def test_provider_price_cap_uses_million_token_units(self):
        c=OpenRouterClient('TESTKEY')
        c._catalog={'x':{'pricing':{'prompt':'0.00000005','completion':'0.00000008'}}}
        with patch.object(c,'request',return_value={}) as request:
            c.request_model('x',{'album1':{},'album2':{}},'rules')
        payload=request.call_args.args[1]
        self.assertAlmostEqual(payload['provider']['max_price']['prompt'], .05)
        self.assertAlmostEqual(payload['provider']['max_price']['completion'], .08)
        self.assertEqual(payload['provider']['max_price']['request'], 0)

    def test_full_context_refuses_known_truncating_models(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            with self.assertRaisesRegex(BenchmarkError,'full.context.*Clef|Clef.*full.context'):
                run_benchmark(None,[{'case_id':'a','input':{'album1':{},'album2':{}}}],
                    Path(d),'rules',['cloudflare/clef'],full_context=True)

    def test_full_context_keeps_large_complete_state(self):
        class Fake:
            calls = 0
            def catalog(self): return {'x':{'context_length':64000,'pricing':{'prompt':'0','completion':'0'}}}
            def request_model(self,model,album_input,*args,**kwargs):
                self.calls += 1
                self.asserted = album_input['album1']['album']
                return {'choices':[{'message':{'content':'{"verdict":"different"}'}}], 'usage':{'cost':0}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            c=Fake()
            case={'case_id':'a','input':{'album1':{'album':'א'*3000},'album2':{}}}
            run_benchmark(c,[case],Path(d),'rules',['x'],repeats=1,full_context=True)
            self.assertEqual(c.calls,1)
            self.assertEqual(c.asserted,'א'*3000)

    def test_tokenizer_guard_counts_rules_and_state_not_bytes(self):
        class Fake:
            calls=0
            def catalog(self): return {'cloudflare/clef':{'context_length':65536,'pricing':{'prompt':'0','completion':'0'}}}
            def request_model(self,*args,**kwargs):
                self.calls+=1
                return {'answers':{'verdict':{'choice':'different'}},'usage':{'cost':0}}
        seen=[]
        def count(text):
            seen.append(text)
            return 1600
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            c=Fake()
            case={'case_id':'a','input':{'album1':{'album':'א'*3000},'album2':{}}}
            with patch('album_deduplicator.experiments.ai_duplicate_benchmark.runner.load_tokenizer',
                       return_value=(count,{'sha256':'official-test'})):
                run_benchmark(c,[case],Path(d),'RULESTEXT',['cloudflare/clef'],repeats=1,tokenizer_path=Path(d)/'tokenizer.json')
            self.assertEqual(c.calls,1)
            self.assertIn('RULESTEXT',seen[0])
            self.assertIn('א'*3000,seen[0])

    def test_qwen_explicitly_disables_reasoning(self):
        payload=build_payload('qwen/qwen3.7-flash',{'album1':{},'album2':{}},'rules')
        self.assertEqual(payload['reasoning'],{'enabled':False})
        self.assertNotIn('reasoning',build_payload('google/gemini-3.1-flash-lite',{'album1':{},'album2':{}},'rules'))

    def test_dedicated_local_key_takes_priority_over_unrelated_global_key(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            env = Path(folder) / '.env'
            env.write_text('OPENROUTER_API_KEY=LOCAL_TEST_KEY\n', encoding='utf-8')
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'OTHER_TEST_KEY'}):
                client = OpenRouterClient(env_path=env)
            self.assertEqual(client.api_key, 'LOCAL_TEST_KEY')

    def test_microsoft_uses_decisions_endpoint(self):
        model='microsoft/microsoft-decision-1'
        c=OpenRouterClient('TESTKEY')
        c._catalog={model:{'pricing':{'prompt':'0.000000042','completion':'0'}}}
        with patch.object(c,'request',return_value={}) as request:
            c.request_model(model,{'album1':{},'album2':{}},'rules')
        endpoint,payload=request.call_args.args
        self.assertEqual(endpoint,'/api/alpha/decisions')
        self.assertEqual(payload['questions']['verdict']['type'],'choice')
        self.assertNotIn('messages',payload)

    def test_timeout_is_not_reported_as_tls_and_does_not_leak_key(self):
        import urllib.error
        c=OpenRouterClient('SUPERSECRET',timeout=120)
        for exc in (TimeoutError('SUPERSECRET'), urllib.error.URLError(TimeoutError('SUPERSECRET'))):
            with self.subTest(type=type(exc).__name__):
                with patch('urllib.request.urlopen',side_effect=exc):
                    with self.assertRaises(BenchmarkError) as ctx: c.catalog()
                self.assertIn('timed out',str(ctx.exception))
                self.assertIn('120',str(ctx.exception))
                self.assertNotIn('TLS',str(ctx.exception))
                self.assertNotIn('SUPERSECRET',str(ctx.exception))


if __name__ == '__main__': unittest.main()
