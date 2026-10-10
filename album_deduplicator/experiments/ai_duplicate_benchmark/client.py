"""Isolated standard-library OpenRouter transport. Never retries or disables TLS."""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from pathlib import Path
import ssl
import subprocess
import urllib.error
import urllib.request

BASE = 'https://openrouter.ai'
PROMPT_VERSION = 2
DECISION_MODELS = ('cloudflare/clef-flash', 'cloudflare/clef', 'cloudflare/clef-omni',
                   'openai/gpt-6-luna-decisions', 'typesafe/jev-1.13', 'microsoft/microsoft-decision-1')
DEFAULT_MODELS = tuple(m for m in DECISION_MODELS if m != 'cloudflare/clef-omni') + ('google/gemini-3.1-flash-lite',
                                   'qwen/qwen3.7-flash')
VERDICTS = ('duplicate', 'different', 'uncertain')
CRITERIA = {
    'duplicate': 'Same artist, album and recorded content; minor tag or format variations are acceptable.',
    'different': 'Distinct albums, editions (Deluxe, Live, Studio), volumes or recorded content.',
    'uncertain': 'Insufficient, conflicting or ambiguous metadata to establish album identity.',
}


class BenchmarkError(Exception):
    """Errors deliberately contain no request headers, credential or provider body."""


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def load_env(path):
    values = {}
    if path and Path(path).is_file():
        for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                name, value = line.split('=', 1)
                if name.strip() in ('OPENROUTER_API_KEY', 'OPENROUTER_MANAGEMENT_KEY'):
                    values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def build_payload(model, album_input, rules, max_tokens=256, pricing=None):
    allowed = {'album1', 'album2', 'similarity_score_script'}
    if not isinstance(album_input, dict) or not {'album1','album2'} <= album_input.keys() or set(album_input) - allowed:
        raise BenchmarkError('Input must contain only album1, album2 and optional similarity_score_script')
    provider = {'allow_fallbacks':False}
    if pricing is not None:
        provider['max_price'] = {'prompt':float(pricing['prompt'])*1_000_000,
            'completion':float(pricing['completion'])*1_000_000,
            'request':float(pricing.get('request',0))}
    if model in DECISION_MODELS:
        return {'model':model, 'state':album_input, 'questions':{'verdict':{
            'type':'choice', 'instructions':rules, 'criteria':CRITERIA}},
            'provider':provider}
    payload = {'model':model, 'messages':[{'role':'system','content':rules},
            {'role':'user','content':compact(album_input)}], 'temperature':0,
            'max_tokens':max_tokens, 'response_format':{'type':'json_object'},
            'provider':provider}
    if model == 'qwen/qwen3.7-flash':
        # Catalog: default_enabled=true, mandatory=false. This task needs only
        # short JSON; otherwise the output cap can be consumed by thinking.
        payload['reasoning'] = {'enabled':False}
    return payload


def parse_response(response, decisions=False):
    try:
        usage = response.get('usage') or {}
        cost = usage.get('cost')
        if cost is not None:
            cost = float(cost)
            if not math.isfinite(cost) or cost < 0: raise ValueError()
        if decisions:
            answer = response['answers']['verdict']
            verdict = answer['choice']
            probabilities = answer.get('probabilities')
            confidence = answer.get('confidence')
            if probabilities is not None:
                if not isinstance(probabilities, dict) or set(probabilities) != set(VERDICTS): raise ValueError()
                if any(isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()): raise ValueError()
                if abs(sum(probabilities.values()) - 1) > .02: raise ValueError()
                if confidence is None: confidence = probabilities[verdict]
            parsed = answer
        else:
            parsed = json.loads(response['choices'][0]['message']['content'])
            verdict = parsed['verdict']
            probabilities = None
            confidence = None  # Gemini similarity score is not calibrated confidence
        if verdict not in VERDICTS: raise ValueError()
        if confidence is not None and (not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1): raise ValueError()
        return {'verdict':verdict,'confidence':confidence,'probabilities':probabilities,
                'cost_usd':cost,'usage':usage,'parsed_answer':parsed}
    except (KeyError, TypeError, ValueError, IndexError):
        raise BenchmarkError('Malformed model response') from None


def estimate_cost(model, input_tokens, output_tokens):
    """One UTF8 byte per token plus framing is deliberately conservative."""
    try:
        pricing = model['pricing']
        prompt = float(pricing['prompt'])
        completion = float(pricing['completion'])
        request = float(pricing.get('request', 0))
        if any(not math.isfinite(p) or p < 0 for p in (prompt,completion,request)): raise ValueError()
        return (input_tokens * prompt + output_tokens * completion + request) * 1.1
    except (KeyError, TypeError, ValueError):
        raise BenchmarkError('Model has unknown or invalid pricing; paid call blocked') from None


class OpenRouterClient:
    def __init__(self, api_key=None, env_path=None, timeout=60):
        if not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or timeout<=0:
            raise BenchmarkError('Transport timeout must be a positive number of seconds')
        self.api_key = api_key or load_env(env_path).get('OPENROUTER_API_KEY') or os.environ.get('OPENROUTER_API_KEY')
        self.timeout = timeout
        self._catalog = None

    def request(self, path, payload=None, *, key=None, authenticated=True):
        auth = key or self.api_key
        if authenticated and not auth: raise BenchmarkError('Missing OPENROUTER_API_KEY')
        headers = {'Content-Type':'application/json','X-OpenRouter-Title':'Album duplicate isolated benchmark'}
        if authenticated: headers['Authorization'] = 'Bearer ' + auth
        req = urllib.request.Request(BASE + path, data=compact(payload).encode('utf-8') if payload is not None else None, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=ssl.create_default_context()) as response:
                result = json.load(response)
            if not isinstance(result, dict): raise BenchmarkError('API response is not an object')
            return result
        except urllib.error.HTTPError as exc:
            suffix = '; network filtering (including Netfree) is possible but unverified' if exc.code == 418 else ''
            raise BenchmarkError(f'OpenRouter HTTP {exc.code}{suffix}') from None
        except TimeoutError:
            raise BenchmarkError(f'OpenRouter request timed out after {self.timeout:g} seconds; billing may be unknown') from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason,TimeoutError):
                raise BenchmarkError(f'OpenRouter request timed out after {self.timeout:g} seconds; billing may be unknown') from None
            if isinstance(exc.reason,ssl.SSLError):
                raise BenchmarkError('OpenRouter TLS failure; filtering including Netfree is possible but unverified') from None
            raise BenchmarkError('OpenRouter network transport failure; cause unverified') from None
        except ssl.SSLError:
            raise BenchmarkError('OpenRouter TLS failure; filtering including Netfree is possible but unverified') from None
        except OSError:
            raise BenchmarkError('OpenRouter network transport failure; cause unverified') from None
        except (ValueError, UnicodeError):
            raise BenchmarkError('OpenRouter returned invalid JSON') from None

    def catalog(self):
        models = {}
        for path in ('/api/v1/models', '/api/v1/models?output_modalities=decisions'):
            response = self.request(path, authenticated=False)
            if not isinstance(response.get('data'),list): raise BenchmarkError('Malformed model catalog')
            for item in response['data']:
                models[item['id']] = item
        self._catalog = models
        return models

    def request_model(self, model, album_input, rules, max_tokens=256):
        catalog = self._catalog or self.catalog()
        if model not in catalog: raise BenchmarkError('Model missing from live catalog')
        estimate_cost(catalog[model],1,max_tokens)  # validate nonnegative known rates
        payload = build_payload(model, album_input, rules, max_tokens, catalog[model]['pricing'])
        endpoint = '/api/alpha/decisions' if model in DECISION_MODELS else '/api/v1/chat/completions'
        return self.request(endpoint, payload)

    def preflight(self):
        response = self.request('/api/v1/key')
        data = response.get('data', {})
        return {k:data.get(k) for k in ('limit','limit_remaining','limit_reset','usage','expires_at','is_free_tier')}

    def provision_key(self, env_path, limit=2):
        path = Path(env_path).resolve()
        if path.name != '.env' or path.parent != Path(__file__).resolve().parent:
            raise BenchmarkError('Dedicated key may only be written to experiment-local .env')
        if path.exists(): raise BenchmarkError('Dedicated .env already exists; refusing to overwrite')
        try:
            ignored = subprocess.run(['git','check-ignore','--quiet',str(path)],
                cwd=path.parent,capture_output=True,check=False)
        except OSError:
            raise BenchmarkError('Cannot verify dedicated credential file is Git-ignored') from None
        if ignored.returncode != 0:
            raise BenchmarkError('Dedicated credential file must be Git-ignored before provisioning')
        if not 0 < limit <= 2: raise BenchmarkError('Key limit must be between zero and $2')
        management = os.environ.get('OPENROUTER_MANAGEMENT_KEY')
        if not management: raise BenchmarkError('Missing OPENROUTER_MANAGEMENT_KEY; create a dedicated capped key in OpenRouter')
        # Create and restrict an empty file BEFORE obtaining a plaintext key.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            if os.name == 'nt':
                who = subprocess.run(['whoami'],capture_output=True,text=True,check=True).stdout.strip()
                subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r',f'{who}:(F)'],capture_output=True,check=True)
            expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).isoformat()
            response = self.request('/api/v1/keys', {'name':'album-duplicate-benchmark','limit':limit,
                'limit_reset':None,'expires_at':expiry,'include_byok_in_limit':True}, key=management)
            key = response.get('key')
            if not isinstance(key,str) or not key.startswith('sk-or-'): raise BenchmarkError('Key creation returned no valid key')
            with path.open('w',encoding='utf-8') as handle:
                handle.write('OPENROUTER_API_KEY=' + key + '\n')
            return {'created':True,'limit':limit,'expires_at':expiry,'path':str(path)}
        except (OSError, subprocess.SubprocessError):
            raise BenchmarkError('Could not securely restrict dedicated credential file') from None
