"""Enrich ``current_segment`` wire with title presentation metadata (P3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..state import GameState

SEGMENT_PRESENTATION_KEYS = frozenset(
    {"presentation_id", "interaction_mode", "primitive", "inform_profile"}
)


@dataclass(frozen=True, slots=True)
class SegmentPresentationContext:
    """Context for ``enrich_current_segment`` (after base segment projection)."""

    state: GameState
    viewer_faction: str | None
    segment: dict[str, Any]
    viewer_may_act: bool
    current_phase: str


def merge_segment_presentation(
    segment: dict[str, Any], patch: dict[str, Any]
) -> dict[str, Any]:
    """Merge allowed presentation keys onto a segment wire dict."""

    out = dict(segment)
    for key, value in patch.items():
        if key not in SEGMENT_PRESENTATION_KEYS:
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out[key] = text
    return out


__all__ = [
    "SEGMENT_PRESENTATION_KEYS",
    "SegmentPresentationContext",
    "merge_segment_presentation",
]
