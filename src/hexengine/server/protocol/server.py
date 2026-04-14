"""Server -> client protocol payloads."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .internals import server_message

_STATE_UPDATE_OMIT_IF_NONE = frozenset(
    {
        "map_display",
        "global_styles",
        "unit_graphics",
        "marker_graphics",
        "markers",
        "server_package_version",
        "turn_rules",
    }
)


@server_message("state_update", omit_if_none=_STATE_UPDATE_OMIT_IF_NONE)
@dataclass
class StateUpdate:
    """Full or partial state update from server."""

    game_state: dict[str, Any]  # Serialized GameState
    sequence_number: int  # For ordering/detecting missed updates
    map_display: dict[str, Any] | None = None  # From scenario MapDisplayConfig
    global_styles: dict[str, Any] | None = None  # GlobalStylesConfig.to_wire_dict()
    unit_graphics: dict[str, Any] | None = None  # unit type -> template wire dict
    marker_graphics: dict[str, Any] | None = None  # marker type -> template wire dict
    markers: list[dict[str, Any]] | None = None  # marker instances
    server_package_version: str | None = None  # hexes wheel version on server
    #: Schedule + factions (+ movement budget) so thin clients can build a matching
    #: `hexengine.gamedef.protocol.GameDefinition` without resolving game packs on disk.
    turn_rules: dict[str, Any] | None = None


@server_message("action_result")
@dataclass
class ActionResult:
    """Result of an action attempt."""

    success: bool = False
    action_id: str | None = None
    error_message: str | None = None


@dataclass
class PlayerInfo:
    """Information about a connected player."""

    player_id: str
    player_name: str
    faction: str
    connected: bool = True
    package_version: str | None = None  # server hexes version (join ack only)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class _PlayerPresenceBase:
    player_id: str
    player_name: str
    faction: str
    connected: bool = True
    package_version: str | None = None

    def to_player_info(self) -> PlayerInfo:
        return PlayerInfo(
            player_id=self.player_id,
            player_name=self.player_name,
            faction=self.faction,
            connected=self.connected,
            package_version=self.package_version,
        )


@server_message("player_joined", omit_if_none=frozenset({"protocol_version"}))
@dataclass
class PlayerJoinedWire(_PlayerPresenceBase):
    """Wire payload for "player_joined" (join ack may set "protocol_version")."""

    protocol_version: str | None = None

    @classmethod
    def from_player_info(
        cls,
        player: PlayerInfo,
        *,
        package_version: str | None = None,
        protocol_version: str | None = None,
    ) -> PlayerJoinedWire:
        return cls(
            player_id=player.player_id,
            player_name=player.player_name,
            faction=player.faction,
            connected=player.connected,
            package_version=package_version
            if package_version is not None
            else player.package_version,
            protocol_version=protocol_version,
        )


@server_message("player_left")
@dataclass
class PlayerLeftWire(_PlayerPresenceBase):
    """Wire payload for "player_left"."""

    @classmethod
    def from_player_info(cls, player: PlayerInfo) -> PlayerLeftWire:
        return cls(
            player_id=player.player_id,
            player_name=player.player_name,
            faction=player.faction,
            connected=player.connected,
            package_version=player.package_version,
        )


@server_message("error")
@dataclass
class ServerError:
    """Server error payload ("error" message)."""

    error: str = "Unknown error"


@server_message("server_log")
@dataclass
class ServerLogEvent:
    """Structured log line broadcast to clients."""

    level: str = "INFO"
    logger: str = ""
    message: str = ""

