"""Turn-schedule lifecycle hooks (called from `HexdemoGameDefinition.after_phase_transition`)."""

from __future__ import annotations

from hexengine.game_log import get_game_logger
from hexengine.state import GameState


def before_union_move(state: GameState) -> None:
    """
    Placeholder: logic to run when entering Union's movement phase each round.

    Examples later: reinforcements, weather, upkeep.
    """
    _ = state
    get_game_logger().info("before_union_move")
