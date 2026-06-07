"""
Wire projection for the active arc segment (composable arcs, Phase 5).

Publishes a per-recipient ``current_segment`` descriptor on ``StateUpdate`` so affordances,
End-Phase blocking, and client draft entry derive from the declared segment rather than
title gate strings.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from ..state import GameState
from .cursor import read_arc_cursor
from .runner import resolve_owner

SEGMENT_WIRE_SCHEMA = 1

CLIENT_DRAFT_ACTIONS = frozenset({"Attack"})

# Segment `kind` values that map to turn-dock arc css modifiers (hexdemo gate mirrors).
KIND_DOCK_ARC_RETREAT = frozenset({"awaiting_retreat", "awaiting_retreat_or_disrupt"})
KIND_DOCK_ARC_ADVANCE = frozenset({"awaiting_advance"})


class SegmentProjectorHost(Protocol):
    """Minimal host surface for segment lookup (GameServer satisfies this)."""

    hooks: Any

    def lookup_arc_spec(self, arc_id: str) -> Any: ...


def _action_locus(action_type: str) -> str:
    return "client_draft" if action_type in CLIENT_DRAFT_ACTIONS else "server"


def default_segment_presentation_patch(
    segment: Mapping[str, Any],
    *,
    viewer_may_act: bool,
    current_phase: str,
) -> dict[str, str]:
    """Engine fallback when the title does not bind ``enrich_current_segment``."""

    presentation_id = dock_arc_from_segment(
        segment,
        viewer_may_act=viewer_may_act,
        current_phase=current_phase,
    )
    patch: dict[str, str] = {"presentation_id": presentation_id}
    locus = segment.get("action_locus")
    if isinstance(locus, Mapping) and str(locus.get("Attack", "")).strip() == "client_draft":
        patch["interaction_mode"] = "attack_plan"
    kind = str(segment.get("kind", "")).strip()
    if kind in KIND_DOCK_ARC_RETREAT:
        patch["interaction_mode"] = "retreat_path"
    return patch


def enrich_current_segment_wire(
    host: SegmentProjectorHost,
    segment: dict[str, Any],
    state: GameState,
    *,
    viewer_faction: str | None,
    viewer_may_act: bool,
) -> dict[str, Any]:
    """Attach ``presentation_id`` / ``interaction_mode`` from title hook or engine default."""

    from ..hooks.core import ENGINE_DEFAULT
    from ..hooks.ui_segment import (
        SegmentPresentationContext,
        merge_segment_presentation,
    )

    phase = str(state.turn.current_phase).strip()
    patch = default_segment_presentation_patch(
        segment,
        viewer_may_act=viewer_may_act,
        current_phase=phase,
    )
    ui = getattr(getattr(host, "hooks", None), "ui", None)
    enrich = getattr(ui, "enrich_current_segment", None) if ui is not None else None
    if callable(enrich):
        ctx = SegmentPresentationContext(
            state=state,
            viewer_faction=viewer_faction,
            segment=dict(segment),
            viewer_may_act=viewer_may_act,
            current_phase=phase,
        )
        raw = enrich(ctx)
        if raw is not ENGINE_DEFAULT and isinstance(raw, dict):
            for key, value in raw.items():
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    patch[key] = text
    return merge_segment_presentation(segment, patch)


def project_current_segment(
    host: SegmentProjectorHost,
    state: GameState,
    *,
    viewer_faction: str | None,
) -> dict[str, Any] | None:
    """Per-recipient projection of the active declared segment (or None when no cursor)."""

    from ..server.arcs.authority_arc_runtime import lookup_arc_spec

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
        "kind": str(segment.kind or "routine"),
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
    """Segment-only phase blocking for title hooks that lack a ``GameServer`` host."""

    from types import SimpleNamespace

    from ..server.arcs.authority_arc_runtime import lookup_arc_spec

    host = SimpleNamespace(hooks=hooks, movement_arc_spec=lambda: None)
    host.lookup_arc_spec = lambda arc_id: lookup_arc_spec(host, arc_id)
    return segment_blocks_routine_phase_advance(
        host, state, viewer_faction=viewer_faction
    )


def dock_arc_from_segment(
    segment: Mapping[str, Any] | None,
    *,
    viewer_may_act: bool,
    current_phase: str,
    extra_gate_actions: list[dict[str, Any]] | None = None,
) -> str:
    """Map a segment descriptor to a turn-dock arc css modifier."""

    if segment is None:
        return "routine" if viewer_may_act else "hidden"

    kind = str(segment.get("kind", "")).strip()
    if kind in KIND_DOCK_ARC_RETREAT:
        return "retreat_gate"
    if kind in KIND_DOCK_ARC_ADVANCE:
        return "advance_gate"

    allowed = segment.get("allowed_actions")
    if isinstance(allowed, list):
        for at in allowed:
            if str(at) == "CombatDisruptInsteadOfRetreat":
                return "retreat_gate"
            if str(at) == "CombatAdvance":
                return "advance_gate"

    if extra_gate_actions:
        for row in extra_gate_actions:
            at = str(row.get("action_type", "")).strip()
            if at == "CombatDisruptInsteadOfRetreat":
                return "retreat_gate"
            if at == "CombatAdvance":
                return "advance_gate"

    if not viewer_may_act and not allowed:
        return "hidden"
    if str(current_phase).strip() == "Combat" and viewer_may_act:
        return "attack_ready"
    return "routine"


def action_rows_from_segment(
    segment: Mapping[str, Any] | None,
    shell_ui: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build primary action rows from ``allowed_actions`` + ``shell_ui`` presentation keys."""

    if not segment:
        return []

    raw = segment.get("allowed_actions")
    if not isinstance(raw, list):
        return []

    su = shell_ui if isinstance(shell_ui, Mapping) else {}
    out: list[dict[str, Any]] = []

    def _label(key: str, default: str) -> str:
        raw_label = su.get(key)
        if isinstance(raw_label, str) and raw_label.strip():
            return raw_label.strip()
        return default

    for action_type in raw:
        at = str(action_type).strip()
        if not at or at == "NextPhase":
            continue
        if at == "CombatDisruptInsteadOfRetreat":
            out.append(
                {
                    "schema": 1,
                    "id": "combat_disrupt_instead",
                    "action_type": at,
                    "label": _label("disrupt_instead_label", "Disrupt instead of retreat"),
                    "title": _label(
                        "disrupt_instead_title",
                        "Take disruption on your retreating stack and waive "
                        "the mandatory retreat (when the title allows).",
                    ),
                    "payload": {},
                    "css_class": "hexengine-primary-action--disrupt",
                    "enabled": True,
                }
            )
        elif at == "CombatAdvance":
            out.append(
                {
                    "schema": 1,
                    "id": "combat_advance",
                    "action_type": at,
                    "label": _label("combat_advance_label", "Advance"),
                    "title": _label(
                        "combat_advance_title",
                        "Advance after opponent retreats (when allowed).",
                    ),
                    "payload": {},
                    "css_class": "hexengine-primary-action--advance",
                    "enabled": True,
                }
            )
        elif at == "CombatDeclineAdvance":
            out.append(
                {
                    "schema": 1,
                    "id": "combat_decline_advance",
                    "action_type": at,
                    "label": _label("combat_decline_advance_label", "Skip"),
                    "title": _label(
                        "combat_decline_advance_title",
                        "Skip the optional advance.",
                    ),
                    "payload": {},
                    "css_class": "hexengine-primary-action--decline-advance",
                    "enabled": True,
                }
            )

    return out


__all__ = [
    "CLIENT_DRAFT_ACTIONS",
    "KIND_DOCK_ARC_ADVANCE",
    "KIND_DOCK_ARC_RETREAT",
    "SEGMENT_WIRE_SCHEMA",
    "SegmentProjectorHost",
    "action_rows_from_segment",
    "default_segment_presentation_patch",
    "dock_arc_from_segment",
    "enrich_current_segment_wire",
    "project_current_segment",
    "segment_allows_action",
    "segment_denies_action_for_faction",
    "segment_blocks_routine_phase_advance",
    "segment_blocks_routine_phase_advance_for_hooks",
]
