from __future__ import annotations

import asyncio

from clogem.llm_clients import (
    LLMResult,
    _is_retryable_error,
    _run_with_retries,
    _run_with_retries_async,
)


def test_run_with_retries_retries_transient_error(monkeypatch):
    monkeypatch.setenv("CLOGEM_LLM_MAX_RETRIES", "2")
    monkeypatch.setattr("clogem.llm_clients.time.sleep", lambda _s: None)
    monkeypatch.setattr("clogem.llm_clients.random.uniform", lambda _a, _b: 0.0)

    attempts = {"n": 0}

    def _call() -> LLMResult:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return LLMResult("", "429 Too Many Requests", 1)
        return LLMResult("ok", "", 0)

    out = _run_with_retries(_call, "test")
    assert out.returncode == 0
    assert out.text == "ok"
    assert attempts["n"] == 3


def test_run_with_retries_does_not_retry_non_retryable(monkeypatch):
    monkeypatch.setenv("CLOGEM_LLM_MAX_RETRIES", "3")
    attempts = {"n": 0}

    def _call() -> LLMResult:
        attempts["n"] += 1
        return LLMResult("", "invalid auth key", 1)

    out = _run_with_retries(_call, "test")
    assert out.returncode == 1
    assert attempts["n"] == 1


def test_run_with_retries_async_retries(monkeypatch):
    monkeypatch.setenv("CLOGEM_LLM_MAX_RETRIES", "1")

    async def _no_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr("clogem.llm_clients.asyncio.sleep", _no_sleep)
    monkeypatch.setattr("clogem.llm_clients.random.uniform", lambda _a, _b: 0.0)

    attempts = {"n": 0}

    async def _call() -> LLMResult:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return LLMResult("", "connection reset by peer", 1)
        return LLMResult("ok-async", "", 0)

    out = asyncio.run(_run_with_retries_async(_call, "test"))
    assert out.returncode == 0
    assert out.text == "ok-async"
    assert attempts["n"] == 2


def test_deadline_timeout_is_not_retried(monkeypatch):
    monkeypatch.setenv("CLOGEM_LLM_MAX_RETRIES", "3")
    attempts = {"n": 0}

    def _call() -> LLMResult:
        attempts["n"] += 1
        return LLMResult("", "Request timed out.", 1)

    out = _run_with_retries(_call, "test")
    assert out.returncode == 1
    assert out.error == "Request timed out."
    assert attempts["n"] == 1
    assert _is_retryable_error(TimeoutError("The read operation timed out")) is False
    assert _is_retryable_error(Exception("504 Gateway Timeout")) is True
