"""
UI-related hooks.

Role in turn resolution:

- The server remains authoritative and computes per-recipient `StateUpdate` payloads.
- Titles can customize what transient messages are shown to each viewer by returning
  `interaction_messages` for a given authoritative `GameState`. Each row may include
  optional `html` for rich banner content (the client prefers `html` over `text`).
- The browser client renders these messages using CSS (titles can provide CSS via
  `turn_rules.faction_ui.css`).
- Optional `map_overlays` returns a list of overlay specs; the engine client creates
  and removes DOM under `#map-world` (map-space coordinates, same pan/zoom as units).

Engine-level messages (network disconnect, exceptions, etc.) are always allowed to
override UI locally on the client and do not require title hooks.

**Title wiring:** use `UIHook` members with `hexengine.hooks.wiring.bind_title_hook`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..state import GameState
from ..ui.display import (
    InformPopup,
    InteractionMessage,
    MapOverlay,
    MapSelectionPreview,
    TurnDockPanel,
)
from .core import ENGINE_DEFAULT, RuleViolation
from .inform_popup import InformPopupContext
from .ui_combat_messages import CombatInteractionMessagesContext
from .ui_segment import SegmentPresentationContext, SegmentPresentationPatch
from .ui_turn_action_dock import TurnActionDockContext


@dataclass(frozen=True, slots=True)
class CombatInteractionContext:
    """Context for combat or retreat interaction lines shown to one viewer."""

    state: GameState
    viewer_faction: str | None
    outcome: str
    retreat_owner_faction: str | None
    shell_ui: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdvanceGateInteractionContext:
    """Context when the active segment is the optional post-retreat advance window."""

    state: GameState
    viewer_faction: str | None
    advancing_faction: str
    shell_ui: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CombatEventSummary:
    """Title-extracted combat result used to fan out per-viewer `combat_event` wires.

    The engine builds `CombatEventWire` per connected player from this summary plus the
    per-viewer `combat_instruction_for_viewer` hook; titles own how to derive it from
    their match state (the engine does not read title bucket combat keys).
    """

    attack_kind: str
    outcome: str
    attacker_id: str
    defender_id: str
    retreat_distance: int | None = None
    retreat_unit_id: str | None = None
    retreat_hexes_remaining: int | None = None


@dataclass(frozen=True, slots=True)
class PlaceMarkerPreviewContext:
    """
    Inputs for ``map_selection_preview`` when ``kind`` is ``place_marker``.

    ``draft`` is a client-supplied snapshot for consultation only, not
    authoritative state until commit.
    """

    state: GameState
    player_faction: str
    draft: dict[str, Any]
    shell_ui: dict[str, Any]
    markers: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class PhaseBannerContext:
    """Context for the persistent turn/phase line in default interaction messages."""

    state: GameState
    viewer_faction: str | None
    current_faction: str
    current_phase: str
    schedule_index: int
    phase_actions_remaining: int


def default_combat_instruction_for_viewer(
    ctx: CombatInteractionContext,
) -> tuple[str, str]:
    """Engine default `(instruction, message)` for combat banners and combat events.

    `instruction` matches wire expectations: `resolved`, `retreat_required`, `wait`.
    """

    recipient = str(ctx.viewer_faction).strip() if ctx.viewer_faction else ""
    outcome = ctx.outcome
    retreat_owner = ctx.retreat_owner_faction

    match (outcome, retreat_owner, recipient):
        case ("defender_destroyed", _, _):
            return "resolved", "Defender destroyed."
        case ("none", _, _):
            return "resolved", "Combat resolved with no effect."
        case (_, None, _):
            return "resolved", "Combat resolved."
        case (_, ro, rec) if rec == ro:
            return (
                "retreat_required",
                "You must retreat this unit in one move (exact hex distance).",
            )
        case _:
            return "wait", "Waiting for the opponent to complete a mandatory retreat."


def default_advance_gate_banners_for_viewer(
    _ctx: AdvanceGateInteractionContext,
) -> tuple[str, str]:
    """Engine default `(text_for_advancing_faction, text_for_other_factions)`."""

    return (
        "Advance is available (click Advance).",
        "Waiting for the opponent to advance.",
    )


def default_phase_banner_text_for_viewer(ctx: PhaseBannerContext) -> str:
    """Engine default single line for the phase `interaction_messages` entry."""

    return (
        f"{ctx.current_faction}: {ctx.current_phase} "
        f"(actions: {ctx.phase_actions_remaining})"
    )


@dataclass(frozen=True, slots=True)
class UIHooks:
    """
    UI policy surface consulted by the server when building per-recipient `StateUpdate`.

    - Return `ENGINE_DEFAULT` to request engine defaults.
    - Return a list of ``InteractionMessage`` DTOs to fully control transient banners.
      Optional ``html`` renders rich content in the turn banner (client prefers
      ``html`` over ``text`` when both are set).
    """

    interaction_messages: (
        Callable[[GameState, str | None], list[InteractionMessage] | object] | None
    ) = None

    inform_popup: (
        Callable[[InformPopupContext], InformPopup | object] | None
    ) = None

    map_overlays: (
        Callable[[GameState, str | None], list[MapOverlay] | object] | None
    ) = None

    combat_instruction_for_viewer: (
        Callable[[CombatInteractionContext], tuple[str, str] | object] | None
    ) = None

    advance_gate_banners_for_viewer: (
        Callable[[AdvanceGateInteractionContext], tuple[str, str] | object] | None
    ) = None

    phase_banner_text_for_viewer: (
        Callable[[PhaseBannerContext], str | object] | None
    ) = None

    phase_banner_html_for_viewer: (
        Callable[[PhaseBannerContext], str | object] | None
    ) = None

    turn_action_dock_for_viewer: (
        Callable[[TurnActionDockContext], list[TurnDockPanel] | object] | None
    ) = None

    enrich_current_segment: (
        Callable[[SegmentPresentationContext], SegmentPresentationPatch | object] | None
    ) = None

    segment_presentation_registry: Callable[[], object] | None = None

    place_marker_preview: (
        Callable[[PlaceMarkerPreviewContext], MapSelectionPreview | object] | None
    ) = None

    combat_interaction_messages: (
        Callable[[CombatInteractionMessagesContext], list[InteractionMessage] | object]
        | None
    ) = None

    combat_event_summary: (
        Callable[[GameState], CombatEventSummary | None | object] | None
    ) = None

    def messages(
        self, state: GameState, viewer_faction: str | None
    ) -> list[InteractionMessage] | object:
        if self.interaction_messages is None:
            return ENGINE_DEFAULT
        return self.interaction_messages(state, viewer_faction)

    def inform_popup_for(self, ctx: InformPopupContext) -> InformPopup | object:
        if self.inform_popup is None:
            return ENGINE_DEFAULT
        return self.inform_popup(ctx)

    def overlays(
        self, state: GameState, viewer_faction: str | None
    ) -> list[MapOverlay] | object:
        if self.map_overlays is None:
            return ENGINE_DEFAULT
        return self.map_overlays(state, viewer_faction)

    def combat_instruction(
        self, ctx: CombatInteractionContext
    ) -> tuple[str, str] | object:
        if self.combat_instruction_for_viewer is None:
            return ENGINE_DEFAULT
        return self.combat_instruction_for_viewer(ctx)

    def advance_gate_banners(
        self, ctx: AdvanceGateInteractionContext
    ) -> tuple[str, str] | object:
        if self.advance_gate_banners_for_viewer is None:
            return ENGINE_DEFAULT
        return self.advance_gate_banners_for_viewer(ctx)

    def phase_banner_text(self, ctx: PhaseBannerContext) -> str | object:
        if self.phase_banner_text_for_viewer is None:
            return ENGINE_DEFAULT
        return self.phase_banner_text_for_viewer(ctx)

    def phase_banner_html(self, ctx: PhaseBannerContext) -> str | object:
        if self.phase_banner_html_for_viewer is None:
            return ENGINE_DEFAULT
        return self.phase_banner_html_for_viewer(ctx)

    def turn_action_dock(
        self, ctx: TurnActionDockContext
    ) -> list[TurnDockPanel] | object:
        if self.turn_action_dock_for_viewer is None:
            return ENGINE_DEFAULT
        return self.turn_action_dock_for_viewer(ctx)

    def enrich_current_segment_for(
        self, ctx: SegmentPresentationContext
    ) -> SegmentPresentationPatch | object:
        if self.enrich_current_segment is None:
            return ENGINE_DEFAULT
        return self.enrich_current_segment(ctx)

    def segment_presentation_registry_spec(self) -> object:
        if self.segment_presentation_registry is None:
            return ENGINE_DEFAULT
        return self.segment_presentation_registry()

    def place_marker_preview_for(
        self, ctx: PlaceMarkerPreviewContext
    ) -> MapSelectionPreview | object:
        if self.place_marker_preview is None:
            return ENGINE_DEFAULT
        return self.place_marker_preview(ctx)

    def combat_interaction_messages_for(
        self, ctx: CombatInteractionMessagesContext
    ) -> list[InteractionMessage] | object:
        if self.combat_interaction_messages is None:
            return ENGINE_DEFAULT
        return self.combat_interaction_messages(ctx)

    def combat_event_summary_for(
        self, state: GameState
    ) -> CombatEventSummary | None | object:
        if self.combat_event_summary is None:
            return ENGINE_DEFAULT
        return self.combat_event_summary(state)


class UIHook(StrEnum):
    """Stable slot ids for `bind_title_hook` (values match `UIHooks` field names)."""

    INTERACTION_MESSAGES = "interaction_messages"
    INFORM_POPUP = "inform_popup"
    MAP_OVERLAYS = "map_overlays"
    COMBAT_INSTRUCTION_FOR_VIEWER = "combat_instruction_for_viewer"
    ADVANCE_GATE_BANNERS_FOR_VIEWER = "advance_gate_banners_for_viewer"
    PHASE_BANNER_TEXT_FOR_VIEWER = "phase_banner_text_for_viewer"
    PHASE_BANNER_HTML_FOR_VIEWER = "phase_banner_html_for_viewer"
    TURN_ACTION_DOCK_FOR_VIEWER = "turn_action_dock_for_viewer"
    ENRICH_CURRENT_SEGMENT = "enrich_current_segment"
    SEGMENT_PRESENTATION_REGISTRY = "segment_presentation_registry"
    PLACE_MARKER_PREVIEW = "place_marker_preview"
    COMBAT_INTERACTION_MESSAGES = "combat_interaction_messages"
    COMBAT_EVENT_SUMMARY = "combat_event_summary"


UIHook._hexengine_hook_bundle = "ui"


__all__ = [
    "AdvanceGateInteractionContext",
    "CombatEventSummary",
    "CombatInteractionContext",
    "CombatInteractionMessagesContext",
    "ENGINE_DEFAULT",
    "PhaseBannerContext",
    "RuleViolation",
    "SegmentPresentationContext",
    "UIHook",
    "UIHooks",
    "default_advance_gate_banners_for_viewer",
    "default_combat_instruction_for_viewer",
    "default_phase_banner_text_for_viewer",
]
