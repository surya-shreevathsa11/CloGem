from __future__ import annotations

from clogem.ui import activity_note, boot_sequence, is_genai_cleanup_noise


def test_boot_sequence_allows_empty_required_provider_set(capsys) -> None:
    # With no required providers, boot sequence should complete without
    # checking external CLIs/SDK keys, and without the old block-letter logo.
    assert boot_sequence(required_providers=set()) is True
    out = capsys.readouterr().out
    assert "clogem" in out
    assert "build · review · evolve" in out
    assert "codex · gemini · claude · grok" in out
    assert "██████" not in out
    assert "system ready" not in out


def test_orbit_frame_keeps_a_center_and_one_spark() -> None:
    from clogem.ui import _orbit_lines

    frame = "\n".join(_orbit_lines(0))
    assert "✦" in frame
    assert "●" in frame
    assert frame.count("●") == 1


def test_optional_model_is_named_without_blocking_startup(capsys) -> None:
    from clogem.ui import _boot_run_step

    assert _boot_run_step("claude", lambda: False, required=False) is True
    out = capsys.readouterr().out
    assert "claude" in out
    assert "unavailable" not in out


def test_boot_step_says_unavailable_without_a_spinner(capsys) -> None:
    from clogem.ui import _boot_run_step

    assert _boot_run_step("codex", lambda: False) is False
    out = capsys.readouterr().out
    assert "codex" in out
    assert "unavailable" in out
    assert "not found" not in out


def test_activity_note_turns_timeouts_and_crashes_into_one_line() -> None:
    assert activity_note("subprocess timed out after 120s", 124) == "timed out"
    assert activity_note("[Errno 7] Argument list too long", 1) == "request was too large"
    assert "Traceback" not in activity_note("Traceback (most recent call last):\nboom", 1)
    assert activity_note("No API key was provided. Please pass a valid API key.", 1) == "needs an API key"
    raw_401 = "401 UNAUTHENTICATED. {'error': {'code': 401, 'message': 'Request had invalid authentication credentials.'}}"
    assert activity_note(raw_401, 1) == "API key was rejected"
    assert "401" not in activity_note(raw_401, 1)
    dump = "failed to refresh available models: unknown variant 'max' {\"models\":[]}"
    assert activity_note(dump, 1) == "update the Codex CLI"


def test_genai_cleanup_noise_is_recognized() -> None:
    exc = AttributeError("'BaseApiClient' object has no attribute '_async_httpx_client'")
    assert is_genai_cleanup_noise("Unhandled exception in event loop", exc)
    assert not is_genai_cleanup_noise("No API key was provided", None)
