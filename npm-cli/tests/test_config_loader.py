from __future__ import annotations

from pathlib import Path

from clogem.config import Settings
from clogem.config_loader import (
    apply_profile_preset,
    load_settings,
    resolve_vector_rag_from_env,
    vector_rag_available,
)


def test_load_settings_merges_project_toml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".clogem.toml").write_text(
        'profile_name = "fast"\nbuild_timeout_sec = 99\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("CLOGEM_VECTOR_RAG", raising=False)
    s, sources = load_settings(cwd=str(tmp_path))
    assert "project:" in "".join(sources)
    assert s.profile == "fast"
    # fast profile caps build_timeout_sec at 90
    assert s.build_timeout_sec == 90


def test_apply_profile_fast_lowers_attempts() -> None:
    base = Settings(validation_max_attempts=3, profile="fast")
    s = apply_profile_preset(base)
    assert s.validation_max_attempts == 1
    assert s.vector_rag is False


def test_resolve_vector_rag_explicit_off(monkeypatch) -> None:
    monkeypatch.setenv("CLOGEM_VECTOR_RAG", "0")
    assert resolve_vector_rag_from_env("0") is False


def test_vector_rag_available_is_bool() -> None:
    assert isinstance(vector_rag_available(), bool)
