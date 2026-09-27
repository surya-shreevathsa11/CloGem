from __future__ import annotations

import logging

from clogem.logging_utils import debug_enabled, get_logger


def test_debug_enabled_from_clogem_env(monkeypatch) -> None:
    monkeypatch.setenv("CLOGEM_DEBUG", "1")
    monkeypatch.delenv("COGEM_DEBUG", raising=False)
    assert debug_enabled() is True


def test_genai_library_warnings_stay_off_the_terminal() -> None:
    get_logger("clogem.test")
    assert logging.getLogger("google_genai").level == logging.ERROR
    assert logging.getLogger("google.genai").level == logging.ERROR


def test_debug_enabled_from_legacy_cogem_env(monkeypatch) -> None:
    monkeypatch.delenv("CLOGEM_DEBUG", raising=False)
    monkeypatch.setenv("COGEM_DEBUG", "true")
    assert debug_enabled() is True
