"""
Game server - the authoritative source of game state for multiplayer.

The server:
- Owns the canonical GameState via ActionManager
- Validates action requests from clients
- Executes valid actions
- Broadcasts state updates to all clients
- Handles player connections and turn management
"""

import logging
import uuid
from typing import Optional, Callable, Any

from ..package_version import hexes_package_version
from ..state import GameState, ActionManager
from ..state.actions import MoveUnit, DeleteUnit, AddUnit, SpendAction, NextPhase
from .protocol import (
    Message,
    MessageType,
    ActionRequest,
    StateUpdate,
    ActionResult,
    JoinGameRequest,
    PlayerInfo,
)


class GameServer:
    """
    Server that manages multiplayer game state.

    This is transport-agnostic - it can work with WebSockets, HTTP, or any
    other communication layer. The transport calls methods on this class
    to process client requests.
    """

    def __init__(
        self,
        initial_state: Optional[GameState] = None,
        map_display: Optional[dict[str, Any]] = None,
        global_styles: Optional[dict[str, Any]] = None,
        unit_graphics: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize the game server.

        Args:
            initial_state: Starting game state, or None to create empty
            map_display: Optional scenario map presentation dict (JSON-safe)
            global_styles: Optional global CSS dict (JSON-safe)
            unit_graphics: Optional unit type -> template dict (JSON-safe)
        """
        self.game_state = initial_state or GameState.create_empty()
        self.action_manager = ActionManager(self.game_state)
        self.map_display = map_display
        self.global_styles = global_styles
        self.unit_graphics = unit_graphics
        self._server_package_version = hexes_package_version()

        # Player management
        self.players: dict[str, PlayerInfo] = {}
        self.faction_to_player: dict[str, str] = {}  # faction -> player_id

        # State tracking
        self.sequence_number = 0

        # Callbacks for sending messages to clients
        self.message_handlers: list[Callable[[str, Message], None]] = []

        self.logger = logging.getLogger("game_server")
        self.logger.info("Game server initialized")

        # Define turn configuration
        # Interleaved: Red-Movement, Blue-Movement, Red-Attack, Blue-Attack
        self.factions = ["Red", "Blue"]
        self.phases = [
            {"name": "Movement", "max_actions": 2},
            {"name": "Attack", "max_actions": 2},
        ]
        self._build_turn_order()

    def _build_turn_order(self) -> None:
        """Build interleaved turn order from factions and phases."""
        # Interleaved: Red-Movement, Blue-Movement, Red-Attack, Blue-Attack
        self.turn_order = []
        for phase in self.phases:
            for faction in self.factions:
                self.turn_order.append(
                    {
                        "faction": faction,
                        "phase": phase["name"],
                        "max_actions": phase["max_actions"],
                    }
                )
        self.logger.info(f"Turn order: {self.turn_order}")

    def _serialize_state(self, state: GameState) -> dict[str, Any]:
        """
        Serialize GameState into JSON-safe primitives.

        Hex keys in locations are converted into explicit position objects
        so the payload can be JSON-encoded without errors.
        """
        units: dict[str, dict[str, Any]] = {}
        for unit_id, unit in state.board.units.items():
            units[unit_id] = {
                "unit_id": unit.unit_id,
                "unit_type": unit.unit_type,
                "faction": unit.faction,
                "position": {"i": unit.position.i, "j": unit.position.j, "k": unit.position.k},
                "health": unit.health,
                "active": unit.active,
            }

        locations: list[dict[str, Any]] = []
        for pos, loc in state.board.locations.items():
            locations.append(
                {
                    "position": {"i": pos.i, "j": pos.j, "k": pos.k},
                    "terrain_type": loc.terrain_type,
                    "movement_cost": loc.movement_cost,
                }
            )

        return {
            "board": {
                "units": units,
                "locations": locations,
            },
            "turn": {
                "current_faction": state.turn.current_faction,
                "current_phase": state.turn.current_phase,
                "phase_actions_remaining": state.turn.phase_actions_remaining,
                "turn_number": state.turn.turn_number,
            },
        }

    def _get_next_phase(self) -> dict:
        """Get the next phase in the turn order."""
        current_state = self.action_manager.current_state
        current_faction = current_state.turn.current_faction
        current_phase = current_state.turn.current_phase

        # Find current position in turn order
        for i, turn_info in enumerate(self.turn_order):
            if (
                turn_info["faction"] == current_faction
                and turn_info["phase"] == current_phase
            ):
                # Return next in sequence (wraps around)
                next_idx = (i + 1) % len(self.turn_order)
                return self.turn_order[next_idx]

        # Fallback: return first turn
        return self.turn_order[0]

    def add_message_handler(self, handler: Callable[[str, Message], None]) -> None:
        """
        Add a handler for outgoing messages.

        Args:
            handler: Function that takes (player_id, message) and sends it to client
        """
        self.message_handlers.append(handler)

    async def handle_message(self, player_id: str, message: Message) -> None:
        """
        Process an incoming message from a client.

        Args:
            player_id: ID of the player sending the message
            message: The message to process
        """
        try:
            if message.type == MessageType.JOIN_GAME:
                await self._handle_join_game(player_id, message)
            elif message.type == MessageType.ACTION_REQUEST:
                await self._handle_action_request(player_id, message)
            elif message.type == MessageType.UNDO_REQUEST:
                await self._handle_undo_request(player_id, message)
            elif message.type == MessageType.REDO_REQUEST:
                await self._handle_redo_request(player_id, message)
            elif message.type == MessageType.LEAVE_GAME:
                await self._handle_leave_game(player_id)
            else:
                self.logger.warning(f"Unknown message type: {message.type}")
        except Exception as e:
            self.logger.error(f"Error handling message from {player_id}: {e}")
            await self._send_error(player_id, str(e))

    async def _handle_join_game(self, player_id: str, message: Message) -> None:
        """Handle a player joining the game."""
        request = JoinGameRequest.from_message(message)

        # Check if player already connected
        if player_id in self.players:
            self.logger.info(f"Player {player_id} reconnecting")
            self.players[player_id].connected = True
            await self._send_state_update(player_id)
            return

        # Assign faction
        faction = request.faction

        # Define available factions (hardcoded for now)
        available_factions = ["Red", "Blue"]

        if not faction or faction in self.faction_to_player:
            # Auto-assign to first available faction
            taken = set(self.faction_to_player.keys())
            available = [f for f in available_factions if f not in taken]
            if not available:
                await self._send_error(
                    player_id, "No factions available (max 2 players)"
                )
                return
            faction = available[0]
        elif faction not in available_factions:
            # Requested faction doesn't exist
            await self._send_error(
                player_id,
                f"Invalid faction: {faction}. Available: {available_factions}",
            )
            return
        elif faction in self.faction_to_player:
            # Requested faction already taken
            await self._send_error(player_id, f"Faction {faction} already taken")
            return

        # Create player info
        player = PlayerInfo(
            player_id=player_id,
            player_name=request.player_name,
            faction=faction,
            connected=True,
        )
        self.players[player_id] = player
        self.faction_to_player[faction] = player_id

        self.logger.info(f"Player {request.player_name} joined as {faction}")

        # Send player_joined to the joining player (so they know their faction)
        join_payload = dict(player.to_dict())
        join_payload["package_version"] = self._server_package_version
        await self._send_message(
            player_id, Message(type=MessageType.PLAYER_JOINED, payload=join_payload)
        )

        # Send full state to joining player
        await self._send_state_update(player_id)

        # Notify other players
        await self._broadcast_player_joined(player)

    async def _handle_action_request(self, player_id: str, message: Message) -> None:
        """Handle an action request from a client."""
        request = ActionRequest.from_message(message)

        # Validate player
        player = self.players.get(player_id)
        if not player:
            await self._send_error(player_id, "Player not in game")
            return

        # Validate it's player's turn
        current_state = self.action_manager.current_state
        current_faction = current_state.turn.current_faction
        if player.faction != current_faction:
            await self._send_error(
                player_id, f"Not your turn (current: {current_faction})"
            )
            return

        # Create action from request
        try:
            action = self._create_action(request)
        except Exception as e:
            await self._send_error(player_id, f"Invalid action: {e}")
            return

        # Execute action
        try:
            self.action_manager.execute(action)
            self.logger.info(
                f"Executed {request.action_type} from {player.player_name}"
            )

            # Spend an action for moves (other action types may cost different amounts)
            if request.action_type in ["MoveUnit"]:
                try:
                    self.logger.debug(f"Spending 1 action for MoveUnit")
                    spend_action = SpendAction(amount=1)
                    self.action_manager.execute(spend_action)

                    # Check if we need to advance to next phase
                    current_state = self.action_manager.current_state
                    self.logger.debug(
                        f"After spending: {current_state.turn.current_faction}-"
                        f"{current_state.turn.current_phase}, "
                        f"actions remaining: {current_state.turn.phase_actions_remaining}"
                    )

                    if current_state.turn.phase_actions_remaining <= 0:
                        next_phase_info = self._get_next_phase()
                        self.logger.info(f"Actions depleted, advancing to next phase")
                        next_phase_action = NextPhase(
                            new_faction=next_phase_info["faction"],
                            new_phase=next_phase_info["phase"],
                            max_actions=next_phase_info["max_actions"],
                        )
                        self.action_manager.execute(next_phase_action)
                        self.logger.info(
                            f"Advanced to {next_phase_info['faction']}-{next_phase_info['phase']}"
                        )
                except Exception as e:
                    self.logger.error(f"Error in turn advancement: {e}", exc_info=True)

            # Send success to requester
            result = ActionResult(success=True, action_id=str(uuid.uuid4()))
            await self._send_message(player_id, result.to_message())

            # Broadcast state update to all players
            await self._broadcast_state_update()

        except Exception as e:
            self.logger.error(f"Action execution failed: {e}")
            await self._send_error(player_id, f"Action failed: {e}")

    async def _handle_undo_request(self, player_id: str, message: Message) -> None:
        """Handle an undo request from a client."""
        from .protocol import UndoRequest
        self.logger.debug(f"Handling undo request from player {player_id}")
        
        request = UndoRequest.from_message(message)

        # Validate player
        player = self.players.get(player_id)
        if not player:
            await self._send_error(player_id, "Player not in game")
            return

        # Check if undo is possible
        if not self.action_manager.can_undo():
            await self._send_error(player_id, "Nothing to undo")
            return

        # Execute undo
        try:
            self.action_manager.undo()
            self.logger.info(f"Undid action for {player.player_name}")

            # Send success to requester
            result = ActionResult(success=True, action_id=str(uuid.uuid4()))
            await self._send_message(player_id, result.to_message())

            # Broadcast state update to all players
            await self._broadcast_state_update()

        except Exception as e:
            self.logger.error(f"Undo failed: {e}")
            await self._send_error(player_id, f"Undo failed: {e}")

    async def _handle_redo_request(self, player_id: str, message: Message) -> None:
        """Handle a redo request from a client."""
        from .protocol import RedoRequest

        request = RedoRequest.from_message(message)

        # Validate player
        player = self.players.get(player_id)
        if not player:
            await self._send_error(player_id, "Player not in game")
            return

        # Check if redo is possible
        if not self.action_manager.can_redo():
            await self._send_error(player_id, "Nothing to redo")
            return

        # Execute redo
        try:
            self.action_manager.redo()
            self.logger.info(f"Redid action for {player.player_name}")

            # Send success to requester
            result = ActionResult(success=True, action_id=str(uuid.uuid4()))
            await self._send_message(player_id, result.to_message())

            # Broadcast state update to all players
            await self._broadcast_state_update()

        except Exception as e:
            self.logger.error(f"Redo failed: {e}")
            await self._send_error(player_id, f"Redo failed: {e}")

    def _create_action(self, request: ActionRequest) -> Any:
        """
        Create an action instance from a request.

        Args:
            request: Action request from client

        Returns:
            Action instance ready to execute
        """
        action_type = request.action_type
        params = request.params

        self.logger.debug(f"Creating action {action_type} with params {params}")
        # Import and instantiate the appropriate action class
        match action_type:
            case "MoveUnit":


                from ..hexes.types import Hex  # Import here to avoid circular dependency

                return MoveUnit(
                    unit_id=params["unit_id"],
                    from_hex=Hex(**params["from_hex"]),
                    to_hex=Hex(**params["to_hex"]),
                )
            case "DeleteUnit":
                return DeleteUnit(unit_id=params["unit_id"])
            case "AddUnit":
                from ..hexes.types import Hex

                return AddUnit(
                    unit_id=params["unit_id"],
                    unit_type=params["unit_type"],
                    faction=params["faction"],
                    position=Hex(**params["position"]),
                    health=params.get("health", 100),
                )
            case "SpendAction":
                return SpendAction(amount=params.get("amount", 1))
            case "NextPhase":
                return NextPhase(
                    new_faction=params["new_faction"],
                    new_phase=params["new_phase"],
                    max_actions=params["max_actions"],
                )
            case _:
                raise ValueError(f"Unknown action type: {action_type}")
        
        

    async def _handle_leave_game(self, player_id: str) -> None:
        """Handle a player leaving the game."""
        player = self.players.get(player_id)
        if player:
            player.connected = False
            self.logger.info(f"Player {player.player_name} disconnected")
            await self._broadcast_player_left(player)

    async def _send_state_update(self, player_id: str) -> None:
        """Send current game state to a specific player."""
        state_dict = self._serialize_state(self.action_manager.current_state)
        update = StateUpdate(
            game_state=state_dict,
            sequence_number=self.sequence_number,
            map_display=self.map_display,
            global_styles=self.global_styles,
            unit_graphics=self.unit_graphics,
            server_package_version=self._server_package_version,
        )
        await self._send_message(player_id, update.to_message())

    async def _broadcast_state_update(self) -> None:
        """Broadcast current game state to all connected players."""
        self.sequence_number += 1
        state_dict = self._serialize_state(self.action_manager.current_state)
        update = StateUpdate(
            game_state=state_dict,
            sequence_number=self.sequence_number,
            map_display=self.map_display,
            global_styles=self.global_styles,
            unit_graphics=self.unit_graphics,
            server_package_version=self._server_package_version,
        )
        message = update.to_message()

        for player_id, player in self.players.items():
            if player.connected:
                await self._send_message(player_id, message)

    async def _broadcast_player_joined(self, player: PlayerInfo) -> None:
        """Notify all players that someone joined."""
        message = Message(type=MessageType.PLAYER_JOINED, payload=player.to_dict())
        for player_id, p in self.players.items():
            if p.connected and player_id != player.player_id:
                await self._send_message(player_id, message)

    async def _broadcast_player_left(self, player: PlayerInfo) -> None:
        """Notify all players that someone left."""
        message = Message(type=MessageType.PLAYER_LEFT, payload=player.to_dict())
        for player_id, p in self.players.items():
            if p.connected and player_id != player.player_id:
                await self._send_message(player_id, message)

    async def _send_error(self, player_id: str, error_message: str) -> None:
        """Send an error message to a player."""
        message = Message(type=MessageType.ERROR, payload={"error": error_message})
        await self._send_message(player_id, message)

    async def _send_message(self, player_id: str, message: Message) -> None:
        """Send a message to a specific player via registered handlers."""
        for handler in self.message_handlers:
            try:
                handler(player_id, message)
            except Exception as e:
                self.logger.error(f"Error in message handler: {e}")

    def get_current_state(self) -> GameState:
        """Get the current authoritative game state."""
        return self.action_manager.current_state

    def get_players(self) -> list[PlayerInfo]:
        """Get list of all players."""
        return list(self.players.values())

    def get_connected_players(self) -> list[PlayerInfo]:
        """Get list of connected players."""
        return [p for p in self.players.values() if p.connected]
