import os
from pathlib import Path
import subprocess
import sys
import textwrap


PROJECT_DIR = Path(__file__).resolve().parents[1]


def run_fresh_python(script):
    env = os.environ.copy()
    env.pop("GEMINI_API_KEY", None)
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def test_dto_import_does_not_load_analysis_or_optional_runtimes():
    run_fresh_python("""
        import sys
        from music_dup_lib.services.dto import AnalysisWarnings
        assert AnalysisWarnings().ml_unavailable is False
        for module in ('numpy', 'google.genai', 'music_dup_lib.services.scoring_service',
                       'music_dup_lib.services.analysis_orchestrator'):
            assert module not in sys.modules, module
    """)


def test_public_service_exports_resolve_to_original_objects():
    run_fresh_python("""
        import sys
        import music_dup_lib.services as services
        from music_dup_lib.services.dto import AlbumSummary
        from music_dup_lib.services.user_decision_store import UserDecisionStore
        assert services.AlbumSummary is AlbumSummary
        assert services.UserDecisionStore is UserDecisionStore
        assert services.UserDecisionStore is UserDecisionStore
        assert 'UserDecisionStore' in dir(services)
        assert 'music_dup_lib.services.scoring_service' not in sys.modules
        try:
            services.unknown_service
        except AttributeError:
            pass
        else:
            raise AssertionError('Unknown exports must raise AttributeError')
    """)


def test_gemini_sdk_is_deferred_until_analyzer_has_a_key():
    run_fresh_python("""
        import sys
        from music_dup_lib.external.gemini_analyzer import GeminiAnalyzer
        assert 'google.genai' not in sys.modules
        try:
            GeminiAnalyzer(api_key='   ')
        except ValueError:
            pass
        else:
            raise AssertionError('Missing API key must retain validation')
        assert 'google.genai' not in sys.modules
    """)


def test_missing_gemini_sdk_fails_at_activation_without_affecting_import():
    run_fresh_python("""
        import importlib.abc
        import sys
        class MissingSDK(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'google.genai' or fullname.startswith('google.genai.'):
                    raise ModuleNotFoundError('Gemini SDK deliberately unavailable')
        sys.meta_path.insert(0, MissingSDK())
        from music_dup_lib.external.gemini_analyzer import GeminiAnalyzer
        try:
            GeminiAnalyzer(api_key='dummy-key')
        except ModuleNotFoundError as exc:
            assert 'deliberately unavailable' in str(exc)
        else:
            raise AssertionError('SDK is required when Gemini is activated')
    """)


def test_scoring_degrades_gracefully_with_missing_gemini_sdk():
    run_fresh_python("""
        import importlib.abc
        import sys
        from types import SimpleNamespace
        class MissingSDK(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'google.genai' or fullname.startswith('google.genai.'):
                    raise ModuleNotFoundError('Gemini SDK deliberately unavailable')
        sys.meta_path.insert(0, MissingSDK())
        import music_dup_lib.services.scoring_service as scoring
        scoring.MLSimilarityModel = lambda: SimpleNamespace(model_loaded=True, prediction_batch_size=32)
        for key in (None, 'dummy-key'):
            service = scoring.ScoringService(use_gemini=True, gemini_api_key=key)
            pairs, warnings = service.apply_scores([], {}, {})
            assert pairs == {}
            assert warnings.gemini_unavailable is True
            assert warnings.ml_unavailable is False
    """)
