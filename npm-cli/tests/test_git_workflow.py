from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clogem.git_workflow import (
    create_branch,
    current_branch,
    fetch_issue_context,
    gh_available,
    git_commit,
    git_diff_written,
    is_protected_branch,
)


# ---------------------------------------------------------------------------
# is_protected_branch
# ---------------------------------------------------------------------------


def test_is_protected_branch_main():
    assert is_protected_branch("main")


def test_is_protected_branch_master():
    assert is_protected_branch("master")


def test_is_protected_branch_feature():
    assert not is_protected_branch("feat/some-feature")


def test_is_protected_branch_empty():
    assert not is_protected_branch("")


# ---------------------------------------------------------------------------
# current_branch
# ---------------------------------------------------------------------------


def test_current_branch_returns_string(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=str(tmp_path),
        capture_output=True,
        env={**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    branch = current_branch(str(tmp_path))
    assert isinstance(branch, str)
    assert branch  # should be "main" or "master"


def test_current_branch_returns_empty_on_bad_path():
    branch = current_branch("/nonexistent/path/xyz")
    assert branch == ""


# ---------------------------------------------------------------------------
# git_diff_written
# ---------------------------------------------------------------------------


def test_git_diff_written_no_files(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    rc, out, err = git_diff_written(str(tmp_path), [])
    assert isinstance(rc, int)
    assert isinstance(out, str)


def test_git_diff_written_missing_files_returns_no_diff(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    rc, out, err = git_diff_written(str(tmp_path), ["nonexistent.py"])
    assert "(no diff: files not found on disk)" in out or rc == 0


# ---------------------------------------------------------------------------
# create_branch — guarded by protected-branch check
# ---------------------------------------------------------------------------


def test_create_branch_rejects_from_protected(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    with patch("clogem.git_workflow.current_branch", return_value="main"):
        ok, msg = create_branch(str(tmp_path), "feat/test")
    assert not ok
    assert "protected" in msg.lower()


def test_create_branch_rejects_invalid_name(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    with patch("clogem.git_workflow.current_branch", return_value="feat/existing"):
        ok, msg = create_branch(str(tmp_path), "bad name!")
    assert not ok
    assert "invalid" in msg.lower()


def test_create_branch_rejects_empty_name(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    with patch("clogem.git_workflow.current_branch", return_value="feat/existing"):
        ok, msg = create_branch(str(tmp_path), "")
    assert not ok
    assert "required" in msg.lower()


# ---------------------------------------------------------------------------
# git_commit — guarded by protected-branch check
# ---------------------------------------------------------------------------


def test_git_commit_rejects_on_main():
    with patch("clogem.git_workflow.current_branch", return_value="main"):
        ok, msg = git_commit("/tmp", "test: commit message")
    assert not ok
    assert "protected" in msg.lower()


def test_git_commit_rejects_empty_message():
    with patch("clogem.git_workflow.current_branch", return_value="feat/branch"):
        ok, msg = git_commit("/tmp", "")
    assert not ok
    assert "empty" in msg.lower()


# ---------------------------------------------------------------------------
# gh_available / fetch_issue_context
# ---------------------------------------------------------------------------


def test_gh_available_returns_bool():
    with patch("clogem.git_workflow.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert gh_available() is True
        mock_run.return_value = MagicMock(returncode=1)
        assert gh_available() is False


def test_gh_available_false_on_timeout():
    with patch("clogem.git_workflow.subprocess.run") as mock_run:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["gh"], timeout=5)
        assert gh_available() is False


def test_fetch_issue_context_no_gh():
    with patch("clogem.git_workflow.gh_available", return_value=False):
        ok, msg = fetch_issue_context(1)
    assert not ok
    assert "gh" in msg.lower()
