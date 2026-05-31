"""
Hexdemo combat as a declared arc (composable arcs, Phase 2a).

This declares the post-`Attack` combat-cleanup FSM as data, using the engine arc builder.
It is the title-owned source of truth that the generic runner will drive in 2b+. The
existing gate FSM in `combat_transitions` + `combat_actions` is the reference; segment
`kind` values are the matching `combat_gate` strings so the two can be parity-checked.

Phase 2a declared and validated the arc; Phase 2b+ routes combat RPCs through the generic
runner. The retreat-step effect is live in 2c.
"""

from __future__ import annotations

from hexengine.arcs import (
    CURRENT,
    NO_OWNER,
    Arc,
    ArcContext,
    OwnerRef,
    arc,
    case,
)
from hexengine.state import GameState
from hexengine.state.action_manager import StateAction
from hexengine.state.title_extension import title_bucket

from . import combat, combat_actions, combat_transitions

# Segment ids (engine cursor values). The gate-bearing segments carry their matching
# `combat_gate` string as `kind` (used for parity with the gate FSM and, later, the dock).
SEG_CLASSIFY = "classify"
SEG_RETREAT_GATE = "retreat_gate"
SEG_RETREAT_OR_DISRUPT_GATE = "retreat_or_disrupt_gate"
SEG_RESOLVE = "resolve"
SEG_ADVANCE_GATE = "advance_gate"

# Title key for the runner's OwnerRef("retreating") resolution.
OWNER_RETREATING = "retreating"


# ---- owner resolution ------------------------------------------------------


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


# ---- guards (pure predicates over ArcContext) ------------------------------


def has_pending_retreat(ctx: ArcContext) -> bool:
    return combat.any_retreat_obligation_pending(ctx.state)


def disrupt_offered(ctx: ArcContext) -> bool:
    return (
        combat_transitions.current_combat_gate(ctx.state)
        == combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT
    )


def advance_available(ctx: ArcContext) -> bool:
    if not ctx.extension_key:
        return False
    return bool(
        combat_actions.maybe_open_advance_after_retreat(ctx.state, ctx.extension_key)
    )


def is_retreat_fulfillment(ctx: ArcContext) -> bool:
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


def is_combat_advance_move(ctx: ArcContext) -> bool:
    if not ctx.extension_key or not ctx.owner_faction:
        return False
    return combat_actions.is_combat_advance_move(
        ctx.state, ctx.params, ctx.owner_faction, ctx.extension_key
    )


# ---- effects (return undoable StateAction lists) ---------------------------


def apply_retreat_step(ctx: ArcContext) -> list[StateAction]:
    """Stacked-retreat move + per-unit obligation clear (Phase 2c)."""

    if not ctx.extension_key or not ctx.owner_faction:
        return []
    return combat_actions.apply_retreat_fulfillment_step(
        ctx.state,
        ctx.extension_key,
        ctx.owner_faction,
        ctx.params,
    )


def disrupt_instead(ctx: ArcContext) -> list[StateAction]:
    return combat_actions.disrupt_instead_of_retreat(
        ctx.state, ctx.extension_key or "", ctx.owner_faction or ""
    )


def open_advance(ctx: ArcContext) -> list[StateAction]:
    return combat_actions.maybe_open_advance_after_retreat(
        ctx.state, ctx.extension_key or ""
    )


def resolve_advance(ctx: ArcContext) -> list[StateAction]:
    return combat_actions.resolve_combat_advance(
        ctx.state, ctx.extension_key or "", ctx.owner_faction or ""
    )


def clear_advance_gate(ctx: ArcContext) -> list[StateAction]:
    return combat_actions.clear_advance_gate(ctx.state, ctx.extension_key or "")


# ---- the declared arc ------------------------------------------------------


def build_combat_arc() -> Arc:
    """Build the hexdemo combat-cleanup arc (Approach A: goto-cycling via `resolve`)."""

    with arc("combat", entry=SEG_CLASSIFY) as a:
        # Entry: pick the gate matching the gate the Attack follow-up just set.
        with a.segment(SEG_CLASSIFY, owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=disrupt_offered, goto=SEG_RETREAT_OR_DISRUPT_GATE),
                case(guard=has_pending_retreat, goto=SEG_RETREAT_GATE),
                case(done=True),  # no retreat outcome -> arc ends immediately
            )

        with a.segment(
            SEG_RETREAT_GATE,
            owner=OwnerRef(OWNER_RETREATING),
            kind=combat_transitions.GATE_AWAITING_RETREAT,
        ) as s:
            s.on(
                "MoveUnit",
                guard=is_retreat_fulfillment,
                effect=apply_retreat_step,
                goto=SEG_RESOLVE,
            )

        with a.segment(
            SEG_RETREAT_OR_DISRUPT_GATE,
            owner=OwnerRef(OWNER_RETREATING),
            kind=combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT,
        ) as s:
            s.on(
                "MoveUnit",
                guard=is_retreat_fulfillment,
                effect=apply_retreat_step,
                goto=SEG_RESOLVE,
            )
            s.on(
                "CombatDisruptInsteadOfRetreat",
                effect=disrupt_instead,
                goto=SEG_RESOLVE,
            )

        # Auto re-classify after each retreat/disrupt step (Approach A loop).
        with a.segment(SEG_RESOLVE, owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=has_pending_retreat, goto=SEG_RETREAT_GATE),
                case(guard=advance_available, effect=open_advance, goto=SEG_ADVANCE_GATE),
                case(done=True),
            )

        with a.segment(
            SEG_ADVANCE_GATE,
            owner=CURRENT,
            kind=combat_transitions.GATE_AWAITING_ADVANCE,
        ) as s:
            s.on("CombatAdvance", effect=resolve_advance, done=True)
            s.on(
                "MoveUnit",
                guard=is_combat_advance_move,
                effect=resolve_advance,
                done=True,
            )
            s.on("CombatDeclineAdvance", effect=clear_advance_gate, done=True)

    return a.build()


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
