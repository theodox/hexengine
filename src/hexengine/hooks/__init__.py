"""
Engine hook surface for title-authored rules.

Role in turn resolution:

- The authoritative server is the only component that executes hooks.
- A title supplies a `TitleHooks` bundle (attribute `hooks` or callable `hooks()` on the
  game definition object).
- During action validation/resolution, the server consults `TitleHooks` and then applies
  deterministic engine state actions.

Titles can return `hooks.DEFAULT` from a hook to request engine default behavior.
"""

from __future__ import annotations

from .attack import AttackContext, AttackHooks, AttackResolution
from .core import DEFAULT, RuleViolation, implements_hook
from .movement import MoveContext, MovementHooks, StackingPolicy
from .title import TitleHooks
from .ui import UIHooks

__all__ = [
    "DEFAULT",
    "RuleViolation",
    "implements_hook",
    "MovementHooks",
    "MoveContext",
    "StackingPolicy",
    "AttackHooks",
    "AttackContext",
    "AttackResolution",
    "TitleHooks",
    "UIHooks",
]

