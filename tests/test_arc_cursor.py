"""Runtime arc cursor: transitions, serialization, and undo/redo (composable arcs, 0b)."""

from __future__ import annotations

import pytest

from hexengine.arcs import (
    HEXENGINE_ARC_CURSOR_KEY,
    ArcCursor,
    SetArcCursor,
    SuspendedFrame,
    cursor_from_snapshot,
    cursor_to_snapshot,
    read_arc_cursor,
    with_arc_cursor,
)
from hexengine.state import GameState
from hexengine.state.action_manager import ActionManager

# ---- Pure cursor transitions ----------------------------------------------


def test_advanced_to_keeps_arc_and_clears_nothing() -> None:
    c = ArcCursor(arc_id="combat", segment_id="awaiting_retreat")
    nxt = c.advanced_to("resolve_retreat")
    assert nxt == ArcCursor(arc_id="combat", segment_id="resolve_retreat")
    assert c.segment_id == "awaiting_retreat"  # original unchanged


def test_suspend_then_resume_round_trip() -> None:
    c = ArcCursor(arc_id="combat", segment_id="awaiting_advance")
    suspended = c.suspended_into("retreat_gate", resume_segment_id="awaiting_advance")
    assert suspended.is_suspended is True
    assert suspended.segment_id == "retreat_gate"
    assert suspended.suspended == SuspendedFrame("awaiting_advance")

    resumed = suspended.resumed()
    assert resumed.is_suspended is False
    assert resumed.segment_id == "awaiting_advance"
    assert resumed.suspended is None


def test_suspend_is_depth_one() -> None:
    c = ArcCursor("a", "s").suspended_into("sub", "s")
    with pytest.raises(ValueError, match="depth-1"):
        c.suspended_into("sub2", "s")


def test_resume_without_frame_raises() -> None:
    with pytest.raises(ValueError, match="no suspended frame"):
        ArcCursor("a", "s").resumed()


# ---- Serialization ---------------------------------------------------------


def test_snapshot_round_trip_plain() -> None:
    c = ArcCursor(arc_id="combat", segment_id="awaiting_advance")
    assert cursor_from_snapshot(cursor_to_snapshot(c)) == c


def test_snapshot_round_trip_suspended() -> None:
    c = ArcCursor("combat", "retreat_gate", SuspendedFrame("awaiting_advance"))
    snap = cursor_to_snapshot(c)
    assert snap["suspended"] == {"resume_segment_id": "awaiting_advance"}
    assert cursor_from_snapshot(snap) == c


# ---- Engine-state read/write ----------------------------------------------


def test_read_returns_none_when_no_cursor() -> None:
    assert read_arc_cursor(GameState.create_empty()) is None


def test_with_arc_cursor_then_read() -> None:
    c = ArcCursor("combat", "awaiting_retreat")
    state = with_arc_cursor(GameState.create_empty(), c)
    assert read_arc_cursor(state) == c


def test_with_arc_cursor_none_removes_key() -> None:
    c = ArcCursor("combat", "awaiting_retreat")
    state = with_arc_cursor(GameState.create_empty(), c)
    cleared = with_arc_cursor(state, None)
    assert HEXENGINE_ARC_CURSOR_KEY not in cleared.engine_state
    assert read_arc_cursor(cleared) is None


# ---- Undo / redo of the cursor alone --------------------------------------


def test_set_cursor_undo_redo_from_empty() -> None:
    mgr = ActionManager(GameState.create_empty())
    c = ArcCursor("combat", "awaiting_retreat")

    mgr.execute(SetArcCursor(c))
    assert read_arc_cursor(mgr.current_state) == c

    mgr.undo()
    assert read_arc_cursor(mgr.current_state) is None
    assert HEXENGINE_ARC_CURSOR_KEY not in mgr.current_state.engine_state

    mgr.redo()
    assert read_arc_cursor(mgr.current_state) == c


def test_cursor_walk_undo_restores_each_prior_state() -> None:
    mgr = ActionManager(GameState.create_empty())

    enter = ArcCursor("combat", "awaiting_retreat")
    advance = enter.advanced_to("resolve_retreat")
    suspend = advance.advanced_to("awaiting_advance").suspended_into(
        "retreat_gate", "awaiting_advance"
    )
    resume = suspend.resumed()

    for cursor in (enter, advance, suspend, resume):
        mgr.execute(SetArcCursor(cursor))
    assert read_arc_cursor(mgr.current_state) == resume

    # Undo back through every step in reverse, checking the exact prior cursor.
    for expected in (suspend, advance, enter, None):
        mgr.undo()
        assert read_arc_cursor(mgr.current_state) == expected


def test_clear_cursor_is_undoable() -> None:
    mgr = ActionManager(GameState.create_empty())
    c = ArcCursor("combat", "awaiting_advance")
    mgr.execute(SetArcCursor(c))
    mgr.execute(SetArcCursor(None))
    assert read_arc_cursor(mgr.current_state) is None

    mgr.undo()
    assert read_arc_cursor(mgr.current_state) == c

    mgr.redo()
    assert read_arc_cursor(mgr.current_state) is None


def test_cursor_action_does_not_touch_other_engine_state() -> None:
    base = GameState.create_empty().with_engine_state({"hexengine_other": {"k": 1}})
    mgr = ActionManager(base)
    mgr.execute(SetArcCursor(ArcCursor("combat", "s")))
    assert mgr.current_state.engine_state["hexengine_other"] == {"k": 1}
    mgr.undo()
    assert mgr.current_state.engine_state["hexengine_other"] == {"k": 1}
