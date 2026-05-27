"""Title-owned ``GameState.extension`` bucket helpers (one pack id per match)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .game_state import GameState

# Top-level extension keys starting with this prefix are reserved for the engine.
ENGINE_EXTENSION_KEY_PREFIX = "hexengine_"


def is_engine_extension_key(key: str) -> bool:
    """True when ``key`` is reserved for engine ephemeral state (e.g. movement arc)."""

    return str(key or "").strip().startswith(ENGINE_EXTENSION_KEY_PREFIX)


def title_bucket(state: GameState, extension_key: str | None) -> dict[str, Any]:
    """Read the title bucket dict, or ``{}`` when missing or not a dict."""

    ek = str(extension_key or "").strip()
    if not ek:
        return {}
    raw = state.extension.get(ek)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def with_title_bucket(
    state: GameState, extension_key: str, bucket: Mapping[str, Any]
) -> GameState:
    """Return state with the title bucket replaced (shallow copy of ``bucket``)."""

    ek = str(extension_key).strip()
    if not ek:
        raise ValueError("extension_key must be non-empty")
    ext = dict(state.extension)
    ext[ek] = dict(bucket)
    return state.with_extension(ext)


__all__ = [
    "ENGINE_EXTENSION_KEY_PREFIX",
    "is_engine_extension_key",
    "title_bucket",
    "with_title_bucket",
]
