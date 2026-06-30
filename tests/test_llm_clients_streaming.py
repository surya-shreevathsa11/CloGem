from __future__ import annotations

import asyncio
from types import SimpleNamespace


def _collect(agen):
    """Run an async generator and collect all yielded strings."""
    async def _run():
        out = []
        async for chunk in agen:
            out.append(chunk)
        return out
    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# openai_stream_async
# ---------------------------------------------------------------------------

def test_openai_stream_async_yields_chunks(monkeypatch):
    chunks = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=", world"))]),
        SimpleNamespace(choices=[]),
    ]

    class _Stream:
        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            for c in chunks:
                yield c

    class _Completions:
        async def create(self, **kwargs):
            assert kwargs.get("stream") is True
            return _Stream()

    class _Chat:
        completions = _Completions()

    class _AsyncOpenAI:
        def __init__(self):
            self.chat = _Chat()

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", _AsyncOpenAI)

    from clogem.llm_clients import openai_stream_async

    result = _collect(openai_stream_async("q", "gpt-4.1-mini", timeout_sec=10))
    assert result == ["Hello", ", world"]


def test_openai_stream_async_skips_empty_deltas(monkeypatch):
    chunks = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=""))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="OK"))]),
    ]

    class _Stream:
        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            for c in chunks:
                yield c

    class _Completions:
        async def create(self, **kwargs):
            return _Stream()

    class _Chat:
        completions = _Completions()

    class _AsyncOpenAI:
        def __init__(self):
            self.chat = _Chat()

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", _AsyncOpenAI)

    from clogem.llm_clients import openai_stream_async

    result = _collect(openai_stream_async("q", "gpt-4.1-mini"))
    assert result == ["OK"]


def test_openai_stream_async_raises_on_import_failure(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def _block(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("no openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block)

    from clogem.llm_clients import openai_stream_async

    async def _run():
        collected = []
        try:
            async for chunk in openai_stream_async("q", "gpt-4.1-mini"):
                collected.append(chunk)
        except RuntimeError as e:
            return str(e)
        return collected

    result = asyncio.run(_run())
    assert "OpenAI SDK import failed" in result


# ---------------------------------------------------------------------------
# gemini_stream_async
# ---------------------------------------------------------------------------

def test_gemini_stream_async_yields_chunks(monkeypatch):
    text_chunks = ["def foo", "():\n", "    pass"]

    class _AioModels:
        async def generate_content_stream(self, **kwargs):
            for t in text_chunks:
                yield SimpleNamespace(text=t)

    class _Client:
        def __init__(self):
            self.aio = SimpleNamespace(models=_AioModels())

    import google.genai
    monkeypatch.setattr(google.genai, "Client", lambda *a, **k: _Client())

    from clogem.llm_clients import gemini_stream_async

    result = _collect(gemini_stream_async("q", "gemini-2.5-flash", timeout_sec=10))
    assert result == text_chunks


def test_gemini_stream_async_skips_empty_text(monkeypatch):
    class _AioModels:
        async def generate_content_stream(self, **kwargs):
            yield SimpleNamespace(text="")
            yield SimpleNamespace(text=None)
            yield SimpleNamespace(text="OK")

    class _Client:
        def __init__(self):
            self.aio = SimpleNamespace(models=_AioModels())

    import google.genai
    monkeypatch.setattr(google.genai, "Client", lambda *a, **k: _Client())

    from clogem.llm_clients import gemini_stream_async

    result = _collect(gemini_stream_async("q", "gemini-2.5-flash"))
    assert result == ["OK"]


# ---------------------------------------------------------------------------
# claude_stream_async
# ---------------------------------------------------------------------------

def test_claude_stream_async_yields_chunks(monkeypatch):
    text_parts = ["Hello", " from", " Claude"]

    class _TextStream:
        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            for t in text_parts:
                yield t

    class _StreamCtx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def text_stream(self):
            return _TextStream()

    class _Messages:
        def stream(self, **kwargs):
            return _StreamCtx()

    class _AsyncAnthropic:
        def __init__(self):
            self.messages = _Messages()

    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _AsyncAnthropic)

    from clogem.llm_clients import claude_stream_async

    result = _collect(claude_stream_async("q", "claude-sonnet-4-6", timeout_sec=10))
    assert result == text_parts


def test_claude_stream_async_skips_empty_text(monkeypatch):
    class _TextStream:
        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            yield ""
            yield None
            yield "OK"

    class _StreamCtx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def text_stream(self):
            return _TextStream()

    class _Messages:
        def stream(self, **kwargs):
            return _StreamCtx()

    class _AsyncAnthropic:
        def __init__(self):
            self.messages = _Messages()

    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _AsyncAnthropic)

    from clogem.llm_clients import claude_stream_async

    result = _collect(claude_stream_async("q", "claude-sonnet-4-6"))
    assert result == ["OK"]
