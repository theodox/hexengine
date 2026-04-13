"""Title hooks around the turn schedule (Hexdemo)."""

from __future__ import annotations

from hexengine.state import GameState

import logging

logger = logging.getLogger(__name__)

def before_union_move(state: GameState) -> None:
    """
    Placeholder: logic to run when entering Union's movement phase each round.

    Examples later: reinforcements, weather, upkeep.
    """
    _ = state
    logger.info("before_union_move")