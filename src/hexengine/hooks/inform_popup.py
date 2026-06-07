"""INFORM lane: map-anchored callout popups (``ui_popup`` wire)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..hexes.types import Hex
from ..state import GameState
from ..ui.display import InformPopup, inform_popup


@dataclass(frozen=True, slots=True)
class InformPopupContext:
    """
    Context for title ``inform_popup`` hook (client ``inspect`` with ``target_kind=inform``).

    ``reason`` is an opaque id (e.g. ``no_enemy_on_hex``). ``inform_kind`` is the resolved
    lane id (client override or ``current_segment`` profile). ``inform_profile`` and
    ``segment_kind`` come from segment projection when the client omits ``inform_kind``.
    """

    state: GameState
    viewer_faction: str | None
    inform_kind: str
    reason: str
    anchor_hex: Hex | None
    unit_id: str | None
    shell_ui: Mapping[str, Any]
    inform_profile: str | None = None
    segment_kind: str | None = None


def _inform_profile_key(ctx: InformPopupContext) -> str:
    profile = str(ctx.inform_profile or "").strip()
    if profile:
        return profile
    return str(ctx.inform_kind or "").strip()


def default_inform_popup_for_viewer(ctx: InformPopupContext) -> InformPopup:
    """Minimal engine default when the title does not bind ``inform_popup``."""

    profile = _inform_profile_key(ctx)
    reason = str(ctx.reason or "").strip()
    su = ctx.shell_ui if isinstance(ctx.shell_ui, Mapping) else {}
    keys = []
    if profile:
        keys.append(f"{profile}_{reason}".replace(".", "_").strip("_"))
    if ctx.segment_kind:
        keys.append(f"{ctx.segment_kind}_{reason}".replace(".", "_").strip("_"))
    text = ""
    for key in keys:
        raw = su.get(key)
        if isinstance(raw, str) and raw.strip():
            text = raw.strip()
            break
    if not text:
        label = profile or str(ctx.inform_kind or "inform").strip() or "inform"
        text = f"{label}: {reason.replace('_', ' ')}."
    return inform_popup(text=text, kind="info", ttl_ms=1500)


__all__ = [
    "InformPopupContext",
    "default_inform_popup_for_viewer",
    "inform_profile_for_context",
]


def inform_profile_for_context(ctx: InformPopupContext) -> str:
    """Resolved inform profile for title popup builders."""

    return _inform_profile_key(ctx)
