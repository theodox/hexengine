"""
Server-side attack plan preview (map selection draft → legality + commit payload).

Shared by ``hooks/interaction.attack_plan_preview`` and tests; mirrors hexdemo
``validate_attack`` eligibility without duplicating CRT resolution.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hexengine.authoring.present import map_selection_preview, panel_action
from hexengine.arcs.title.attack_wire import (
    normalize_attack_party_ids,
    sorted_unique_hexes_from_unit_ids,
)
from hexengine.hexes.los import has_line_of_sight
from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
from hexengine.hooks.interaction import AttackContext, InteractionHooks
from hexengine.retreat_path import hexes_to_wire
from hexengine.state import GameState
from hexengine.state.map_feature_queries import edges_block_los_predicate
from hexengine.ui.display import MapSelectionPreview, PanelAction

from ..state import session_state
from .transitions import attack_planning_blocked_reason

_ATTACK_KIND = "combined"
_ATTACK_PLAN_KIND = "attack_plan"
_ATTACK_DRAFT_PRESENTATION_ID = "attack_draft"


def _attack_plan_draft_policy(draft: Mapping[str, Any]) -> dict[str, Any]:
    """Consult-only dock policy while the client holds an attack-plan snapshot."""

    if _parse_target_hex(dict(draft)) is None and not _parse_attacker_ids(dict(draft)):
        return {}
    return {
        "disable_end_phase": True,
        "draft_presentation_id": _ATTACK_DRAFT_PRESENTATION_ID,
    }


def _shell_label(shell_ui: Mapping[str, Any], key: str, default: str) -> str:
    raw = shell_ui.get(key) if isinstance(shell_ui, Mapping) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return default


def _terrain_blocks_los(board):
    def blocks(h: Hex) -> bool:
        loc = board.effective_location(h)
        if loc is None:
            return False
        return bool(getattr(loc, "block_los", False))

    return blocks


def _unit_can_attack_defender_hex(
    state: GameState,
    unit_id: str,
    defender_hex: Hex,
    *,
    blocks,
    edges_block,
) -> bool:
    u = state.board.units.get(unit_id)
    if u is None or not u.active:
        return False
    if u.faction != state.turn.current_faction:
        return False
    ut = str(u.unit_type).lower()
    if ut in ("infantry", "inf"):
        return distance(u.position, defender_hex) == 1
    if ut in ("artillery", "art"):
        try:
            atk_range = int(u.attributes.get("range", 0))
        except (TypeError, ValueError):
            atk_range = 0
        d = distance(u.position, defender_hex)
        if not (atk_range > 1 and d > 1 and d <= atk_range):
            return False
        return has_line_of_sight(
            u.position, defender_hex, blocks=blocks, edges_block=edges_block
        )
    return False


def _enemy_on_hex(state: GameState, h: Hex, attacker_faction: str) -> bool:
    for u in state.board.active_units_at_hex(h):
        if u.faction != attacker_faction:
            return True
    return False


def _already_attacked_this_phase(state: GameState, unit_id: str) -> bool:
    return unit_id in session_state.attacks_this_phase(state)


def _parse_target_hex(draft: dict[str, Any]) -> Hex | None:
    raw = draft.get("target_hex")
    if not isinstance(raw, dict):
        return None
    try:
        return Hex(int(raw["i"]), int(raw["j"]), int(raw["k"]))
    except (KeyError, TypeError, ValueError):
        return None


def _parse_attacker_ids(draft: dict[str, Any]) -> list[str]:
    raw = draft.get("attacker_ids")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for x in raw:
        if isinstance(x, str) and (s := x.strip()) and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _valid_target_hexes(
    state: GameState,
    *,
    board_hexes: list[Hex],
    player_faction: str,
) -> list[Hex]:
    blocks = _terrain_blocks_los(state.board)
    edges_block = edges_block_los_predicate(state.board)
    fac = str(player_faction).strip()
    out: list[Hex] = []
    seen: set[tuple[int, int, int]] = set()
    for h in board_hexes:
        if not _enemy_on_hex(state, h, fac):
            continue
        t = (int(h.i), int(h.j), int(h.k))
        if t in seen:
            continue
        for uid, u in state.board.units.items():
            if not u.active or u.faction != fac:
                continue
            if _already_attacked_this_phase(state, uid):
                continue
            if _unit_can_attack_defender_hex(
                state, uid, h, blocks=blocks, edges_block=edges_block
            ):
                seen.add(t)
                out.append(h)
                break
    return sorted(out, key=lambda x: (x.i, x.j, x.k))


def _eligible_attacker_ids(
    state: GameState,
    target_hex: Hex,
    *,
    player_faction: str,
) -> list[str]:
    blocks = _terrain_blocks_los(state.board)
    edges_block = edges_block_los_predicate(state.board)
    fac = str(player_faction).strip()
    out: list[str] = []
    for uid, u in sorted(state.board.units.items()):
        if not u.active or u.faction != fac:
            continue
        if _already_attacked_this_phase(state, uid):
            continue
        if _unit_can_attack_defender_hex(
            state, uid, target_hex, blocks=blocks, edges_block=edges_block
        ):
            out.append(uid)
    return out


def build_attack_commit_payload(
    state: GameState,
    *,
    target_hex: Hex,
    attacker_ids: list[str],
) -> dict[str, Any] | None:
    """Wire ``Attack`` params matching client ``confirm_attack_plan``."""
    if not attacker_ids:
        return None
    fac = str(state.turn.current_faction).strip()
    defenders = [
        u
        for u in state.board.active_units_at_hex(target_hex)
        if u.faction != fac and u.active
    ]
    if not defenders:
        return None
    defender_id = defenders[-1].unit_id
    defender_ids = sorted(str(u.unit_id) for u in defenders)
    attacker_ids_sorted = sorted(attacker_ids)
    primary_attacker_id = attacker_ids_sorted[0]

    seen_att: set[tuple[int, int, int]] = set()
    attacker_hexes_wire: list[dict[str, int]] = []
    for uid in attacker_ids_sorted:
        u = state.board.units.get(uid)
        if u is None or not u.active:
            continue
        t = (int(u.position.i), int(u.position.j), int(u.position.k))
        if t in seen_att:
            continue
        seen_att.add(t)
        attacker_hexes_wire.append({"i": t[0], "j": t[1], "k": t[2]})
    attacker_hexes_wire.sort(key=lambda d: (d["i"], d["j"], d["k"]))
    defender_hexes_wire = [
        {"i": int(target_hex.i), "j": int(target_hex.j), "k": int(target_hex.k)},
    ]
    return {
        "attack_kind": _ATTACK_KIND,
        "attacker_id": primary_attacker_id,
        "attacker_ids": attacker_ids_sorted,
        "defender_id": defender_id,
        "defender_ids": defender_ids,
        "attacker_hexes": attacker_hexes_wire,
        "defender_hexes": defender_hexes_wire,
    }


def _try_validate_commit(
    state: GameState,
    player_faction: str,
    payload: dict[str, Any],
    *,
    interaction_hooks: InteractionHooks,
) -> str | None:
    """Return an error string when commit would fail validate_attack; else None."""
    fn = interaction_hooks.validate_attack
    if fn is None:
        return "Attack validation not configured"
    anchor_a = str(payload.get("attacker_id", "")).strip()
    anchor_d = str(payload.get("defender_id", "")).strip()
    if not anchor_a or not anchor_d:
        return "Incomplete attack plan"
    attacker_ids = normalize_attack_party_ids(
        payload, anchor_id=anchor_a, plural_key="attacker_ids"
    )
    defender_ids = normalize_attack_party_ids(
        payload, anchor_id=anchor_d, plural_key="defender_ids"
    )
    attacker_hexes = sorted_unique_hexes_from_unit_ids(state, attacker_ids)
    defender_hexes = sorted_unique_hexes_from_unit_ids(state, defender_ids)
    ctx = AttackContext(
        state=state,
        attacker_ids=attacker_ids,
        defender_ids=defender_ids,
        attacker_hexes=attacker_hexes,
        defender_hexes=defender_hexes,
        player_faction=str(player_faction).strip(),
        attack_kind=str(payload.get("attack_kind", _ATTACK_KIND)).strip(),
        params=dict(payload),
    )
    try:
        fn(ctx)
    except Exception as e:
        return str(e)
    return None


def _panel_actions(
    shell_ui: Mapping[str, Any],
    *,
    confirm_enabled: bool,
    has_draft: bool,
) -> tuple[PanelAction, ...]:
    if not has_draft:
        return ()
    return (
        panel_action(
            id="attack_plan_confirm",
            action_type="Attack",
            label=_shell_label(shell_ui, "attack_confirm_label", "Confirm attack"),
            title=_shell_label(
                shell_ui,
                "attack_confirm_label",
                "Confirm attack",
            ),
            payload={},
            css_class="hexengine-primary-action--confirm",
            enabled=confirm_enabled,
        ),
        panel_action(
            id="attack_plan_cancel",
            action_type="AttackPlanCancel",
            label=_shell_label(shell_ui, "attack_cancel_label", "Cancel"),
            title=_shell_label(shell_ui, "attack_cancel_label", "Cancel attack plan"),
            payload={},
            css_class="hexengine-primary-action--cancel",
            enabled=True,
        ),
    )


def compute_attack_plan_preview(
    state: GameState,
    *,
    player_faction: str,
    draft: dict[str, Any],
    shell_ui: Mapping[str, Any],
    board_hexes: list[Hex],
    interaction_hooks: InteractionHooks,
) -> MapSelectionPreview:
    """Map-selection preview for ``kind=attack_plan``."""
    blocked = attack_planning_blocked_reason(state, player_faction)
    if blocked:
        return map_selection_preview(
            kind=_ATTACK_PLAN_KIND,
            status_text=blocked,
            confirm_enabled=False,
            valid_target_hexes=[],
            eligible_attacker_ids=[],
        )

    target = _parse_target_hex(draft)
    attacker_ids = _parse_attacker_ids(draft)

    if target is None:
        targets = _valid_target_hexes(
            state, board_hexes=board_hexes, player_faction=player_faction
        )
        status = _shell_label(
            shell_ui,
            "attack_pick_target_status",
            "Combat: select target hex and attackers, then confirm.",
        )
        return map_selection_preview(
            kind=_ATTACK_PLAN_KIND,
            status_text=status,
            confirm_enabled=False,
            valid_target_hexes=hexes_to_wire(targets),
            eligible_attacker_ids=[],
        )

    if not _enemy_on_hex(state, target, str(player_faction).strip()):
        status = "No enemy unit on target"
        return map_selection_preview(
            kind=_ATTACK_PLAN_KIND,
            status_text=status,
            confirm_enabled=False,
            valid_target_hexes=hexes_to_wire(
                _valid_target_hexes(
                    state, board_hexes=board_hexes, player_faction=player_faction
                )
            ),
            eligible_attacker_ids=[],
            panel_actions=_panel_actions(
                shell_ui, confirm_enabled=False, has_draft=True
            ),
            **_attack_plan_draft_policy(draft),
        )

    eligible = _eligible_attacker_ids(state, target, player_faction=player_faction)
    selected = [uid for uid in attacker_ids if uid in eligible]
    commit = (
        build_attack_commit_payload(state, target_hex=target, attacker_ids=selected)
        if selected
        else None
    )
    err = (
        _try_validate_commit(state, player_faction, commit, interaction_hooks=interaction_hooks)
        if commit
        else "Select at least one attacker"
    )
    confirm_enabled = commit is not None and err is None
    if err and selected:
        status = err
    elif not selected:
        status = _shell_label(
            shell_ui,
            "attack_target_set_status",
            "Target set — select attackers, then confirm.",
        )
    else:
        status = _shell_label(
            shell_ui,
            "attack_target_set_status",
            "Target set — adjust attackers or confirm.",
        )

    return map_selection_preview(
        kind=_ATTACK_PLAN_KIND,
        status_text=status,
        confirm_enabled=confirm_enabled,
        valid_target_hexes=hexes_to_wire(
            _valid_target_hexes(
                state, board_hexes=board_hexes, player_faction=player_faction
            )
        ),
        eligible_attacker_ids=eligible,
        commit_payload=commit if confirm_enabled else None,
        panel_actions=_panel_actions(
            shell_ui,
            confirm_enabled=confirm_enabled,
            has_draft=True,
        ),
        **_attack_plan_draft_policy(draft),
    )


__all__ = [
    "compute_attack_plan_preview",
    "build_attack_commit_payload",
]
