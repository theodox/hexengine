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


__all__ = ["attacks_this_phase", "bucket"]
