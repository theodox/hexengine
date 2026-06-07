"""
Hexdemo combat as a declared arc (composable arcs, Phase 2a).

Uses the engine combat cleanup pattern with hexdemo-specific guards, effects, and gate
wire strings. Segment ids and graph shape live in ``authoring.patterns.combat``; this
module binds title hooks and owner resolution.
"""

from __future__ import annotations

from hexengine.arcs import Arc, ArcContext
from hexengine.authoring.patterns.combat import (
    COMBAT_ARC_ID,
    CombatArcGateKinds,
    OWNER_RETREATING,
    SEG_ADVANCE_GATE,
    SEG_CLASSIFY,
    SEG_RESOLVE,
    SEG_RETREAT_GATE,
    SEG_RETREAT_OR_DISRUPT_GATE,
    build_combat_cleanup_arc,
)
from hexengine.state import GameState
from hexengine.state.action_manager import StateAction
from hexengine.state.title_extension import title_bucket

from . import combat, combat_actions, combat_transitions, title_state


def retreating_faction(state: GameState) -> str | None:
    """Faction that currently owns a pending retreat obligation (or None)."""

    ek = state.title_bucket_key
    if not ek:
        return None
    ro = title_bucket(state, ek).get("retreat_obligations")
    if not isinstance(ro, dict):
        return None
    for uid, raw in ro.items():
        try:
            if int(raw) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        u = state.board.units.get(str(uid))
        if u is not None and u.active:
            return str(u.faction)
    return None


def resolve_owner_ref(key: str, state: GameState) -> str | None:
    """OwnerRefResolver for the combat arc (only knows the "retreating" owner)."""

    if key == OWNER_RETREATING:
        return retreating_faction(state)
    return None


class _HexdemoCombatArcEffects:
    """Title hooks bound into the shared combat cleanup arc pattern."""

    def has_pending_retreat(self, ctx: ArcContext) -> bool:
        return combat.any_retreat_obligation_pending(ctx.state)

    def disrupt_offered(self, ctx: ArcContext) -> bool:
        if not ctx.extension_key:
            return False
        if not title_state.disrupt_instead_offered(ctx.state):
            return False
        return combat.any_retreat_obligation_pending(ctx.state)

    def advance_available(self, ctx: ArcContext) -> bool:
        if not ctx.extension_key:
            return False
        return bool(
            combat_actions.maybe_open_advance_after_retreat(ctx.state, ctx.extension_key)
        )

    def is_retreat_fulfillment(self, ctx: ArcContext) -> bool:
        uid = ctx.params.get("unit_id")
        if not isinstance(uid, str) or not ctx.extension_key:
            return False
        ro = title_bucket(ctx.state, ctx.extension_key).get("retreat_obligations")
        if not isinstance(ro, dict):
            return False
        try:
            return int(ro.get(uid, 0)) > 0
        except (TypeError, ValueError):
            return False

    def is_combat_advance_move(self, ctx: ArcContext) -> bool:
        if not ctx.extension_key or not ctx.owner_faction:
            return False
        return combat_actions.is_combat_advance_move(
            ctx.state, ctx.params, ctx.owner_faction, ctx.extension_key
        )

    def apply_retreat_step(self, ctx: ArcContext) -> list[StateAction]:
        if not ctx.extension_key or not ctx.owner_faction:
            return []
        return combat_actions.apply_retreat_fulfillment_step(
            ctx.state,
            ctx.extension_key,
            ctx.owner_faction,
            ctx.params,
        )

    def disrupt_instead(self, ctx: ArcContext) -> list[StateAction]:
        return combat_actions.disrupt_instead_of_retreat(
            ctx.state, ctx.extension_key or "", ctx.owner_faction or ""
        )

    def open_advance(self, ctx: ArcContext) -> list[StateAction]:
        return combat_actions.maybe_open_advance_after_retreat(
            ctx.state, ctx.extension_key or ""
        )

    def resolve_advance(self, ctx: ArcContext) -> list[StateAction]:
        return combat_actions.resolve_combat_advance(
            ctx.state, ctx.extension_key or "", ctx.owner_faction or ""
        )

    def clear_advance_gate(self, ctx: ArcContext) -> list[StateAction]:
        return combat_actions.clear_advance_gate(ctx.state, ctx.extension_key or "")


_HEXDEMO_COMBAT_EFFECTS = _HexdemoCombatArcEffects()

_HEXDEMO_COMBAT_GATES = CombatArcGateKinds(
    awaiting_retreat=combat_transitions.GATE_AWAITING_RETREAT,
    awaiting_retreat_or_disrupt=combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT,
    awaiting_advance=combat_transitions.GATE_AWAITING_ADVANCE,
)


def build_combat_arc() -> Arc:
    """Build the hexdemo combat-cleanup arc."""

    return build_combat_cleanup_arc(
        _HEXDEMO_COMBAT_EFFECTS,
        _HEXDEMO_COMBAT_GATES,
        arc_id=COMBAT_ARC_ID,
    )


__all__ = [
    "OWNER_RETREATING",
    "SEG_ADVANCE_GATE",
    "SEG_CLASSIFY",
    "SEG_RESOLVE",
    "SEG_RETREAT_GATE",
    "SEG_RETREAT_OR_DISRUPT_GATE",
    "build_combat_arc",
    "resolve_owner_ref",
    "retreating_faction",
]
