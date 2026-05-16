"""
Engine-only `@hook` decorator and `validate_title_contract`.

Catalog registration lives in `hooks.internal.catalog`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..core import SINGLE_DEFAULT, HookContractError
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


def validate_title_contract(game_definition: Any) -> None:
    """Validate title hook contracts against the game definition.

    When `turn_order()` includes a combat-oriented phase name (`Attack`, `Combat`,
    or strings containing `attack` / `combat`), `TitleHooks.attack` must provide
    `validate_attack` and `resolve_attack` callables. Implementations may return
    `ENGINE_DEFAULT` from those callables to decline attacks at action time.

    Raises:
        HookContractError: When an attack-capable schedule has incomplete attack hooks.
    """

    bundle = read_title_hooks_from_definition(game_definition)
    if not _schedule_expects_attack_hooks(game_definition):
        return
    a = bundle.attack
    if a.validate_attack is not None and a.resolve_attack is not None:
        return
    raise HookContractError(
        message=(
            "Turn schedule includes a combat/attack phase but TitleHooks.attack is "
            "missing validate_attack and/or resolve_attack. Provide callables (they may "
            "return ENGINE_DEFAULT if attacks are not supported)."
        ),
        details={"schedule_requires_attack_hooks": True},
    )


__all__ = ["hook", "validate_title_contract"]
