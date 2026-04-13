"""Server-authoritative randomness integrated with `hexengine.state.GameState`."""

from __future__ import annotations

import secrets
from typing import Any

from ..state import GameState


class RngService:
    """
    Dice and percentile rolls; each result appends a JSON-safe record to `rng_log`.

    Client previews must not use this type for authoritative combat—only the server.
    """

    @staticmethod
    def roll_d6(state: GameState) -> tuple[GameState, int]:
        v = secrets.randbelow(6) + 1
        entry: dict[str, Any] = {"kind": "d6", "value": v, "rolls": [v]}
        new_log = state.rng_log + (entry,)
        return state.with_rng_log(new_log), v

    @staticmethod
    def roll_2d6(state: GameState) -> tuple[GameState, int]:
        a = secrets.randbelow(6) + 1
        b = secrets.randbelow(6) + 1
        total = a + b
        entry: dict[str, Any] = {
            "kind": "2d6",
            "value": total,
            "rolls": [a, b],
        }
        new_log = state.rng_log + (entry,)
        return state.with_rng_log(new_log), total

    @staticmethod
    def roll_percentile(state: GameState) -> tuple[GameState, int]:
        value = secrets.randbelow(100) + 1
        entry: dict[str, Any] = {"kind": "d100", "value": value, "rolls": [value]}
        new_log = state.rng_log + (entry,)
        return state.with_rng_log(new_log), value
