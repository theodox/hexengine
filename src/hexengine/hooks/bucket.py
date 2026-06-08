"""
Author-facing session-state bucket patches.

Build ``BucketPatch`` values and apply them with ``ApplyBucketPatch`` (or return
``CombatOutcome`` from attack hooks). Engine read/write uses
``hexengine.state.engine_session_state``.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..state import GameState
from ..state.action_manager import StateAction
from ..state.actions import ApplyBucketPatch
from ..state.engine_session_state import BucketPatch, engine_read_session_state

__all__ = [
    "ApplyBucketPatch",
    "BucketPatch",
    "clear_session_bucket",
]


def clear_session_bucket(
    state: GameState,
    remove_keys: Sequence[str],
    *,
    session_state_key: str | None = None,
) -> list[StateAction]:
    """
    Return actions that drop ``remove_keys`` from the pack session-state bucket.

    Uses ``state.session_state_key`` when ``session_state_key`` is omitted. Returns
    ``[]`` when the key is unset, ``remove_keys`` is empty, or the bucket is absent.
    """

    ek = str(session_state_key or state.session_state_key or "").strip()
    if not ek or not remove_keys:
        return []
    if not engine_read_session_state(state, ek):
        return []
    return [
        ApplyBucketPatch(ek, BucketPatch.remove_only(*remove_keys)),
    ]
