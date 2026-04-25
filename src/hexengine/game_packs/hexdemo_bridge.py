"""
Hexdemo title: import only after ``gameroot.ensure_hexdemo_package_import_path`` has run.

Keeps ``hexdemo`` / ``games.hexdemo`` imports out of ``gameroot.py`` and other scattered
call sites.
"""

from __future__ import annotations

from hexengine.gamedef.protocol import GameDefinition


def load_game_definition(*, schedule: str = "interleaved") -> GameDefinition:
    """
    Build Hexdemo's ``GameDefinition`` for the given server/client schedule string.

    Raises:
        ModuleNotFoundError: if ``hexdemo`` is not importable (path not prepared).
    """
    from hexdemo.registry import build_game_definition

    key = "sequential" if schedule.strip().lower() == "sequential" else "interleaved"
    return build_game_definition(key)
