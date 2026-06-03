from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass
class ValidationReport:
    ok: bool
    tests_rc: int = 0
    lint_rc: int = 0
    typecheck_rc: int = 0
    tests_text: str = ""
    lint_text: str = ""
    typecheck_text: str = ""
    sections: List[str] = field(default_factory=list)

    def as_prompt_block(self) -> str:
        parts = []
        if self.tests_text.strip():
            parts.append("### Tests\n" + self.tests_text.strip())
        if self.lint_text.strip():
            parts.append("### Lint\n" + self.lint_text.strip())
        if self.typecheck_text.strip():
            parts.append("### Typecheck\n" + self.typecheck_text.strip())
        if not parts:
            return self.tests_text or "(validation produced no output)"
        return "\n\n".join(parts)


def git_tracked_files(repo_root: str) -> List[str]:
    """
    Return git-tracked file paths (relative to repo_root).
    Uses `git ls-files -z` to safely handle spaces.
    """
    repo_root = os.path.abspath(repo_root)
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_root,
            capture_output=True,
        )
    except OSError:
        return []

    if proc.returncode != 0:
        return []

    raw = proc.stdout or b""
    if not raw:
        return []
    parts = raw.split(b"\x00")
    out: List[str] = []
    for p in parts:
        if not p:
            continue
        try:
            out.append(p.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(p.decode("utf-8", errors="replace"))
    return out


def copy_files_into_folder(
    repo_root: str,
    sandbox_root: str,
    rel_paths: Iterable[str],
    *,
    extra_ignore_prefixes: Sequence[str] = (),
) -> int:
    """
    Copy listed files from repo_root -> sandbox_root preserving directories.
    Returns number of files successfully copied.
    """
    copied = 0
    for rel in rel_paths:
        if not rel:
            continue
        rel_norm = rel.replace("\\", "/").lstrip("/")
        if any(rel_norm.startswith(prefix) for prefix in extra_ignore_prefixes):
            continue

        src = os.path.join(repo_root, rel_norm)
        if not os.path.isfile(src):
            # Might have been deleted between ls-files and copy.
            continue
        dst = os.path.join(sandbox_root, rel_norm)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied


def copy_git_tracked_repo_to_sandbox(
    repo_root: str,
    sandbox_root: str,
    *,
    extra_ignore_prefixes: Sequence[str] = ("node_modules/", ".git/"),
) -> Tuple[bool, int]:
    """
    Copy only git-tracked files into sandbox_root.
    Returns (used_git_tracked, files_copied).
    """
    files = git_tracked_files(repo_root)
    if not files:
        return False, 0
    # mkdir is handled by caller; ensure it exists for safety.
    os.makedirs(sandbox_root, exist_ok=True)
    copied = copy_files_into_folder(
        repo_root,
        sandbox_root,
        files,
        extra_ignore_prefixes=extra_ignore_prefixes,
    )
    return True, copied


def rel_paths_from_abs(repo_root: str, abs_paths: Iterable[str]) -> List[str]:
    repo_root = os.path.abspath(repo_root)
    out: List[str] = []
    for abs_p in abs_paths:
        if not abs_p:
            continue
        try:
            if os.path.isfile(abs_p):
                out.append(os.path.relpath(abs_p, repo_root).replace("\\", "/"))
        except ValueError:
            continue
    return out


def copy_repo_to_sandbox_with_extras(
    repo_root: str,
    sandbox_root: str,
    extra_rel_paths: Optional[Iterable[str]] = None,
    *,
    extra_ignore_prefixes: Sequence[str] = ("node_modules/", ".git/"),
) -> Tuple[bool, int]:
    """
    Copy git-tracked files plus extra relative paths (e.g. session-written untracked).
    """
    used_git, copied = copy_git_tracked_repo_to_sandbox(
        repo_root,
        sandbox_root,
        extra_ignore_prefixes=extra_ignore_prefixes,
    )
    extras = list(extra_rel_paths or [])
    if extras:
        copied += copy_files_into_folder(
            repo_root,
            sandbox_root,
            extras,
            extra_ignore_prefixes=extra_ignore_prefixes,
        )
    return used_git, copied


def detect_typecheck_command(repo_root: str) -> Optional[List[str]]:
    """Best-effort typecheck command for the repo."""
    root = os.path.abspath(repo_root)
    if os.path.isfile(os.path.join(root, "pyrightconfig.json")):
        return ["pyright"]
    if os.path.isfile(os.path.join(root, "mypy.ini")) or _pyproject_has_tool(
        root, "mypy"
    ):
        return ["python", "-m", "mypy", "."]
    if os.path.isfile(os.path.join(root, "tsconfig.json")):
        return ["npx", "tsc", "--noEmit"]
    return None


def _pyproject_has_tool(repo_root: str, tool: str) -> bool:
    path = os.path.join(repo_root, "pyproject.toml")
    if not os.path.isfile(path):
        return False
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return False
    return f"[tool.{tool}" in text or f'[tool."{tool}"' in text

