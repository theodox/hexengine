"""Contract sentinels, `@hook` metadata, catalog, and `validate_title_contract`."""

from __future__ import annotations

import dataclasses
import types

import pytest

from hexengine.hooks.attack import AttackHook, AttackHooks, attack_hooks_unsupported
from hexengine.hooks.core import (
    ENGINE_DEFAULT,
    PRESET,
    REQUIRED,
    SINGLE_DEFAULT,
    HookContractError,
)
from hexengine.hooks.internal import (
    get_engine_catalog_hook,
    hook,
    movement_budget_for_unit_engine_default,
    validate_title_contract,
)
from hexengine.hooks.movement import MovementHook, MovementHooks
from hexengine.hooks.preset_options import PresetOptions
from hexengine.hooks.title import TitleHooks
from hexengine.hooks.ui import (
    AdvanceGateInteractionContext,
    PhaseBannerContext,
    UIHook,
    UIHooks,
    default_advance_gate_banners_for_viewer,
    default_phase_banner_text_for_viewer,
)
from hexengine.hooks.ui_segment import SegmentPresentationPatch
from hexengine.hooks.wiring import assemble_title_hooks, bind_title_hook
from hexengine.state import GameState
from hexengine.state.logic import DEFAULT_MOVEMENT_BUDGET


def test_contract_sentinels_are_distinct() -> None:
    assert len({REQUIRED, PRESET, SINGLE_DEFAULT, ENGINE_DEFAULT}) == 4


def test_hook_metadata_default_contract() -> None:
    @hook()
    def sample_move(_x: int) -> int:
        return _x

    assert sample_move.__hexengine_hook_contract__ is SINGLE_DEFAULT
    assert not hasattr(sample_move, "__hexengine_engine_impl__")


def test_hook_metadata_required_and_engine_impl() -> None:
    def _impl(_: int) -> int:
        return 1

    @hook(contract=REQUIRED, engine_impl=_impl)
    def need_title(_x: int) -> int:
        raise NotImplementedError

    assert need_title.__hexengine_hook_contract__ is REQUIRED
    assert need_title.__hexengine_engine_impl__ is _impl


def test_hook_metadata_preset_bundle() -> None:
    p = PresetOptions(A=lambda: 1, B=lambda: 2)

    @hook(contract=PRESET, presets=p, preset_attr="speed")
    def preset_fn() -> None:
        return None

    assert preset_fn.__hexengine_hook_contract__ is PRESET
    assert preset_fn.__hexengine_presets__ is p
    assert preset_fn.__hexengine_preset_attr__ == "speed"


def test_validate_title_contract_skips_unknown_or_move_only_schedule() -> None:
    validate_title_contract(object())


def test_validate_title_contract_fails_when_combat_phase_without_attack_hooks() -> None:
    from hexengine.gamedef.game_data import GameData

    class BadAttack:
        def turn_order(self) -> list[dict[str, object]]:
            return [{"faction": "A", "phase": "Attack", "max_actions": 1}]

        hooks = TitleHooks()

        @property
        def game_data(self) -> GameData:
            return GameData.empty()

    class BadCombat:
        def turn_order(self) -> list[dict[str, object]]:
            return [{"faction": "U", "phase": "Combat", "max_actions": 2}]

        hooks = TitleHooks()

        @property
        def game_data(self) -> GameData:
            return GameData.empty()

    for bad in (BadAttack(), BadCombat()):
        with pytest.raises(HookContractError):
            validate_title_contract(bad)


def test_validate_title_contract_passes_builtin_combat_schedule() -> None:
    from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition

    validate_title_contract(InterleavedTwoFactionGameDefinition())


def test_validate_title_contract_requires_turn_action_dock_when_extension_key() -> None:
    from hexengine.gamedef.game_data import GameData

    class PackWithExtension:
        @property
        def game_data(self) -> GameData:
            return GameData.empty().replacing(title_state_extension_key="pack")

        hooks = TitleHooks()

    with pytest.raises(HookContractError, match="turn_action_dock_for_viewer"):
        validate_title_contract(PackWithExtension())


def test_validate_title_contract_requires_combat_arc_with_extension_key() -> None:
    from hexengine.authoring.patterns.schedule import (
        build_turn_registry,
        interleaved_slots,
    )
    from hexengine.gamedef.game_data import GameData
    from hexengine.hooks.arcs import ArcsHooks
    from hexengine.hooks.ui_turn_action_dock import empty_turn_action_dock_for_viewer

    turn_registry = build_turn_registry(
        interleaved_slots(
            ("Red", "Blue"),
            (("Movement", 2, "move"), ("Attack", 2, "attack")),
            faction_first=True,
        ),
        allowed_actions_for_phase=lambda phase: frozenset({"NextPhase"}),
    )

    class PackWithoutCombatArc:
        @property
        def game_data(self) -> GameData:
            return GameData.empty().replacing(title_state_extension_key="pack")

        hooks = TitleHooks(
            ui=UIHooks(
                turn_action_dock_for_viewer=empty_turn_action_dock_for_viewer,
                segment_presentation_registry=lambda: frozenset({"move", "attack"}),
                enrich_current_segment=lambda _ctx: SegmentPresentationPatch(),
            ),
            arcs=ArcsHooks(turn_arc_registry=lambda: turn_registry),
        )

        def turn_order(self):
            return []

    with pytest.raises(HookContractError, match="COMBAT_ARC"):
        validate_title_contract(PackWithoutCombatArc())


def test_validate_title_contract_checks_combat_rules_binding_methods() -> None:
    from hexengine.arcs import ArcSpec
    from hexengine.authoring.patterns.schedule import (
        build_turn_registry,
        interleaved_slots,
    )
    from hexengine.gamedef.game_data import GameData
    from hexengine.hooks.arcs import ArcsHooks
    from hexengine.hooks.ui_turn_action_dock import empty_turn_action_dock_for_viewer

    slots = interleaved_slots(
        ("blue", "red"),
        (("Combat", 1, "combat"),),
    )
    reg = build_turn_registry(
        slots, allowed_actions_for_phase=lambda _p: frozenset({"Attack"})
    )

    class IncompleteBinding:
        def validate_attack(self, _ctx):
            return None

    class PackWithIncompleteBinding:
        @property
        def game_data(self) -> GameData:
            return GameData.empty().replacing(title_state_extension_key="pack")

        def turn_order(self):
            return [{"faction": "blue", "phase": "Combat", "max_actions": 1}]

        hooks = TitleHooks(
            ui=UIHooks(
                turn_action_dock_for_viewer=empty_turn_action_dock_for_viewer,
                segment_presentation_registry=lambda: frozenset({"combat"}),
                enrich_current_segment=lambda _ctx: SegmentPresentationPatch(),
            ),
            arcs=ArcsHooks(
                turn_arc_registry=lambda: reg,
                combat_arc=lambda: ArcSpec(arc=reg.routine_specs["blue_combat"].arc),
                combat_rules_binding=lambda: IncompleteBinding(),
            ),
            attack=AttackHooks(
                validate_attack=lambda _c: None,
                resolve_attack=lambda _c: None,
            ),
        )

    with pytest.raises(HookContractError, match="COMBAT_RULES_BINDING"):
        validate_title_contract(PackWithIncompleteBinding())


def test_validate_title_contract_requires_turn_arc_registry_with_extension_key() -> (
    None
):
    from hexengine.gamedef.game_data import GameData
    from hexengine.hooks.ui_turn_action_dock import empty_turn_action_dock_for_viewer

    class PackWithDockOnly:
        @property
        def game_data(self) -> GameData:
            return GameData.empty().replacing(title_state_extension_key="pack")

        hooks = TitleHooks(
            ui=UIHooks(turn_action_dock_for_viewer=empty_turn_action_dock_for_viewer),
        )

    with pytest.raises(HookContractError, match="TURN_ARC_REGISTRY"):
        validate_title_contract(PackWithDockOnly())


def test_engine_catalog_has_movement_budget_default() -> None:
    fn = get_engine_catalog_hook("movement.movement_budget_for_unit")
    assert fn is movement_budget_for_unit_engine_default


def test_engine_catalog_auto_advance_after_move_spend_when_depleted() -> None:
    from hexengine.hooks.internal.catalog import (
        auto_advance_phase_after_move_spend_engine_default,
    )
    from hexengine.hooks.movement_advance import (
        default_auto_advance_phase_after_move_spend,
    )
    from hexengine.state.game_state import TurnState

    fn = get_engine_catalog_hook("movement.auto_advance_phase_after_move_spend")
    assert fn is auto_advance_phase_after_move_spend_engine_default
    import dataclasses

    st = GameState.create_empty()
    assert default_auto_advance_phase_after_move_spend(st) is False
    st2 = dataclasses.replace(
        st,
        turn=TurnState(
            current_faction="A",
            current_phase="Move",
            phase_actions_remaining=0,
            turn_number=st.turn.turn_number,
            schedule_index=st.turn.schedule_index,
        ),
    )
    assert default_auto_advance_phase_after_move_spend(st2) is True


def test_attack_hooks_unsupported_contract() -> None:
    a = attack_hooks_unsupported()
    assert a.validate_attack is not None and a.resolve_attack is not None


def test_hook_accepts_title_field_for_assembly() -> None:
    @hook(title_field="attack.validate_attack")
    def _stub_attack_validate(_ctx: object) -> None:
        return None

    assert _stub_attack_validate.__hexengine_title_field__ == ("attack.validate_attack")


def test_assemble_title_hooks_from_modules() -> None:
    @bind_title_hook(MovementHook.MOVEMENT_BUDGET_FOR_UNIT)
    def budget(_s: object, _u: str) -> float:
        return 1.0

    mod = types.ModuleType("hexengine_test_wiring")
    mod.budget = budget
    th = assemble_title_hooks(mod)
    assert th.movement.movement_budget_for_unit is budget


def test_hook_enum_members_match_dataclass_fields() -> None:
    assert {e.value for e in MovementHook} == {
        f.name for f in dataclasses.fields(MovementHooks)
    }
    assert {e.value for e in AttackHook} == {
        f.name for f in dataclasses.fields(AttackHooks)
    }
    assert {e.value for e in UIHook} == {f.name for f in dataclasses.fields(UIHooks)}


def test_assemble_title_hooks_rejects_duplicate_paths() -> None:
    from hexengine.authoring.present import inform_popup
    from hexengine.hooks.inform_popup import InformPopupContext

    @bind_title_hook(UIHook.INFORM_POPUP)
    def a(_ctx: InformPopupContext):
        return inform_popup(text="a")

    @bind_title_hook(UIHook.INFORM_POPUP)
    def b(_ctx: InformPopupContext):
        return inform_popup(text="b")

    mod = types.ModuleType("hexengine_test_wiring_dup")
    mod.a = a
    mod.b = b
    with pytest.raises(HookContractError):
        assemble_title_hooks(mod)


def test_bind_title_hook_rebind_raises() -> None:
    with pytest.raises(ValueError, match="already bound"):

        @bind_title_hook(MovementHook.VALIDATE_MOVE)
        @bind_title_hook(MovementHook.VALIDATE_MOVE)
        def _twice() -> None:  # pragma: no cover - definition fails
            pass


def test_hexdemo_build_hooks_wires_all_marked() -> None:
    from games.hexdemo.hooks import build_hooks

    th = build_hooks()
    assert th.movement.zoc_hexes_for_unit is not None
    assert th.attack.validate_attack is not None
    assert th.ui.inform_popup is not None
    assert th.ui.phase_banner_text_for_viewer is not None
    assert th.ui.phase_banner_html_for_viewer is not None
    assert th.ui.combat_instruction_for_viewer is not None
    assert th.ui.advance_gate_banners_for_viewer is not None
    assert th.ui.turn_action_dock_for_viewer is not None
    assert th.ui.combat_interaction_messages is not None


def test_segment_gate_actions_disrupt_row() -> None:
    from hexengine.arcs.segment_wire import action_rows_from_segment

    segment = {
        "schema": 1,
        "arc_id": "combat",
        "segment_id": "retreat_or_disrupt_gate",
        "kind": "awaiting_retreat_or_disrupt",
        "owner": "confederate",
        "allowed_actions": ["MoveUnit", "CombatDisruptInsteadOfRetreat"],
        "action_locus": {},
    }
    rows = action_rows_from_segment(segment, {})
    types = {r.action_type for r in rows}
    assert "CombatDisruptInsteadOfRetreat" in types


def test_movement_budget_catalog_default_matches_engine_constant() -> None:
    st = GameState.create_empty()
    assert movement_budget_for_unit_engine_default(st, "any") == float(
        DEFAULT_MOVEMENT_BUDGET
    )
    assert (
        movement_budget_for_unit_engine_default.__hexengine_hook_contract__
        is SINGLE_DEFAULT
    )


def test_default_advance_gate_banners_pair() -> None:
    st = GameState.create_empty()
    ctx = AdvanceGateInteractionContext(
        state=st,
        viewer_faction="union",
        advancing_faction="union",
    )
    a, w = default_advance_gate_banners_for_viewer(ctx)
    assert "Advance" in a and "Waiting" in w


def test_default_phase_banner_text_format() -> None:
    st = GameState.create_empty()
    ctx = PhaseBannerContext(
        state=st,
        viewer_faction=None,
        current_faction="union",
        current_phase="Move",
        schedule_index=0,
        phase_actions_remaining=2,
    )
    s = default_phase_banner_text_for_viewer(ctx)
    assert "union" in s and "Move" in s and "actions: 2" in s
