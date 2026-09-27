"""
REPL orchestration for Clogem.

The interactive main loop lives in ``clogem.cli.async_main`` for now.
Non-interactive single turns use the same loop via ``_single_run_mode`` in cli.

Future work: move the ``while True`` turn body into ``async def run_repl_turn(ctx)``.
"""

from __future__ import annotations

__all__: list[str] = []
