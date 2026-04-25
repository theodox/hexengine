"""
Game server - the authoritative source of game state for multiplayer.

The server:
- Owns the canonical GameState via ActionManager
- Validates action requests from clients
- Executes valid actions
- Broadcasts state updates to all clients
- Handles player connections and turn management
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from ..game_log import GameLogger, game_logger_scope
from ..gamedef.protocol import GameDefinition
from ..gamedef.unit_attributes import merge_spawn_attributes, validate_unit_attributes_patch
from ..hexes.types import Hex, HexColRow
from ..package_version import hexes_package_version
from ..hexes.math import distance
from ..state import ActionManager, GameState
from ..state.actions import (
    AddUnit,
    Attack,
    ClearHexdemoCombatExtension,
    ClearUnitRetreatObligation,
    DeleteUnit,
    MoveUnit,
    NextPhase,
    PatchUnitAttributes,
    SpendAction,
)
from ..state.logic import (
    DEFAULT_MOVEMENT_BUDGET,
    is_valid_move,
    retreat_impassable_enemy_zoc_hexes,
)
from ..state.marker_placement import (
    MarkerPlacementRule,
    default_marker_destination_allowed,
)
from ..state.phase_rules import phase_allows_unit_move
from ..state.snapshot import game_state_from_wire_dict, game_state_to_wire_dict
from .protocol import (
    ActionRequest,
    ActionResult,
    CombatEventWire,
    JoinGameRequest,
    LeaveGameRequest,
    LoadSnapshotRequest,
    Message,
    PlayerInfo,
    PlayerJoinedWire,
    PlayerLeftWire,
    RedoRequest,
    ServerError,
    ServerLogEvent,
    StateUpdate,
    UndoRequest,
)


def _turn_rules_rota_id(entries: list[dict[str, Any]]) -> str:
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class GameServer:
    """
    Server that manages multiplayer game state.

    This is transport-agnostic - it can work with WebSockets, HTTP, or any
    other communication layer. The transport calls methods on this class
    to process client requests.
    """

    def __init__(
        self,
        initial_state: GameState | None = None,
        map_display: dict[str, Any] | None = None,
        global_styles: dict[str, Any] | None = None,
        unit_graphics: dict[str, Any] | None = None,
        marker_graphics: dict[str, Any] | None = None,
        markers: list[dict[str, Any]] | None = None,
        marker_placement_rule: MarkerPlacementRule | None = None,
        *,
        game_definition: GameDefinition,
    ) -> None:
        """
        Initialize the game server.

        Args:
            initial_state: Starting game state, or None to create empty
            map_display: Optional scenario map presentation dict (JSON-safe)
            global_styles: Optional global CSS dict (JSON-safe)
            unit_graphics: Optional unit type -> template dict (JSON-safe)
            marker_placement_rule: Optional `(state, marker_wire_dict, to_hex) -> bool`
                for marker moves/adds; if omitted, uses empty-hex rule (board hex, no unit).
            game_definition: Turn schedule and factions (required).
        """
        self.game_state = initial_state or GameState.create_empty()
        self.action_manager = ActionManager(self.game_state)
        self.map_display = map_display
        self.global_styles = global_styles
        self.unit_graphics = unit_graphics
        self.marker_graphics = marker_graphics
        self.markers = [] if markers is None else list(markers)
        self._marker_placement_rule = marker_placement_rule
        self._server_package_version = hexes_package_version()
        self._game_definition = game_definition

        # Player management
        self.players: dict[str, PlayerInfo] = {}
        self.faction_to_player: dict[str, str] = {}  # faction -> player_id

        # State tracking
        self.sequence_number = 0

        # Callbacks for sending messages to clients
        self.message_handlers: list[Callable[[str, Message], None]] = []

        self.logger = logging.getLogger("game_server")
        self.logger.info("Game server initialized")

        self.turn_order = self._game_definition.turn_order()
        self.logger.info(f"Turn order: {self.turn_order}")

        self._pending_game_log_events: deque[tuple[str, str, str]] = deque()

    def _serialize_state(self, state: GameState) -> dict[str, Any]:
        """Serialize GameState into JSON-safe primitives."""
        return game_state_to_wire_dict(state)

    def _get_next_phase(self) -> dict:
        """Get the next phase in the turn order."""
        return self._game_definition.get_next_phase(self.action_manager.current_state)

    def _suggested_focus_unit_id_for_player_id(self, player_id: str) -> str | None:
        """Per-viewer selection hint from optional ``GameDefinition`` focus hook."""
        player = self.players.get(player_id)
        if player is None:
            return None
        fac = str(player.faction).strip() if player.faction else ""
        if not fac:
            return None
        fn = getattr(self._game_definition, "focus_unit_id_after_state_sync", None)
        if not callable(fn):
            return None
        uid = fn(self.action_manager.current_state, fac)
        if not isinstance(uid, str) or not uid.strip():
            return None
        return uid.strip()

    def _retreat_obligations_for_player_id(self, player_id: str) -> dict[str, int] | None:
        """
        Per-viewer mandatory retreat obligations for the player's faction.

        Only populated when the title exposes ``retreat_obligation_hexes_remaining``.
        """
        player = self.players.get(player_id)
        if player is None:
            return None
        fac = str(player.faction).strip() if player.faction else ""
        if not fac:
            return None
        fn = getattr(self._game_definition, "retreat_obligation_hexes_remaining", None)
        if not callable(fn):
            return None
        st = self.action_manager.current_state
        out: dict[str, int] = {}
        for uid, u in st.board.units.items():
            if not u.active or u.faction != fac:
                continue
            n = fn(st, uid)
            if n is None:
                continue
            try:
                ni = int(n)
            except (TypeError, ValueError):
                continue
            if ni > 0:
                out[str(uid)] = ni
        return out or None

    def _turn_rules_wire(self) -> dict[str, Any]:
        """Full turn rota + budget + fingerprint for thin clients (no game pack on disk)."""
        entries = self._game_definition.turn_order()
        budget = float(
            getattr(self._game_definition, "_movement_budget", DEFAULT_MOVEMENT_BUDGET)
        )
        out: dict[str, Any] = {
            "turn_rules_schema": 1,
            "entries": entries,
            "movement_budget": budget,
            "rota_id": _turn_rules_rota_id(entries),
        }
        attr_key = getattr(self._game_definition, "movement_budget_attribute_key", None)
        if isinstance(attr_key, str) and attr_key.strip():
            out["movement_budget_attribute"] = attr_key.strip()
        out["client_contract"] = {
            "schema": 1,
            "features": sorted(
                f
                for f in (
                    "suggested_focus_unit_id"
                    if callable(
                        getattr(self._game_definition, "focus_unit_id_after_state_sync", None)
                    )
                    else None,
                    "retreat_obligations"
                    if callable(
                        getattr(self._game_definition, "retreat_obligation_hexes_remaining", None)
                    )
                    else None,
                    "zoc_hexes_for_unit"
                    if callable(getattr(self._game_definition, "zoc_hexes_for_unit", None))
                    else None,
                )
                if f is not None
            ),
        }
        return out

    def _invoke_phase_transition_hook(self) -> None:
        fn = getattr(self._game_definition, "after_phase_transition", None)
        if callable(fn):
            fn(self.action_manager.current_state)

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
        gl = self._make_game_logger()
        with game_logger_scope(gl):
            try:
                handler = _CLIENT_INBOUND_HANDLERS.get(message.type)
                if handler is None:
                    self.logger.warning(f"Unknown message type: {message.type}")
                else:
                    await handler(self, player_id, message)
            except Exception as e:
                self.logger.error(f"Error handling message from {player_id}: {e}")
                await self._send_error(player_id, str(e))
            finally:
                await self._flush_game_log_queue()

    def _make_game_logger(self) -> GameLogger:
        return GameLogger(
            logger_name="hexengine.game",
            enqueue_client=self._enqueue_game_client_log,
        )

    def _enqueue_game_client_log(self, level: str, logger_name: str, text: str) -> None:
        self._pending_game_log_events.append((level, logger_name, text))

    async def _flush_game_log_queue(self) -> None:
        while self._pending_game_log_events:
            level, logger_name, text = self._pending_game_log_events.popleft()
            outgoing = ServerLogEvent(
                level=level, logger=logger_name, message=text
            ).to_message()
            for pid, player in list(self.players.items()):
                if player.connected:
                    await self._send_message(pid, outgoing)

    async def _handle_join_game(self, player_id: str, message: Message) -> None:
        """Handle a player joining the game."""
        request = JoinGameRequest.from_message(message)

        # Check if player already connected
        if player_id in self.players:
            self.logger.info(f"Player {player_id} reconnecting")
            self.players[player_id].connected = True
            await self._send_state_update(player_id)
            return

        # Assign faction: explicit preference must be honored or rejected — never
        # silently auto-assign to another faction when the client named one.
        requested = request.faction
        if isinstance(requested, str) and not requested.strip():
            requested = None

        available_factions = self._game_definition.available_factions()

        if requested is None:
            # No preference: first free faction
            taken = set(self.faction_to_player.keys())
            available = [f for f in available_factions if f not in taken]
            if not available:
                await self._send_error(
                    player_id, "No factions available (max 2 players)"
                )
                return
            faction = available[0]
        elif requested not in available_factions:
            await self._send_error(
                player_id,
                f"Invalid faction: {requested}. Available: {available_factions}",
            )
            return
        elif requested in self.faction_to_player:
            await self._send_error(player_id, f"Faction {requested} already taken")
            return
        else:
            faction = requested

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
        await self._send_message(
            player_id,
            PlayerJoinedWire.from_player_info(
                player,
                package_version=self._server_package_version,
                protocol_version="1",
            ).to_message(),
        )

        # Send full state to joining player
        await self._send_state_update(player_id)

        # Notify other players
        await self._broadcast_player_joined(player)

    def _after_next_phase_applied(self) -> None:
        """Title hook then strip hexdemo combat keys (per-segment reset)."""
        self._invoke_phase_transition_hook()
        try:
            self.action_manager.execute(ClearHexdemoCombatExtension())
        except Exception as e:
            self.logger.error(
                "ClearHexdemoCombatExtension failed: %s", e, exc_info=True
            )

    def _retreat_obligation_hexes_remaining(
        self, state: GameState, unit_id: str | None
    ) -> int | None:
        if not unit_id:
            return None
        fn = getattr(
            self._game_definition, "retreat_obligation_hexes_remaining", None
        )
        if callable(fn):
            return fn(state, unit_id)
        return None

    def _faction_has_pending_retreat(self, state: GameState, faction: str) -> bool:
        fn = getattr(
            self._game_definition, "faction_has_pending_retreat_obligation", None
        )
        if callable(fn):
            return bool(fn(state, faction))
        return False

    def _retreat_owner_faction(
        self, state: GameState, outcome: str, attacker_id: str, defender_id: str
    ) -> str | None:
        if outcome == "attacker_retreat":
            u = state.board.units.get(attacker_id)
            return u.faction if u else None
        if outcome == "defender_retreat":
            u = state.board.units.get(defender_id)
            return u.faction if u else None
        return None

    def _combat_instruction_for_player(
        self, recipient_faction: str, *, outcome: str, retreat_owner_faction: str | None
    ) -> tuple[str, str]:
        if outcome == "defender_destroyed":
            return "resolved", "Defender destroyed."
        if outcome == "none":
            return "resolved", "Combat resolved with no effect."
        if retreat_owner_faction is None:
            return "resolved", "Combat resolved."
        if recipient_faction == retreat_owner_faction:
            return (
                "retreat_required",
                "You must retreat this unit in one move (exact hex distance).",
            )
        return "wait", "Waiting for the opponent to complete a mandatory retreat."

    async def _broadcast_combat_events(self, state_after: GameState) -> None:
        hx = state_after.extension.get("hexdemo")
        if not isinstance(hx, dict):
            return
        last_combat = hx.get("last_combat")
        if not isinstance(last_combat, dict):
            return
        outcome = str(last_combat.get("outcome", ""))
        attack_kind = str(last_combat.get("attack_kind", ""))
        attacker_id = str(last_combat.get("attacker_id", ""))
        defender_id = str(last_combat.get("defender_id", ""))
        retreat_distance = last_combat.get("retreat_distance")
        rd_int: int | None = None
        if isinstance(retreat_distance, int):
            rd_int = retreat_distance
        elif retreat_distance is not None:
            try:
                rd_int = int(retreat_distance)
            except (TypeError, ValueError):
                rd_int = None
        retreat_unit_raw = last_combat.get("retreat_unit_id")
        ru: str | None = str(retreat_unit_raw) if retreat_unit_raw else None
        ob = (
            hx.get("retreat_obligations")
            if isinstance(hx.get("retreat_obligations"), dict)
            else {}
        )
        hex_remaining: int | None = None
        if ru is not None:
            raw_rem = ob.get(ru)
            if isinstance(raw_rem, (int, float, str)):
                try:
                    hex_remaining = int(raw_rem)
                except (TypeError, ValueError):
                    hex_remaining = None
        retreat_owner = self._retreat_owner_faction(
            state_after, outcome, attacker_id, defender_id
        )
        for pid, pinfo in self.players.items():
            if not pinfo.connected:
                continue
            inst, msg = self._combat_instruction_for_player(
                pinfo.faction,
                outcome=outcome,
                retreat_owner_faction=retreat_owner,
            )
            ru_payload = ru if inst == "retreat_required" else None
            hr_payload = hex_remaining if inst == "retreat_required" else None
            rd_payload = rd_int if outcome.endswith("retreat") else None
            evt = CombatEventWire(
                attack_kind=attack_kind,
                outcome=outcome,
                attacker_id=attacker_id,
                defender_id=defender_id,
                instruction=inst,
                message=msg,
                retreat_unit_id=ru_payload,
                retreat_hexes_remaining=hr_payload,
                retreat_distance=rd_payload,
            )
            await self._send_message(pid, evt.to_message())

    async def _handle_action_request(self, player_id: str, message: Message) -> None:
        """Handle an action request from a client."""
        request = ActionRequest.from_message(message)

        # Validate player
        player = self.players.get(player_id)
        if not player:
            await self._send_error(player_id, "Player not in game")
            return

        current_state = self.action_manager.current_state
        current_faction = current_state.turn.current_faction

        if request.action_type == "Attack":
            if player.faction != current_faction:
                await self._send_error(
                    player_id, f"Not your turn (current: {current_faction})"
                )
                return
            fn = getattr(self._game_definition, "validate_attack_request", None)
            if not callable(fn):
                await self._send_error(
                    player_id, "This game title does not support Attack actions"
                )
                return
            params = request.params
            try:
                fn(
                    current_state,
                    player_faction=player.faction,
                    attack_kind=str(params.get("attack_kind", "")),
                    params=params,
                )
            except Exception as e:
                await self._send_error(player_id, str(e))
                return
            attack_kind = str(params.get("attack_kind", ""))
            att = str(params.get("attacker_id", ""))
            deff = str(params.get("defender_id", ""))
            try:
                atk = Attack(attack_kind, att, deff)
                self.action_manager.execute(atk)
            except Exception as e:
                await self._send_error(player_id, f"Action failed: {e}")
                return
            st_after = self.action_manager.current_state
            await self._broadcast_combat_events(st_after)
            adv_fn = getattr(
                self._game_definition, "should_auto_advance_phase_after_attack", None
            )
            if callable(adv_fn) and adv_fn(st_after):
                next_phase_info = self._get_next_phase()
                self.logger.info(
                    "Auto-advancing phase after attack (%s → %s %s)",
                    st_after.turn.current_faction,
                    next_phase_info["faction"],
                    next_phase_info["phase"],
                )
                next_phase_action = NextPhase(
                    new_faction=next_phase_info["faction"],
                    new_phase=next_phase_info["phase"],
                    max_actions=next_phase_info["max_actions"],
                    new_schedule_index=int(next_phase_info["schedule_index"]),
                )
                self.action_manager.execute(next_phase_action)
                self._after_next_phase_applied()
            result = ActionResult(success=True, action_id=str(uuid.uuid4()))
            await self._send_message(player_id, result.to_message())
            await self._broadcast_state_update()
            return

        uid_for_move: str | None = None
        is_retreat_fulfillment = False
        if request.action_type == "MoveUnit" and isinstance(
            request.params.get("unit_id"), str
        ):
            uid_for_move = str(request.params["unit_id"])
            retreat_rem = self._retreat_obligation_hexes_remaining(
                current_state, uid_for_move
            )
            is_retreat_fulfillment = retreat_rem is not None

        if not is_retreat_fulfillment:
            if player.faction != current_faction:
                await self._send_error(
                    player_id, f"Not your turn (current: {current_faction})"
                )
                return
        else:
            unit = current_state.board.units.get(uid_for_move or "")
            if unit is None or unit.faction != player.faction:
                await self._send_error(player_id, "That unit is not yours")
                return

        if request.action_type == "MoveMarker":
            try:
                self._apply_move_marker(request.params)
            except Exception as e:
                self.logger.error("MoveMarker failed: %s", e, exc_info=True)
                await self._send_error(player_id, f"Action failed: {e}")
                return
            result = ActionResult(success=True, action_id=str(uuid.uuid4()))
            await self._send_message(player_id, result.to_message())
            await self._broadcast_state_update()
            return

        if request.action_type == "AddMarker":
            try:
                self._apply_add_marker(request.params)
            except Exception as e:
                self.logger.error("AddMarker failed: %s", e, exc_info=True)
                await self._send_error(player_id, f"Action failed: {e}")
                return
            result = ActionResult(success=True, action_id=str(uuid.uuid4()))
            await self._send_message(player_id, result.to_message())
            await self._broadcast_state_update()
            return

        if request.action_type == "RemoveMarker":
            try:
                self._apply_remove_marker(request.params)
            except Exception as e:
                self.logger.error("RemoveMarker failed: %s", e, exc_info=True)
                await self._send_error(player_id, f"Action failed: {e}")
                return
            result = ActionResult(success=True, action_id=str(uuid.uuid4()))
            await self._send_message(player_id, result.to_message())
            await self._broadcast_state_update()
            return

        if request.action_type == "PatchUnitAttributes":
            if player.faction != current_faction:
                await self._send_error(
                    player_id, f"Not your turn (current: {current_faction})"
                )
                return
            uid = str(request.params.get("unit_id", ""))
            patch = request.params.get("patch")
            if not isinstance(patch, dict):
                await self._send_error(player_id, "patch must be an object")
                return
            raw_remove = request.params.get("remove_keys", [])
            if isinstance(raw_remove, str):
                remove_t = (raw_remove,) if raw_remove else ()
            elif isinstance(raw_remove, list):
                remove_t = tuple(str(x) for x in raw_remove)
            else:
                remove_t = ()
            unit = current_state.board.units.get(uid)
            if unit is None or not unit.active:
                await self._send_error(player_id, "Unknown unit")
                return
            if unit.faction != player.faction:
                await self._send_error(player_id, "That unit is not yours")
                return
            try:
                validate_unit_attributes_patch(
                    self._game_definition, current_state, uid, dict(patch)
                )
            except Exception as e:
                await self._send_error(player_id, str(e))
                return
            try:
                self.action_manager.execute(
                    PatchUnitAttributes(uid, dict(patch), remove_keys=remove_t)
                )
            except Exception as e:
                await self._send_error(player_id, f"Action failed: {e}")
                return
            result = ActionResult(success=True, action_id=str(uuid.uuid4()))
            await self._send_message(player_id, result.to_message())
            await self._broadcast_state_update()
            return

        if request.action_type == "MoveUnit":
            try:
                self._validate_move_unit_request(
                    current_state,
                    request.params,
                    player,
                    is_retreat_fulfillment=is_retreat_fulfillment,
                )
            except ValueError as e:
                await self._send_error(player_id, str(e))
                return

        # Create action from request (NextPhase is always server-authoritative)
        try:
            if request.action_type == "NextPhase":
                info = self._get_next_phase()
                action = NextPhase(
                    new_faction=info["faction"],
                    new_phase=info["phase"],
                    max_actions=info["max_actions"],
                    new_schedule_index=int(info["schedule_index"]),
                )
            else:
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

            if isinstance(action, NextPhase):
                self._after_next_phase_applied()

            if request.action_type == "MoveUnit" and is_retreat_fulfillment:
                if uid_for_move is None:
                    raise RuntimeError("MoveUnit retreat without unit_id")
                self.action_manager.execute(ClearUnitRetreatObligation(uid_for_move))

            # Spend an action for normal moves (retreat fulfillment never spends)
            if request.action_type == "MoveUnit" and not is_retreat_fulfillment:
                try:
                    self.logger.debug("Spending 1 action for MoveUnit")
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
                        self.logger.info("Actions depleted, advancing to next phase")
                        next_phase_action = NextPhase(
                            new_faction=next_phase_info["faction"],
                            new_phase=next_phase_info["phase"],
                            max_actions=next_phase_info["max_actions"],
                            new_schedule_index=int(next_phase_info["schedule_index"]),
                        )
                        self.action_manager.execute(next_phase_action)
                        self._after_next_phase_applied()
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

        UndoRequest.from_message(message)

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

        RedoRequest.from_message(message)

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

    async def _handle_load_snapshot(self, player_id: str, message: Message) -> None:
        """Replace server state from a client snapshot and broadcast."""
        request = LoadSnapshotRequest.from_message(message)

        player = self.players.get(player_id)
        if not player:
            await self._send_error(player_id, "Player not in game")
            return

        try:
            new_state = game_state_from_wire_dict(request.game_state)
        except Exception as e:
            self.logger.error(f"Invalid load_snapshot from {player_id}: {e}")
            await self._send_error(player_id, f"Invalid snapshot: {e}")
            return

        self.action_manager.replace_state(new_state)
        self.game_state = self.action_manager.current_state
        self.logger.info(f"Loaded snapshot from {player.player_name}")

        await self._broadcast_state_update()

    def _marker_destination_allowed(
        self, state: GameState, marker_wire: dict[str, Any], to_hex: Hex
    ) -> bool:
        if self._marker_placement_rule is not None:
            return self._marker_placement_rule(state, marker_wire, to_hex)
        return default_marker_destination_allowed(state, marker_wire, to_hex)

    def add_marker_row(
        self,
        marker_id: str,
        marker_type: str,
        col: int,
        row: int,
        *,
        active: bool = True,
    ) -> None:
        """
        Append a marker (same validation as the `AddMarker` wire action).

        Does not broadcast; call `_broadcast_state_update` (or equivalent)
        from async game code after mutating server state.
        """
        self._apply_add_marker(
            {
                "marker_id": marker_id,
                "marker_type": marker_type,
                "position": [col, row],
                "active": active,
            }
        )

    def remove_marker_by_id(self, marker_id: str) -> None:
        """
        Remove a marker by id (same as `RemoveMarker`).

        Does not broadcast; see `add_marker_row`.
        """
        self._apply_remove_marker({"marker_id": marker_id})

    def _apply_move_marker(self, params: dict[str, Any]) -> None:
        """Update `self.markers` when a client sends `MoveMarker`."""
        mid = str(params["marker_id"])
        fp = params["from_position"]
        tp = params["to_position"]
        if (
            not isinstance(fp, list | tuple)
            or len(fp) != 2
            or not isinstance(tp, list | tuple)
            or len(tp) != 2
        ):
            raise ValueError("from_position and to_position must be [col, row]")
        from_hex = Hex.from_hex_col_row(HexColRow(col=int(fp[0]), row=int(fp[1])))
        to_hex = Hex.from_hex_col_row(HexColRow(col=int(tp[0]), row=int(tp[1])))
        if from_hex == to_hex:
            return

        idx: int | None = None
        cur: dict[str, Any] | None = None
        for i, m in enumerate(self.markers):
            if str(m.get("id")) == mid:
                idx = i
                cur = dict(m)
                break
        if cur is None or idx is None:
            raise ValueError(f"Unknown marker {mid!r}")
        pos = cur.get("position")
        if not isinstance(pos, list | tuple) or len(pos) != 2:
            raise ValueError("marker has invalid position")
        if int(pos[0]) != int(fp[0]) or int(pos[1]) != int(fp[1]):
            raise ValueError("from_position does not match server marker position")

        state = self.action_manager.current_state
        if not self._marker_destination_allowed(state, cur, to_hex):
            raise ValueError("Illegal marker placement")

        new_row = {**cur, "position": [int(tp[0]), int(tp[1])]}
        self.markers = [dict(m) for m in self.markers]
        self.markers[idx] = new_row

    def _apply_add_marker(self, params: dict[str, Any]) -> None:
        mid = str(params["marker_id"])
        mtype = str(params["marker_type"])
        pos = params["position"]
        active = bool(params.get("active", True))
        if not mid or not mtype:
            raise ValueError("marker_id and marker_type are required")
        if not isinstance(pos, list | tuple) or len(pos) != 2:
            raise ValueError("position must be [col, row]")
        if any(str(m.get("id")) == mid for m in self.markers):
            raise ValueError(f"duplicate marker id {mid!r}")
        mg = self.marker_graphics
        if mg is not None and mtype not in mg:
            raise ValueError(
                f"unknown marker type {mtype!r} (no marker_graphics entry)"
            )
        to_hex = Hex.from_hex_col_row(HexColRow(col=int(pos[0]), row=int(pos[1])))
        state = self.action_manager.current_state
        row = {
            "id": mid,
            "type": mtype,
            "position": [int(pos[0]), int(pos[1])],
            "active": active,
        }
        if not self._marker_destination_allowed(state, row, to_hex):
            raise ValueError("Illegal marker placement")
        self.markers = [*self.markers, row]

    def _apply_remove_marker(self, params: dict[str, Any]) -> None:
        mid = str(params["marker_id"])
        if not any(str(m.get("id")) == mid for m in self.markers):
            raise ValueError(f"Unknown marker {mid!r}")
        self.markers = [m for m in self.markers if str(m.get("id")) != mid]

    def _movement_budget_for_unit(self, state: GameState, unit_id: str) -> float:
        gd = self._game_definition
        fn = getattr(gd, "movement_budget_for_unit", None)
        if callable(fn):
            return float(fn(state, unit_id))
        return DEFAULT_MOVEMENT_BUDGET

    def _zoc_hexes_for_unit(self, state: GameState, unit_id: str) -> frozenset[Hex] | None:
        gd = self._game_definition
        fn = getattr(gd, "zoc_hexes_for_unit", None)
        if not callable(fn):
            return None
        raw = fn(state, unit_id)
        if raw is None:
            return None
        if isinstance(raw, frozenset):
            return raw
        return frozenset(raw)

    def _validate_move_unit_request(
        self,
        state: GameState,
        params: dict[str, Any],
        player: PlayerInfo,
        *,
        is_retreat_fulfillment: bool = False,
    ) -> None:
        """
        Authoritative checks before `hexengine.state.actions.MoveUnit` is built.

        Uses terrain costs, occupancy, and the title movement budget (see
        `GameDefinition.movement_budget_for_unit` when implemented).
        """
        unit_id = params.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id.strip():
            raise ValueError("MoveUnit requires non-empty unit_id")

        fh, th = params.get("from_hex"), params.get("to_hex")
        if not isinstance(fh, dict) or not isinstance(th, dict):
            raise ValueError("MoveUnit requires from_hex and to_hex objects")
        from_hex = Hex(**fh)
        to_hex = Hex(**th)
        if from_hex == to_hex:
            raise ValueError("MoveUnit requires a destination different from from_hex")

        unit = state.board.units.get(unit_id)
        if unit is None:
            raise ValueError(f"Unknown unit {unit_id!r}")
        if not unit.active:
            raise ValueError(f"Unit {unit_id!r} is not active")
        if unit.faction != player.faction:
            raise ValueError("That unit is not yours")
        if unit.position != from_hex:
            raise ValueError("from_hex does not match the unit's position")

        if is_retreat_fulfillment:
            rem = self._retreat_obligation_hexes_remaining(state, unit_id)
            if rem is None:
                raise ValueError("No retreat obligation for this unit")
            leg = distance(from_hex, to_hex)
            if leg != rem:
                raise ValueError(
                    f"Retreat move must cover exactly {rem} hexes (cube distance); got {leg}"
                )
            budget = float(rem)
            # Retreat cannot pass through enemy ZOC unless the same hex is also in
            # friendly ZOC (overlap cancels enemy control for retreat routing).
            title_zoc = self._zoc_hexes_for_unit(state, unit_id)
            enemy_only = retreat_impassable_enemy_zoc_hexes(
                state, unit_id, enemy_zoc_ring=title_zoc
            )
            if not is_valid_move(
                state,
                unit_id,
                to_hex,
                budget,
                zoc_hexes=None,
                blocked_hexes=enemy_only,
            ):
                raise ValueError("Illegal retreat path for current terrain")
            return

        if self._faction_has_pending_retreat(state, player.faction):
            raise ValueError("Complete mandatory retreat before other moves")

        if not phase_allows_unit_move(state.turn.current_phase):
            raise ValueError(
                "Moves are only allowed in a movement phase "
                f"(current: {state.turn.current_phase!r})"
            )

        budget = self._movement_budget_for_unit(state, unit_id)
        zoc = self._zoc_hexes_for_unit(state, unit_id)
        if not is_valid_move(state, unit_id, to_hex, budget, zoc_hexes=zoc):
            raise ValueError("Illegal move for current terrain and movement budget")

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
                from ..hexes.types import (
                    Hex,  # Import here to avoid circular dependency
                )

                return MoveUnit(
                    unit_id=params["unit_id"],
                    from_hex=Hex(**params["from_hex"]),
                    to_hex=Hex(**params["to_hex"]),
                )
            case "DeleteUnit":
                return DeleteUnit(unit_id=params["unit_id"])
            case "AddUnit":
                from ..hexes.types import Hex

                raw_attrs = params.get("attributes")
                inst = dict(raw_attrs) if isinstance(raw_attrs, dict) else {}
                merged = merge_spawn_attributes(
                    self._game_definition,
                    str(params["unit_type"]),
                    inst,
                    state=self.action_manager.current_state,
                )
                sk_raw = params.get("stack_index")
                sk_opt: int | None
                if sk_raw is None or sk_raw == "":
                    sk_opt = None
                else:
                    sk_opt = int(sk_raw)
                raw_g = params.get("graphics")
                g_opt: str | None
                if raw_g is None or raw_g == "":
                    g_opt = None
                else:
                    gs = str(raw_g).strip()
                    g_opt = gs if gs else None
                return AddUnit(
                    unit_id=params["unit_id"],
                    unit_type=params["unit_type"],
                    faction=params["faction"],
                    position=Hex(**params["position"]),
                    health=int(params.get("health", 100)),
                    stack_index=sk_opt,
                    graphics=g_opt,
                    attributes=merged,
                )
            case "SpendAction":
                return SpendAction(amount=params.get("amount", 1))
            case "NextPhase":
                return NextPhase(
                    new_faction=params["new_faction"],
                    new_phase=params["new_phase"],
                    max_actions=params["max_actions"],
                    new_schedule_index=int(params.get("new_schedule_index", 0)),
                )
            case _:
                raise ValueError(f"Unknown action type: {action_type}")

    async def _handle_leave_game(self, player_id: str) -> None:
        """Handle a player leaving the game."""
        player = self.players.get(player_id)
        if player:
            self.logger.info(f"Player {player.player_name} disconnected")
            await self._broadcast_player_left(player)
            # Free faction slot: each WebSocket gets a new player_id on reconnect.
            if self.faction_to_player.get(player.faction) == player_id:
                del self.faction_to_player[player.faction]
            del self.players[player_id]

    async def _send_state_update(self, player_id: str) -> None:
        """Send current game state to a specific player."""
        state_dict = self._serialize_state(self.action_manager.current_state)
        update = StateUpdate(
            game_state=state_dict,
            sequence_number=self.sequence_number,
            map_display=self.map_display,
            global_styles=self.global_styles,
            unit_graphics=self.unit_graphics,
            marker_graphics=self.marker_graphics,
            markers=self.markers,
            server_package_version=self._server_package_version,
            turn_rules=self._turn_rules_wire(),
            suggested_focus_unit_id=self._suggested_focus_unit_id_for_player_id(
                player_id
            ),
            retreat_obligations=self._retreat_obligations_for_player_id(player_id),
        )
        await self._send_message(player_id, update.to_message())

    async def _broadcast_state_update(self) -> None:
        """Broadcast current game state to all connected players."""
        self.sequence_number += 1
        state_dict = self._serialize_state(self.action_manager.current_state)
        turn_rules = self._turn_rules_wire()
        for player_id, player in self.players.items():
            if player.connected:
                update = StateUpdate(
                    game_state=state_dict,
                    sequence_number=self.sequence_number,
                    map_display=self.map_display,
                    global_styles=self.global_styles,
                    unit_graphics=self.unit_graphics,
                    marker_graphics=self.marker_graphics,
                    markers=self.markers,
                    server_package_version=self._server_package_version,
                    turn_rules=turn_rules,
                    suggested_focus_unit_id=self._suggested_focus_unit_id_for_player_id(
                        player_id
                    ),
                    retreat_obligations=self._retreat_obligations_for_player_id(
                        player_id
                    ),
                )
                await self._send_message(player_id, update.to_message())

    async def _broadcast_player_joined(self, player: PlayerInfo) -> None:
        """Notify all players that someone joined."""
        message = PlayerJoinedWire.from_player_info(player).to_message()
        for player_id, p in self.players.items():
            if p.connected and player_id != player.player_id:
                await self._send_message(player_id, message)

    async def _broadcast_player_left(self, player: PlayerInfo) -> None:
        """Notify all players that someone left."""
        message = PlayerLeftWire.from_player_info(player).to_message()
        for player_id, p in self.players.items():
            if p.connected and player_id != player.player_id:
                await self._send_message(player_id, message)

    async def _send_error(self, player_id: str, error_message: str) -> None:
        """Send an error message to a player."""
        await self._send_message(player_id, ServerError(error=error_message).to_message())

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


async def _dispatch_leave_game(server: GameServer, player_id: str, _message: Message) -> None:
    await server._handle_leave_game(player_id)


_ClientInboundHandler = Callable[[GameServer, str, Message], Awaitable[None]]

_CLIENT_INBOUND_HANDLERS: dict[str, _ClientInboundHandler] = {
    JoinGameRequest.wire_type: GameServer._handle_join_game,
    ActionRequest.wire_type: GameServer._handle_action_request,
    UndoRequest.wire_type: GameServer._handle_undo_request,
    RedoRequest.wire_type: GameServer._handle_redo_request,
    LeaveGameRequest.wire_type: _dispatch_leave_game,
    LoadSnapshotRequest.wire_type: GameServer._handle_load_snapshot,
}
