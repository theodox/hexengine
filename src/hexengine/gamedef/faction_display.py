"""Faction id → human-readable labels for turn UI (no browser / Pyodide imports)."""

from __future__ import annotations

# Wire / scenario faction id → turn banner label
_FACTION_DISPLAY_LABEL: dict[str, str] = {
    "red": "Red",
    "blue": "Blue",
    "confederate": "Confederate",
    "union": "Union",
}


def display_faction_name(faction: str) -> str:
    """Short label for turn UI (known ids match CSS classes on #turn-display)."""
    key = faction.strip().lower()
    if key in _FACTION_DISPLAY_LABEL:
        return _FACTION_DISPLAY_LABEL[key]
    return faction.replace("_", " ").strip().title() or faction


def display_phase_name(phase: str) -> str:
    """Sentence-case phase for turn UI (e.g. `attack` → `Attack`)."""
    p = phase.strip()
    if not p:
        return phase
    return p[0].upper() + p[1:]
