"""
Post-attack combat cleanup arc pattern (classify → retreat → resolve loop → advance).

Title packs inject guards and effects via ``CombatArcEffectsBinding`` and supply
segment ``ui_mode`` strings for gate-bearing segments (parity with the title FSM table).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ...arcs.runner import ArcSpec, OwnerRefResolver
from ...arcs.spec import CURRENT, NO_OWNER, Arc, ArcContext, OwnerRef
from ...hooks.combat_rules import CombatArcRulesBinding, CombatRulesBinding
from ...state.action_manager import StateAction
from ...ui.display import PanelAction, panel_action
from ..builder import arc, case

COMBAT_ARC_ID = "combat"

SEG_ATTACK = "attack"
SEG_CLASSIFY = "classify"
SEG_RETREAT_GATE = "retreat_gate"
SEG_RETREAT_OR_DISRUPT_GATE = "retreat_or_disrupt_gate"
SEG_RESOLVE = "resolve"
SEG_ADVANCE_GATE = "advance_gate"

OWNER_RETREATING = "retreating"

Guard = Callable[[ArcContext], bool]
Effect = Callable[[ArcContext], list[StateAction]]


@dataclass(frozen=True, slots=True)
class CombatArcGateUiModes:
    """Segment ``ui_mode`` strings for gate-bearing combat arc segments."""

    awaiting_retreat: str
    awaiting_retreat_or_disrupt: str
    awaiting_advance: str


class CombatArcEffectsBinding(Protocol):
    """Host-bound guards and effects wired into the combat cleanup arc."""

    def has_pending_retreat(self, ctx: ArcContext) -> bool: ...

    def disrupt_offered(self, ctx: ArcContext) -> bool: ...

    def advance_available(self, ctx: ArcContext) -> bool: ...

    def is_retreat_fulfillment(self, ctx: ArcContext) -> bool: ...

    def is_combat_advance_move(self, ctx: ArcContext) -> bool: ...

    def apply_retreat_step(self, ctx: ArcContext) -> list[StateAction]: ...

    def disrupt_instead(self, ctx: ArcContext) -> list[StateAction]: ...

    def open_advance(self, ctx: ArcContext) -> list[StateAction]: ...

    def resolve_advance(self, ctx: ArcContext) -> list[StateAction]: ...

    def clear_advance_gate(self, ctx: ArcContext) -> list[StateAction]: ...


def build_combat_cleanup_arc(
    effects: CombatArcEffectsBinding,
    gates: CombatArcGateUiModes,
    *,
    arc_id: str = COMBAT_ARC_ID,
    attack_effect: Effect | None = None,
    attack_ui_mode: str = "combat",
) -> Arc:
    """
    Build the combat arc (optional ``attack`` segment + cleanup subgraph).

    When ``attack_effect`` is set, segment ``attack`` accepts ``Attack`` and hands off to
    ``classify``. Entry stays ``classify`` so ``begin_combat_arc`` can open cleanup-only
    flows after bucket state is already set.

    ``classify`` picks the gate matching what the attack follow-up set. ``resolve`` auto
    re-classifies after each retreat or disrupt step.
    """

    with arc(arc_id, entry=SEG_CLASSIFY) as a:
        if attack_effect is not None:
            with a.segment(
                SEG_ATTACK,
                owner=CURRENT,
                ui_mode=str(attack_ui_mode),
                allowed_actions=frozenset({"Attack"}),
            ) as s:
                s.on("Attack", effect=attack_effect, goto=SEG_CLASSIFY)

        with a.segment(SEG_CLASSIFY, owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=effects.disrupt_offered, goto=SEG_RETREAT_OR_DISRUPT_GATE),
                case(guard=effects.has_pending_retreat, goto=SEG_RETREAT_GATE),
                case(
                    guard=effects.advance_available,
                    effect=effects.open_advance,
                    goto=SEG_ADVANCE_GATE,
                ),
                case(done=True),
            )

        with a.segment(
            SEG_RETREAT_GATE,
            owner=OwnerRef(OWNER_RETREATING),
            ui_mode=gates.awaiting_retreat,
        ) as s:
            s.on(
                "MoveUnit",
                guard=effects.is_retreat_fulfillment,
                effect=effects.apply_retreat_step,
                goto=SEG_RESOLVE,
            )

        with a.segment(
            SEG_RETREAT_OR_DISRUPT_GATE,
            owner=OwnerRef(OWNER_RETREATING),
            ui_mode=gates.awaiting_retreat_or_disrupt,
        ) as s:
            s.on(
                "MoveUnit",
                guard=effects.is_retreat_fulfillment,
                effect=effects.apply_retreat_step,
                goto=SEG_RESOLVE,
            )
            s.on(
                "CombatDisruptInsteadOfRetreat",
                effect=effects.disrupt_instead,
                goto=SEG_RESOLVE,
            )

        with a.segment(SEG_RESOLVE, owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=effects.has_pending_retreat, goto=SEG_RETREAT_GATE),
                case(
                    guard=effects.advance_available,
                    effect=effects.open_advance,
                    goto=SEG_ADVANCE_GATE,
                ),
                case(done=True),
            )

        with a.segment(
            SEG_ADVANCE_GATE,
            owner=CURRENT,
            ui_mode=gates.awaiting_advance,
        ) as s:
            s.on("CombatAdvance", effect=effects.resolve_advance, done=True)
            s.on(
                "MoveUnit",
                guard=effects.is_combat_advance_move,
                effect=effects.resolve_advance,
                done=True,
            )
            s.on("CombatDeclineAdvance", effect=effects.clear_advance_gate, done=True)

    return a.build()


def combat_gate_panel_actions(
    segment: Mapping[str, Any] | None,
    shell_ui: Mapping[str, Any],
) -> tuple[PanelAction, ...]:
    """
    Optional dock rows for combat cleanup gate ``allowed_actions``.

    Titles using ``build_combat_cleanup_arc`` call this from ``TURN_ACTION_DOCK_FOR_VIEWER``;
    the engine catalog default dock does not inject these rows.
    """

    if not segment:
        return ()

    raw = segment.get("allowed_actions")
    if not isinstance(raw, list):
        return ()

    su = shell_ui if isinstance(shell_ui, Mapping) else {}
    out: list[PanelAction] = []

    def _label(key: str, default: str) -> str:
        raw_label = su.get(key)
        if isinstance(raw_label, str) and raw_label.strip():
            return raw_label.strip()
        return default

    for action_type in raw:
        at = str(action_type).strip()
        if not at or at == "NextPhase":
            continue
        if at == "CombatDisruptInsteadOfRetreat":
            out.append(
                panel_action(
                    id="combat_disrupt_instead",
                    action_type=at,
                    label=_label("disrupt_instead_label", "Disrupt instead of retreat"),
                    title=_label(
                        "disrupt_instead_title",
                        "Take disruption on your retreating stack and waive "
                        "the mandatory retreat (when the title allows).",
                    ),
                    payload={},
                    css_class="hexengine-primary-action--disrupt",
                    enabled=True,
                )
            )
        elif at == "CombatAdvance":
            out.append(
                panel_action(
                    id="combat_advance",
                    action_type=at,
                    label=_label("combat_advance_label", "Advance"),
                    title=_label(
                        "combat_advance_title",
                        "Advance after opponent retreats (when allowed).",
                    ),
                    payload={},
                    css_class="hexengine-primary-action--advance",
                    enabled=True,
                )
            )
        elif at == "CombatDeclineAdvance":
            out.append(
                panel_action(
                    id="combat_decline_advance",
                    action_type=at,
                    label=_label("combat_decline_advance_label", "Skip"),
                    title=_label(
                        "combat_decline_advance_title",
                        "Skip the optional advance.",
                    ),
                    payload={},
                    css_class="hexengine-primary-action--decline-advance",
                    enabled=True,
                )
            )

    return tuple(out)


_COMBAT_RULES_BINDING_METHODS: tuple[str, ...] = (
    "validate_attack",
    "resolve_attack",
    "combat_outcome_after_applied",
    "detect_combat_advance_move",
    "has_pending_retreat",
    "disrupt_offered",
    "advance_available",
    "is_retreat_fulfillment",
    "is_combat_advance_move",
    "apply_retreat_step",
    "disrupt_instead",
    "open_advance",
    "resolve_advance",
    "clear_advance_gate",
)


def combat_rules_binding_missing_methods(binding: Any) -> tuple[str, ...]:
    """Return method names missing from a ``CombatRulesBinding`` (empty when complete)."""

    missing: list[str] = []
    for name in _COMBAT_RULES_BINDING_METHODS:
        if not callable(getattr(binding, name, None)):
            missing.append(name)
    return tuple(missing)


def combat_rules_binding_satisfies(binding: Any) -> bool:
    return not combat_rules_binding_missing_methods(binding)


class CombatRulesEffectsAdapter:
    """Bridge a ``CombatRulesBinding`` into ``CombatArcEffectsBinding`` for the pattern."""

    def __init__(self, binding: CombatArcRulesBinding) -> None:
        self._binding = binding

    def has_pending_retreat(self, ctx: ArcContext) -> bool:
        return bool(self._binding.has_pending_retreat(ctx))

    def disrupt_offered(self, ctx: ArcContext) -> bool:
        return bool(self._binding.disrupt_offered(ctx))

    def advance_available(self, ctx: ArcContext) -> bool:
        return bool(self._binding.advance_available(ctx))

    def is_retreat_fulfillment(self, ctx: ArcContext) -> bool:
        return bool(self._binding.is_retreat_fulfillment(ctx))

    def is_combat_advance_move(self, ctx: ArcContext) -> bool:
        return bool(self._binding.is_combat_advance_move(ctx))

    def apply_retreat_step(self, ctx: ArcContext) -> list[StateAction]:
        return list(self._binding.apply_retreat_step(ctx))

    def disrupt_instead(self, ctx: ArcContext) -> list[StateAction]:
        return list(self._binding.disrupt_instead(ctx))

    def open_advance(self, ctx: ArcContext) -> list[StateAction]:
        return list(self._binding.open_advance(ctx))

    def resolve_advance(self, ctx: ArcContext) -> list[StateAction]:
        return list(self._binding.resolve_advance(ctx))

    def clear_advance_gate(self, ctx: ArcContext) -> list[StateAction]:
        return list(self._binding.clear_advance_gate(ctx))


def combat_rules_effects_adapter(
    binding: CombatArcRulesBinding,
) -> CombatRulesEffectsAdapter:
    """Wrap a ``CombatRulesBinding`` for ``build_combat_cleanup_arc`` / pack graph builders."""

    return CombatRulesEffectsAdapter(binding)


def combat_arc_to_spec(
    arc_obj: Arc,
    *,
    owner_resolver: OwnerRefResolver | None = None,
    advance_move_detector: Callable[..., bool] | None = None,
) -> ArcSpec:
    """Wrap a built combat ``Arc`` in ``ArcSpec`` metadata (owner resolver, advance detector)."""

    return ArcSpec(
        arc=arc_obj,
        owner_resolver=owner_resolver,
        advance_move_detector=advance_move_detector,
    )


def combat_rules_binding_to_arc_spec(
    binding: CombatRulesBinding,
    gates: CombatArcGateUiModes,
    *,
    arc_id: str = COMBAT_ARC_ID,
    owner_resolver: OwnerRefResolver | None = None,
    advance_move_detector: Callable[..., bool] | None = None,
    attack_effect: Effect | None = None,
    attack_ui_mode: str = "combat",
) -> ArcSpec:
    """
    Build ``ArcSpec`` from one author binding (cleanup subgraph + optional attack segment).

    Titles that own the graph in pack code should call ``combat_arc_to_spec`` on a
    locally built ``Arc`` instead.
    """

    if not combat_rules_binding_satisfies(binding):
        missing = ", ".join(combat_rules_binding_missing_methods(binding))
        raise TypeError(f"CombatRulesBinding missing methods: {missing}")

    effects = combat_rules_effects_adapter(binding)
    return combat_arc_to_spec(
        build_combat_cleanup_arc(
            effects,
            gates,
            arc_id=arc_id,
            attack_effect=attack_effect,
            attack_ui_mode=attack_ui_mode,
        ),
        owner_resolver=owner_resolver,
        advance_move_detector=advance_move_detector
        or binding.detect_combat_advance_move,
    )


__all__ = [
    "COMBAT_ARC_ID",
    "CombatArcEffectsBinding",
    "CombatArcGateUiModes",
    "OWNER_RETREATING",
    "SEG_ADVANCE_GATE",
    "SEG_ATTACK",
    "SEG_CLASSIFY",
    "SEG_RESOLVE",
    "SEG_RETREAT_GATE",
    "SEG_RETREAT_OR_DISRUPT_GATE",
    "build_combat_cleanup_arc",
    "CombatRulesEffectsAdapter",
    "combat_arc_to_spec",
    "combat_gate_panel_actions",
    "combat_rules_binding_missing_methods",
    "combat_rules_binding_satisfies",
    "combat_rules_binding_to_arc_spec",
    "combat_rules_effects_adapter",
]
