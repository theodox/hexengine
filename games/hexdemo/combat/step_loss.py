"""
Hexdemo combat step-loss policy (infantry two-step cadence, optional steps table).

CRT resolution builds abstract step_losses rows; expand_step_losses turns them into
generic unit_ops for engine ApplyCombatEffects.
"""

from __future__ import annotations

from typing import Any

from hexengine.hooks.unit import ApplyUnitAttributesPatch, UnitAttributesPatch
from hexengine.state import GameState
from hexengine.state.actions import DeleteUnit


def _unit_type_is_infantry(unit) -> bool:
    return str(unit.unit_type).strip().lower() == "infantry"


def _int_attr(attrs: dict[str, Any], key: str, default: int = 0) -> int:
    raw = attrs.get(key, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _graphics_template_key_for_step(
    attrs: dict[str, Any], *, step_index: int
) -> str | None:
    raw = attrs.get("steps")
    if not isinstance(raw, list) or step_index < 0 or step_index >= len(raw):
        return None
    row = raw[step_index]
    if not isinstance(row, dict):
        return None
    g = row.get("graphics")
    if isinstance(g, str):
        s = g.strip()
        if s:
            return s
    return None


def _step1_patch_from_explicit_steps(attrs: dict[str, Any]) -> dict[str, Any] | None:
    raw = attrs.get("steps")
    if not isinstance(raw, list) or len(raw) < 2:
        return None
    step1 = raw[1]
    if not isinstance(step1, dict):
        return None
    patch: dict[str, Any] = {}
    if "combat" in step1:
        try:
            patch["combat"] = max(0, int(step1["combat"]))
        except (TypeError, ValueError):
            pass
    if "morale" in step1:
        try:
            patch["morale"] = max(0, int(step1["morale"]))
        except (TypeError, ValueError):
            pass
    return patch or None


def _step_loss_row_unit_ops(state: GameState, unit_id: str) -> tuple[GameState, list[dict[str, Any]]]:
    """One step-loss application as ordered unit_ops plus updated state."""

    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return state, []

    raw = unit.attributes.get("steps_lost", 0)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 0

    if n <= 0:
        patch: dict[str, Any] = {"steps_lost": 1}
        if _unit_type_is_infantry(unit):
            explicit = _step1_patch_from_explicit_steps(unit.attributes)
            if explicit is not None:
                patch.update(explicit)
            else:
                c = _int_attr(unit.attributes, "combat", 0)
                m = _int_attr(unit.attributes, "morale", 0)
                patch["combat"] = max(0, c - 1)
                patch["morale"] = max(0, m - 1)
        ops: list[dict[str, Any]] = [
            {"op": "patch", "unit_id": unit_id, "values": patch},
        ]
        st = ApplyUnitAttributesPatch(
            unit_id, UnitAttributesPatch(values=patch)
        ).apply(state)
        u2 = st.board.units.get(unit_id)
        if u2 is not None and u2.active:
            gkey = _graphics_template_key_for_step(u2.attributes, step_index=1)
            if gkey is not None and gkey != u2.graphics:
                ops.append({"op": "graphics", "unit_id": unit_id, "graphics": gkey})
                st = st.with_board(st.board.with_unit(u2.with_graphics(gkey)))
        return st, ops

    st = DeleteUnit(unit_id).apply(state)
    return st, [{"op": "deactivate", "unit_id": unit_id}]


def expand_step_losses(
    state: GameState, step_rows: list[dict[str, object]]
) -> dict[str, Any]:
    """Expand CRT step_losses rows into ApplyCombatEffects unit_ops."""

    st = state
    unit_ops: list[dict[str, Any]] = []
    for row in step_rows:
        if not isinstance(row, dict):
            continue
        uid = str(row.get("unit_id", "")).strip()
        if not uid:
            continue
        try:
            count = int(row.get("count", 1))
        except (TypeError, ValueError):
            count = 1
        for _ in range(max(count, 1)):
            st, ops = _step_loss_row_unit_ops(st, uid)
            unit_ops.extend(ops)
            if any(op.get("op") == "deactivate" and op.get("unit_id") == uid for op in ops):
                break
    if not unit_ops:
        return {}
    return {"unit_ops": unit_ops}


__all__ = [
    "expand_step_losses",
]
