"""
Authority **arcs** for multiplayer matches.

An **arc** is a single server-orchestrated thread of work that may span several client
RPCs or internal steps (for example: one `Attack` plus follow-up combat state, or a
stepwise move with interrupt passes). It is “server authority” in that progression
and legality belong to `GameServer` and state actions, not to thin clients.

A **segment** is one atomic step along an arc (one pipeline stage, one hex step in a
path, one interrupt resolution, and so on). Overlay arcs (combat cleanup,
movement stepwise) suspend the routine arc cursor; the turn registry schedules
which routine arc is active each slot.

This package holds arc runtime bridges (`authority_arc_runtime`, attack/movement/
combat cleanup dispatch). Shared vocabulary and movement wire details are documented
in `hexengine.state.movement_arc`.
"""

from __future__ import annotations

from .authority_arc_runtime import (
    ArcRuntimeHost,
    begin_combat_arc,
    begin_movement_arc,
    begin_routine_slot,
    combat_arc_spec,
    drive_combat_arc_event,
    drive_movement_arc_event,
    lookup_arc_spec,
    movement_arc_spec,
    resolve_active_segment_owner,
    restore_routine_cursor,
    schedule_next_phase_info,
    sync_movement_cursor_from_payload,
    turn_arc_registry_from_hooks,
)
from .authority_attack import (
    AUTHORITY_ATTACK_PIPELINE,
    AuthorityAttackHost,
    AuthorityAttackPipelineStep,
    dedupe_wire_id_list,
    execute_authority_attack_request,
    normalize_attack_party_ids,
    optional_wire_hex_frozenset,
    sorted_unique_hexes_from_unit_ids,
)
from .authority_combat_cleanup import (
    AuthorityCombatCleanupHost,
    finalize_retreat_fulfillment_stack,
    retreat_stack_unit_ids,
    validate_retreat_fulfillment_stack,
    handle_combat_advance_rpc,
    handle_combat_disrupt_instead_of_retreat,
    handle_move_unit_combat_advance_resolution,
    move_unit_is_combat_advance_fulfillment,
)
from .authority_movement import (
    AuthorityMovementHost,
    continue_stepwise_move_unit,
    dedupe_faction_ids,
    handle_authority_move_unit_normal,
    handle_authority_retreat_path_move_unit,
    path_tuple_from_movement_arc,
    read_movement_arc,
)

__all__ = [
    "AUTHORITY_ATTACK_PIPELINE",
    "ArcRuntimeHost",
    "AuthorityAttackHost",
    "AuthorityAttackPipelineStep",
    "AuthorityCombatCleanupHost",
    "AuthorityMovementHost",
    "begin_combat_arc",
    "begin_movement_arc",
    "begin_routine_slot",
    "combat_arc_spec",
    "continue_stepwise_move_unit",
    "drive_combat_arc_event",
    "drive_movement_arc_event",
    "lookup_arc_spec",
    "movement_arc_spec",
    "resolve_active_segment_owner",
    "restore_routine_cursor",
    "schedule_next_phase_info",
    "sync_movement_cursor_from_payload",
    "turn_arc_registry_from_hooks",
    "dedupe_faction_ids",
    "dedupe_wire_id_list",
    "execute_authority_attack_request",
    "finalize_retreat_fulfillment_stack",
    "retreat_stack_unit_ids",
    "validate_retreat_fulfillment_stack",
    "handle_authority_move_unit_normal",
    "handle_authority_retreat_path_move_unit",
    "handle_combat_advance_rpc",
    "handle_combat_disrupt_instead_of_retreat",
    "handle_move_unit_combat_advance_resolution",
    "move_unit_is_combat_advance_fulfillment",
    "normalize_attack_party_ids",
    "optional_wire_hex_frozenset",
    "path_tuple_from_movement_arc",
    "read_movement_arc",
    "sorted_unique_hexes_from_unit_ids",
]
