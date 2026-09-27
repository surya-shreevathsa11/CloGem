from __future__ import annotations

import os
import shutil
from typing import Dict, Iterable, List, Sequence, Set, Tuple


ROLES: Tuple[str, ...] = (
    "orchestrator",
    "planner",
    "coder",
    "reviewer",
    "summariser",
)
PROVIDERS: Tuple[str, ...] = ("codex", "gemini", "claude", "grok")

DEFAULT_ROLE_PROVIDER_MAP: Dict[str, str] = {
    "orchestrator": "codex",
    "planner": "grok",
    "coder": "codex",
    "reviewer": "gemini",
    "summariser": "gemini",
}


def _normalize_pair(raw: str) -> Tuple[str, str]:
    txt = (raw or "").strip()
    if not txt or "=" not in txt:
        raise ValueError(f"Invalid role/provider pair: {raw!r}")
    role, provider = txt.split("=", 1)
    role = role.strip().lower()
    provider = provider.strip().lower()
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}")
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    return role, provider


def parse_role_provider_pairs(
    items: Sequence[str],
) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for it in items:
        role, provider = _normalize_pair(it)
        out[role] = provider
    return out


def parse_role_provider_map_env(raw: str) -> Dict[str, str]:
    txt = (raw or "").strip()
    if not txt:
        return {}
    parts = [p.strip() for p in txt.split(",") if p.strip()]
    return parse_role_provider_pairs(parts)


def resolve_role_provider_map(
    *,
    env_map_raw: str,
    cli_pairs: Sequence[str],
) -> Dict[str, str]:
    out = dict(DEFAULT_ROLE_PROVIDER_MAP)
    out.update(parse_role_provider_map_env(env_map_raw))
    out.update(parse_role_provider_pairs(cli_pairs))
    return out


def needed_providers(role_provider_map: Dict[str, str], roles: Iterable[str] | None = None) -> Set[str]:
    use_roles = list(roles) if roles is not None else list(ROLES)
    out: Set[str] = set()
    for role in use_roles:
        provider = role_provider_map.get(role, DEFAULT_ROLE_PROVIDER_MAP[role])
        out.add(provider)
    return out


def explicit_role_names(*, env_map_raw: str, cli_pairs: Sequence[str]) -> Set[str]:
    """Roles the user set via env or CLI, as opposed to the built-in defaults."""
    names = set(parse_role_provider_map_env(env_map_raw))
    names.update(parse_role_provider_pairs(list(cli_pairs)))
    return names


def grok_provider_available() -> bool:
    """True when the Grok CLI is on PATH or an xAI API key is set."""
    if os.environ.get("XAI_API_KEY", "").strip():
        return True
    raw = os.environ.get("CLOGEM_GROK_CMD", "").strip()
    exe = raw.split()[0] if raw else "grok"
    return bool(shutil.which(exe) or os.path.isfile(exe))


def fallback_default_grok(
    role_provider_map: Dict[str, str],
    explicit_roles: Set[str],
) -> Dict[str, str]:
    """
    When Grok is unavailable, roles that default to grok fall back to Codex.

    An explicit ``planner=grok`` (or any other explicit grok mapping) is left
    alone so boot can report that Grok is required.
    """
    out = dict(role_provider_map)
    for role, provider in list(out.items()):
        if provider == "grok" and role not in explicit_roles:
            out[role] = "codex"
    return out
