from __future__ import annotations

from clogem.config import Settings


def test_settings_from_env_parses_booleans_and_ints(monkeypatch) -> None:
    monkeypatch.setenv("CLOGEM_ASYNC_LLM", "0")
    monkeypatch.setenv("CLOGEM_MCP_TIMEOUT_SEC", "77")
    monkeypatch.setenv("CLOGEM_VECTOR_RAG", "1")
    s = Settings.from_env()
    assert s.async_llm is False
    assert s.mcp_timeout_sec == 77
    assert s.vector_rag is True


def test_settings_choice_fallback(monkeypatch) -> None:
    monkeypatch.setenv("CLOGEM_CODEX_BACKEND", "invalid")
    s = Settings.from_env()
    assert s.codex_backend == "auto"


def test_grok_backend_and_model_from_env(monkeypatch) -> None:
    monkeypatch.setenv("CLOGEM_GROK_BACKEND", "cli")
    monkeypatch.setenv("CLOGEM_GROK_SDK_MODEL", "grok-4.3")
    s = Settings.from_env()
    assert s.grok_backend == "cli"
    assert s.grok_sdk_model == "grok-4.3"


def test_grok_backend_invalid_falls_back_to_auto(monkeypatch) -> None:
    monkeypatch.setenv("CLOGEM_GROK_BACKEND", "nope")
    s = Settings.from_env()
    assert s.grok_backend == "auto"
