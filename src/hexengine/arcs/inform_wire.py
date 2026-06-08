"""
INFORM lane resolution from ``current_segment`` (P4).

When the client omits ``inform_kind`` on an ``inspect`` request, the server derives the
active inform profile from the per-viewer ``current_segment`` projection.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..state import GameState
from .segment_wire import SegmentProjectorHost, project_current_segment


@dataclass(frozen=True, slots=True)
class ResolvedInformLane:
    """Effective INFORM grouping for title hooks and engine defaults."""

    inform_kind: str
    inform_profile: str | None
    segment_ui_mode: str | None


def resolve_inform_lane(
    host: SegmentProjectorHost,
    state: GameState,
    *,
    viewer_faction: str | None,
    client_inform_kind: str = "",
) -> ResolvedInformLane:
    """
    Resolve inform profile / kind for an ``inspect`` INFORM request.

    Precedence: explicit client ``inform_kind`` → ``current_segment.inform_profile`` →
    ``current_segment.interaction_mode`` (client-draft lanes).
    """

    client = str(client_inform_kind or "").strip()
    segment_ui_mode: str | None = None
    profile = ""
    seg = project_current_segment(host, state, viewer_faction=viewer_faction)
    if isinstance(seg, dict):
        sk = str(seg.get("ui_mode", "")).strip()
        segment_ui_mode = sk or None
        profile = str(seg.get("inform_profile", "")).strip()
    effective = client or profile
    if not effective and isinstance(seg, dict):
        effective = str(seg.get("interaction_mode", "")).strip()
    lane_profile = profile or effective or None
    return ResolvedInformLane(
        inform_kind=effective,
        inform_profile=lane_profile,
        segment_ui_mode=segment_ui_mode,
    )


__all__ = ["ResolvedInformLane", "resolve_inform_lane"]
