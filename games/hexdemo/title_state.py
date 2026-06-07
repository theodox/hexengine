"""
Hexdemo match-scoped title state in ``GameState.title_state``.

One pack id per session (`PACK_STATE_EXTENSION_KEY`). All reads of the hexdemo
bucket should go through ``bucket()`` so extension layout stays in one place.
"""

from __future__ import annotations

from typing import Any

from hexengine.state import GameState
from hexengine.state.title_extension import title_bucket as _title_bucket

from .constants import PACK_STATE_EXTENSION_KEY


def bucket(state: GameState) -> dict[str, Any]:
    """Copy of the hexdemo title bucket, or ``{}`` if absent."""

    if state.title_bucket_key == PACK_STATE_EXTENSION_KEY:
        return dict(state.title_state)
    return _title_bucket(state, PACK_STATE_EXTENSION_KEY)


def attacks_this_phase(state: GameState) -> list[str]:
    """Unit ids that have already attacked in the current combat phase."""

    raw = bucket(state).get("attacks_this_phase")
    if not isinstance(raw, list):
        return []
    return [uid for uid in raw if isinstance(uid, str)]


def last_combat(state: GameState) -> dict[str, Any] | None:
    """Latest combat result payload from the title bucket, if present."""

    raw = bucket(state).get("last_combat")
    return dict(raw) if isinstance(raw, dict) else None


def retreat_obligations(state: GameState) -> dict[str, Any]:
    """Per-unit mandatory retreat steps remaining (unit id → steps)."""

    raw = bucket(state).get("retreat_obligations")
    return dict(raw) if isinstance(raw, dict) else {}


def advance_offer(state: GameState) -> dict[str, Any] | None:
    """Optional post-retreat advance window metadata (``faction``, …)."""

    raw = bucket(state).get("advance")
    return dict(raw) if isinstance(raw, dict) else None


def disrupt_instead_offered(state: GameState) -> bool:
    """True when optional disrupt-instead-of-retreat was offered for this combat."""

    return bool(bucket(state).get("disrupt_instead_offered"))


__all__ = [
    "advance_offer",
    "attacks_this_phase",
    "bucket",
    "disrupt_instead_offered",
    "last_combat",
    "retreat_obligations",
]
