"""Title-owned and engine-owned ``GameState`` buckets (one pack id per match)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .game_state import GameState

# Top-level engine keys in ``GameState.engine_state`` use this prefix.
ENGINE_EXTENSION_KEY_PREFIX = "hexengine_"


def is_engine_extension_key(key: str) -> bool:
    """True when ``key`` is reserved for engine ephemeral state (e.g. movement arc)."""

    return str(key or "").strip().startswith(ENGINE_EXTENSION_KEY_PREFIX)


def title_bucket(state: GameState, extension_key: str | None) -> dict[str, Any]:
    """Read the title bucket dict when ``extension_key`` matches ``title_bucket_key``."""

    ek = str(extension_key or "").strip()
    if not ek or state.title_bucket_key != ek:
        return {}
    return dict(state.title_state)


def with_title_bucket(
    state: GameState, extension_key: str, bucket: Mapping[str, Any]
) -> GameState:
    """Return state with the title bucket replaced (shallow copy of ``bucket``)."""

    ek = str(extension_key).strip()
    if not ek:
        raise ValueError("extension_key must be non-empty")
    if state.title_bucket_key not in (None, ek):
        raise ValueError(
            f"title_bucket_key {state.title_bucket_key!r} does not match {ek!r}"
        )
    return state.with_title_state(dict(bucket), title_bucket_key=ek)


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
    "ENGINE_EXTENSION_KEY_PREFIX",
    "engine_bucket",
    "is_engine_extension_key",
    "title_bucket",
    "with_engine_bucket",
    "with_title_bucket",
]
