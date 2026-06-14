"""
Wire projection for the active arc segment (composable arcs, Phase 5).

Publishes a per-recipient ``current_segment`` descriptor on ``StateUpdate`` so legality,
End-Phase blocking, and client draft entry derive from the declared segment rather than
title gate strings. Projects ``ui_mode`` (title UI/policy bucket) alongside ``segment_id`` (graph node).
Dock button presentation is title-owned — see ``combat_gate_panel_actions``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from ..state import GameState
from .cursor import read_arc_cursor
from .runner import resolve_owner

SEGMENT_WIRE_SCHEMA = 1

# Action types assembled client-side before commit (wire ``action_locus``).
CLIENT_DRAFT_ACTIONS = frozenset({"Attack"})


class SegmentProjectorHost(Protocol):
    """Minimal host surface for segment lookup (GameServer satisfies this)."""

    hooks: Any

    def lookup_arc_spec(self, arc_id: str) -> Any: ...


def _action_locus(action_type: str) -> str:
    return "client_draft" if action_type in CLIENT_DRAFT_ACTIONS else "server"


def enrich_current_segment_wire(
    host: SegmentProjectorHost,
    segment: dict[str, Any],
    state: GameState,
    *,
    viewer_faction: str | None,
    viewer_may_act: bool,
) -> dict[str, Any]:
    """Attach ``presentation_id`` / ``interaction_mode`` from ``ENRICH_CURRENT_SEGMENT``."""

    from ..hooks.core import ENGINE_DEFAULT
    from ..hooks.ui_segment import (
        SegmentPresentationContext,
        merge_segment_presentation,
    )

    phase = str(state.turn.current_phase).strip()
    ui = getattr(getattr(host, "hooks", None), "ui", None)
    enrich = getattr(ui, "enrich_current_segment", None) if ui is not None else None
    if not callable(enrich):
        return dict(segment)
    ctx = SegmentPresentationContext(
        state=state,
        viewer_faction=viewer_faction,
        segment=dict(segment),
        viewer_may_act=viewer_may_act,
        current_phase=phase,
    )
    raw = enrich(ctx)
    if raw is ENGINE_DEFAULT:
        return dict(segment)
    from ..hooks.ui_segment import SegmentPresentationPatch

    if not isinstance(raw, SegmentPresentationPatch):
        raise TypeError(
            "enrich_current_segment must return SegmentPresentationPatch or "
            f"ENGINE_DEFAULT, got {type(raw).__name__}"
        )
    return merge_segment_presentation(segment, raw.to_wire_dict())


def project_current_segment(
    host: SegmentProjectorHost,
    state: GameState,
    *,
    viewer_faction: str | None,
) -> dict[str, Any] | None:
    """Per-recipient projection of the active declared segment (or None when no cursor)."""

    from .title.lookup import lookup_arc_spec

    cursor = read_arc_cursor(state)
    if cursor is None:
        return None

    spec = lookup_arc_spec(host, cursor.arc_id)
    if spec is None:
        return None

    segment = spec.arc.get(cursor.segment_id)
    owner = resolve_owner(segment.owner, state, spec.owner_resolver)
    viewer = str(viewer_faction or "").strip()
    owner_s = str(owner).strip() if owner else ""

    viewer_may_act = bool(viewer and owner_s and viewer == owner_s)
    allowed = sorted(segment.allowed_actions) if viewer_may_act else []

    base = {
        "schema": SEGMENT_WIRE_SCHEMA,
        "arc_id": str(cursor.arc_id),
        "segment_id": str(cursor.segment_id),
        "ui_mode": str(segment.ui_mode or "routine"),
        "owner": owner_s or None,
        "allowed_actions": allowed,
        "action_locus": {at: _action_locus(at) for at in allowed},
    }
    return enrich_current_segment_wire(
        host,
        base,
        state,
        viewer_faction=viewer_faction,
        viewer_may_act=viewer_may_act,
    )


def segment_allows_action(segment: Mapping[str, Any] | None, action_type: str) -> bool:
    if not segment:
        return False
    raw = segment.get("allowed_actions")
    if not isinstance(raw, list):
        return False
    return str(action_type) in {str(x) for x in raw}


def segment_denies_action_for_faction(
    host: SegmentProjectorHost,
    state: GameState,
    viewer_faction: str | None,
    action_type: str,
) -> bool:
    """True when a segment is active and omits ``action_type`` for this viewer."""

    seg = project_current_segment(host, state, viewer_faction=viewer_faction)
    if seg is None:
        return False
    return not segment_allows_action(seg, action_type)


def segment_blocks_routine_phase_advance(
    host: SegmentProjectorHost,
    state: GameState,
    *,
    viewer_faction: str | None = None,
) -> bool:
    """True when the active segment forbids ``NextPhase`` for the acting viewer."""

    actor = str(viewer_faction or state.turn.current_faction).strip()
    seg = project_current_segment(host, state, viewer_faction=actor)
    if seg is None:
        return False
    return not segment_allows_action(seg, "NextPhase")


def segment_blocks_routine_phase_advance_for_hooks(
    hooks: Any,
    state: GameState,
    *,
    viewer_faction: str | None = None,
) -> bool:
    """Segment-only phase blocking for title hooks that lack a GameServer host."""

    from types import SimpleNamespace

    from .title.lookup import attach_arc_lookup

    host = attach_arc_lookup(SimpleNamespace(hooks=hooks, movement_arc_spec=lambda: None))
    return segment_blocks_routine_phase_advance(
        host, state, viewer_faction=viewer_faction
    )


__all__ = [
    "CLIENT_DRAFT_ACTIONS",
    "SEGMENT_WIRE_SCHEMA",
    "SegmentProjectorHost",
    "enrich_current_segment_wire",
    "project_current_segment",
    "segment_allows_action",
    "segment_denies_action_for_faction",
    "segment_blocks_routine_phase_advance",
    "segment_blocks_routine_phase_advance_for_hooks",
]
