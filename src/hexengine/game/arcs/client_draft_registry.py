"""
Client-local SELECT draft registry keyed by ``InteractionKind``.

Draft input stays on the browser until commit; this table wires each mode to
its active check and default draft-step ``presentation_id`` when segment wire
and preview omit one.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...gamedef.interactions import InteractionKind

DraftActiveFn = Callable[[], bool]

DEFAULT_DRAFT_PRESENTATION_BY_MODE: dict[str, str] = {
    InteractionKind.ATTACK_PLAN: "attack_draft",
    InteractionKind.RETREAT_PATH: "retreat_path_draft",
    InteractionKind.PLACE_MARKER: "place_marker_draft",
}

_DRAFT_ACTIVE_METHODS: tuple[tuple[str, str], ...] = (
    (InteractionKind.ATTACK_PLAN, "_attack_plan_draft_active"),
    (InteractionKind.RETREAT_PATH, "_retreat_path_draft_active"),
    (InteractionKind.PLACE_MARKER, "_place_marker_relocate_active"),
)


def draft_active_handlers(game: Any) -> dict[str, DraftActiveFn]:
    """Bound draft-active checks for kinds implemented on ``game``."""

    out: dict[str, DraftActiveFn] = {}
    for mode, method_name in _DRAFT_ACTIVE_METHODS:
        fn = getattr(game, method_name, None)
        if callable(fn):
            out[str(mode)] = fn
    return out


def is_draft_active_for_mode(game: Any, mode: str | None) -> bool:
    m = str(mode or "").strip()
    if not m:
        return False
    fn = draft_active_handlers(game).get(m)
    if fn is None:
        return False
    try:
        return bool(fn())
    except Exception:
        return False


def default_draft_presentation_id(mode: str | None) -> str | None:
    m = str(mode or "").strip()
    if not m:
        return None
    return DEFAULT_DRAFT_PRESENTATION_BY_MODE.get(m)


def resolve_draft_presentation_id(
    game: Any,
    *,
    mode: str | None,
    draft_active: bool,
) -> str | None:
    """Preview override, then segment registry, then engine default per kind."""

    if not draft_active:
        return None
    preview_fn = getattr(game, "_preview_draft_presentation_id", None)
    if callable(preview_fn):
        pid = preview_fn()
        if pid:
            return pid
    segment_fn = getattr(game, "_segment_draft_presentation_id", None)
    if callable(segment_fn):
        pid = segment_fn()
        if pid:
            return pid
    return default_draft_presentation_id(mode)


__all__ = [
    "DEFAULT_DRAFT_PRESENTATION_BY_MODE",
    "default_draft_presentation_id",
    "draft_active_handlers",
    "is_draft_active_for_mode",
    "resolve_draft_presentation_id",
]
