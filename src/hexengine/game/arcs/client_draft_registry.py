"""
Client-local SELECT draft registry keyed by ``InteractionKind``.

Draft input stays on the browser until commit. Titles declare rows in
``game_data.toml`` → ``[client_contract.select_modes]`` (``draft_active_method``,
``draft_presentation_id``).
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

_DEFAULT_DRAFT_ACTIVE_METHODS: tuple[tuple[str, str], ...] = (
    (InteractionKind.ATTACK_PLAN, "_attack_plan_draft_active"),
    (InteractionKind.RETREAT_PATH, "_retreat_path_draft_active"),
    (InteractionKind.PLACE_MARKER, "_place_marker_relocate_active"),
)


def _select_modes_for_game(game: Any):
    td_fn = getattr(game, "_client_title_data", None)
    if callable(td_fn):
        return td_fn().client_contract.select_modes
    return ()


def _draft_active_rows_for_game(game: Any) -> tuple[tuple[str, str], ...]:
    rows = _select_modes_for_game(game)
    if rows:
        manifest_rows = tuple(
            (r.kind, r.draft_active_method)
            for r in rows
            if r.draft_active_method
        )
        if manifest_rows:
            return manifest_rows
    return _DEFAULT_DRAFT_ACTIVE_METHODS


def draft_active_handlers(game: Any) -> dict[str, DraftActiveFn]:
    """Bound draft-active checks for kinds implemented on ``game``."""

    out: dict[str, DraftActiveFn] = {}
    for mode, method_name in _draft_active_rows_for_game(game):
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


def default_draft_presentation_id(
    mode: str | None,
    game: Any | None = None,
) -> str | None:
    m = str(mode or "").strip()
    if not m:
        return None
    if game is not None:
        rows = _select_modes_for_game(game)
        for row in rows:
            if row.kind == m and row.draft_presentation_id:
                return row.draft_presentation_id
    return DEFAULT_DRAFT_PRESENTATION_BY_MODE.get(m)


def resolve_draft_presentation_id(
    game: Any,
    *,
    mode: str | None,
    draft_active: bool,
) -> str | None:
    """Preview override, then segment registry, then manifest/default per kind."""

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
    return default_draft_presentation_id(mode, game)


__all__ = [
    "DEFAULT_DRAFT_PRESENTATION_BY_MODE",
    "default_draft_presentation_id",
    "draft_active_handlers",
    "is_draft_active_for_mode",
    "resolve_draft_presentation_id",
]
