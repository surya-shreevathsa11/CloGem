from __future__ import annotations

import os
import re
import subprocess
from typing import List, Optional, Tuple


_PROTECTED_BRANCHES = frozenset({"main", "master"})


def current_branch(repo_root: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except OSError:
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def is_protected_branch(name: str) -> bool:
    return (name or "").strip().lower() in _PROTECTED_BRANCHES


def git_diff_written(repo_root: str, written_files: List[str]) -> Tuple[int, str, str]:
    """Run git diff scoped to written_files; include untracked via --no-index fallback."""
    if not written_files:
        try:
            proc = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return proc.returncode, proc.stdout or "", proc.stderr or ""
        except OSError as e:
            return 1, "", str(e)

    paths = []
    for p in written_files:
        abs_p = p if os.path.isabs(p) else os.path.join(repo_root, p)
        if os.path.exists(abs_p):
            try:
                rel = os.path.relpath(abs_p, repo_root)
                paths.append(rel)
            except ValueError:
                paths.append(p)

    if not paths:
        return 0, "(no diff: files not found on disk)", ""

    try:
        proc = subprocess.run(
            ["git", "diff", "--"] + paths,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = proc.stdout or ""
        if not out.strip():
            proc2 = subprocess.run(
                ["git", "status", "--short", "--"] + paths,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            out = (proc2.stdout or "") + "\n" + (proc.stderr or "")
        return proc.returncode, out, proc.stderr or ""
    except OSError as e:
        return 1, "", str(e)


def create_branch(repo_root: str, name: str) -> Tuple[bool, str]:
    branch = (name or "").strip()
    if not branch:
        return False, "Branch name is required."
    cur = current_branch(repo_root)
    if is_protected_branch(cur):
        return False, f"Refusing to branch from protected branch '{cur}'."
    if re.search(r"[^\w./-]", branch):
        return False, "Invalid branch name."
    try:
        proc = subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as e:
        return False, str(e)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "git checkout failed").strip()
    return True, f"Switched to new branch '{branch}'."


def git_commit(repo_root: str, message: str) -> Tuple[bool, str]:
    cur = current_branch(repo_root)
    if is_protected_branch(cur):
        return False, f"Refusing to commit on protected branch '{cur}'."
    msg = (message or "").strip()
    if not msg:
        return False, "Commit message is empty."
    try:
        proc = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except OSError as e:
        return False, str(e)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "git commit failed").strip()
    return True, (proc.stdout or "Committed.").strip()


def gh_available() -> bool:
    try:
        proc = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0
    except OSError:
        return False


def fetch_issue_context(
    issue_num: int,
    *,
    repo: str = "surya-shreevathsa11/Clogem",
) -> Tuple[bool, str]:
    if not gh_available():
        return False, "GitHub CLI (gh) is not available on PATH."
    try:
        proc = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(issue_num),
                "--repo",
                repo,
                "--json",
                "title,body,number,labels",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as e:
        return False, str(e)
    if proc.returncode != 0:
        return False, (proc.stderr or "gh issue view failed").strip()
    return True, (proc.stdout or "").strip()


def create_pull_request(
    repo_root: str,
    title: str,
    body: str,
    *,
    base: str = "main",
) -> Tuple[bool, str]:
    if not gh_available():
        return False, "GitHub CLI (gh) is not available on PATH."
    cur = current_branch(repo_root)
    if is_protected_branch(cur):
        return False, f"Refusing to open PR from protected branch '{cur}'."
    try:
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--base",
                base,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except OSError as e:
        return False, str(e)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "gh pr create failed").strip()
    return True, (proc.stdout or "PR created.").strip()
