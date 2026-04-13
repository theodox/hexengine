"""Turn banner (#turn-display) faction CSS classes (browser DOM)."""

from __future__ import annotations

from ..gamedef.faction_display import display_faction_name, display_phase_name

# All faction class names ever applied to the strip; remove before adding the active one.
TURN_STRIP_FACTION_CLASSES: tuple[str, ...] = (
    "red",
    "blue",
    "confederate",
    "union",
)


def apply_turn_strip_faction(turn_bg, faction: str) -> None:
    """Clear known faction styling classes, then add `faction.lower()`."""
    for c in TURN_STRIP_FACTION_CLASSES:
        turn_bg.classList.remove(c)
    turn_bg.classList.add(faction.lower())


__all__ = [
    "TURN_STRIP_FACTION_CLASSES",
    "apply_turn_strip_faction",
    "display_faction_name",
    "display_phase_name",
]
