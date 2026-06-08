"""UnitAttributesPatch + ApplyUnitAttributesPatch."""

from __future__ import annotations

from hexengine.hexes.types import Hex
from hexengine.hooks.unit import ApplyUnitAttributesPatch, UnitAttributesPatch
from hexengine.state import BoardState, GameState, UnitState
from hexengine.state.action_manager import ActionManager


def test_apply_unit_attributes_patch_undo() -> None:
    board = BoardState(
        units={
            "u1": UnitState(
                unit_id="u1",
                unit_type="inf",
                faction="union",
                position=Hex(0, 0, 0),
                active=True,
                attributes={"morale": 3, "drop": True},
            )
        }
    )
    mgr = ActionManager(GameState(board=board, turn=GameState.create_empty().turn))
    mgr.execute(
        ApplyUnitAttributesPatch(
            "u1",
            UnitAttributesPatch(values={"morale": 1}, remove_keys=("drop",)),
        )
    )
    u = mgr.current_state.board.units["u1"]
    assert u.attributes["morale"] == 1
    assert "drop" not in u.attributes
    mgr.undo()
    u2 = mgr.current_state.board.units["u1"]
    assert u2.attributes["morale"] == 3
    assert u2.attributes["drop"] is True
