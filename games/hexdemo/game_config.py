"""
Hexdemo match configuration — **edit here** to change turn order, factions, and budgets.

The engine calls `hexdemo.registry.build_game_definition`, which builds a
`hexengine.gamedef.protocol.GameDefinition` from `HexdemoMatchConfig`.

Typical changes:

- **Declarative wire** (stack cap, faction labels, highlight CSS, …) —
  `resources/game_data.toml`, referenced from `hexengine_pack.toml` `[gamedata]`.
- **Faction order** — `HEXDEMO_FACTIONS` in `hexdemo.constants` (first side opens
  the round; see `hexengine.gameroot.initial_turn_slot_for_game_definition`).
- **Turn rota** — edit `hexdemo_four_phase_entries` (or replace the
  `StaticScheduleGameDefinition` built in `game_definition_from_config`).
- **Movement preview budget** — set `movement_budget` to match scenario feel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hexengine.gamedef import unit_attributes as unit_attr_helpers
from hexengine.gamedef.builtin import StaticScheduleGameDefinition
from hexengine.gamedef.game_data import GameData
from hexengine.gamedef.game_data_toml import load_game_data_for_pack_root
from hexengine.gamedef.protocol import GameDefinition
from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
from hexengine.state import DEFAULT_MOVEMENT_BUDGET, GameState
from hexengine.state.logic import adjacent_enemy_zoc_hexes
from hexengine.state.phase_rules import phase_allows_unit_move

from . import combat
from .constants import HEXDEMO_FACTIONS, PACK_STATE_EXTENSION_KEY

_HEXDEMO_PACK_ROOT = Path(__file__).resolve().parent


def hexdemo_four_phase_entries(
    factions: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    """Union Move, Union Combat, Confederate Move, Confederate Combat."""
    if len(factions) < 2:
        raise ValueError("hexdemo four-phase schedule requires two factions")
    union, confederate = factions[0], factions[1]
    return (
        {"faction": union, "phase": "Move", "max_actions": 4},
        {"faction": union, "phase": "Combat", "max_actions": 2},
        {"faction": confederate, "phase": "Move", "max_actions": 4},
        {"faction": confederate, "phase": "Combat", "max_actions": 2},
    )


class HexdemoGameDefinition:
    """
    Wraps a `GameDefinition` with Hexdemo-specific lifecycle hooks.

    Delegates turn geometry to the inner definition.
    """

    __slots__ = ("_base",)

    def __init__(self, base: GameDefinition) -> None:
        self._base = base

    @property
    def game_data(self) -> GameData:
        """Wire-facing title data from `resources/game_data.toml` (see `hexengine_pack.toml`)."""
        return load_game_data_for_pack_root(_HEXDEMO_PACK_ROOT)

    @property
    def hooks(self):
        from .hooks import build_hooks

        return build_hooks()

    @property
    def marker_placement_rule(self):
        from .marker_rules import default_marker_placement_rule

        return default_marker_placement_rule()

    @property
    def _movement_budget(self) -> float:
        """Scalar schedule budget on the inner definition (used by server `turn_rules` wire)."""
        return float(self._base._movement_budget)

    def available_factions(self) -> list[str]:
        return list(self._base.available_factions())

    def turn_order(self) -> list[dict[str, Any]]:
        return self._base.turn_order()

    def get_next_phase(self, state: GameState) -> dict[str, Any]:
        return self._base.get_next_phase(state)

    def movement_budget_for_unit(self, state: GameState, unit_id: str) -> float:
        u = state.board.units.get(unit_id)
        if u is None:
            raise ValueError(f"Unknown unit {unit_id!r}")
        raw = u.attributes.get("movement")
        if raw is not None:
            return float(raw)
        return float(self._base._movement_budget)

    def zoc_hexes_for_unit(self, state: GameState, unit_id: str) -> frozenset[Hex]:
        """Adjacent-enemy ZOC hexes; engine applies stop-on-entry during reachability."""
        return adjacent_enemy_zoc_hexes(state, unit_id)

    def validate_attack_request(
        self,
        state: GameState,
        *,
        player_faction: str,
        attack_kind: str,
        params: dict[str, Any],
    ) -> None:
        """
        Title rules for `Attack` (adjacency and combat phase); not encoded in `phase_rules`.
        """
        if attack_kind not in ("combined",):
            raise ValueError(f"Unknown attack_kind for hexdemo: {attack_kind!r}")
        phase = str(state.turn.current_phase)
        if phase not in ("Combat", "Attack"):
            raise ValueError("Attacks are only allowed during the combat phase")
        if player_faction != state.turn.current_faction:
            raise ValueError("Not your turn")
        if combat.any_retreat_obligation_pending(state):
            raise ValueError("Resolve retreat before issuing another attack")
        attacker_id = params.get("attacker_id")
        defender_id = params.get("defender_id")
        if not isinstance(attacker_id, str) or not attacker_id.strip():
            raise ValueError("attacker_id is required")
        if not isinstance(defender_id, str) or not defender_id.strip():
            raise ValueError("defender_id is required")
        attacker = state.board.units.get(attacker_id)
        defender = state.board.units.get(defender_id)
        if attacker is None or not attacker.active:
            raise ValueError("Invalid attacker")
        if defender is None or not defender.active:
            raise ValueError("Invalid defender")
        if attacker.faction != player_faction:
            raise ValueError("You do not control the attacker")
        if attacker.faction == defender.faction:
            raise ValueError("Cannot attack same faction")
        # Multi-attacker support: params may include `attacker_ids` (list[str]).
        raw_attacker_ids = params.get("attacker_ids")
        attacker_ids: list[str] = []
        if isinstance(raw_attacker_ids, list) and raw_attacker_ids:
            for uid in raw_attacker_ids:
                if isinstance(uid, str) and uid.strip():
                    attacker_ids.append(uid.strip())
        if not attacker_ids:
            attacker_ids = [str(attacker_id)]

        from hexengine.hexes.los import has_line_of_sight
        from hexengine.state import edges_block_los_predicate

        def blocks(h: Hex) -> bool:
            loc = state.board.effective_location(h)
            if loc is None:
                return False
            return bool(getattr(loc, "block_los", False))

        edges_block = edges_block_los_predicate(state.board)

        # Each attacker must be eligible vs the target hex (defender.position).
        target_hex = defender.position
        for aid in attacker_ids:
            a = state.board.units.get(aid)
            if a is None or not a.active:
                raise ValueError("Invalid attacker")
            if a.faction != player_faction:
                raise ValueError("You do not control the attacker")
            if a.faction == defender.faction:
                raise ValueError("Cannot attack same faction")

            dist = distance(a.position, target_hex)
            ut = str(a.unit_type).lower()
            if ut in ("infantry", "inf"):
                if dist != 1:
                    raise ValueError("Infantry attacker is not adjacent to the target")
            elif ut in ("artillery", "art"):
                raw_range = a.attributes.get("range")
                try:
                    atk_range = int(raw_range) if raw_range is not None else 0
                except Exception:
                    atk_range = 0
                if atk_range <= 1:
                    raise ValueError("Artillery has no ranged capability")
                if not (dist > 1 and dist <= atk_range):
                    raise ValueError("Artillery target is out of range")
                if not has_line_of_sight(
                    a.position, target_hex, blocks=blocks, edges_block=edges_block
                ):
                    raise ValueError("No line of sight to target")
            else:
                raise ValueError(
                    f"Unit type {ut!r} cannot participate in combined attacks"
                )
        from . import title_state

        prev = title_state.bucket(state).get("attacks_this_phase")
        if isinstance(prev, list):
            for aid in attacker_ids:
                if aid in prev:
                    raise ValueError(
                        "That unit has already attacked this combat phase"
                    )

    def retreat_obligation_hexes_remaining(
        self, state: GameState, unit_id: str
    ) -> int | None:
        """Optional `GameDefinition` hook: read mandatory retreat steps from hexdemo state."""
        return combat.retreat_hexes_remaining(state, unit_id)

    def any_retreat_obligation_pending(self, state: GameState) -> bool:
        """Optional hook: any unit owes a retreat move."""
        return combat.any_retreat_obligation_pending(state)

    def faction_has_pending_retreat_obligation(
        self, state: GameState, faction: str
    ) -> bool:
        """Optional hook: `faction` still owes a retreat fulfillment."""
        return combat.faction_has_pending_retreat(state, faction)

    def focus_unit_id_after_state_sync(
        self, state: GameState, viewer_faction: str | None
    ) -> str | None:
        """Optional hook: which unit the client should select after a state sync."""
        from . import focus

        return focus.focus_unit_id_after_state_sync(state, viewer_faction)

    def default_attributes_for_unit_type(self, unit_type: str) -> dict[str, Any]:
        fn = getattr(self._base, "default_attributes_for_unit_type", None)
        if callable(fn):
            return dict(fn(unit_type))
        return unit_attr_helpers.default_attributes_for_unit_type(self._base, unit_type)

    def merge_spawn_attributes(
        self,
        unit_type: str,
        instance_attrs: dict[str, Any],
        state: GameState | None = None,
    ) -> dict[str, Any]:
        fn = getattr(self._base, "merge_spawn_attributes", None)
        if callable(fn):
            return dict(fn(unit_type, dict(instance_attrs or {}), state))
        return unit_attr_helpers.merge_spawn_attributes(
            self._base, unit_type, instance_attrs, state=state
        )

    def validate_unit_attributes_patch(
        self, state: GameState, unit_id: str, patch: dict[str, Any]
    ) -> None:
        fn = getattr(self._base, "validate_unit_attributes_patch", None)
        if callable(fn):
            fn(state, unit_id, patch)
            return
        unit_attr_helpers.validate_unit_attributes_patch(
            self._base, state, unit_id, patch
        )

    def after_phase_transition(self, state: GameState) -> list:
        """
        Called by the server after each `NextPhase` is applied.

        Returns title-owned `StateAction`s for the engine to execute. Hexdemo clears
        its own phase-scoped combat bookkeeping here (the engine does not know these
        bucket keys).
        """
        from . import combat_transitions
        from .hooks.turn_schedule import before_union_move

        t = state.turn
        if t.current_faction == "union" and phase_allows_unit_move(t.current_phase):
            before_union_move(state)
        return combat_transitions.clear_combat_state_actions(state)


@dataclass(frozen=True, slots=True)
class HexdemoMatchConfig:
    """Title-owned settings for one match (authoritative server + thin clients)."""

    factions: tuple[str, ...] = HEXDEMO_FACTIONS
    movement_budget: float = DEFAULT_MOVEMENT_BUDGET


def game_definition_from_config(config: HexdemoMatchConfig) -> GameDefinition:
    """Return a fresh `GameDefinition` for `config` (single static four-phase rota)."""
    base = StaticScheduleGameDefinition(
        hexdemo_four_phase_entries(config.factions),
        movement_budget=config.movement_budget,
    )
    return HexdemoGameDefinition(base)


def default_match_config() -> HexdemoMatchConfig:
    """Default factions and movement budget for the shipped rota."""
    return HexdemoMatchConfig()
