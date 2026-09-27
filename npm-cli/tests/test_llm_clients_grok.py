from __future__ import annotations

from clogem.llm_clients import grok_generate


def test_grok_generate_uses_xai_base_url(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("CLOGEM_LLM_MAX_RETRIES", "0")
    captured: dict = {}

    class _Message:
        content = "hello from grok"

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs):
            captured["create"] = kwargs
            return _Response()

    class _Chat:
        completions = _Completions()

    class _Client:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.chat = _Chat()

    monkeypatch.setattr("openai.OpenAI", _Client)
    out = grok_generate("fix the bug", "grok-4.7", timeout_sec=12)

    assert out.returncode == 0
    assert out.text == "hello from grok"
    assert captured["init"]["api_key"] == "xai-test"
    assert captured["init"]["base_url"] == "https://api.x.ai/v1"
    assert captured["create"]["model"] == "grok-4.7"
    assert captured["create"]["timeout"] == 12


def test_grok_generate_missing_key_does_not_call_client(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    called = {"n": 0}

    class _Client:
        def __init__(self, **kwargs):
            called["n"] += 1

    monkeypatch.setattr("openai.OpenAI", _Client)
    out = grok_generate("hi", "grok-4.7")

    assert out.returncode == 1
    assert "XAI_API_KEY" in out.error
    assert called["n"] == 0
