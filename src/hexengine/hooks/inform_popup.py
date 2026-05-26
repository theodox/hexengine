"""INFORM lane: map-anchored callout popups (``ui_popup`` wire)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..hexes.types import Hex
from ..state import GameState
from .core import ENGINE_DEFAULT


@dataclass(frozen=True, slots=True)
class InformPopupContext:
    """
    Context for title ``inform_popup`` hook (client ``inspect`` with ``target_kind=inform``).

    ``reason`` is an opaque id (e.g. ``no_enemy_on_hex``); ``inform_kind`` groups flows
    (e.g. ``attack_plan``). Titles map to ``shell_ui`` copy.
    """

    state: GameState
    viewer_faction: str | None
    inform_kind: str
    reason: str
    anchor_hex: Hex | None
    unit_id: str | None
    shell_ui: Mapping[str, Any]


def default_inform_popup_for_viewer(ctx: InformPopupContext) -> dict[str, Any]:
    """Minimal engine default when the title does not bind ``inform_popup``."""

    key = f"{ctx.inform_kind}_{ctx.reason}".replace(".", "_").strip("_")
    su = ctx.shell_ui if isinstance(ctx.shell_ui, Mapping) else {}
    raw = su.get(key) if isinstance(su, Mapping) else None
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
    else:
        text = f"{ctx.inform_kind}: {ctx.reason}".replace("_", " ")
    return {"text": text, "kind": "info", "ttl_ms": 1500}


__all__ = [
    "InformPopupContext",
    "default_inform_popup_for_viewer",
]
