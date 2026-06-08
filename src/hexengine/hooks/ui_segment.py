"""Enrich ``current_segment`` wire with title presentation metadata (P3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..state import GameState

SEGMENT_PRESENTATION_KEYS = frozenset(
    {
        "presentation_id",
        "draft_presentation_id",
        "interaction_mode",
        "primitive",
        "inform_profile",
    }
)


@dataclass(frozen=True, slots=True)
class SegmentPresentationContext:
    """Context for ``enrich_current_segment`` (after base segment projection)."""

    state: GameState
    viewer_faction: str | None
    segment: dict[str, Any]
    viewer_may_act: bool
    current_phase: str


@dataclass(frozen=True, slots=True)
class SegmentPresentationPatch:
    """Presentation fields merged onto ``current_segment`` (subset of registry row)."""

    presentation_id: str | None = None
    draft_presentation_id: str | None = None
    interaction_mode: str | None = None
    primitive: str | None = None
    inform_profile: str | None = None

    def to_wire_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for key in SEGMENT_PRESENTATION_KEYS:
            raw = getattr(self, key, None)
            if raw is None:
                continue
            text = str(raw).strip()
            if text:
                out[key] = text
        return out


def segment_presentation_patch(
    *,
    presentation_id: str | None = None,
    draft_presentation_id: str | None = None,
    interaction_mode: str | None = None,
    primitive: str | None = None,
    inform_profile: str | None = None,
) -> SegmentPresentationPatch:
    """Build enrich hook output (author-facing)."""
    return SegmentPresentationPatch(
        presentation_id=presentation_id,
        draft_presentation_id=draft_presentation_id,
        interaction_mode=interaction_mode,
        primitive=primitive,
        inform_profile=inform_profile,
    )


def merge_segment_presentation(
    segment: dict[str, Any], patch: dict[str, str]
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
    "SegmentPresentationPatch",
    "merge_segment_presentation",
    "segment_presentation_patch",
]
