from __future__ import annotations

from clogem.services.routing import parse_session_directive


def test_parse_session_directive_extracts_build() -> None:
    rest, directive = parse_session_directive("/build implement feature")
    assert directive == "build"
    assert rest == "implement feature"


def test_parse_session_directive_extracts_research() -> None:
    rest, directive = parse_session_directive("/research what is CRISPR?")
    assert directive == "research"
    assert rest == "what is CRISPR?"


def test_parse_session_directive_leaves_plain_text() -> None:
    rest, directive = parse_session_directive("add a login page")
    assert directive is None
    assert rest == "add a login page"
