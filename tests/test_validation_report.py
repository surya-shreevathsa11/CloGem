from __future__ import annotations

import os
from pathlib import Path

import pytest

from clogem.validation import (
    ValidationReport,
    copy_repo_to_sandbox_with_extras,
    detect_typecheck_command,
    git_tracked_files,
)


# ---------------------------------------------------------------------------
# ValidationReport
# ---------------------------------------------------------------------------


def test_validation_report_ok_default():
    r = ValidationReport(ok=True)
    assert r.ok is True
    assert r.tests_rc == 0
    assert r.lint_rc == 0


def test_validation_report_as_prompt_block_empty():
    r = ValidationReport(ok=True)
    result = r.as_prompt_block()
    assert isinstance(result, str)


def test_validation_report_as_prompt_block_with_tests():
    r = ValidationReport(ok=False, tests_text="FAILED: 2 errors")
    block = r.as_prompt_block()
    assert "Tests" in block
    assert "FAILED: 2 errors" in block


def test_validation_report_as_prompt_block_all_sections():
    r = ValidationReport(
        ok=False,
        tests_text="tests failed",
        lint_text="lint error",
        typecheck_text="type error",
    )
    block = r.as_prompt_block()
    assert "Tests" in block
    assert "Lint" in block
    assert "Typecheck" in block


def test_validation_report_sections_field():
    r = ValidationReport(ok=True, sections=["tests passed"])
    assert "tests passed" in r.sections


# ---------------------------------------------------------------------------
# copy_repo_to_sandbox_with_extras
# ---------------------------------------------------------------------------


def test_copy_sandbox_with_extras_copies_extra_files(tmp_path):
    src = tmp_path / "repo"
    src.mkdir()
    (src / ".git").mkdir()
    (src / "tracked.py").write_text("# tracked")
    extra = src / "untracked.py"
    extra.write_text("# extra")

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    # Even without git tracking, the extras should be copied
    _used_git, copied = copy_repo_to_sandbox_with_extras(
        str(src),
        str(sandbox),
        extra_rel_paths=["untracked.py"],
    )
    # Extra file should be in sandbox
    assert (sandbox / "untracked.py").is_file()


def test_copy_sandbox_with_extras_empty_extras(tmp_path):
    src = tmp_path / "repo"
    src.mkdir()
    (src / ".git").mkdir()

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    _used_git, copied = copy_repo_to_sandbox_with_extras(
        str(src),
        str(sandbox),
        extra_rel_paths=[],
    )
    assert isinstance(copied, int)
    assert copied >= 0


def test_copy_sandbox_ignores_dotgit(tmp_path):
    src = tmp_path / "repo"
    src.mkdir()
    git_dir = src / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main")

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    copy_repo_to_sandbox_with_extras(
        str(src),
        str(sandbox),
        extra_rel_paths=[".git/HEAD"],
    )
    # .git/ should be ignored by default extra_ignore_prefixes
    assert not (sandbox / ".git" / "HEAD").is_file()


# ---------------------------------------------------------------------------
# detect_typecheck_command
# ---------------------------------------------------------------------------


def test_detect_typecheck_no_config(tmp_path):
    result = detect_typecheck_command(str(tmp_path))
    assert result is None


def test_detect_typecheck_pyright(tmp_path):
    (tmp_path / "pyrightconfig.json").write_text("{}")
    result = detect_typecheck_command(str(tmp_path))
    assert result is not None
    assert "pyright" in result


def test_detect_typecheck_tsconfig(tmp_path):
    (tmp_path / "tsconfig.json").write_text("{}")
    result = detect_typecheck_command(str(tmp_path))
    assert result is not None
    assert "tsc" in result[1] or "npx" in result[0]
