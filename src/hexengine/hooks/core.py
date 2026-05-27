"""
Core hook helpers and shared types.

These utilities support the engine ↔ title boundary during turn resolution:

A `Hook` is an engine customiztion point that titles can use or override. Hooks
are marked with a `@hook` decorator that records contract metadata.

- The authoritative server resolves a client action by consulting a `TitleHooks` bundle.
- Hooks are expected to be pure with respect to match state: return data, or raise a
  `RuleViolation`/`ValueError` to reject an action.
- Returning `ENGINE_DEFAULT` means "use engine default behavior for this hook point".
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints

ENGINE_DEFAULT: object = object()

# Bind-time contract modes (distinct from runtime return sentinel `ENGINE_DEFAULT`).
REQUIRED: object = object()
PRESET: object = object()
SINGLE_DEFAULT: object = object()


@dataclass(frozen=True, slots=True)
class HookContractError(Exception):
    """Hook registration or title binding violated an expected contract."""

    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message or "Hook contract error"


@dataclass(frozen=True, slots=True)
class RuleViolation(Exception):
    """Title rule rejection (safe to surface to the user)."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message or self.code


def implements_hook(
    hook_id: str,
    *,
    ctx_type: type[Any] | None = None,
    return_type: type[Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to declare "this function implements hook X".

    This is a lightweight import-time check. It does not require a type checker,
    but it will fail fast for obvious signature mistakes.

    Note: the decorated target may be a plain function, a method, or a callable
    object instance. For callable objects we validate against `obj.__call__`.
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        try:
            fn.__hexengine_hook_id__ = str(hook_id)
        except (AttributeError, TypeError):
            # Some callable objects may be slot-only or otherwise disallow new attrs.
            pass

        # Support validating callable object instances by inspecting `__call__`.
        # We still tag the object itself with the hook id.
        target: Callable[..., Any]
        if inspect.isfunction(fn) or inspect.ismethod(fn):
            target = fn
        else:
            if not callable(fn):
                raise TypeError(f"{hook_id}: decorated object is not callable")
            target = fn.__call__

        if ctx_type is not None:
            sig = inspect.signature(target)
            params = list(sig.parameters.values())
            if not params:
                raise TypeError(
                    f"{hook_id}: hook function must accept a context argument"
                )
            # Allow methods (`self, ctx`) and plain functions (`ctx`).
            ctx_param = params[-1]
            hints = get_type_hints(target)
            ann = hints.get(ctx_param.name)
            if ann is not None and ann is not ctx_type:
                raise TypeError(
                    f"{hook_id}: context param {ctx_param.name!r} annotated as {ann!r}, "
                    f"expected {ctx_type!r}"
                )

        if return_type is not None:
            hints = get_type_hints(target)
            ann = hints.get("return")
            if ann is None:
                raise TypeError(
                    f"{hook_id}: hook function must annotate its return type"
                )
            # We accept `ENGINE_DEFAULT` at runtime; annotation should still be the data type.
            if ann is not return_type:
                raise TypeError(
                    f"{hook_id}: return annotated as {ann!r}, expected {return_type!r}"
                )

        return fn

    return deco


__all__ = [
    "ENGINE_DEFAULT",
    "REQUIRED",
    "PRESET",
    "SINGLE_DEFAULT",
    "HookContractError",
    "RuleViolation",
    "implements_hook",
]
