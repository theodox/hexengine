"""Apply title combat outcomes after Attack + ApplyCombatEffects (server re-export)."""

from __future__ import annotations

from ...arcs.title.attack_outcome import (
    follow_up_state_actions_after_attack,
    split_resolve_result,
)

__all__ = [
    "follow_up_state_actions_after_attack",
    "split_resolve_result",
]
