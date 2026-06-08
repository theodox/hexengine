"""Engine read/write for pack session state and engine ephemeral buckets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .game_state import GameState

# Top-level engine keys in ``GameState.engine_state`` use this prefix.
ENGINE_EXTENSION_KEY_PREFIX = "hexengine_"


@dataclass(frozen=True, slots=True)
class BucketPatch:
    """Partial update to a pack session-state bucket (shallow merge at top level)."""

    values: dict[str, Any] = field(default_factory=dict)
    remove_keys: tuple[str, ...] = ()

    def to_action(self, session_state_key: str) -> "ApplyBucketPatch":
        from .actions import ApplyBucketPatch

        return ApplyBucketPatch(session_state_key, self)


def is_engine_extension_key(key: str) -> bool:
    """True when ``key`` is reserved for engine ephemeral state (e.g. movement arc)."""

    return str(key or "").strip().startswith(ENGINE_EXTENSION_KEY_PREFIX)


def engine_read_session_state(
    state: GameState, session_state_key: str | None
) -> dict[str, Any]:
    """Read session-state dict when ``session_state_key`` matches ``GameState.session_state_key``."""

    ek = str(session_state_key or "").strip()
    if not ek or state.session_state_key != ek:
        return {}
    return dict(state.session_state)


def engine_write_session_state(
    state: GameState, session_state_key: str, bucket: Mapping[str, Any]
) -> GameState:
    """Return state with session-state dict replaced (shallow copy of ``bucket``)."""

    ek = str(session_state_key).strip()
    if not ek:
        raise ValueError("session_state_key must be non-empty")
    if state.session_state_key not in (None, ek):
        raise ValueError(
            f"session_state_key {state.session_state_key!r} does not match {ek!r}"
        )
    return state.with_session_state(dict(bucket), session_state_key=ek)


def engine_bucket(state: GameState, engine_key: str) -> dict[str, Any]:
    """Read one engine state entry, or ``{}`` when missing or not a dict."""

    k = str(engine_key or "").strip()
    if not k:
        return {}
    raw = state.engine_state.get(k)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def with_engine_bucket(
    state: GameState, engine_key: str, bucket: Mapping[str, Any]
) -> GameState:
    """Return state with one engine state entry replaced."""

    k = str(engine_key).strip()
    if not k:
        raise ValueError("engine_key must be non-empty")
    if not is_engine_extension_key(k):
        raise ValueError(f"Not an engine extension key: {k!r}")
    es = dict(state.engine_state)
    es[k] = dict(bucket)
    return state.with_engine_state(es)


__all__ = [
    "BucketPatch",
    "ENGINE_EXTENSION_KEY_PREFIX",
    "engine_bucket",
    "engine_read_session_state",
    "engine_write_session_state",
    "is_engine_extension_key",
    "with_engine_bucket",
]
