"""Assemble `TitleHooks` from modules using `bind_title_hook` markers."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from enum import Enum
from types import ModuleType
from typing import Any

from .arcs import ArcHook, ArcsHooks
from .core import HookContractError
from .interaction import InteractionHook, InteractionHooks
from .modification import ModificationHook, ModificationHooks
from .title import TitleHooks
from .ui import UIHook, UIHooks

_BUNDLE_TYPES: dict[str, type[Any]] = {
    "modification": ModificationHooks,
    "interaction": InteractionHooks,
    "ui": UIHooks,
    "arcs": ArcsHooks,
}

TitleHookMarker = ModificationHook | InteractionHook | UIHook | ArcHook


def _bundle_field_from_marker(marker: TitleHookMarker) -> tuple[str, str]:
    if not isinstance(marker, Enum):
        raise HookContractError(
            message=(
                "bind_title_hook requires a hook enum member "
                "(ModificationHook, InteractionHook, UIHook, or ArcHook)"
            ),
            details={"marker": repr(marker)},
        )
    bundle = getattr(type(marker), "_hexengine_hook_bundle", None)
    if not isinstance(bundle, str) or not bundle.strip():
        msg = f"Hook enum {type(marker).__name__!r} is missing _hexengine_hook_bundle"
        raise HookContractError(message=msg, details={"marker": repr(marker)})
    field = str(marker.value)
    return bundle.strip(), field


def bind_title_hook(
    marker: TitleHookMarker,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a callable as the implementation for `TitleHooks` at a hook slot."""

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
    modification: dict[str, Callable[..., Any]] | None = None,
    interaction: dict[str, Callable[..., Any]] | None = None,
    ui: dict[str, Callable[..., Any]] | None = None,
    arcs: dict[str, Callable[..., Any]] | None = None,
) -> TitleHooks:
    """Build a `TitleHooks` bundle from decorated module callables."""

    sink: dict[str, dict[str, Callable[..., Any]]] = {
        "modification": {},
        "interaction": {},
        "ui": {},
        "arcs": {},
    }
    for mod in modules:
        _scan_module(mod, sink)
    if modification:
        for k in modification:
            _validate_bundle_field("modification", k)
        sink["modification"].update(modification)
    if interaction:
        for k in interaction:
            _validate_bundle_field("interaction", k)
        sink["interaction"].update(interaction)
    if ui:
        for k in ui:
            _validate_bundle_field("ui", k)
        sink["ui"].update(ui)
    if arcs:
        for k in arcs:
            _validate_bundle_field("arcs", k)
        sink["arcs"].update(arcs)
    return TitleHooks(
        modification=ModificationHooks(**sink["modification"]),
        interaction=InteractionHooks(**sink["interaction"]),
        ui=UIHooks(**sink["ui"]),
        arcs=ArcsHooks(**sink["arcs"]),
    )


__all__ = ["assemble_title_hooks", "bind_title_hook"]
