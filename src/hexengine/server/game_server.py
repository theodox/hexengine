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
from pathlib import Path
from typing import Any

from ..arcs import ArcSpec
from ..arcs.registry import TurnArcRegistry
from ..game_log import GameLogger, game_logger_scope
from ..game_packs.resources import (
    infer_pack_id_from_root,
    infer_pack_root_from_definition,
    pack_asset_base_url,
    pack_asset_url,
)
from ..gamedef.protocol import GameDefinition
from ..gamedef.unit_attributes import (
    merge_spawn_attributes,
    validate_unit_attributes_patch,
)
from ..hexes.math import distance
from ..hexes.types import Hex, HexColRow
from ..hooks.core import ENGINE_DEFAULT
from ..hooks.inform_popup import InformPopupContext, default_inform_popup_for_viewer
from ..hooks.internal import get_engine_catalog_hook, validate_title_contract
from ..hooks.map_selection_registry import bound_map_selection_kinds
from ..hooks.movement import MoveContext
from ..hooks.title import TitleHooks, read_title_hooks_from_definition
from ..hooks.ui import (
    AdvanceGateInteractionContext,
    CombatEventSummary,
    CombatInteractionContext,
    PhaseBannerContext,
    TurnActionDockContext,
    default_advance_gate_banners_for_viewer,
    default_combat_instruction_for_viewer,
    default_phase_banner_text_for_viewer,
)
from ..package_version import hexes_package_version
from ..state import ActionManager, GameState
from ..state.action_manager import StateAction
from ..state.actions import (
    AddUnit,
    DeleteUnit,
    MoveUnit,
    NextPhase,
    PatchUnitAttributes,
    SpendAction,
    WriteHexengineMovementArc,
)
from ..state.logic import (
    DEFAULT_MOVEMENT_BUDGET,
    is_valid_move,
)
from ..state.marker_placement import (
    MarkerPlacementRule,
    default_marker_destination_allowed,
)
from ..state.phase_rules import (
    phase_allows_movement_interrupt_pass,
    phase_allows_unit_move,
)
from ..state.snapshot import game_state_from_wire_dict, game_state_to_wire_dict
from .arcs import (
    COMBAT_ARC_REQUIRED_MSG,
    begin_routine_slot,
    drive_movement_arc_event,
    execute_authority_attack_request,
    finish_combat_arc_dispatch,
    handle_authority_move_unit_normal,
    handle_authority_retreat_path_move_unit,
    lookup_arc_spec,
    move_unit_is_combat_advance_fulfillment,
    read_movement_arc,
    resolve_active_segment_owner,
    restore_routine_cursor,
    schedule_next_phase_info,
    try_combat_arc_move_unit,
    try_combat_arc_rpc,
    turn_arc_registry_from_hooks,
    validate_retreat_fulfillment_stack,
)
from .map_selection import compute_map_selection_preview
from .preview import compute_marker_drag_preview, compute_unit_drag_preview
from .protocol import (
    ActionRequest,
    ActionResult,
    CombatEventWire,
    InspectRequest,
    JoinGameRequest,
    LeaveGameRequest,
    LoadSnapshotRequest,
    MapSelectionPreviewRequest,
    MapSelectionPreviewWire,
    MarkerPreviewRequest,
    MarkerPreviewWire,
    Message,
    PlayerInfo,
    PlayerJoinedWire,
    PlayerLeftWire,
    RedoRequest,
    ServerError,
    ServerLogEvent,
    StateUpdate,
    UIPopupWire,
    UndoRequest,
    UnitPreviewRequest,
    UnitPreviewWire,
)


def _turn_rules_rota_id(entries: list[dict[str, Any]]) -> str:
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _resolve_title_resource_href(
    game_definition: Any,
    rel: str,
    *,
    pack_root: Path | None,
    asset_base_url: str | None,
) -> str | None:
    """
    Resolve a title resource reference to a browser URL.

    Pack-relative paths (no ``..``) map to ``asset_base_url`` when set; absolute
    paths and http(s) URLs pass through unchanged.
    """
    raw = (rel or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute() or ".." in p.parts:
        return raw.replace("\\", "/")
    if raw.startswith(("http://", "https://", "/")):
        return raw.replace("\\", "/")
    root = pack_root
    if root is None:
        root = infer_pack_root_from_definition(game_definition)
    if root is None:
        return None
    return pack_asset_url(
        root,
        raw,
        asset_base_url=asset_base_url,
        static_root=None,
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
        initial_state: GameState | None = None,
        map_display: dict[str, Any] | None = None,
        global_styles: dict[str, Any] | None = None,
        unit_graphics: dict[str, Any] | None = None,
        marker_graphics: dict[str, Any] | None = None,
        markers: list[dict[str, Any]] | None = None,
        marker_placement_rule: MarkerPlacementRule | None = None,
        *,
        game_definition: GameDefinition,
        pack_id: str | None = None,
        pack_root: Path | str | None = None,
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
            pack_id: Owning pack id for ``/pack/<id>/`` asset URLs (optional).
            pack_root: Pack directory (``games/<id>/``); inferred when omitted.
        """
        init_state = initial_state or GameState.create_empty()
        raw_tek = getattr(game_definition.game_data, "title_state_extension_key", None)
        if isinstance(raw_tek, str) and raw_tek.strip():
            init_state = init_state.with_title_bucket_key(raw_tek.strip())
        self.action_manager = ActionManager(init_state)
        self.map_display = map_display
        self.global_styles = global_styles
        self.unit_graphics = unit_graphics
        self.marker_graphics = marker_graphics
        self.markers = [] if markers is None else list(markers)
        self._marker_placement_rule = marker_placement_rule
        if self._marker_placement_rule is None:
            # Optional: allow titles to declare marker placement rules on the game definition
            # so local preview and the authoritative server can share one policy surface.
            gd_rule = getattr(game_definition, "marker_placement_rule", None)
            if callable(gd_rule):
                self._marker_placement_rule = gd_rule
        self._server_package_version = hexes_package_version()
        self._game_definition = game_definition
        self._pack_id = (pack_id or "").strip() or None
        self._pack_root = Path(pack_root).resolve() if pack_root is not None else None
        self._pack_context_ready = False
        self.hooks = self._bind_title_hooks()
        self.game_data = self._game_definition.game_data
        validate_title_contract(game_definition)

        # Player management
        self.players: dict[str, PlayerInfo] = {}
        self.faction_to_player: dict[str, str] = {}  # faction -> player_id

        # State tracking
        self.sequence_number = 0

        # Callbacks for sending messages to clients
        self.message_handlers: list[Callable[[str, Message], None]] = []

        self.logger = logging.getLogger("game_server")
        self.logger.info("Game server initialized")

        self._pending_game_log_events: deque[tuple[str, str, str]] = deque()
        self._movement_arc_spec_cache: ArcSpec | None = None

        reg = self.turn_arc_registry()
        if reg is not None:
            self.turn_order = reg.schedule.turn_order_entries()
        else:
            self.turn_order = self._game_definition.turn_order()
        self.logger.info(f"Turn order: {self.turn_order}")

        self.begin_routine_slot(
            int(self.action_manager.current_state.turn.schedule_index)
        )

    def turn_arc_registry(self) -> TurnArcRegistry | None:
        return turn_arc_registry_from_hooks(self.hooks)

    def lookup_arc_spec(self, arc_id: str) -> ArcSpec | None:
        return lookup_arc_spec(self, arc_id)

    def begin_routine_slot(self, schedule_index: int) -> None:
        begin_routine_slot(self, schedule_index)

    def restore_routine_cursor(self) -> None:
        restore_routine_cursor(self)

    def _segment_owner_faction(self, state: GameState | None = None) -> str:
        st = state if state is not None else self.action_manager.current_state
        return resolve_active_segment_owner(self, st) or str(st.turn.current_faction)

    def _actor_may_act(
        self, player_faction: str, state: GameState | None = None
    ) -> bool:
        return str(player_faction) == self._segment_owner_faction(state)

    def movement_arc_spec(self) -> ArcSpec | None:
        """Built-in stepwise movement arc (host-bound effects, cached per server)."""

        override = self.hooks.arcs.movement_arc_spec()
        if isinstance(override, ArcSpec):
            return override
        if override is not ENGINE_DEFAULT:
            return None
        if self._movement_arc_spec_cache is None:
            from ..hooks.internal.authoring_bridge import (
                build_default_movement_arc_spec,
            )

            self._movement_arc_spec_cache = build_default_movement_arc_spec(self)
        return self._movement_arc_spec_cache

    def movement_arc_effects_binding(self):
        """Host-bound movement arc guards/effects (used by authoring_bridge only)."""

        from .arcs.movement_arc_effects import MovementArcEffects

        return MovementArcEffects(self)

    @property
    def game_state(self) -> GameState:
        """Authoritative match state (same object as `action_manager.current_state`)."""

        return self.action_manager.current_state

    # --- GameDefinition access helpers (optional hooks / attributes) ---
    def _bind_title_hooks(self) -> TitleHooks:
        """
        Bind the title hook bundle once per server instance.

        Titles may provide either:
        - `game_definition.hooks` as a `TitleHooks` instance, or
        - `game_definition.hooks()` returning a `TitleHooks` instance.

        If absent or invalid, the server uses an empty `TitleHooks()` bundle.
        """

        return read_title_hooks_from_definition(self._game_definition)

    def _ensure_pack_context(self) -> None:
        if self._pack_context_ready:
            return
        if self._pack_root is None:
            self._pack_root = infer_pack_root_from_definition(self._game_definition)
        if self._pack_id is None and self._pack_root is not None:
            self._pack_id = infer_pack_id_from_root(self._pack_root)
        self._pack_context_ready = True

    def _pack_asset_base_url(self) -> str | None:
        self._ensure_pack_context()
        if not self._pack_id:
            return None
        return pack_asset_base_url(self._pack_id)

    def _resolve_pack_resource_href(self, rel: str) -> str | None:
        self._ensure_pack_context()
        return _resolve_title_resource_href(
            self._game_definition,
            rel,
            pack_root=self._pack_root,
            asset_base_url=self._pack_asset_base_url(),
        )

    def _call(
        self,
        name: str,
        fallback: Any,
        /,
        *args: Any,
        type: type[Any] | tuple[type[Any], ...] | None = None,
        coerce: bool = False,
    ) -> Any:
        """
        Call an optional `GameDefinition` hook by name.

        - If the hook is missing or not callable: return `fallback`.
        - If `type` is provided:
          - with `coerce=False` (default): raise `TypeError` when the return value is not an instance.
          - with `coerce=True`: attempt to coerce the return value to `type` (single-type only)
            using the type constructor (e.g. `int(x)`, `float(x)`, `str(x)`). If coercion fails,
            raise `TypeError`.
        """
        fn = getattr(self._game_definition, name, None)
        if not callable(fn):
            return fallback
        out = fn(*args)
        if type is not None and not isinstance(out, type):
            if coerce and isinstance(type, type):
                try:
                    out = type(out)
                except Exception as e:
                    raise TypeError(
                        f"GameDefinition.{name} returned {type(out).__name__}; "
                        f"could not coerce to {type.__name__}"
                    ) from e
            else:
                raise TypeError(
                    f"GameDefinition.{name} returned {type(out).__name__}, expected {type!r}"
                )
        return out

    def _get_attr(
        self,
        name: str,
        fallback: Any,
        /,
        *,
        type: type[Any] | tuple[type[Any], ...] | None = None,
        strip: bool = False,
    ) -> Any:
        """
        Read an optional `GameDefinition` attribute by name.

        - If missing: return `fallback`.
        - If `type` is provided: return `fallback` when the value is not an instance.
        - If `strip=True` and the value is a string: strip whitespace before returning.
        """
        raw = getattr(self._game_definition, name, fallback)
        if type is not None and not isinstance(raw, type):
            return fallback
        if strip and isinstance(raw, str):
            return raw.strip()
        return raw

    def _serialize_state(self, state: GameState) -> dict[str, Any]:
        """Serialize GameState into JSON-safe primitives."""
        return game_state_to_wire_dict(state)

    def _get_next_phase(self) -> dict:
        """Get the next phase in the turn order."""

        scheduled = schedule_next_phase_info(self)
        if scheduled is not None:
            return scheduled
        return self._game_definition.get_next_phase(self.action_manager.current_state)

    def _suggested_focus_unit_id_for_player_id(self, player_id: str) -> str | None:
        """Per-viewer selection hint from optional GameDefinition focus hook."""
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

    def _retreat_obligations_for_player_id(
        self, player_id: str
    ) -> dict[str, int] | None:
        """
        Per-viewer mandatory retreat obligations for the player's faction.

        Only populated when the title exposes retreat_obligation_hexes_remaining.
        """
        player = self.players.get(player_id)
        if player is None:
            return None
        fac = str(player.faction).strip() if player.faction else ""
        if not fac:
            return None
        st = self.action_manager.current_state
        out: dict[str, int] = {}
        for uid, u in st.board.units.items():
            if not u.active or u.faction != fac:
                continue
            n = self._retreat_obligation_hexes_remaining(st, uid)
            if n is None:
                continue
            out[str(uid)] = int(n)
        return out or None

    def _title_extension_key(self) -> str | None:
        raw = self.game_data.title_state_extension_key
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return None

    def _title_bucket(self, state: GameState | None = None) -> dict[str, Any]:
        """Title-owned extension bucket for this match (empty when no key configured)."""
        from ..state.title_extension import title_bucket

        ek = self._title_extension_key()
        if not ek:
            return {}
        st = state if state is not None else self.action_manager.current_state
        return title_bucket(st, ek)

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
        gd = self.game_data
        # Thin clients need a scalar stacking limit for drag preview and warnings.
        mx = gd.max_active_units_per_hex
        if mx is not None:
            try:
                n = int(mx)
            except (TypeError, ValueError):
                n = 0
            if n > 0:
                out["max_active_units_per_hex"] = n
        # Optional title-provided UI metadata (labels, CSS class names, and CSS).
        try:
            facs = list(self._game_definition.available_factions())
        except Exception:
            facs = []
        if facs:
            fd = getattr(self._game_definition, "faction_display_name", None)
            fd_map = gd.faction_display_names
            fc = getattr(self._game_definition, "faction_css_class", None)
            fc_map = gd.faction_css_classes
            resolved: list[tuple[str, str | None, str | None]] = []
            for f in facs:
                fid = str(f)
                label: str | None = None
                if callable(fd):
                    try:
                        raw = fd(fid)
                        if isinstance(raw, str) and raw.strip():
                            label = raw.strip()
                    except Exception:
                        label = None
                if label is None and isinstance(fd_map, dict):
                    raw = fd_map.get(fid)
                    if isinstance(raw, str) and raw.strip():
                        label = raw.strip()
                css_class: str | None = None
                if callable(fc):
                    try:
                        raw = fc(fid)
                        if isinstance(raw, str) and raw.strip():
                            css_class = raw.strip()
                    except Exception:
                        css_class = None
                if css_class is None and isinstance(fc_map, dict):
                    raw = fc_map.get(fid)
                    if isinstance(raw, str) and raw.strip():
                        css_class = raw.strip()
                resolved.append((fid, label, css_class))

            missing_labels = sorted(fid for fid, lab, _ in resolved if lab is None)
            if missing_labels:
                ids = ", ".join(missing_labels)
                out["faction_display_contract_error"] = {
                    "schema": 1,
                    "text": (
                        "Hexengine faction UI contract: every schedule faction needs a "
                        f"non-empty display label. Missing labels for: {ids}. "
                        "Provide `GameData.faction_display_names` (for example the "
                        "`[faction_display_names]` table in title game_data TOML) or implement "
                        "`GameDefinition.faction_display_name(faction_id) -> str`."
                    ),
                    "missing_faction_ids": missing_labels,
                }
            else:
                rows: list[dict[str, Any]] = []
                for fid, lab, css_class in resolved:
                    assert lab is not None
                    row: dict[str, Any] = {"id": fid, "label": lab}
                    if css_class is not None:
                        row["css_class"] = css_class
                    rows.append(row)
                out["faction_ui"] = {"schema": 1, "factions": rows}
                css_text: str | None = None
                tcss = gd.title_css
                if isinstance(tcss, str) and tcss.strip():
                    css_text = tcss.strip()
                else:
                    css_raw = getattr(self._game_definition, "title_css", None)
                    if callable(css_raw):
                        try:
                            v = css_raw()
                            if isinstance(v, str) and v.strip():
                                css_text = v
                        except Exception:
                            css_text = None
                    elif isinstance(css_raw, str) and css_raw.strip():
                        css_text = css_raw
                if css_text is not None:
                    out["faction_ui"]["css"] = css_text
                css_href: str | None = None
                tfile = gd.title_css_file
                if isinstance(tfile, str) and tfile.strip():
                    css_href = self._resolve_pack_resource_href(tfile.strip())
                else:
                    css_file_raw = getattr(
                        self._game_definition, "title_css_file", None
                    )
                    if callable(css_file_raw):
                        try:
                            v = css_file_raw()
                            if isinstance(v, str) and v.strip():
                                css_href = self._resolve_pack_resource_href(v)
                        except Exception:
                            css_href = None
                    elif isinstance(css_file_raw, str) and css_file_raw.strip():
                        css_href = self._resolve_pack_resource_href(css_file_raw)
                if css_href:
                    out["faction_ui"]["css_href"] = css_href
        # Optional title-provided highlight styling for move/retreat/marker previews.
        ui = dict(gd.hex_highlight_ui) if gd.hex_highlight_ui else None
        if ui:
            # Minimal validation + normalization: keep only known keys.
            out_ui: dict[str, Any] = {"schema": 1}
            for k in (
                "move_hex_class",
                "retreat_hex_class",
                "retreat_through_hex_class",
                "marker_hex_class",
            ):
                raw = ui.get(k)
                if isinstance(raw, str) and raw.strip():
                    out_ui[k] = raw.strip()
            if len(out_ui) > 1:
                out["ui"] = out_ui
        shell = dict(gd.shell_ui) if gd.shell_ui else None
        if shell:
            out_shell: dict[str, Any] = {"schema": 1}
            for k, v in shell.items():
                if k == "attack_planning_phases" and isinstance(v, list):
                    out_shell[k] = [str(p).strip() for p in v if str(p).strip()]
                elif isinstance(v, str) and v.strip():
                    out_shell[k] = v.strip()
            if len(out_shell) > 1:
                out["shell_ui"] = out_shell
        kind_styles = (
            dict(gd.interaction_kind_styles) if gd.interaction_kind_styles else None
        )
        if kind_styles:
            out["interaction_kind_styles"] = {
                str(k).strip(): str(v).strip()
                for k, v in kind_styles.items()
                if str(k).strip() and isinstance(v, str) and str(v).strip()
            }
        tek = self._title_extension_key()
        if tek:
            out["title_state_extension_key"] = tek
        attr_key = gd.movement_budget_attribute_key
        if isinstance(attr_key, str) and attr_key.strip():
            out["movement_budget_attribute"] = attr_key.strip()
        asset_base = self._pack_asset_base_url()
        if asset_base:
            out["asset_base_url"] = asset_base
        out_cc: dict[str, Any] = {
            "schema": 1,
            "features": sorted(
                f
                for f in (
                    "suggested_focus_unit_id"
                    if callable(
                        getattr(
                            self._game_definition,
                            "focus_unit_id_after_state_sync",
                            None,
                        )
                    )
                    else None,
                    "retreat_obligations"
                    if getattr(
                        self.hooks.movement, "retreat_obligation_hexes_remaining", None
                    )
                    else None,
                    "zoc_hexes_for_unit"
                    if getattr(self.hooks.movement, "zoc_hexes_for_unit", None)
                    is not None
                    else None,
                    "attack_planning_ui"
                    if (
                        getattr(self.hooks.attack, "validate_attack", None) is not None
                        and getattr(self.hooks.attack, "resolve_attack", None)
                        is not None
                    )
                    else None,
                    "server_drag_previews",
                    "map_selection_previews"
                    if bound_map_selection_kinds(self.hooks)
                    else None,
                )
                if f is not None
            ),
        }
        cc_manifest = getattr(gd, "client_contract", None)
        if cc_manifest is not None:
            wire_manifest = cc_manifest.to_wire_dict()
            for key in ("select_modes", "panel_action_routes"):
                rows = wire_manifest.get(key)
                if rows:
                    out_cc[key] = rows
        out["client_contract"] = out_cc
        return out

    def _iter_board_hexes(self, state: GameState) -> list[Hex]:
        """
        Hexes considered "on board" for previews and marker placement.

        Prefer scenario `map_display.grid_hexes` (explicit board footprint); fall back to
        explicit terrain locations when grid_hexes is not provided.
        """
        md = self.map_display if isinstance(self.map_display, dict) else None
        raw = md.get("grid_hexes") if isinstance(md, dict) else None
        if isinstance(raw, list) and raw:
            out: list[Hex] = []
            for item in raw:
                if isinstance(item, list | tuple) and len(item) == 3:
                    try:
                        out.append(Hex(int(item[0]), int(item[1]), int(item[2])))
                    except Exception:
                        continue
            if out:
                return out
        # No explicit grid list; derive from declared dimensions (scenario uses odd-q col/row).
        if isinstance(md, dict):
            cols = md.get("hex_columns")
            rows = md.get("hex_rows")
            try:
                icols = int(cols) if cols is not None else 0
                irows = int(rows) if rows is not None else 0
            except (TypeError, ValueError):
                icols = 0
                irows = 0
            if icols > 0 and irows > 0:
                from ..map.layout import iter_map_grid_hex_col_rows

                return list(iter_map_grid_hex_col_rows(icols, irows))
        return list(state.board.locations.keys())

    def _invoke_phase_transition_hook(self) -> None:
        raw = self._call(
            "after_phase_transition", None, self.action_manager.current_state
        )
        if raw is None:
            return
        if not isinstance(raw, list):
            raise TypeError(
                "GameDefinition.after_phase_transition must return None or "
                "list[StateAction]"
            )
        for action in raw:
            if not isinstance(action, StateAction):
                raise TypeError(
                    "after_phase_transition entries must be StateAction instances"
                )
            try:
                self.action_manager.execute(action)
            except Exception as e:
                self.logger.error(
                    "after_phase_transition action failed: %s", e, exc_info=True
                )

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
        # Be forgiving about case for URL/querystring inputs ("Union" vs "union").
        if isinstance(requested, str):
            requested_norm = requested.strip().lower()
        else:
            requested_norm = None
        available_by_norm = {str(f).strip().lower(): str(f) for f in available_factions}

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
        elif requested_norm not in available_by_norm:
            await self._send_error(
                player_id,
                f"Invalid faction: {requested}. Available: {available_factions}",
            )
            return
        else:
            requested_canon = available_by_norm[requested_norm]
            if requested_canon in self.faction_to_player:
                await self._send_error(
                    player_id, f"Faction {requested_canon} already taken"
                )
                return
            faction = requested_canon

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

    def _resolve_auto_advance_policy(
        self, raw: bool | object, *, catalog_path: str | None
    ) -> bool:
        """Resolve title hook result; optional engine catalog when ``raw`` is ``ENGINE_DEFAULT``."""

        if raw is ENGINE_DEFAULT:
            if catalog_path is None:
                return False
            catalog = get_engine_catalog_hook(catalog_path)
            if catalog is None:
                return False
            raw = catalog(self.action_manager.current_state)
        return bool(raw)

    def _maybe_auto_advance_phase(
        self,
        raw: bool | object,
        *,
        catalog_path: str | None,
        log_reason: str,
    ) -> bool:
        """Apply ``NextPhase`` when policy (title hook or catalog) returns true."""

        if not self._resolve_auto_advance_policy(raw, catalog_path=catalog_path):
            return False
        next_phase_info = self._get_next_phase()
        self.logger.info("Auto-advancing phase (%s)", log_reason)
        next_phase_action = NextPhase(
            new_faction=next_phase_info["faction"],
            new_phase=next_phase_info["phase"],
            max_actions=next_phase_info["max_actions"],
            new_schedule_index=int(next_phase_info["schedule_index"]),
        )
        self.action_manager.execute(next_phase_action)
        self._after_next_phase_applied()
        self.logger.info(
            "Advanced to %s-%s",
            next_phase_info["faction"],
            next_phase_info["phase"],
        )
        return True

    def _after_next_phase_applied(self) -> None:
        """Clear engine movement arc, then run the title phase-transition hook.

        Title combat bookkeeping cleanup (phase-scoped bucket keys) is owned by the
        title via `GameDefinition.after_phase_transition` returning `StateAction`s.
        """
        try:
            self.action_manager.execute(WriteHexengineMovementArc(None))
        except Exception as e:
            self.logger.error(
                "WriteHexengineMovementArc clear failed: %s", e, exc_info=True
            )
        self.begin_routine_slot(
            int(self.action_manager.current_state.turn.schedule_index)
        )
        self._invoke_phase_transition_hook()

    def _retreat_obligation_hexes_remaining(
        self, state: GameState, unit_id: str | None
    ) -> int | None:
        if not unit_id:
            return None
        out = self.hooks.movement.retreat_remaining(state, unit_id)
        if out is ENGINE_DEFAULT:
            return None
        try:
            n = int(out) if out is not None else None
        except (TypeError, ValueError):
            return None
        return n if n is not None and n > 0 else None

    def _faction_has_pending_retreat(self, state: GameState, faction: str) -> bool:
        out = self.hooks.movement.faction_retreat_pending(state, faction)
        if out is ENGINE_DEFAULT:
            return False
        return bool(out)

    def _resolve_blocks_routine_phase_advance(
        self, state: GameState | None = None
    ) -> bool:
        from ..arcs.segment_wire import segment_blocks_routine_phase_advance

        st = state if state is not None else self.action_manager.current_state
        return segment_blocks_routine_phase_advance(
            self, st, viewer_faction=str(st.turn.current_faction)
        )

    def _combat_instruction_for_viewer(
        self,
        state: GameState,
        recipient_faction: str | None,
        *,
        outcome: str,
        retreat_owner_faction: str | None,
    ) -> tuple[str, str]:
        """Resolve per-viewer combat line via `UIHooks` or engine default."""

        ctx = CombatInteractionContext(
            state=state,
            viewer_faction=recipient_faction,
            outcome=outcome,
            retreat_owner_faction=retreat_owner_faction,
            shell_ui=dict(self.game_data.shell_ui),
        )
        raw = self.hooks.ui.combat_instruction(ctx)
        if raw is ENGINE_DEFAULT:
            return default_combat_instruction_for_viewer(ctx)
        if (
            isinstance(raw, tuple)
            and len(raw) == 2
            and isinstance(raw[0], str)
            and isinstance(raw[1], str)
        ):
            return raw[0], raw[1]
        raise TypeError(
            "hooks.ui.combat_instruction_for_viewer must return (str, str) or hooks.ENGINE_DEFAULT"
        )

    def _advance_gate_banner_text_pair(
        self,
        state: GameState,
        viewer_faction: str | None,
        advancing_faction: str,
    ) -> tuple[str, str]:
        """Return (line for the advancing faction viewer, line for other viewers)."""

        ctx = AdvanceGateInteractionContext(
            state=state,
            viewer_faction=viewer_faction,
            advancing_faction=advancing_faction,
            shell_ui=dict(self.game_data.shell_ui),
        )
        raw = self.hooks.ui.advance_gate_banners(ctx)
        if raw is ENGINE_DEFAULT:
            return default_advance_gate_banners_for_viewer(ctx)
        if (
            isinstance(raw, tuple)
            and len(raw) == 2
            and isinstance(raw[0], str)
            and isinstance(raw[1], str)
        ):
            return raw[0], raw[1]
        raise TypeError(
            "hooks.ui.advance_gate_banners_for_viewer must return (str, str) or hooks.ENGINE_DEFAULT"
        )

    def _phase_interaction_banner_text(
        self, state: GameState, viewer_faction: str | None
    ) -> str:
        """Single line for the default phase `kind: phase` interaction row."""

        t = state.turn
        ctx = PhaseBannerContext(
            state=state,
            viewer_faction=viewer_faction,
            current_faction=str(t.current_faction),
            current_phase=str(t.current_phase),
            schedule_index=int(t.schedule_index),
            phase_actions_remaining=int(t.phase_actions_remaining),
        )
        raw = self.hooks.ui.phase_banner_text(ctx)
        if raw is ENGINE_DEFAULT:
            return default_phase_banner_text_for_viewer(ctx)
        if isinstance(raw, str):
            return raw
        raise TypeError(
            "hooks.ui.phase_banner_text_for_viewer must return str or hooks.ENGINE_DEFAULT"
        )

    def _phase_interaction_banner_html(
        self, state: GameState, viewer_faction: str | None
    ) -> str | None:
        """Optional HTML for the default phase interaction row (None when unset)."""

        t = state.turn
        ctx = PhaseBannerContext(
            state=state,
            viewer_faction=viewer_faction,
            current_faction=str(t.current_faction),
            current_phase=str(t.current_phase),
            schedule_index=int(t.schedule_index),
            phase_actions_remaining=int(t.phase_actions_remaining),
        )
        raw = self.hooks.ui.phase_banner_html(ctx)
        if raw is ENGINE_DEFAULT:
            return None
        if isinstance(raw, str):
            html = raw.strip()
            return html or None
        raise TypeError(
            "hooks.ui.phase_banner_html_for_viewer must return str or hooks.ENGINE_DEFAULT"
        )

    def _interaction_messages_for_player_id(
        self, player_id: str
    ) -> list[dict[str, Any]] | None:
        """
        Per-recipient transient UI messages delivered via `StateUpdate`.

        Schema (each entry): {"schema": 1, "kind": str, "text": str} plus optional
        html/dedupe_key/ttl_ms/css_class for client-side lifecycle and styling.
        When `html` is present the client renders it instead of `text`.
        """
        player = self.players.get(player_id)
        if player is None or not player.connected:
            return None
        st = self.action_manager.current_state

        from ..hooks.internal.ui_wire import interaction_messages_to_wire
        from ..ui.display import InteractionMessage

        # Title override: allow full control via hooks.ui.interaction_messages.
        viewer_faction = str(player.faction) if player.faction else None
        title_out = self.hooks.ui.messages(st, viewer_faction)
        if title_out is not ENGINE_DEFAULT:
            return interaction_messages_to_wire(title_out) or None

        out: list[InteractionMessage] = []

        # Phase/turn transition banner (deduped client-side).
        schedule_index = int(st.turn.schedule_index)
        phase_line = self._phase_interaction_banner_text(st, viewer_faction)
        phase_html = self._phase_interaction_banner_html(st, viewer_faction)
        out.append(
            InteractionMessage(
                kind="phase",
                text=phase_line,
                html=phase_html,
                dedupe_key=f"phase:{schedule_index}",
                ttl_ms=None,
                css_class="interaction-msg--phase",
            )
        )

        from ..hooks.ui_combat_messages import (
            CombatInteractionMessagesContext,
            default_combat_interaction_messages,
        )

        ek = self._title_extension_key()
        msg_ctx = CombatInteractionMessagesContext(
            state=st,
            viewer_faction=viewer_faction,
            extension_key=ek,
            current_segment=self.project_current_segment(
                st, viewer_faction=viewer_faction
            ),
            shell_ui=dict(self.game_data.shell_ui),
        )
        combat_raw = self.hooks.ui.combat_interaction_messages_for(msg_ctx)
        if combat_raw is ENGINE_DEFAULT:
            combat_rows = default_combat_interaction_messages(
                msg_ctx,
                combat_instruction=lambda outcome, ro: (
                    self._combat_instruction_for_viewer(
                        st,
                        viewer_faction,
                        outcome=outcome,
                        retreat_owner_faction=ro,
                    )
                ),
                advance_gate_banners=lambda adv_faction: (
                    self._advance_gate_banner_text_pair(st, viewer_faction, adv_faction)
                ),
            )
        elif isinstance(combat_raw, list):
            combat_rows = combat_raw
        else:
            raise TypeError(
                "hooks.ui.combat_interaction_messages must return "
                "list[InteractionMessage] or hooks.ENGINE_DEFAULT"
            )
        out.extend(combat_rows)

        return interaction_messages_to_wire(out) or None

    def _shell_ui_label(self, key: str, default: str) -> str:
        su = self.game_data.shell_ui
        if isinstance(su, dict):
            raw = su.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return default

    def project_current_segment(
        self, state: GameState, *, viewer_faction: str | None
    ) -> dict[str, Any] | None:
        from ..arcs.segment_wire import project_current_segment

        return project_current_segment(self, state, viewer_faction=viewer_faction)

    def _current_segment_for_player_id(self, player_id: str) -> dict[str, Any] | None:
        player = self.players.get(player_id)
        if player is None or not player.connected:
            return None
        viewer = str(player.faction).strip() if player.faction else ""
        if not viewer:
            return None
        return self.project_current_segment(
            self.action_manager.current_state, viewer_faction=viewer
        )

    def _turn_action_dock_context_for_player_id(
        self, player_id: str
    ) -> TurnActionDockContext | None:
        player = self.players.get(player_id)
        if player is None or not player.connected:
            return None
        st = self.action_manager.current_state
        viewer_faction = str(player.faction).strip() if player.faction else ""
        if not viewer_faction:
            return None
        turn = st.turn
        current_faction = str(turn.current_faction).strip()
        current_segment = self.project_current_segment(
            st, viewer_faction=viewer_faction
        )
        segment_owner = (
            str(current_segment.get("owner", "")).strip()
            if isinstance(current_segment, dict)
            else ""
        )
        viewer_is_turn_owner = (
            viewer_faction == segment_owner
            if segment_owner
            else viewer_faction == current_faction
        )
        features = frozenset()
        tr = self._turn_rules_wire()
        cc = tr.get("client_contract")
        if isinstance(cc, dict):
            raw_feats = cc.get("features")
            if isinstance(raw_feats, list):
                features = frozenset(
                    str(x).strip() for x in raw_feats if str(x).strip()
                )
        return TurnActionDockContext(
            state=st,
            viewer_faction=viewer_faction,
            extension_key=self._title_extension_key(),
            shell_ui=dict(self.game_data.shell_ui),
            schedule_index=int(turn.schedule_index),
            current_faction=current_faction,
            current_phase=str(turn.current_phase).strip(),
            phase_actions_remaining=int(turn.phase_actions_remaining),
            viewer_is_turn_owner=viewer_is_turn_owner,
            client_contract_features=features,
            current_segment=current_segment,
        )

    def _turn_action_dock_for_player_id(
        self, player_id: str
    ) -> list[dict[str, Any]] | None:
        """Per-recipient turn action dock (ENGINE_DEFAULT → engine catalog)."""
        ctx = self._turn_action_dock_context_for_player_id(player_id)
        if ctx is None:
            return None
        raw = self.hooks.ui.turn_action_dock(ctx)
        if raw is ENGINE_DEFAULT:
            catalog = get_engine_catalog_hook("ui.turn_action_dock_for_viewer")
            if catalog is None:
                raise NotImplementedError(
                    "ui.turn_action_dock_for_viewer: no title hook and no engine "
                    "catalog default"
                )
            raw = catalog(ctx)
        from ..hooks.internal.ui_wire import turn_action_dock_to_wire

        return turn_action_dock_to_wire(raw) or None

    def _interaction_panels_for_player_id(
        self, player_id: str
    ) -> list[dict[str, Any]] | None:
        """Per-recipient turn action dock via ``TURN_ACTION_DOCK_FOR_VIEWER``."""
        if self.hooks.ui.turn_action_dock_for_viewer is None:
            return None
        return self._turn_action_dock_for_player_id(player_id)

    def _map_overlays_for_player_id(self, player_id: str) -> list[dict[str, Any]]:
        """
        Per-recipient map overlay specs for StateUpdate.map_overlays.

        The browser client owns DOM: it creates/updates/removes elements from this list.
        Each dict must include schema 1, id, kind, hex (i/j/k), and
        presentation fields for the kind (e.g. text for glyph).
        """
        player = self.players.get(player_id)
        if player is None or not player.connected:
            return []
        st = self.action_manager.current_state
        viewer_faction = str(player.faction) if player.faction else None
        from ..hooks.internal.ui_wire import map_overlays_to_wire

        raw = self.hooks.ui.overlays(st, viewer_faction)
        if raw is ENGINE_DEFAULT:
            return []
        return map_overlays_to_wire(raw)

    async def _broadcast_combat_events(self, state_after: GameState) -> None:
        raw = self.hooks.ui.combat_event_summary_for(state_after)
        if raw is ENGINE_DEFAULT or raw is None:
            return
        if not isinstance(raw, CombatEventSummary):
            raise TypeError(
                "hooks.ui.combat_event_summary must return CombatEventSummary, None, "
                "or hooks.ENGINE_DEFAULT"
            )
        summary = raw
        outcome = str(summary.outcome)
        attack_kind = str(summary.attack_kind)
        attacker_id = str(summary.attacker_id)
        defender_id = str(summary.defender_id)
        rd_int = summary.retreat_distance
        ru = summary.retreat_unit_id
        hex_remaining = summary.retreat_hexes_remaining
        from ..hooks.ui_combat_messages import retreat_owner_faction

        retreat_owner = retreat_owner_faction(
            state_after, outcome, attacker_id, defender_id
        )
        for pid, pinfo in self.players.items():
            if not pinfo.connected:
                continue
            inst, msg = self._combat_instruction_for_viewer(
                state_after,
                str(pinfo.faction) if pinfo.faction else None,
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

        # Treat MoveUnit to the vacated defender hex as an optional combat advance.
        is_advance_fulfillment = False
        if request.action_type == "MoveUnit":
            is_advance_fulfillment = move_unit_is_combat_advance_fulfillment(
                self.hooks,
                current_state,
                request.params,
                player_faction=str(player.faction),
                extension_key=self._title_extension_key(),
            )

        if request.action_type == "CombatDisruptInsteadOfRetreat":
            outcome = await try_combat_arc_rpc(
                self, player_id, player, "CombatDisruptInsteadOfRetreat"
            )
            if await finish_combat_arc_dispatch(self, player_id, outcome):
                return
            await self._send_error(player_id, COMBAT_ARC_REQUIRED_MSG)
            return

        if request.action_type == "CombatAdvance":
            outcome = await try_combat_arc_rpc(self, player_id, player, "CombatAdvance")
            if await finish_combat_arc_dispatch(self, player_id, outcome):
                return
            await self._send_error(player_id, COMBAT_ARC_REQUIRED_MSG)
            return

        if request.action_type == "CombatDeclineAdvance":
            outcome = await try_combat_arc_rpc(
                self, player_id, player, "CombatDeclineAdvance"
            )
            if await finish_combat_arc_dispatch(self, player_id, outcome):
                return
            await self._send_error(player_id, COMBAT_ARC_REQUIRED_MSG)
            return

        if request.action_type == "PassMovementInterrupt":
            if not self._actor_may_act(player.faction, current_state):
                await self._send_error(
                    player_id,
                    f"Not your turn (current: {self._segment_owner_faction(current_state)})",
                )
                return
            if not phase_allows_movement_interrupt_pass(
                current_state.turn.current_phase
            ):
                await self._send_error(
                    player_id, "No movement interrupt to pass right now"
                )
                return
            if await drive_movement_arc_event(
                self, player_id, player, "PassMovementInterrupt", {}
            ):
                return
            await self._send_error(player_id, "Movement arc rejected interrupt pass")
            return

        if request.action_type == "Attack":
            if not self._actor_may_act(player.faction, current_state):
                await self._send_error(
                    player_id,
                    f"Not your turn (current: {self._segment_owner_faction(current_state)})",
                )
                return
            ok = await execute_authority_attack_request(
                self,
                player_id=player_id,
                player_faction=str(player.faction),
                current_state=current_state,
                params=request.params,
            )
            if not ok:
                return
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

        if request.action_type == "MoveUnit" and is_retreat_fulfillment:
            unit = current_state.board.units.get(uid_for_move or "")
            if unit is None or unit.faction != player.faction:
                await self._send_error(player_id, "That unit is not yours")
                return
            try:
                self._validate_move_unit_request(
                    current_state,
                    request.params,
                    player,
                    is_retreat_fulfillment=True,
                )
                if uid_for_move is not None:
                    validate_retreat_fulfillment_stack(
                        self,
                        st_before=current_state,
                        uid_for_move=uid_for_move,
                        player=player,
                        request=request,
                    )
            except ValueError as e:
                await self._send_error(player_id, str(e))
                return

        if request.action_type == "MoveUnit":
            move_outcome = await try_combat_arc_move_unit(
                self,
                player_id,
                player,
                dict(request.params),
                is_retreat_fulfillment=is_retreat_fulfillment,
                is_advance_fulfillment=is_advance_fulfillment,
            )
            if await finish_combat_arc_dispatch(self, player_id, move_outcome):
                return
            if is_retreat_fulfillment or is_advance_fulfillment:
                await self._send_error(player_id, COMBAT_ARC_REQUIRED_MSG)
                return

        if not is_retreat_fulfillment:
            if not self._actor_may_act(player.faction, current_state):
                await self._send_error(
                    player_id,
                    f"Not your turn (current: {self._segment_owner_faction(current_state)})",
                )
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
            if not self._actor_may_act(player.faction, current_state):
                await self._send_error(
                    player_id,
                    f"Not your turn (current: {self._segment_owner_faction(current_state)})",
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
            retreat_rem_steps: int | None = None
            if is_retreat_fulfillment and uid_for_move is not None:
                retreat_rem_steps = self._retreat_obligation_hexes_remaining(
                    current_state, uid_for_move
                )
                if retreat_rem_steps is not None:
                    if await handle_authority_retreat_path_move_unit(
                        self,
                        player_id,
                        player,
                        request,
                        current_state,
                        retreat_remaining=int(retreat_rem_steps),
                        uid_for_move=uid_for_move,
                    ):
                        return
            if not is_retreat_fulfillment:
                if await handle_authority_move_unit_normal(
                    self, player_id, player, request, current_state
                ):
                    return
            if not is_retreat_fulfillment:
                try:
                    self._validate_move_unit_request(
                        current_state,
                        request.params,
                        player,
                        is_retreat_fulfillment=False,
                    )
                except ValueError as e:
                    await self._send_error(player_id, str(e))
                    return

        # Create action from request (NextPhase is always server-authoritative)
        try:
            if request.action_type == "NextPhase":
                if read_movement_arc(self.action_manager.current_state):
                    raise ValueError(
                        "Advance phase is blocked while a movement arc is incomplete"
                    )
                if self._resolve_blocks_routine_phase_advance():
                    raise ValueError(
                        "Cannot advance phase while combat obligations are pending"
                    )
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

            # Spend an action for normal moves (retreat fulfillment never spends)
            if request.action_type == "MoveUnit" and not is_retreat_fulfillment:
                try:
                    self._spend_action_after_normal_move_unit()
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

    def _hex_from_wire_dict(self, raw: Any) -> Hex | None:
        if not isinstance(raw, dict):
            return None
        try:
            return Hex(int(raw["i"]), int(raw["j"]), int(raw["k"]))
        except (KeyError, TypeError, ValueError):
            return None

    def _marker_anchor_hex(self, marker_id: str) -> Hex | None:
        for m in self.markers:
            if str(m.get("id", "")).strip() != str(marker_id).strip():
                continue
            hx = m.get("hex")
            if isinstance(hx, dict):
                parsed = self._hex_from_wire_dict(hx)
                if parsed is not None:
                    return parsed
            pos = m.get("position")
            if isinstance(pos, list | tuple) and len(pos) == 2:
                try:
                    return Hex.from_hex_col_row(
                        HexColRow(col=int(pos[0]), row=int(pos[1]))
                    )
                except (TypeError, ValueError):
                    return None
        return None

    def _resolve_inspect_anchor_hex(
        self,
        *,
        state: GameState,
        target_kind: str,
        target_id: str,
        context: dict[str, Any] | None,
    ) -> Hex | None:
        k = str(target_kind or "").strip()
        ctx = context if isinstance(context, dict) else {}
        if k == "unit":
            u = state.board.units.get(str(target_id).strip())
            return u.position if u is not None else None
        if k == "marker":
            return self._marker_anchor_hex(target_id)
        if k == "inform":
            hx = self._hex_from_wire_dict(ctx.get("hex"))
            if hx is not None:
                return hx
            uid = str(ctx.get("unit_id", "")).strip()
            if uid:
                u = state.board.units.get(uid)
                if u is not None:
                    return u.position
        return None

    async def _send_ui_popup_to_player(
        self,
        player_id: str,
        *,
        anchor_hex: Hex,
        pm: dict[str, Any],
    ) -> None:
        raw_text = pm.get("text")
        raw_html = pm.get("html")
        txt = "" if raw_text is None else str(raw_text).strip()
        html = "" if raw_html is None else str(raw_html).strip()
        if not txt and not html:
            return
        kind = str(pm.get("kind", "info"))
        ttl_raw = pm.get("ttl_ms", 800)
        ttl_ms = None if ttl_raw is None else int(ttl_raw)
        css_class_raw = pm.get("css_class")
        css_class = None if css_class_raw is None else str(css_class_raw)
        popup = UIPopupWire(
            text=txt or None,
            html=html or None,
            hex={
                "i": int(anchor_hex.i),
                "j": int(anchor_hex.j),
                "k": int(anchor_hex.k),
            },
            kind=kind,
            ttl_ms=ttl_ms,
            css_class=css_class,
        )
        await self._send_message(player_id, popup.to_message())

    async def _handle_inspect_request(self, player_id: str, message: Message) -> None:
        req = InspectRequest.from_message(message)
        player = self.players.get(player_id)
        if not player or not player.connected:
            return

        state = self.action_manager.current_state
        viewer_faction = player.faction
        target_kind = str(req.target_kind).strip()
        target_id = str(req.target_id).strip()
        ctx = req.context if isinstance(req.context, dict) else None

        anchor_hex = self._resolve_inspect_anchor_hex(
            state=state,
            target_kind=target_kind,
            target_id=target_id,
            context=ctx,
        )
        if anchor_hex is None:
            return

        shell = dict(self.game_data.shell_ui) if self.game_data.shell_ui else {}
        inform_kind = ""
        inform_profile: str | None = None
        segment_kind: str | None = None
        unit_id: str | None = None
        if target_kind == "inform":
            client_inform_kind = ""
            if isinstance(ctx, dict):
                client_inform_kind = str(ctx.get("inform_kind", "")).strip()
                uid_raw = ctx.get("unit_id")
                if uid_raw is not None and str(uid_raw).strip():
                    unit_id = str(uid_raw).strip()
            from ..arcs.inform_wire import resolve_inform_lane

            lane = resolve_inform_lane(
                self,
                state,
                viewer_faction=viewer_faction,
                client_inform_kind=client_inform_kind,
            )
            inform_kind = lane.inform_kind
            inform_profile = lane.inform_profile
            segment_kind = lane.segment_kind

        ip_ctx = InformPopupContext(
            state=state,
            viewer_faction=viewer_faction,
            target_kind=target_kind,
            target_id=target_id,
            anchor_hex=anchor_hex,
            shell_ui=shell,
            inform_kind=inform_kind,
            reason=target_id if target_kind == "inform" else "",
            unit_id=unit_id,
            inform_profile=inform_profile,
            segment_kind=segment_kind,
        )
        pm = self.hooks.ui.inform_popup_for(ip_ctx)
        if pm is ENGINE_DEFAULT or pm is None:
            pm = default_inform_popup_for_viewer(ip_ctx)
        from ..hooks.internal.ui_wire import inform_popup_to_wire

        pm = inform_popup_to_wire(pm)
        await self._send_ui_popup_to_player(player_id, anchor_hex=anchor_hex, pm=pm)

    async def _handle_marker_preview_request(
        self, player_id: str, message: Message
    ) -> None:
        req = MarkerPreviewRequest.from_message(message)
        player = self.players.get(player_id)
        if not player or not player.connected:
            return
        state = self.action_manager.current_state
        marker_id = str(req.marker_id)
        marker_type = str(req.marker_type)
        request_id = str(getattr(req, "request_id", "") or "")
        marker_wire = {"id": marker_id, "type": marker_type}

        hexes = compute_marker_drag_preview(
            state=state,
            marker_wire=marker_wire,
            board_hexes=self._iter_board_hexes(state),
            destination_allowed=self._marker_destination_allowed,
        )

        # Optional title CSS class from turn_rules.ui.marker_hex_class (client already
        # falls back to "highlight" when absent).
        css_class: str | None = None
        try:
            ui = self._turn_rules_wire().get("ui")
            if isinstance(ui, dict):
                raw = ui.get("marker_hex_class")
                if isinstance(raw, str) and raw.strip():
                    css_class = raw.strip()
        except Exception:
            css_class = None

        await self._send_message(
            player_id,
            MarkerPreviewWire(
                marker_id=marker_id,
                hexes=hexes,
                css_class=css_class,
                request_id=request_id,
            ).to_message(),
        )

    async def _handle_unit_preview_request(
        self, player_id: str, message: Message
    ) -> None:
        req = UnitPreviewRequest.from_message(message)
        player = self.players.get(player_id)
        if not player or not player.connected:
            return

        state = self.action_manager.current_state
        unit_id = str(req.unit_id)
        request_id = str(getattr(req, "request_id", "") or "")
        u = state.board.units.get(unit_id)
        if u is None or not u.active:
            return

        preview = compute_unit_drag_preview(
            state=state,
            unit_id=unit_id,
            player_faction=str(player.faction),
            board_hexes=self._iter_board_hexes(state),
            retreat_hexes_remaining=self._retreat_obligation_hexes_remaining,
            faction_has_pending_retreat=self._faction_has_pending_retreat,
            movement_budget_for_unit=self._movement_budget_for_unit,
            zoc_hexes_for_unit=self._zoc_hexes_for_unit,
            max_active_units_per_hex=self._max_active_units_per_hex,
            movement_step_cost_fn=self._movement_step_cost_fn,
            retreat_blocked_hexes=self.hooks.movement.retreat_blocked,
        )
        kind = preview.kind
        out_hexes = preview.hexes
        through_hexes = preview.through_hexes
        through_css_class: str | None = None

        css_class: str | None = None
        try:
            ui = self._turn_rules_wire().get("ui")
            if isinstance(ui, dict):
                key = "retreat_hex_class" if kind == "retreat" else "move_hex_class"
                raw = ui.get(key)
                if isinstance(raw, str) and raw.strip():
                    css_class = raw.strip()
                if kind == "retreat":
                    raw2 = ui.get("retreat_through_hex_class")
                    if isinstance(raw2, str) and raw2.strip():
                        through_css_class = raw2.strip()
        except Exception:
            css_class = None

        await self._send_message(
            player_id,
            UnitPreviewWire(
                unit_id=unit_id,
                kind=kind,
                hexes=out_hexes,
                css_class=css_class,
                through_hexes=through_hexes,
                through_css_class=through_css_class,
                request_id=request_id,
            ).to_message(),
        )

    async def _handle_map_selection_preview_request(
        self, player_id: str, message: Message
    ) -> None:
        req = MapSelectionPreviewRequest.from_message(message)
        player = self.players.get(player_id)
        if not player or not player.connected:
            return

        state = self.action_manager.current_state
        kind = str(req.kind or "").strip()
        draft = dict(req.draft) if isinstance(req.draft, dict) else {}
        request_id = str(getattr(req, "request_id", "") or "")
        shell = dict(self.game_data.shell_ui) if self.game_data.shell_ui else {}
        raw = compute_map_selection_preview(
            state=state,
            player_faction=str(player.faction),
            kind=kind,
            draft=draft,
            shell_ui=shell,
            board_hexes=self._iter_board_hexes(state),
            hooks=self.hooks,
            markers=[dict(m) for m in self.markers if isinstance(m, dict)],
        )
        await self._send_message(
            player_id,
            MapSelectionPreviewWire(
                kind=str(raw.get("kind", kind)),
                status_text=str(raw.get("status_text", "")),
                confirm_enabled=bool(raw.get("confirm_enabled", False)),
                request_id=request_id,
                valid_target_hexes=raw.get("valid_target_hexes"),
                eligible_attacker_ids=raw.get("eligible_attacker_ids"),
                commit_payload=raw.get("commit_payload"),
                panel_actions=raw.get("panel_actions"),
                legal_next_hexes=raw.get("legal_next_hexes"),
                preview_path_hexes=raw.get("preview_path_hexes"),
                through_hexes=raw.get("through_hexes"),
                disable_end_phase=(
                    bool(raw["disable_end_phase"])
                    if isinstance(raw.get("disable_end_phase"), bool)
                    else None
                ),
                draft_presentation_id=(
                    str(raw["draft_presentation_id"]).strip()
                    if isinstance(raw.get("draft_presentation_id"), str)
                    and str(raw["draft_presentation_id"]).strip()
                    else None
                ),
            ).to_message(),
        )

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
        out = self.hooks.movement.budget(state, unit_id)
        if out is not ENGINE_DEFAULT:
            try:
                return float(out)
            except (TypeError, ValueError):
                raise TypeError(
                    "Movement hook movement_budget_for_unit must return a number or hooks.ENGINE_DEFAULT"
                ) from None
        fn = get_engine_catalog_hook("movement.movement_budget_for_unit")
        if fn is None:
            raise RuntimeError(
                "Engine hook catalog missing movement.movement_budget_for_unit"
            )
        return fn(state, unit_id)

    def _max_active_units_per_hex(self, state: GameState, unit_id: str) -> int | None:
        """
        Max active units allowed to *end* stacked on a hex for this unit, or None.

        Authoritative value comes from `GameServer.game_data.max_active_units_per_hex`.
        """
        _ = state, unit_id
        raw = self.game_data.max_active_units_per_hex
        if raw is None:
            return None
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    def _zoc_hexes_for_unit(
        self, state: GameState, unit_id: str
    ) -> frozenset[Hex] | None:
        raw = self.hooks.movement.zoc(state, unit_id)
        if raw is ENGINE_DEFAULT or raw is None:
            return None
        return raw if isinstance(raw, frozenset) else frozenset(raw)

    def _movement_step_cost_fn(
        self, unit_id: str
    ) -> Callable[[GameState, Hex, Hex, float], float] | None:
        """Per-step cost callback for reachability when the title implements movement_step_cost_for_unit."""
        mh = self.hooks.movement
        if mh.movement_step_cost_for_unit is None:
            return None

        def fn(s: GameState, from_h: Hex, to_h: Hex, base: float) -> float:
            raw = mh.step_cost_move(s, unit_id, from_h, to_h, base)
            if raw is ENGINE_DEFAULT:
                return base
            return float(raw)

        return fn

    def _movement_step_total_cost(
        self, state: GameState, unit_id: str, from_h: Hex, to_h: Hex
    ) -> float:
        base = state.board.get_movement_cost(to_h)
        if base == float("inf"):
            return float("inf")
        fn = self._movement_step_cost_fn(unit_id)
        if fn is None:
            return float(base)
        return float(fn(state, from_h, to_h, base))

    async def _send_move_unit_success_and_broadcast(self, player_id: str) -> None:
        result = ActionResult(success=True, action_id=str(uuid.uuid4()))
        await self._send_message(player_id, result.to_message())
        await self._broadcast_state_update()

    def _spend_action_after_normal_move_unit(self) -> None:
        self.logger.debug("Spending 1 action for MoveUnit")
        self.action_manager.execute(SpendAction(amount=1))
        current_state = self.action_manager.current_state
        self.logger.debug(
            f"After spending: {current_state.turn.current_faction}-"
            f"{current_state.turn.current_phase}, "
            f"actions remaining: {current_state.turn.phase_actions_remaining}"
        )
        policy = self.hooks.movement.auto_advance_after_move_spend(current_state)
        self._maybe_auto_advance_phase(
            policy,
            catalog_path="movement.auto_advance_phase_after_move_spend",
            log_reason="after move spend",
        )

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
            ctx = MoveContext(
                state=state,
                unit_id=unit_id,
                from_hex=from_hex,
                to_hex=to_hex,
                player_faction=str(player.faction),
                is_retreat_fulfillment=True,
            )
            out = self.hooks.movement.validate_retreat(ctx, rem)
            if out is ENGINE_DEFAULT:
                leg = distance(from_hex, to_hex)
                if leg != rem:
                    raise ValueError(
                        f"Retreat move must cover exactly {rem} hexes (cube distance); got {leg}"
                    )
            budget = float(rem)
            blocked = self.hooks.movement.retreat_blocked(state, unit_id)
            if blocked is ENGINE_DEFAULT or blocked is None:
                blocked_hexes = None
            else:
                blocked_hexes = (
                    blocked if isinstance(blocked, frozenset) else frozenset(blocked)
                )
            # Occupied destination (enemy or stacked beyond limit) is always illegal.
            for u in state.board.active_units_at_hex(to_hex):
                if u.unit_id != unit_id and u.faction != player.faction:
                    raise ValueError("Destination hex is occupied by an enemy unit")
            max_stack = self._max_active_units_per_hex(state, unit_id)
            if (
                max_stack is not None
                and len(state.board.active_units_at_hex(to_hex)) >= max_stack
            ):
                raise ValueError(
                    f"Destination hex already has {max_stack} active units (stacking limit)"
                )
            step_fn = self._movement_step_cost_fn(unit_id)
            if not is_valid_move(
                state,
                unit_id,
                to_hex,
                budget,
                zoc_hexes=None,
                blocked_hexes=blocked_hexes,
                max_active_units_per_hex=max_stack,
                step_cost=step_fn,
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
        for u in state.board.active_units_at_hex(to_hex):
            if u.unit_id != unit_id and u.faction != player.faction:
                raise ValueError("Destination hex is occupied by an enemy unit")
        max_stack = self._max_active_units_per_hex(state, unit_id)
        if (
            max_stack is not None
            and len(state.board.active_units_at_hex(to_hex)) >= max_stack
        ):
            raise ValueError(
                f"Destination hex already has {max_stack} active units (stacking limit)"
            )
        step_fn = self._movement_step_cost_fn(unit_id)
        if not is_valid_move(
            state,
            unit_id,
            to_hex,
            budget,
            zoc_hexes=zoc,
            max_active_units_per_hex=max_stack,
            step_cost=step_fn,
        ):
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
            interaction_messages=self._interaction_messages_for_player_id(player_id),
            map_overlays=self._map_overlays_for_player_id(player_id),
            interaction_panels=self._interaction_panels_for_player_id(player_id),
            current_segment=self._current_segment_for_player_id(player_id),
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
                    interaction_messages=self._interaction_messages_for_player_id(
                        player_id
                    ),
                    map_overlays=self._map_overlays_for_player_id(player_id),
                    interaction_panels=self._interaction_panels_for_player_id(
                        player_id
                    ),
                    current_segment=self._current_segment_for_player_id(player_id),
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
        await self._send_message(
            player_id, ServerError(error=error_message).to_message()
        )

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


async def _dispatch_leave_game(
    server: GameServer, player_id: str, _message: Message
) -> None:
    await server._handle_leave_game(player_id)


_ClientInboundHandler = Callable[[GameServer, str, Message], Awaitable[None]]

_CLIENT_INBOUND_HANDLERS: dict[str, _ClientInboundHandler] = {
    JoinGameRequest.wire_type: GameServer._handle_join_game,
    ActionRequest.wire_type: GameServer._handle_action_request,
    InspectRequest.wire_type: GameServer._handle_inspect_request,
    MarkerPreviewRequest.wire_type: GameServer._handle_marker_preview_request,
    UnitPreviewRequest.wire_type: GameServer._handle_unit_preview_request,
    MapSelectionPreviewRequest.wire_type: GameServer._handle_map_selection_preview_request,
    UndoRequest.wire_type: GameServer._handle_undo_request,
    RedoRequest.wire_type: GameServer._handle_redo_request,
    LeaveGameRequest.wire_type: _dispatch_leave_game,
    LoadSnapshotRequest.wire_type: GameServer._handle_load_snapshot,
}
