"""
Template segment presentation registry (extend when adding combat gates).

Bind ``UIHook.SEGMENT_PRESENTATION_REGISTRY`` to return the keys of
``PRESENTATION_BY_UI_MODE`` when ``title_state_extension_key`` is set.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Primitive(StrEnum):
    INFORM = "inform"
    SELECT = "select"
    DECIDE = "decide"
    SEQUENCE = "sequence"


@dataclass(frozen=True, slots=True)
class SegmentPresentation:
    ui_mode: str
    presentation_id: str
    primitive: Primitive
    interaction_mode: str | None = None
    inform_profile: str | None = None


PRESENTATION_BY_UI_MODE: dict[str, SegmentPresentation] = {
    "move": SegmentPresentation(
        ui_mode="move",
        presentation_id="routine",
        primitive=Primitive.DECIDE,
    ),
    # Add when enabling combat schedule + extension key, e.g.:
    # "combat": SegmentPresentation(..., interaction_mode="attack_plan"),
    # "awaiting_retreat": SegmentPresentation(..., primitive=Primitive.SEQUENCE, ...),
}


def segment_presentation_ui_modes() -> frozenset[str]:
    return frozenset(PRESENTATION_BY_UI_MODE.keys())


__all__ = [
    "PRESENTATION_BY_UI_MODE",
    "Primitive",
    "SegmentPresentation",
    "segment_presentation_ui_modes",
]
