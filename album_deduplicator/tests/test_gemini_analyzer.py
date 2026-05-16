from types import SimpleNamespace

from google.genai import types

from music_dup_lib import config
from music_dup_lib.external.gemini_analyzer import GeminiAnalyzer


def test_gemini_generate_content_uses_configured_thinking_level():
    captured = {}

    class DummyModels:
        def generate_content_stream(self, *, model, contents, config):
            captured["config"] = config
            return [
                SimpleNamespace(
                    text='{"verdict":"uncertain","similarity_score_from_model":50,"reason":"test"}'
                )
            ]

    analyzer = GeminiAnalyzer(api_key="dummy-key")
    analyzer.client = SimpleNamespace(models=DummyModels())
    analyzer.conversation = []

    response = analyzer._send_and_receive()

    assert response
    thinking_config = captured["config"].thinking_config
    assert isinstance(thinking_config, types.ThinkingConfig)
    assert thinking_config.thinking_level == types.ThinkingLevel.MEDIUM
    assert config.GEMINI_THINKING_LEVEL == "medium"
