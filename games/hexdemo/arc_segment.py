"""Hexdemo helpers for reading the active declared arc segment (composable arcs)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hexengine.arcs.segment_wire import (
    project_current_segment,
    segment_allows_action,
    segment_blocks_routine_phase_advance,
)
from hexengine.server.arcs.authority_arc_runtime import lookup_arc_spec
from hexengine.state import GameState


def _segment_host():
    from .hooks import build_hooks

    hooks = build_hooks()
    host = SimpleNamespace(hooks=hooks, movement_arc_spec=lambda: None)
    host.lookup_arc_spec = lambda arc_id: lookup_arc_spec(host, arc_id)
    return host


def project_segment_for_faction(
    state: GameState, viewer_faction: str | None
) -> dict[str, Any] | None:
    """Per-viewer segment descriptor from declared arcs (or None without a cursor)."""

    return project_current_segment(
        _segment_host(), state, viewer_faction=viewer_faction
    )


def phase_advance_blocked(state: GameState) -> bool:
    """True when the active segment forbids ``NextPhase`` for the current faction."""

    return segment_blocks_routine_phase_advance(
        _segment_host(),
        state,
        viewer_faction=str(state.turn.current_faction),
    )


def segment_denies_action(
    state: GameState,
    viewer_faction: str | None,
    action_type: str,
) -> bool:
    """True when a segment is active and omits ``action_type`` from allowed_actions."""

    seg = project_segment_for_faction(state, viewer_faction)
    if seg is None:
        return False
    return not segment_allows_action(seg, action_type)


__all__ = [
    "phase_advance_blocked",
    "project_segment_for_faction",
    "segment_denies_action",
]
