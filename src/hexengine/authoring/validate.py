"""
Load-time validation for declared arc graphs and turn registries.

Pure functions only; called from hooks.internal at server startup.
"""

from __future__ import annotations

from typing import Any

from ..arcs.registry import TurnArcRegistry
from ..arcs.runner import ArcSpec
from ..hooks.core import ENGINE_DEFAULT
from ..hooks.title import TitleHooks


def _validate_arc_spec(label: str, spec: ArcSpec, errors: list[str]) -> None:
    try:
        spec.arc.validate()
    except ValueError as exc:
        errors.append(f"{label}: {exc}")


def _validate_turn_registry(registry: TurnArcRegistry, errors: list[str]) -> None:
    slot_ids = {s.routine_arc_id for s in registry.schedule.slots}
    missing = slot_ids - set(registry.routine_specs.keys())
    if missing:
        errors.append(
            "turn_arc_registry: schedule references routine arc ids with no spec: "
            + ", ".join(sorted(missing))
        )
    extra = set(registry.routine_specs.keys()) - slot_ids
    if extra:
        errors.append(
            "turn_arc_registry: routine_specs contains ids not in schedule: "
            + ", ".join(sorted(extra))
        )
    for arc_id, spec in registry.routine_specs.items():
        _validate_arc_spec(f"routine arc {arc_id!r}", spec, errors)


def validate_arc_contract(bundle: TitleHooks) -> list[str]:
    """
    Validate declared arcs on a title hook bundle.

    Returns a list of human-readable error strings (empty when valid).
    """

    errors: list[str] = []

    reg_raw = bundle.arcs.turn_arc_registry_spec()
    if reg_raw is not ENGINE_DEFAULT:
        if not isinstance(reg_raw, TurnArcRegistry):
            errors.append(
                "turn_arc_registry hook must return TurnArcRegistry or ENGINE_DEFAULT"
            )
        else:
            _validate_turn_registry(reg_raw, errors)

    combat_raw = bundle.arcs.combat_arc_spec()
    if combat_raw is not ENGINE_DEFAULT:
        if not isinstance(combat_raw, ArcSpec):
            errors.append("combat_arc hook must return ArcSpec or ENGINE_DEFAULT")
        else:
            _validate_arc_spec("combat_arc", combat_raw, errors)

    movement_raw = bundle.arcs.movement_arc_spec()
    if movement_raw is not ENGINE_DEFAULT:
        if not isinstance(movement_raw, ArcSpec):
            errors.append("movement_arc hook must return ArcSpec or ENGINE_DEFAULT")
        else:
            _validate_arc_spec("movement_arc", movement_raw, errors)

    return errors


def validate_arc_contract_for_definition(game_definition: Any) -> list[str]:
    from ..hooks.title import read_title_hooks_from_definition

    return validate_arc_contract(read_title_hooks_from_definition(game_definition))


__all__ = [
    "validate_arc_contract",
    "validate_arc_contract_for_definition",
]
