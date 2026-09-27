from __future__ import annotations

from clogem.ui import activity_note, boot_sequence


def test_boot_sequence_allows_empty_required_provider_set() -> None:
    # With no required providers, boot sequence should complete without
    # checking external CLIs/SDK keys.
    assert boot_sequence(required_providers=set()) is True


def test_activity_note_turns_timeouts_and_crashes_into_one_line() -> None:
    assert activity_note("subprocess timed out after 120s", 124) == "timed out"
    assert activity_note("[Errno 7] Argument list too long", 1) == "request was too large"
    assert "Traceback" not in activity_note("Traceback (most recent call last):\nboom", 1)
