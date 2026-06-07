"""
Template segment presentation registry (extend when adding combat gates).

Bind ``UIHook.SEGMENT_PRESENTATION_REGISTRY`` to return the keys of
``PRESENTATION_BY_SEGMENT_KIND`` when ``title_state_extension_key`` is set.
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
    kind: str
    presentation_id: str
    primitive: Primitive
    interaction_mode: str | None = None
    inform_profile: str | None = None


PRESENTATION_BY_SEGMENT_KIND: dict[str, SegmentPresentation] = {
    "move": SegmentPresentation(
        kind="move",
        presentation_id="routine",
        primitive=Primitive.DECIDE,
    ),
    # Add when enabling combat schedule + extension key, e.g.:
    # "combat": SegmentPresentation(..., interaction_mode="attack_plan"),
    # "awaiting_retreat": SegmentPresentation(..., primitive=Primitive.SEQUENCE, ...),
}


def segment_presentation_kinds() -> frozenset[str]:
    return frozenset(PRESENTATION_BY_SEGMENT_KIND.keys())


__all__ = [
    "PRESENTATION_BY_SEGMENT_KIND",
    "Primitive",
    "SegmentPresentation",
    "segment_presentation_kinds",
]
