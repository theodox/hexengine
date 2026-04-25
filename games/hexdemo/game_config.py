"""
Hexdemo match configuration — **edit here** to change turn order, factions, and budgets.

The engine calls `hexdemo.registry.build_game_definition`, which builds a
`hexengine.gamedef.protocol.GameDefinition` from `HexdemoMatchConfig`.

Typical changes:

- **Faction order** — `HEXDEMO_FACTIONS` in `hexdemo.constants` (first side opens
  the round; see `hexengine.gameroot.initial_turn_slot_for_game_definition`).
- **Default vs sequential** — `schedule` (`interleaved` / `default` use the four-phase
  Union/Confederate Move/Combat rota; `sequential` uses Movement/Attack blocks).
- **Movement preview budget** — set `movement_budget` to match scenario feel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from hexengine.gamedef import unit_attributes as unit_attr_helpers
from hexengine.gamedef.builtin import (
    SequentialTwoFactionGameDefinition,
    StaticScheduleGameDefinition,
)
from hexengine.gamedef.protocol import GameDefinition
from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
from hexengine.state import DEFAULT_MOVEMENT_BUDGET, GameState
from hexengine.state.logic import adjacent_enemy_zoc_hexes
from hexengine.state.phase_rules import phase_allows_unit_move

from . import combat
from .constants import HEXDEMO_FACTIONS

Schedule = Literal["interleaved", "sequential"]


def hexdemo_four_phase_entries(
    factions: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    """Union Move, Union Combat, Confederate Move, Confederate Combat."""
    if len(factions) < 2:
        raise ValueError("hexdemo four-phase schedule requires two factions")
    union_side, confed_side = factions[0], factions[1]
    return (
        {"faction": union_side, "phase": "Move", "max_actions": 2},
        {"faction": union_side, "phase": "Combat", "max_actions": 2},
        {"faction": confed_side, "phase": "Move", "max_actions": 2},
        {"faction": confed_side, "phase": "Combat", "max_actions": 2},
    )


class HexdemoGameDefinition:
    """
    Wraps a `GameDefinition` with Hexdemo-specific lifecycle hooks.

    Delegates turn geometry to the inner definition.
    """

    __slots__ = ("_base",)

    #: Published in `StateUpdate.turn_rules` so thin clients match per-unit budgets.
    movement_budget_attribute_key = "movement"

    def __init__(self, base: GameDefinition) -> None:
        self._base = base

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
        Title rules for ``Attack`` (adjacency and combat phase); not encoded in ``phase_rules``.
        """
        if attack_kind != "adjacent":
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
        if distance(attacker.position, defender.position) != 1:
            raise ValueError("Defender is not adjacent to the attacker")
        hx = state.extension.get("hexdemo")
        if isinstance(hx, dict):
            prev = hx.get("attacks_this_phase")
            if isinstance(prev, list) and attacker_id in prev:
                raise ValueError("That unit has already attacked this combat phase")

    def should_auto_advance_phase_after_attack(self, state: GameState) -> bool:
        """
        Advance the schedule when every active unit of the current faction has attacked
        this combat segment and no mandatory retreat is pending.
        """
        if combat.any_retreat_obligation_pending(state):
            return False
        phase = str(state.turn.current_phase)
        if phase not in ("Combat", "Attack"):
            return False
        faction = state.turn.current_faction
        active_ids = {
            u.unit_id
            for u in state.board.units.values()
            if u.active and u.faction == faction
        }
        if not active_ids:
            return True
        hx = state.extension.get("hexdemo")
        if not isinstance(hx, dict):
            return False
        raw = hx.get("attacks_this_phase")
        if not isinstance(raw, list):
            return False
        attacked: set[str] = set()
        for uid in raw:
            if not isinstance(uid, str):
                continue
            u = state.board.units.get(uid)
            if u is not None and u.active and u.faction == faction:
                attacked.add(uid)
        return active_ids <= attacked

    def retreat_obligation_hexes_remaining(
        self, state: GameState, unit_id: str
    ) -> int | None:
        """Optional ``GameDefinition`` hook: read mandatory retreat steps from hexdemo state."""
        return combat.retreat_hexes_remaining(state, unit_id)

    def any_retreat_obligation_pending(self, state: GameState) -> bool:
        """Optional hook: any unit owes a retreat move."""
        return combat.any_retreat_obligation_pending(state)

    def faction_has_pending_retreat_obligation(
        self, state: GameState, faction: str
    ) -> bool:
        """Optional hook: ``faction`` still owes a retreat fulfillment."""
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
        return unit_attr_helpers.default_attributes_for_unit_type(
            self._base, unit_type
        )

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

    def after_phase_transition(self, state: GameState) -> None:
        """
        Called by the server after each `NextPhase` is applied.

        Combat bookkeeping in ``extension['hexdemo']`` is cleared by the engine
        (`GameServer` runs `ClearHexdemoCombatExtension` after every phase advance).
        """
        from .turn_hooks import before_union_move

        t = state.turn
        if t.current_faction == "union" and phase_allows_unit_move(t.current_phase):
            before_union_move(state)


@dataclass(frozen=True, slots=True)
class HexdemoMatchConfig:
    """
    Title-owned settings for one match (authoritative server + thin clients).

    `schedule` `interleaved` (and registry `default`) use the four-phase rota.
    `sequential` uses classic Movement/Attack per faction (IGOUGO).
    """

    schedule: Schedule
    factions: tuple[str, ...] = HEXDEMO_FACTIONS
    movement_budget: float = DEFAULT_MOVEMENT_BUDGET

    @classmethod
    def from_registry_key(cls, key: str) -> HexdemoMatchConfig:
        """
        Map `hexdemo.registry.build_game_definition` ids to a config.

        Keys: `default` / `interleaved` → four-phase rota; `sequential` → Movement/Attack sequential.
        """
        k = key.strip().lower()
        if k in ("default", "interleaved"):
            return cls(schedule="interleaved")
        if k == "sequential":
            return cls(schedule="sequential")
        raise KeyError(f"Unknown hexdemo game definition id: {key!r}")


def game_definition_from_config(config: HexdemoMatchConfig) -> GameDefinition:
    """Return a fresh `GameDefinition` for `config`."""
    if config.schedule == "sequential":
        base: GameDefinition = SequentialTwoFactionGameDefinition(
            factions=config.factions,
            movement_budget=config.movement_budget,
        )
    else:
        base = StaticScheduleGameDefinition(
            hexdemo_four_phase_entries(config.factions),
            movement_budget=config.movement_budget,
        )
    return HexdemoGameDefinition(base)


def default_match_config() -> HexdemoMatchConfig:
    """Default four-phase schedule with `hexdemo.constants.HEXDEMO_FACTIONS`."""
    return HexdemoMatchConfig(schedule="interleaved")
