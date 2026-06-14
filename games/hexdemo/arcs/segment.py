"""Hexdemo helpers for reading the active declared arc segment (composable arcs)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hexengine.arcs.segment_wire import (
    project_current_segment,
    segment_allows_action,
    segment_blocks_routine_phase_advance,
    segment_denies_action_for_faction,
)
from hexengine.server.arcs.authority_arc_runtime import lookup_arc_spec
from hexengine.state import GameState

_SEGMENT_HOST: SimpleNamespace | None = None


def _segment_host() -> SimpleNamespace:
    global _SEGMENT_HOST
    if _SEGMENT_HOST is None:
        from ..hooks import (
            build_hooks,  # breaks cycle: hooks → interaction → arcs.segment → hooks
        )

        hooks = build_hooks()
        host = SimpleNamespace(hooks=hooks, movement_arc_spec=lambda: None)
        host.lookup_arc_spec = lambda arc_id: lookup_arc_spec(host, arc_id)
        _SEGMENT_HOST = host
    return _SEGMENT_HOST


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

    return segment_denies_action_for_faction(
        _segment_host(), state, viewer_faction, action_type
    )


def segment_ui_mode(state: GameState, viewer_faction: str | None) -> str:
    """Active declared segment ``ui_mode`` for ``viewer_faction``, or ``""``."""

    seg = project_segment_for_faction(state, viewer_faction)
    if not seg:
        return ""
    return str(seg.get("ui_mode", "")).strip()


def segment_allows(
    state: GameState,
    viewer_faction: str | None,
    action_type: str,
) -> bool:
    """True when the projected segment lists ``action_type`` in ``allowed_actions``."""

    seg = project_segment_for_faction(state, viewer_faction)
    if seg is None:
        return False
    return segment_allows_action(seg, action_type)


__all__ = [
    "phase_advance_blocked",
    "project_segment_for_faction",
    "segment_allows",
    "segment_denies_action",
    "segment_ui_mode",
]
