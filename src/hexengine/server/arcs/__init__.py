"""
Authority **arcs** for multiplayer matches.

An **arc** is a single server-orchestrated thread of work that may span several client
RPCs or internal steps (for example: one `Attack` plus follow-up combat state, or a
stepwise move with interrupt passes). It is “server authority” in that progression
and legality belong to `GameServer` and state actions, not to thin clients.

A **segment** is one atomic step along an arc (one pipeline stage, one hex step in a
path, one interrupt resolution, and so on). Arcs compose segments; turn schedule
phases are a separate layer.

This package holds three arc implementations (`authority_attack`, `authority_movement`,
`authority_combat_cleanup`). Shared vocabulary and movement wire details are documented
in `hexengine.state.movement_arc`.
"""

from __future__ import annotations

from .authority_arc_runtime import (
    ArcRuntimeHost,
    begin_combat_arc,
    begin_movement_arc,
    combat_arc_spec,
    drive_combat_arc_event,
    drive_movement_arc_event,
    movement_arc_spec,
    sync_movement_cursor_from_payload,
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
    "combat_arc_spec",
    "continue_stepwise_move_unit",
    "drive_combat_arc_event",
    "drive_movement_arc_event",
    "movement_arc_spec",
    "sync_movement_cursor_from_payload",
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
