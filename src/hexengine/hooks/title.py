"""
Top-level hook bundle that the server can bind once per game definition.

This intentionally stays small: it is the "one obvious place" to look for all
 rules customization entry points.

Role in turn resolution:

- The server binds one `TitleHooks` instance when it constructs `GameServer`.
- Every client action is resolved against the authoritative `GameState` by consulting
  `self.hooks.<area>.<hook>(...)` (movement, attack, etc.).
- Titles return `hooks.DEFAULT` to request engine defaults at a hook point.
"""

from __future__ import annotations

from dataclasses import dataclass

from .attack import AttackHooks
from .movement import MovementHooks
from .ui import UIHooks


@dataclass(frozen=True, slots=True)
class TitleHooks:
    movement: MovementHooks = MovementHooks()
    attack: AttackHooks = AttackHooks()
    ui: UIHooks = UIHooks()


__all__ = ["TitleHooks"]

