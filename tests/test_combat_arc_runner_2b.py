"""
Phase 2b: routing combat RPCs through the generic arc runner.

These drive the engine arc-runtime bridge (`begin_combat_arc` / `drive_combat_arc_event`)
against the real hexdemo combat arc. They assert that the Attack follow-up classifies into
the right gate, that the runner accepts valid RPCs, and that it returns False on a stale
cursor, wrong owner, or undeclared arc (no legacy fallback when a combat arc is bound).
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

from games.hexdemo import combat_arc, combat_transitions
from games.hexdemo.hooks import build_hooks

from hexengine.arcs import ArcCursor, SetArcCursor, read_arc_cursor
from hexengine.authoring.patterns.combat import combat_gate_panel_actions
from hexengine.hexes.types import Hex
from hexengine.hooks.title import TitleHooks
from hexengine.server.arcs import begin_combat_arc, drive_combat_arc_event
from hexengine.state import ActionManager, GameState
from hexengine.state.game_state import UnitState
from hexengine.state.title_extension import title_bucket

HOOKS = build_hooks()


class _Host:
    """Minimal stand-in for the GameServer surface the arc runtime needs."""

    def __init__(self, state: GameState, hooks: TitleHooks = HOOKS) -> None:
        self.hooks = hooks
        self.action_manager = ActionManager(state)
        self.sent: list[tuple[str, object]] = []
        self.broadcasts = 0

    async def _send_message(self, player_id: str, message: object) -> None:
        self.sent.append((player_id, message))

    async def _broadcast_state_update(self) -> None:
        self.broadcasts += 1


def _state(
    gate: str | None = None,
    *,
    unit_faction: str = "union",
    obligations: dict | None = None,
    advance: dict | None = None,
    current: str = "union",
) -> GameState:
    unit = UnitState(
        unit_id="u1", unit_type="inf", faction=unit_faction, position=Hex(0, 0, 0)
    )
    st = GameState.create_empty()
    st = st.with_board(st.board.with_unit(unit))
    st = st.with_turn(replace(st.turn, current_faction=current))
    bucket: dict = {}
    if gate == combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT:
        bucket["disrupt_instead_offered"] = True
    if obligations is not None:
        bucket["retreat_obligations"] = obligations
    if advance is not None:
        bucket["advance"] = advance
    return st.with_title_state(bucket, title_bucket_key="hexdemo")


def _player(faction: str) -> SimpleNamespace:
    return SimpleNamespace(faction=faction)


# ---- begin_combat_arc: classify auto-advance lands on the matching gate ----


def test_begin_lands_on_retreat_or_disrupt_gate() -> None:
    host = _Host(
        _state(
            combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT,
            obligations={"u1": 1},
        )
    )
    begin_combat_arc(host)
    cur = read_arc_cursor(host.action_manager.current_state)
    assert cur is not None
    assert cur.arc_id == "combat"
    assert cur.segment_id == combat_arc.SEG_RETREAT_OR_DISRUPT_GATE


def test_begin_lands_on_retreat_gate() -> None:
    host = _Host(
        _state(combat_transitions.GATE_AWAITING_RETREAT, obligations={"u1": 1})
    )
    begin_combat_arc(host)
    cur = read_arc_cursor(host.action_manager.current_state)
    assert cur is not None
    assert cur.segment_id == combat_arc.SEG_RETREAT_GATE


def test_begin_with_no_gate_finishes_immediately() -> None:
    host = _Host(_state(None))
    begin_combat_arc(host)
    cur = read_arc_cursor(host.action_manager.current_state)
    # Phase 4: overlay arc completion restores the routine schedule cursor.
    assert cur is None or cur.arc_id != "combat"


def test_begin_is_noop_without_declared_arc() -> None:
    host = _Host(
        _state(
            combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT, obligations={"u1": 1}
        ),
        hooks=TitleHooks(),
    )
    begin_combat_arc(host)
    assert read_arc_cursor(host.action_manager.current_state) is None


# ---- drive_combat_arc_event: runner authoritative only when it accepts --------


def test_disrupt_through_runner_clears_obligation_and_cursor() -> None:
    host = _Host(
        _state(
            combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT,
            obligations={"u1": 1},
        )
    )
    begin_combat_arc(host)

    handled = asyncio.run(
        drive_combat_arc_event(
            host, "p1", _player("union"), "CombatDisruptInsteadOfRetreat"
        )
    )

    assert handled is True
    assert host.broadcasts == 1
    final = host.action_manager.current_state
    hx = title_bucket(final, "hexdemo")
    assert not hx.get("retreat_obligations")
    assert not hx.get("disrupt_instead_offered")
    assert final.board.units["u1"].attributes.get("disrupted") is True
    cur = read_arc_cursor(final)
    assert cur is None or cur.arc_id != "combat"


def test_disrupt_by_wrong_faction_rejected() -> None:
    host = _Host(
        _state(
            combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT,
            obligations={"u1": 1},
        )
    )
    begin_combat_arc(host)
    cursor_before = read_arc_cursor(host.action_manager.current_state)

    handled = asyncio.run(
        drive_combat_arc_event(
            host, "p1", _player("rebel"), "CombatDisruptInsteadOfRetreat"
        )
    )

    assert handled is False  # wrong owner -> rejected (no legacy handler)
    assert host.broadcasts == 0
    # Runner made no state change on rejection.
    assert read_arc_cursor(host.action_manager.current_state) == cursor_before
    hx = title_bucket(host.action_manager.current_state, "hexdemo")
    assert hx.get("retreat_obligations") == {"u1": 1}


def test_decline_advance_through_runner_clears_gate_and_cursor() -> None:
    host = _Host(
        _state(
            combat_transitions.GATE_AWAITING_ADVANCE,
            advance={"faction": "union"},
            current="union",
        )
    )
    # Advance gate is reached only after a retreat/disrupt step; seed the cursor there
    # directly (the realistic runtime position when the advance RPC arrives).
    host.action_manager.execute(
        SetArcCursor(ArcCursor(arc_id="combat", segment_id=combat_arc.SEG_ADVANCE_GATE))
    )

    handled = asyncio.run(
        drive_combat_arc_event(host, "p1", _player("union"), "CombatDeclineAdvance")
    )

    assert handled is True
    assert host.broadcasts == 1
    final = host.action_manager.current_state
    hx = title_bucket(final, "hexdemo")
    assert "advance" not in hx
    cur = read_arc_cursor(final)
    assert cur is None or cur.arc_id != "combat"


def test_decline_advance_by_non_current_faction_rejected() -> None:
    host = _Host(
        _state(
            combat_transitions.GATE_AWAITING_ADVANCE,
            advance={"faction": "union"},
            current="union",
        )
    )
    host.action_manager.execute(
        SetArcCursor(ArcCursor(arc_id="combat", segment_id=combat_arc.SEG_ADVANCE_GATE))
    )

    handled = asyncio.run(
        drive_combat_arc_event(host, "p1", _player("rebel"), "CombatDeclineAdvance")
    )

    assert handled is False  # owner is CURRENT (union); rebel is not the owner
    assert host.broadcasts == 0


def test_drive_rejects_without_active_cursor() -> None:
    host = _Host(
        _state(combat_transitions.GATE_AWAITING_ADVANCE, advance={"faction": "union"})
    )
    handled = asyncio.run(
        drive_combat_arc_event(host, "p1", _player("union"), "CombatDeclineAdvance")
    )
    assert (
        handled is False
    )  # no cursor set -> dispatch rejects (see test_combat_arc_dispatch)


def test_drive_not_declared_without_combat_arc() -> None:
    host = _Host(
        _state(
            combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT,
            obligations={"u1": 1},
        ),
        hooks=TitleHooks(),
    )
    handled = asyncio.run(
        drive_combat_arc_event(
            host, "p1", _player("union"), "CombatDisruptInsteadOfRetreat"
        )
    )
    assert handled is False


# ---- dock surface: the Skip row appears at awaiting_advance -------------------


def test_dock_offers_skip_at_awaiting_advance() -> None:
    segment = {
        "schema": 1,
        "arc_id": "combat",
        "segment_id": combat_arc.SEG_ADVANCE_GATE,
        "ui_mode": combat_transitions.GATE_AWAITING_ADVANCE,
        "owner": "union",
        "allowed_actions": [
            "CombatAdvance",
            "MoveUnit",
            "CombatDeclineAdvance",
        ],
        "action_locus": {},
    }
    rows = combat_gate_panel_actions(segment, {})
    types = {r.action_type for r in rows}
    assert "CombatAdvance" in types
    assert "CombatDeclineAdvance" in types
