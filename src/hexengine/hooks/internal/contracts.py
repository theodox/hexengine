"""
Engine-only `@hook` decorator and `validate_title_contract`.

Catalog registration lives in `hooks.internal.catalog`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..core import ENGINE_DEFAULT, SINGLE_DEFAULT, HookContractError
from ..preset_options import PresetOptions
from ..title import read_title_hooks_from_definition


def hook(
    *,
    contract: object = SINGLE_DEFAULT,
    engine_impl: Callable[..., Any] | None = None,
    presets: PresetOptions | None = None,
    preset_attr: str | None = None,
    title_field: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach contract metadata to a function. Does not change call behavior.

    Args:
        contract: One of `REQUIRED`, `PRESET`, or `SINGLE_DEFAULT`.
        engine_impl: For `SINGLE_DEFAULT`, the single engine implementation.
        presets: For `PRESET`, a `PresetOptions` bundle.
        preset_attr: `GameDefinition` attribute name whose value picks a preset key.
        title_field: Optional `bundle.field` path for `assemble_title_hooks`.

    Returns:
        Decorator that sets `__hexengine_*__` attributes on the wrapped callable.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__hexengine_hook_contract__ = contract
        if engine_impl is not None:
            fn.__hexengine_engine_impl__ = engine_impl
        if presets is not None:
            fn.__hexengine_presets__ = presets
        if preset_attr is not None:
            fn.__hexengine_preset_attr__ = preset_attr
        if title_field is not None:
            existing = getattr(fn, "__hexengine_title_field__", None)
            if existing is not None and existing != title_field:
                msg = f"{fn!r} already bound to title hook {existing!r}"
                raise ValueError(msg)
            fn.__hexengine_title_field__ = title_field
        return fn

    return decorator


def _phase_implies_attack_schedule(phase: str) -> bool:
    p = str(phase).strip().lower()
    if p in ("attack", "combat"):
        return True
    return "attack" in p or "combat" in p


def _schedule_expects_attack_hooks(game_definition: Any) -> bool:
    try:
        order = game_definition.turn_order()
    except Exception:
        return False
    for slot in order:
        if not isinstance(slot, dict):
            continue
        if _phase_implies_attack_schedule(str(slot.get("phase", ""))):
            return True
    return False


def _title_requires_turn_action_dock(game_definition: Any) -> bool:
    """Title packs with combat extension state must bind the turn action dock."""
    gd = getattr(game_definition, "game_data", None)
    if gd is None:
        return False
    key = getattr(gd, "title_state_extension_key", None)
    return bool(str(key or "").strip())


def validate_title_contract(game_definition: Any) -> None:
    """Validate title hook contracts against the game definition.

    When `turn_order()` includes a combat-oriented phase name (`Attack`, `Combat`,
    or strings containing `attack` / `combat`), `TitleHooks.attack` must provide
    `validate_attack` and `resolve_attack` callables. Implementations may return
    `ENGINE_DEFAULT` from those callables to decline attacks at action time.

    When `GameData.title_state_extension_key` is set (title combat extension bucket),
    `TitleHooks.ui.turn_action_dock_for_viewer` and
    `TitleHooks.ui.segment_presentation_registry` must be bound. Commit UI is delivered
    only via ``interaction_panels`` (turn action dock).

    Raises:
        HookContractError: When an attack-capable schedule has incomplete attack hooks.
    """

    bundle = read_title_hooks_from_definition(game_definition)
    if _title_requires_turn_action_dock(game_definition):
        if bundle.ui.turn_action_dock_for_viewer is None:
            raise HookContractError(
                message=(
                    "title_state_extension_key is set but "
                    "TitleHooks.ui.turn_action_dock_for_viewer is not bound. "
                    "Wire UIHook.TURN_ACTION_DOCK_FOR_VIEWER in the title hooks package."
                ),
                details={"requires_turn_action_dock": True},
            )
        from ...arcs.registry import TurnArcRegistry

        reg_raw = bundle.arcs.turn_arc_registry_spec()
        if not isinstance(reg_raw, TurnArcRegistry):
            raise HookContractError(
                message=(
                    "title_state_extension_key requires ArcHook.TURN_ARC_REGISTRY "
                    "returning a TurnArcRegistry."
                ),
                details={"requires_turn_arc_registry": True},
            )
        if bundle.ui.segment_presentation_registry is None:
            raise HookContractError(
                message=(
                    "title_state_extension_key is set but "
                    "TitleHooks.ui.segment_presentation_registry is not bound. "
                    "Wire UIHook.SEGMENT_PRESENTATION_REGISTRY (hexdemo: segment_ui.py)."
                ),
                details={"requires_segment_presentation_registry": True},
            )
        if bundle.ui.enrich_current_segment is None:
            raise HookContractError(
                message=(
                    "title_state_extension_key is set but "
                    "TitleHooks.ui.enrich_current_segment is not bound. "
                    "Wire UIHook.ENRICH_CURRENT_SEGMENT (hexdemo: segment_presentation.py)."
                ),
                details={"requires_enrich_current_segment": True},
            )
        from ...arcs import ArcSpec

        combat_raw = bundle.arcs.combat_arc_spec()
        if not isinstance(combat_raw, ArcSpec):
            raise HookContractError(
                message=(
                    "title_state_extension_key requires ArcHook.COMBAT_ARC "
                    "returning an ArcSpec."
                ),
                details={"requires_combat_arc": True},
            )
    if _schedule_expects_attack_hooks(game_definition):
        a = bundle.attack
        if a.validate_attack is None or a.resolve_attack is None:
            raise HookContractError(
                message=(
                    "Turn schedule includes a combat/attack phase but TitleHooks.attack is "
                    "missing validate_attack and/or resolve_attack. Provide callables (they may "
                    "return ENGINE_DEFAULT if attacks are not supported)."
                ),
                details={"schedule_requires_attack_hooks": True},
            )

    if _title_requires_turn_action_dock(
        game_definition
    ) and _schedule_expects_attack_hooks(game_definition):
        binding_raw = bundle.arcs.combat_rules_binding_spec()
        if binding_raw is not ENGINE_DEFAULT:
            from ...authoring.patterns.combat import (
                combat_rules_binding_missing_methods,
            )

            missing = combat_rules_binding_missing_methods(binding_raw)
            if missing:
                raise HookContractError(
                    message=(
                        "ArcHook.COMBAT_RULES_BINDING is set but the binding is missing "
                        f"methods: {', '.join(missing)}"
                    ),
                    details={"combat_rules_binding_missing": list(missing)},
                )

    from .authoring_bridge import validate_declared_arcs

    arc_errors = validate_declared_arcs(game_definition)
    if arc_errors:
        raise HookContractError(
            message="Declared arc contract validation failed: " + "; ".join(arc_errors),
            details={"arc_contract_errors": arc_errors},
        )


__all__ = ["hook", "validate_title_contract"]
