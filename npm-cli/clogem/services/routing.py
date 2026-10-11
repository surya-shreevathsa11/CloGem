from __future__ import annotations

import re
from typing import Optional, Tuple

_SESSION_DIRECTIVE = re.compile(
    r"^/(build|plan|debug|agent|ask|research)(?:\s+|$)(.*)$",
    re.I | re.DOTALL,
)


def parse_session_directive(raw: str) -> Tuple[str, Optional[str]]:
    """Strip one leading /build /plan /debug /agent /ask /research; return (rest, directive name or None)."""
    s = raw.strip()
    m = _SESSION_DIRECTIVE.match(s)
    if not m:
        return raw, None
    name = m.group(1).lower()
    rest = (m.group(2) or "").strip()
    return rest, name
