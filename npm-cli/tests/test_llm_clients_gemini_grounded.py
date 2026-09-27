from __future__ import annotations

from unittest.mock import MagicMock


def test_gemini_generate_with_google_search_uses_client(monkeypatch):
    mock_client = MagicMock()
    mock_rsp = MagicMock()
    mock_rsp.text = "Grounded answer"
    mock_client.models.generate_content.return_value = mock_rsp

    import google.genai

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(google.genai, "Client", lambda *a, **k: mock_client)

    from clogem.llm_clients import gemini_generate_with_google_search

    r = gemini_generate_with_google_search("q", "gemini-2.5-flash", timeout_sec=30)
    assert r.returncode == 0
    assert r.text == "Grounded answer"
    mock_client.models.generate_content.assert_called_once()
    call_kw = mock_client.models.generate_content.call_args.kwargs
    assert "config" in call_kw
    cfg = call_kw["config"]
    assert cfg.tools and len(cfg.tools) == 1


def test_gemini_generate_does_not_open_a_client_without_a_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from clogem.llm_clients import gemini_generate

    result = gemini_generate("hi", "gemini-2.5-flash")
    assert result.returncode == 1
    assert "API key" in result.error
