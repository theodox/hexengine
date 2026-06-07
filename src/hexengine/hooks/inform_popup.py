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
    Context for ``INFORM_POPUP`` (all ``InspectRequest`` targets).

    ``target_kind`` is ``unit``, ``marker``, or ``inform``. For the inform lane,
    ``target_id`` is the reason id; ``inform_kind`` / ``inform_profile`` come from
    segment projection when the client omits ``inform_kind``.
    """

    state: GameState
    viewer_faction: str | None
    target_kind: str
    target_id: str
    anchor_hex: Hex | None
    shell_ui: Mapping[str, Any]
    inform_kind: str = ""
    reason: str = ""
    unit_id: str | None = None
    inform_profile: str | None = None
    segment_kind: str | None = None


def inform_profile_for_context(ctx: InformPopupContext) -> str:
    """Resolved inform profile for title popup builders."""

    profile = str(ctx.inform_profile or "").strip()
    if profile:
        return profile
    return str(ctx.inform_kind or "").strip()


def default_inform_popup_for_viewer(ctx: InformPopupContext) -> InformPopup:
    """Engine catalog default when the title does not bind ``INFORM_POPUP``."""

    target_kind = str(ctx.target_kind).strip()
    target_id = str(ctx.target_id).strip()

    if target_kind == "unit":
        u = ctx.state.board.units.get(target_id)
        if u is None:
            return inform_popup(text=f"{target_id} (missing)", kind="error", ttl_ms=1200)
        return inform_popup(text=f"{target_id} @ {u.faction}", kind="info", ttl_ms=800)

    if target_kind == "marker":
        return inform_popup(text=f"marker {target_id}", kind="info", ttl_ms=800)

    profile = inform_profile_for_context(ctx)
    reason = str(ctx.reason or target_id).strip()
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
