"""Turn banner (#turn-display) faction CSS class management (browser DOM)."""

from __future__ import annotations

from ..gamedef.faction_display import display_faction_name, display_phase_name


def apply_turn_strip_faction(turn_bg, faction: str, *, css_class: str | None = None) -> None:
    """Remove the previously applied faction class (if any), then add `css_class`."""
    prev = getattr(getattr(turn_bg, "dataset", None), "factionClass", None)
    if prev:
        turn_bg.classList.remove(prev)
    nxt = (css_class or faction).lower()
    turn_bg.classList.add(nxt)
    if getattr(turn_bg, "dataset", None) is not None:
        turn_bg.dataset.factionClass = nxt


__all__ = [
    "apply_turn_strip_faction",
    "display_faction_name",
    "display_phase_name",
]
