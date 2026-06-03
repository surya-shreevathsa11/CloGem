from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from clogem.config import Settings, _as_bool, _as_choice, _as_int

_PROFILE_NAMES = ("default", "fast", "thorough")

# Maps TOML keys (snake_case) to Settings field names.
_TOML_FIELD_ALIASES: Dict[str, str] = {
    "codex_backend": "codex_backend",
    "gemini_backend": "gemini_backend",
    "subprocess_timeout_sec": "subprocess_timeout_sec",
    "router_timeout_sec": "router_timeout_sec",
    "build_timeout_sec": "build_timeout_sec",
    "pdf_timeout_sec": "pdf_timeout_sec",
    "validation_timeout_sec": "validation_timeout_sec",
    "validation_max_attempts": "validation_max_attempts",
    "validation_docker": "validation_docker",
    "vector_rag": "vector_rag",
    "log_dir": "log_dir",
    "profile": "profile",
    "plan_ttl_hours": "plan_ttl_hours",
    "debug": "debug",
}


def _load_toml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    raw = path.read_bytes()
    try:
        import tomllib

        return tomllib.loads(raw.decode("utf-8"))
    except ImportError:
        try:
            import tomli

            return tomli.loads(raw.decode("utf-8"))
        except ImportError:
            return {}


def config_file_paths(cwd: Optional[str] = None) -> List[Tuple[str, Path]]:
    """Return (label, path) for config files in merge order."""
    base = Path(cwd or os.getcwd())
    home = Path.home() / ".config" / "clogem" / "config.toml"
    local = base / ".clogem.toml"
    out: List[Tuple[str, Path]] = []
    if home.is_file():
        out.append(("user", home))
    if local.is_file():
        out.append(("project", local))
    return out


def _profile_section(data: Dict[str, Any], profile: str) -> Dict[str, Any]:
    profiles = data.get("profile")
    if not isinstance(profiles, dict):
        return {}
    section = profiles.get(profile)
    if isinstance(section, dict):
        return section
    return {}


def _merge_toml_into_settings(base: Settings, toml_data: Dict[str, Any], profile: str) -> Settings:
    """Apply [profile.X] and top-level keys onto a Settings copy via replace."""
    d = base.as_dict()
    top_profile = (toml_data.get("profile_name") or toml_data.get("active_profile") or profile)
    if isinstance(top_profile, str) and top_profile.strip():
        d["profile"] = top_profile.strip().lower()

    prof = _profile_section(toml_data, d.get("profile", "default"))
    for src in (prof, toml_data):
        if not isinstance(src, dict):
            continue
        for key, val in src.items():
            if key == "profile" or key.startswith("profile."):
                continue
            field = _TOML_FIELD_ALIASES.get(key, key)
            if field in d and val is not None:
                d[field] = val

    return Settings(**{k: d[k] for k in Settings.__dataclass_fields__})  # type: ignore[arg-type]


def vector_rag_available() -> bool:
    try:
        import lancedb  # noqa: F401

        return True
    except ImportError:
        return False


def resolve_vector_rag_from_env(explicit_env: Optional[str] = None) -> bool:
    """
    Smart default: on when lancedb is installed unless CLOGEM_VECTOR_RAG=0.
    Explicit env always wins.
    """
    if explicit_env is not None and explicit_env.strip():
        return _as_bool(explicit_env, False)
    if os.environ.get("CLOGEM_VECTOR_RAG") is not None:
        return _as_bool(os.environ.get("CLOGEM_VECTOR_RAG"), False)
    return vector_rag_available()


def apply_profile_preset(settings: Settings) -> Settings:
    """Apply fast/thorough presets on top of merged settings."""
    p = (settings.profile or "default").strip().lower()
    if p not in _PROFILE_NAMES or p == "default":
        return settings
    d = settings.as_dict()
    base_to = d.get("subprocess_timeout_sec", 60)
    if p == "fast":
        d["validation_max_attempts"] = min(d.get("validation_max_attempts", 2), 1)
        d["vector_rag"] = False
        d["router_timeout_sec"] = min(d.get("router_timeout_sec", base_to), 45)
        d["build_timeout_sec"] = min(d.get("build_timeout_sec", base_to), 90)
    elif p == "thorough":
        d["validation_max_attempts"] = max(d.get("validation_max_attempts", 2), 3)
        d["validation_docker"] = True
        d["router_timeout_sec"] = max(d.get("router_timeout_sec", base_to), 90)
        d["build_timeout_sec"] = max(d.get("build_timeout_sec", base_to), 300)
        d["pdf_timeout_sec"] = max(d.get("pdf_timeout_sec", 180), 300)
        d["validation_timeout_sec"] = max(d.get("validation_timeout_sec", base_to), 600)
        if vector_rag_available():
            d["vector_rag"] = True
    return Settings(**{k: d[k] for k in Settings.__dataclass_fields__})  # type: ignore[arg-type]


def load_settings(
    *,
    cwd: Optional[str] = None,
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[Settings, List[str]]:
    """
    Merge: defaults → TOML files → env → cli_overrides → profile preset.

    Returns (settings, list of loaded config source labels).
    """
    sources: List[str] = ["defaults"]
    s = Settings.from_env()
    # Re-resolve vector_rag with smart default when env unset
    env_rag = os.environ.get("CLOGEM_VECTOR_RAG")
    d = s.as_dict()
    d["vector_rag"] = resolve_vector_rag_from_env(env_rag)
    s = Settings(**{k: d[k] for k in Settings.__dataclass_fields__})  # type: ignore[arg-type]

    for label, path in config_file_paths(cwd):
        data = _load_toml(path)
        if data:
            s = _merge_toml_into_settings(s, data, s.profile)
            sources.append(f"{label}:{path}")

    s = apply_profile_preset(s)

    if cli_overrides:
        d = s.as_dict()
        for key, val in cli_overrides.items():
            if key in d and val is not None:
                d[key] = val
        s = Settings(**{k: d[k] for k in Settings.__dataclass_fields__})  # type: ignore[arg-type]
        sources.append("cli")

    return s, sources
