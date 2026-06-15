"""Engine default for ``UIHook.COMBAT_INTERACTION_MESSAGES`` (no bucket reads)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..ui.display import InteractionMessage
from .ui import CombatInteractionMessagesContext


def default_combat_interaction_messages(
    ctx: CombatInteractionMessagesContext,
    *,
    combat_instruction: Callable[[str, str | None], tuple[str, str]],
    advance_gate_banners: Callable[[str], tuple[str, str]],
) -> list[InteractionMessage]:
    """Engine ``ENGINE_DEFAULT``: no combat rows (titles bind the hook or use the pattern)."""

    _ = (ctx, combat_instruction, advance_gate_banners)
    return []


__all__ = [
    "CombatInteractionMessagesContext",
    "default_combat_interaction_messages",
]
