from __future__ import annotations

from hexengine.hexes.types import Hex
from hexengine.state import GameState
from hexengine.state.actions import AddUnit, Attack


def test_attack_can_destroy_multiple_defenders_on_one_hex() -> None:
    st = GameState.create_empty(initial_faction="union", initial_phase="Combat")
    h_att = Hex(0, 0, 0)
    h_def = Hex(2, -1, -1)

    st = AddUnit("att", "inf", "union", h_att).apply(st)
    st = AddUnit("d1", "inf", "confederate", h_def).apply(st)
    st = AddUnit("d2", "inf", "confederate", h_def).apply(st)

    st = st.with_extension({"hexdemo": {}})

    atk = Attack(
        "combined",
        "att",
        "d1",
        extension_key="hexdemo",
        outcome="defender_destroyed",
        attacker_ids=("att",),
        defender_ids=("d1", "d2"),
        rng_entry={"op": "test"},
    )

    st2 = atk.apply(st)
    assert st2.board.units["d1"].active is False
    assert st2.board.units["d2"].active is False

    hx = st2.extension.get("hexdemo")
    assert isinstance(hx, dict)
    lc = hx.get("last_combat")
    assert isinstance(lc, dict)
    assert lc.get("defender_ids") == ["d1", "d2"]
    assert lc.get("defender_hexes") == [{"i": h_def.i, "j": h_def.j, "k": h_def.k}]
    assert lc.get("attacker_hexes") == [{"i": h_att.i, "j": h_att.j, "k": h_att.k}]

