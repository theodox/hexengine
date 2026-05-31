"""Generic arc runner: gating, suspend/resume, auto-advance, undo (composable arcs, Phase 1)."""

from __future__ import annotations

import pytest

from hexengine.arcs import (
    CURRENT,
    NO_OWNER,
    Arc,
    OwnerRef,
    RunResult,
    arc,
    begin_arc,
    case,
    read_arc_cursor,
    submit_event,
)
from hexengine.state import GameState
from hexengine.state.action_manager import ActionManager
from hexengine.state.actions import PatchTitleBucket
from hexengine.state.title_extension import title_bucket

EK = "combat_test"


# ---- title-supplied callables (effects / guards / owner resolver) ----------


def _set_flag(flag: str):
    def effect(ctx):
        return [PatchTitleBucket(ctx.extension_key, {flag: True})]

    return effect


def _flag_is_set(flag: str):
    def guard(ctx) -> bool:
        return bool(title_bucket(ctx.state, ctx.extension_key).get(flag))

    return guard


def _retreating_is_blue(key: str, state: GameState) -> str | None:
    return "Blue" if key == "retreating" else None


def _combat_arc() -> Arc:
    with arc("combat") as a:
        with a.segment("attack", owner=CURRENT, kind="routine") as s:
            s.on(
                "Attack",
                interrupt="retreat_gate",
                resume_at="advance_gate",
                effect=_set_flag("attacked"),
            )
        with a.segment(
            "retreat_gate", owner=OwnerRef("retreating"), kind="retreat_gate"
        ) as s:
            s.on("RetreatUnit", resume=True, effect=_set_flag("retreated"))
            s.on("DisruptInsteadOfRetreat", resume=True)
        with a.segment("advance_gate", owner=CURRENT, kind="advance_gate") as s:
            s.on("CombatAdvance", done=True, effect=_set_flag("advanced"))
            s.on("DeclineAdvance", done=True)
    return a.build()


def _manager() -> ActionManager:
    state = GameState.create_empty(initial_faction="Red").with_title_state(
        {}, title_bucket_key=EK
    )
    return ActionManager(state)


# ---- begin + happy-path walk ------------------------------------------------


def test_begin_arc_sets_cursor_to_entry() -> None:
    mgr = _manager()
    begin_arc(_combat_arc(), mgr, resolver=_retreating_is_blue)
    cursor = read_arc_cursor(mgr.current_state)
    assert cursor is not None
    assert (cursor.arc_id, cursor.segment_id) == ("combat", "attack")
    assert cursor.is_suspended is False


def test_full_combat_walk() -> None:
    a = _combat_arc()
    mgr = _manager()
    begin_arc(a, mgr, resolver=_retreating_is_blue)

    # Red attacks -> suspend into the defender's retreat gate.
    r1 = submit_event(a, mgr, action_type="Attack", actor="Red", resolver=_retreating_is_blue)
    assert r1.ok
    cur = read_arc_cursor(mgr.current_state)
    assert (cur.segment_id, cur.is_suspended) == ("retreat_gate", True)
    assert title_bucket(mgr.current_state, EK)["attacked"] is True

    # Blue retreats -> resume back to the attacker's advance gate.
    r2 = submit_event(
        a, mgr, action_type="RetreatUnit", actor="Blue", resolver=_retreating_is_blue
    )
    assert r2.ok
    cur = read_arc_cursor(mgr.current_state)
    assert (cur.segment_id, cur.is_suspended) == ("advance_gate", False)
    assert title_bucket(mgr.current_state, EK)["retreated"] is True

    # Red advances -> arc complete, cursor cleared.
    r3 = submit_event(
        a, mgr, action_type="CombatAdvance", actor="Red", resolver=_retreating_is_blue
    )
    assert r3.ok
    assert read_arc_cursor(mgr.current_state) is None
    assert title_bucket(mgr.current_state, EK)["advanced"] is True


# ---- legality gating --------------------------------------------------------


def test_wrong_owner_rejected() -> None:
    a = _combat_arc()
    mgr = _manager()
    begin_arc(a, mgr, resolver=_retreating_is_blue)
    res = submit_event(a, mgr, action_type="Attack", actor="Blue", resolver=_retreating_is_blue)
    assert res.ok is False
    assert "not segment owner" in res.reason
    # No state change: still at entry.
    assert read_arc_cursor(mgr.current_state).segment_id == "attack"


def test_disallowed_action_rejected() -> None:
    a = _combat_arc()
    mgr = _manager()
    begin_arc(a, mgr, resolver=_retreating_is_blue)
    res = submit_event(a, mgr, action_type="Nope", actor="Red", resolver=_retreating_is_blue)
    assert res.ok is False
    assert "not allowed" in res.reason


def test_owner_resolution_for_owner_ref() -> None:
    a = _combat_arc()
    mgr = _manager()
    begin_arc(a, mgr, resolver=_retreating_is_blue)
    submit_event(a, mgr, action_type="Attack", actor="Red", resolver=_retreating_is_blue)
    # Now at retreat_gate owned by Blue (resolved from OwnerRef("retreating")).
    red_try = submit_event(
        a, mgr, action_type="RetreatUnit", actor="Red", resolver=_retreating_is_blue
    )
    assert red_try.ok is False and "not segment owner" in red_try.reason


def test_no_active_arc_rejected() -> None:
    a = _combat_arc()
    mgr = _manager()
    res = submit_event(a, mgr, action_type="Attack", actor="Red", resolver=_retreating_is_blue)
    assert res.ok is False and res.reason == "no active arc"


# ---- automatic segments + branching ----------------------------------------


def _arc_with_auto_resolve(*, eliminate: bool) -> Arc:
    """attack -> (auto) resolve -> advance/cleanup, branching on a title flag."""

    with arc("auto_combat") as a:
        with a.segment("attack", owner=CURRENT) as s:
            s.on("Attack", goto="resolve", effect=_set_flag("attacked"))
        with a.segment("resolve", owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=_flag_is_set("eliminated"), goto="cleanup"),
                case(goto="advance"),
            )
        with a.segment("advance", owner=CURRENT) as s:
            s.on("CombatAdvance", done=True)
        with a.segment("cleanup", owner=NO_OWNER) as s:
            s.auto(done=True)
    return a.build()


def test_auto_advance_skips_ownerless_segment() -> None:
    a = _arc_with_auto_resolve(eliminate=False)
    mgr = _manager()
    begin_arc(a, mgr)
    submit_event(a, mgr, action_type="Attack", actor="Red")
    # The runner fired the automatic 'resolve' and rested on the owned 'advance'.
    assert read_arc_cursor(mgr.current_state).segment_id == "advance"


def test_auto_branch_picks_guarded_arm_and_finishes() -> None:
    a = _arc_with_auto_resolve(eliminate=True)
    mgr = _manager()
    # Pre-set the flag so the eliminated arm (auto -> cleanup -> done) is taken.
    mgr.execute(PatchTitleBucket(EK, {"eliminated": True}))
    begin_arc(a, mgr)
    submit_event(a, mgr, action_type="Attack", actor="Red")
    # resolve -> cleanup -> done, all automatic: arc cleared.
    assert read_arc_cursor(mgr.current_state) is None


# ---- guard rejection on an owned segment ------------------------------------


def test_guarded_event_with_no_passing_arm_rejected() -> None:
    with arc("g", entry="s") as bld:
        with bld.segment("s", owner=CURRENT) as s:
            s.branch("Go", case(guard=_flag_is_set("ready"), done=True))
        # 'ready' is never set, so the only arm's guard fails.
    a = bld.build()
    mgr = _manager()
    begin_arc(a, mgr)
    res = submit_event(a, mgr, action_type="Go", actor="Red")
    assert res.ok is False and "passed its guard" in res.reason
    assert read_arc_cursor(mgr.current_state).segment_id == "s"


# ---- rewind: the whole event undoes ----------------------------------------


def test_event_is_undoable() -> None:
    a = _combat_arc()
    mgr = _manager()
    begin_arc(a, mgr, resolver=_retreating_is_blue)
    before = mgr.current_state
    submit_event(a, mgr, action_type="Attack", actor="Red", resolver=_retreating_is_blue)
    assert title_bucket(mgr.current_state, EK).get("attacked") is True

    # Attack produced two actions: the effect patch and the cursor move. Undo both.
    mgr.undo()
    mgr.undo()
    assert read_arc_cursor(mgr.current_state) == read_arc_cursor(before)
    assert title_bucket(mgr.current_state, EK).get("attacked") is None
    assert read_arc_cursor(mgr.current_state).segment_id == "attack"


# ---- loud failure on a mis-declared automatic loop --------------------------


def test_automatic_self_loop_raises() -> None:
    with arc("spin", entry="loop") as bld:
        with bld.segment("loop", owner=NO_OWNER) as s:
            s.auto(goto="loop")
    a = bld.build()
    mgr = _manager()
    with pytest.raises(RuntimeError, match="automatic steps"):
        begin_arc(a, mgr)
