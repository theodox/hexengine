"""
Top-level hook bundle that the server can bind once per game definition.

This intentionally stays small: it is the "one obvious place" to look for all
 rules customization entry points.

Role in turn resolution:

- The server binds one `TitleHooks` instance when it constructs `GameServer`.
- Every client action is resolved against the authoritative `GameState` by consulting
  `self.hooks.<area>.<hook>(...)` (movement, attack, etc.).
- Titles return `hooks.ENGINE_DEFAULT` to request engine defaults at a hook point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .arcs import ArcsHooks
from .attack import AttackHooks
from .movement import MovementHooks
from .ui import UIHooks


def read_title_hooks_from_definition(game_definition: Any) -> TitleHooks:
    """Resolve `TitleHooks` from a game definition (same rules as `GameServer` binding)."""

    raw = getattr(game_definition, "hooks", None)
    if raw is None:
        return TitleHooks()
    if callable(raw):
        try:
            raw = raw()
        except Exception:
            return TitleHooks()
    return raw if isinstance(raw, TitleHooks) else TitleHooks()


@dataclass(frozen=True, slots=True)
class TitleHooks:
    movement: MovementHooks = MovementHooks()
    attack: AttackHooks = AttackHooks()
    ui: UIHooks = UIHooks()
    arcs: ArcsHooks = ArcsHooks()


__all__ = ["TitleHooks", "read_title_hooks_from_definition"]
