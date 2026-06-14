"""
Top-level hook bundle that the server can bind once per game definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .arcs import ArcsHooks
from .interaction import InteractionHooks
from .modification import ModificationHooks
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
    modification: ModificationHooks = ModificationHooks()
    interaction: InteractionHooks = InteractionHooks()
    ui: UIHooks = UIHooks()
    arcs: ArcsHooks = ArcsHooks()


__all__ = ["TitleHooks", "read_title_hooks_from_definition"]
