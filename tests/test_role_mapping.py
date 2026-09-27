from __future__ import annotations

import pytest

from clogem.role_mapping import (
    DEFAULT_ROLE_PROVIDER_MAP,
    explicit_role_names,
    fallback_default_grok,
    grok_provider_available,
    needed_providers,
    parse_role_provider_map_env,
    parse_role_provider_pairs,
    resolve_role_provider_map,
)


def test_parse_role_provider_pairs_accepts_grok() -> None:
    out = parse_role_provider_pairs(["coder=grok"])
    assert out == {"coder": "grok"}
    out = parse_role_provider_pairs(["coder=claude", "reviewer=gemini"])
    assert out == {"coder": "claude", "reviewer": "gemini"}


def test_parse_role_provider_pairs_invalid_role() -> None:
    with pytest.raises(ValueError):
        parse_role_provider_pairs(["writer=codex"])


def test_parse_role_provider_map_env_empty() -> None:
    assert parse_role_provider_map_env("") == {}


def test_resolve_role_provider_map_precedence_cli_over_env() -> None:
    out = resolve_role_provider_map(
        env_map_raw="coder=gemini,reviewer=claude",
        cli_pairs=["coder=claude"],
    )
    assert out["coder"] == "claude"
    assert out["reviewer"] == "claude"
    assert out["summariser"] == DEFAULT_ROLE_PROVIDER_MAP["summariser"]


def test_default_planner_is_grok() -> None:
    assert DEFAULT_ROLE_PROVIDER_MAP["planner"] == "grok"
    assert DEFAULT_ROLE_PROVIDER_MAP["coder"] == "codex"
    assert DEFAULT_ROLE_PROVIDER_MAP["reviewer"] == "gemini"


def test_fallback_default_grok_keeps_explicit_mapping() -> None:
    mapping = resolve_role_provider_map(env_map_raw="", cli_pairs=["planner=grok"])
    explicit = explicit_role_names(env_map_raw="", cli_pairs=["planner=grok"])
    out = fallback_default_grok(mapping, explicit)
    assert out["planner"] == "grok"


def test_fallback_default_grok_uses_codex_when_not_explicit() -> None:
    mapping = resolve_role_provider_map(env_map_raw="", cli_pairs=[])
    out = fallback_default_grok(mapping, explicit_roles=set())
    assert out["planner"] == "codex"
    assert "grok" not in needed_providers(out)


def test_grok_provider_available_via_cli_or_key(monkeypatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("CLOGEM_GROK_CMD", raising=False)
    monkeypatch.setattr("clogem.role_mapping.shutil.which", lambda _exe: None)
    assert grok_provider_available() is False
    monkeypatch.setattr("clogem.role_mapping.shutil.which", lambda exe: "/home/user/.grok/bin/grok" if exe == "grok" else None)
    assert grok_provider_available() is True
    monkeypatch.setattr("clogem.role_mapping.shutil.which", lambda _exe: None)
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    assert grok_provider_available() is True


def test_needed_providers_from_roles() -> None:
    mapping = {
        "orchestrator": "codex",
        "planner": "claude",
        "coder": "claude",
        "reviewer": "gemini",
        "summariser": "gemini",
    }
    assert needed_providers(mapping) == {"codex", "claude", "gemini"}
