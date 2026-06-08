"""Title-owned constants for the hexdemo pack."""

from __future__ import annotations

# Faction ids used in scenario TOML, wire join, and GameDefinition / turn state.
# Order: player 1 (Union) first in the rota, then Confederates.
HEXDEMO_FACTIONS: tuple[str, ...] = ("union", "confederate")

# Pack id for ``GameState.session_state`` / ``GameState.session_state_key``.
PACK_SESSION_STATE_KEY = "hexdemo"
