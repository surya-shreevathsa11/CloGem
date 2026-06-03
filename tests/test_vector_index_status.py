from __future__ import annotations

import json
import os
import time
from pathlib import Path


def test_get_index_status_no_index(tmp_path):
    from clogem.vector_index import get_index_status

    status = get_index_status(str(tmp_path))
    assert isinstance(status, dict)
    assert "index_exists" in status
    assert status["index_exists"] is False
    assert "deps_available" in status
    assert "manifest_file_count" in status
    assert status["manifest_file_count"] == 0


def test_get_index_status_with_manifest(tmp_path):
    from clogem.vector_index import get_index_status

    index_dir = tmp_path / ".clogem" / "vector_db"
    index_dir.mkdir(parents=True)
    manifest = {"file1.py": {"hash": "abc"}, "file2.py": {"hash": "def"}}
    (index_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    status = get_index_status(str(tmp_path))
    assert status["index_exists"] is True
    assert status["manifest_file_count"] == 2
    assert status["manifest_mtime"] is not None


def test_get_index_status_bad_manifest(tmp_path):
    from clogem.vector_index import get_index_status

    index_dir = tmp_path / ".clogem" / "vector_db"
    index_dir.mkdir(parents=True)
    (index_dir / "manifest.json").write_text("not json", encoding="utf-8")

    status = get_index_status(str(tmp_path))
    assert status["index_exists"] is True
    assert status["manifest_file_count"] == 0  # parse failed


def test_get_index_status_deps_field(tmp_path):
    from clogem.vector_index import get_index_status

    status = get_index_status(str(tmp_path))
    assert isinstance(status["deps_available"], bool)
    assert isinstance(status.get("deps_error", ""), str)


def test_warm_vector_index_no_deps_does_not_raise(tmp_path):
    """warm_vector_index should silently fail when deps are unavailable."""
    from clogem.vector_index import warm_vector_index

    # Should not raise even if lancedb/sentence-transformers are missing
    warm_vector_index(str(tmp_path))
