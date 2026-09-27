from __future__ import annotations

from clogem.ui import activity_note, boot_sequence, is_genai_cleanup_noise


def test_boot_sequence_allows_empty_required_provider_set() -> None:
    # With no required providers, boot sequence should complete without
    # checking external CLIs/SDK keys.
    assert boot_sequence(required_providers=set()) is True


def test_activity_note_turns_timeouts_and_crashes_into_one_line() -> None:
    assert activity_note("subprocess timed out after 120s", 124) == "timed out"
    assert activity_note("[Errno 7] Argument list too long", 1) == "request was too large"
    assert "Traceback" not in activity_note("Traceback (most recent call last):\nboom", 1)
    assert activity_note("No API key was provided. Please pass a valid API key.", 1) == "needs an API key"
    dump = "failed to refresh available models: unknown variant 'max' {\"models\":[]}"
    assert activity_note(dump, 1) == "update the Codex CLI"


def test_genai_cleanup_noise_is_recognized() -> None:
    exc = AttributeError("'BaseApiClient' object has no attribute '_async_httpx_client'")
    assert is_genai_cleanup_noise("Unhandled exception in event loop", exc)
    assert not is_genai_cleanup_noise("No API key was provided", None)
