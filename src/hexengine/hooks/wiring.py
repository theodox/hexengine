"""Assemble `TitleHooks` from modules using `bind_title_hook` markers."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from enum import Enum
from types import ModuleType
from typing import Any

from .arcs import ArcHook, ArcsHooks
from .attack import AttackHook, AttackHooks
from .core import HookContractError
from .movement import MovementHook, MovementHooks
from .title import TitleHooks
from .ui import UIHook, UIHooks

_BUNDLE_TYPES: dict[str, type[Any]] = {
    "movement": MovementHooks,
    "attack": AttackHooks,
    "ui": UIHooks,
    "arcs": ArcsHooks,
}

TitleHookMarker = str | MovementHook | AttackHook | UIHook | ArcHook


def _bundle_field_from_marker(marker: TitleHookMarker) -> tuple[str, str]:
    if isinstance(marker, Enum):
        bundle = getattr(type(marker), "_hexengine_hook_bundle", None)
        if not isinstance(bundle, str) or not bundle.strip():
            msg = (
                f"Hook enum {type(marker).__name__!r} is missing _hexengine_hook_bundle"
            )
            raise HookContractError(message=msg, details={"marker": repr(marker)})
        field = str(marker.value)
        return bundle.strip(), field
    return _parse_title_path(str(marker))


def bind_title_hook(
    marker: TitleHookMarker,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a callable as the implementation for `TitleHooks` at a hook slot.

    Prefer passing a **StrEnum** member from the matching hooks module:

    - `hexengine.hooks.movement.MovementHook` — values align with `MovementHooks` fields
    - `hexengine.hooks.attack.AttackHook` — `AttackHooks` fields
    - `hexengine.hooks.ui.UIHook` — `UIHooks` fields

    Legacy **string** paths `\"bundle.field\"` (e.g. `\"movement.validate_move\"`) are
    still accepted for compatibility.

    Use `assemble_title_hooks` to collect decorated functions from one or more
    modules into a frozen `TitleHooks` instance.

    Raises:
        ValueError: If `fn` is already bound to another path.
        HookContractError: If a string path is malformed or an enum is misconfigured.
    """

    bundle, field = _bundle_field_from_marker(marker)
    _validate_bundle_field(bundle, field)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        existing = getattr(fn, "__hexengine_title_field__", None)
        if existing is not None:
            msg = f"{fn!r} is already bound to title hook {existing!r}"
            raise ValueError(msg)
        fn.__hexengine_title_field__ = marker
        return fn

    return decorator


def _parse_title_path(path: str) -> tuple[str, str]:
    parts = path.split(".", 1)
    if (
        len(parts) != 2
        or not parts[0].strip()
        or not parts[1].strip()
        or "." in parts[1]
    ):
        raise HookContractError(
            message=f"Invalid title hook path {path!r} (expected 'bundle.field')",
            details={"path": path},
        )
    return parts[0].strip(), parts[1].strip()


def _validate_bundle_field(bundle: str, field: str) -> None:
    cls = _BUNDLE_TYPES.get(bundle)
    if cls is None:
        raise HookContractError(
            message=f"Unknown hook bundle {bundle!r}",
            details={"bundle": bundle},
        )
    valid = {f.name for f in dataclasses.fields(cls)}
    if field not in valid:
        raise HookContractError(
            message=f"Unknown field {field!r} on {bundle} hooks",
            details={"bundle": bundle, "field": field, "valid": sorted(valid)},
        )


def _scan_module(
    mod: ModuleType, sink: dict[str, dict[str, Callable[..., Any]]]
) -> None:
    for name in dir(mod):
        if name.startswith("_"):
            continue
        obj = getattr(mod, name, None)
        if obj is None or not callable(obj):
            continue
        marker = getattr(obj, "__hexengine_title_field__", None)
        if not marker:
            continue
        bundle, field = _bundle_field_from_marker(marker)
        _validate_bundle_field(bundle, field)
        if field in sink[bundle]:
            prev = sink[bundle][field]
            p1 = getattr(prev, "__name__", repr(prev))
            p2 = getattr(obj, "__name__", repr(obj))
            raise HookContractError(
                message=f"Duplicate title hook for {bundle}.{field}: {p2} and {p1}",
                details={"bundle": bundle, "field": field},
            )
        sink[bundle][field] = obj


def assemble_title_hooks(
    *modules: ModuleType,
    movement: dict[str, Callable[..., Any]] | None = None,
    attack: dict[str, Callable[..., Any]] | None = None,
    ui: dict[str, Callable[..., Any]] | None = None,
    arcs: dict[str, Callable[..., Any]] | None = None,
) -> TitleHooks:
    """Build a `TitleHooks` bundle from decorated module callables.

    Scans each module's public attributes for callables marked with
    `__hexengine_title_field__` (via `bind_title_hook` with a hook enum or legacy
    string path, or `@hook(title_field=…)`).

    Optional `movement`, `attack`, and `ui` keyword arguments are merged on top
    (same keys as `MovementHooks` / `AttackHooks` / `UIHooks`
    fields), overwriting discovered callables — useful for small lambdas that are not
    worth a separate module-level function.

    Raises:
        HookContractError: On invalid paths, unknown fields, or duplicate bindings.
    """

    sink: dict[str, dict[str, Callable[..., Any]]] = {
        "movement": {},
        "attack": {},
        "ui": {},
        "arcs": {},
    }
    for mod in modules:
        _scan_module(mod, sink)
    if movement:
        for k in movement:
            _validate_bundle_field("movement", k)
        sink["movement"].update(movement)
    if attack:
        for k in attack:
            _validate_bundle_field("attack", k)
        sink["attack"].update(attack)
    if ui:
        for k in ui:
            _validate_bundle_field("ui", k)
        sink["ui"].update(ui)
    if arcs:
        for k in arcs:
            _validate_bundle_field("arcs", k)
        sink["arcs"].update(arcs)
    return TitleHooks(
        movement=MovementHooks(**sink["movement"]),
        attack=AttackHooks(**sink["attack"]),
        ui=UIHooks(**sink["ui"]),
        arcs=ArcsHooks(**sink["arcs"]),
    )


__all__ = ["assemble_title_hooks", "bind_title_hook"]
