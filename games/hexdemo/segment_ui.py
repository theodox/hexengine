"""
Hexdemo segment presentation registry (ui_mode → skin / primitives).

Maps declared arc segment ``ui_mode`` strings to author-facing presentation metadata.
Dock and inform hooks resolve copy and CSS through ``presentation_id``; legality stays
on ``current_segment.allowed_actions`` from the engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .combat.transitions import (
    GATE_AWAITING_ADVANCE,
    GATE_AWAITING_RETREAT,
    GATE_AWAITING_RETREAT_OR_DISRUPT,
)


class Primitive(StrEnum):
    """Player interaction primitive for a segment UX mode (see TITLE_AUTHORING.md)."""

    INFORM = "inform"
    SELECT = "select"
    DECIDE = "decide"
    SEQUENCE = "sequence"


@dataclass(frozen=True, slots=True)
class SegmentPresentation:
    """One UI mode: ties arc segment ``ui_mode`` to presentation and interaction."""

    ui_mode: str
    presentation_id: str
    primitive: Primitive
    interaction_mode: str | None = None
    draft_presentation_id: str | None = None
    inform_profile: str | None = None


# ``ui_mode`` values from routine schedule slots (``move`` / ``combat``) and combat arc gates.
PRESENTATION_BY_UI_MODE: dict[str, SegmentPresentation] = {
    "move": SegmentPresentation(
        ui_mode="move",
        presentation_id="routine",
        primitive=Primitive.DECIDE,
    ),
    "combat": SegmentPresentation(
        ui_mode="combat",
        presentation_id="attack_ready",
        primitive=Primitive.SEQUENCE,
        interaction_mode="attack_plan",
        draft_presentation_id="attack_draft",
        inform_profile="attack_plan",
    ),
    GATE_AWAITING_RETREAT: SegmentPresentation(
        ui_mode=GATE_AWAITING_RETREAT,
        presentation_id="retreat_gate",
        primitive=Primitive.SELECT,
        interaction_mode="retreat_path",
        draft_presentation_id="retreat_path_draft",
        inform_profile="retreat_gate",
    ),
    GATE_AWAITING_RETREAT_OR_DISRUPT: SegmentPresentation(
        ui_mode=GATE_AWAITING_RETREAT_OR_DISRUPT,
        presentation_id="retreat_gate",
        primitive=Primitive.SELECT,
        interaction_mode="retreat_path",
        draft_presentation_id="retreat_path_draft",
        inform_profile="retreat_gate",
    ),
    GATE_AWAITING_ADVANCE: SegmentPresentation(
        ui_mode=GATE_AWAITING_ADVANCE,
        presentation_id="advance_gate",
        primitive=Primitive.DECIDE,
        inform_profile="advance_gate",
    ),
}


def segment_presentation(
    segment: Mapping[str, Any] | None,
) -> SegmentPresentation | None:
    """Lookup registry row for the active segment ``ui_mode``, if registered."""

    if not segment:
        return None
    ui_mode = str(segment.get("ui_mode", "")).strip()
    if not ui_mode:
        return None
    return PRESENTATION_BY_UI_MODE.get(ui_mode)


def resolve_presentation_id(
    segment: Mapping[str, Any] | None,
    *,
    viewer_may_act: bool,
    current_phase: str,
    extra_gate_actions: list[dict[str, Any]] | None = None,
) -> str:
    """Skin key for the turn action dock from the segment presentation registry."""

    _ = (current_phase, extra_gate_actions)
    row = segment_presentation(segment)
    if row is not None:
        return row.presentation_id
    if not segment:
        return "hidden" if not viewer_may_act else "routine"
    ui_mode = str(segment.get("ui_mode", "")).strip() or "(unknown)"
    raise ValueError(f"No segment presentation registered for ui_mode {ui_mode!r}")


__all__ = [
    "PRESENTATION_BY_UI_MODE",
    "Primitive",
    "SegmentPresentation",
    "resolve_presentation_id",
    "segment_presentation",
]
