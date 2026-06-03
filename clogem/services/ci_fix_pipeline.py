from __future__ import annotations

import re
import subprocess
from typing import Optional, Tuple


def wants_ci_fix_task(text: str) -> bool:
    if not text or len(text.strip()) < 8:
        return False
    t = text.lower()
    if re.search(
        r"\b(ci|github\s+actions|workflow|pipeline)\b.*\b(fail|failed|fix|red|broken)\b",
        t,
    ):
        return True
    if re.search(r"\bfix\s+(the\s+)?ci\b", t):
        return True
    return False


def fetch_ci_logs(repo_root: str, max_lines: int = 120) -> Tuple[bool, str]:
    """Best-effort gh run view for latest failed run."""
    try:
        proc = subprocess.run(
            ["gh", "run", "list", "--limit", "5", "--json", "databaseId,conclusion,status"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as e:
        return False, str(e)
    if proc.returncode != 0:
        return False, (proc.stderr or "gh run list failed").strip()

    import json

    try:
        runs = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return False, "Could not parse gh run list"

    run_id = None
    for r in runs if isinstance(runs, list) else []:
        if isinstance(r, dict) and r.get("conclusion") == "failure":
            run_id = r.get("databaseId")
            break
    if run_id is None:
        return False, "No failed GitHub Actions run found."

    try:
        proc2 = subprocess.run(
            ["gh", "run", "view", str(run_id), "--log-failed"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except OSError as e:
        return False, str(e)
    log = (proc2.stdout or proc2.stderr or "").strip()
    lines = log.splitlines()
    if len(lines) > max_lines:
        log = "\n".join(lines[-max_lines:]) + f"\n\n[truncated to last {max_lines} lines]"
    return proc2.returncode == 0 or bool(log), log
