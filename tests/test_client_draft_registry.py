"""Client-local SELECT draft registry."""

from __future__ import annotations

from hexengine.game.arcs.client_draft_registry import (
    default_draft_presentation_id,
    is_draft_active_for_mode,
    resolve_draft_presentation_id,
)
from hexengine.gamedef.interactions import InteractionKind


class _StubGame:
    def __init__(self) -> None:
        self._preview_pid: str | None = None
        self._segment_pid: str | None = None
        self._active = False

    def _attack_plan_draft_active(self) -> bool:
        return self._active

    def _preview_draft_presentation_id(self) -> str | None:
        return self._preview_pid

    def _segment_draft_presentation_id(self) -> str | None:
        return self._segment_pid


def test_is_draft_active_for_mode_uses_registry() -> None:
    g = _StubGame()
    g._active = True
    assert is_draft_active_for_mode(g, InteractionKind.ATTACK_PLAN) is True
    g._active = False
    assert is_draft_active_for_mode(g, InteractionKind.ATTACK_PLAN) is False


def test_default_draft_presentation_id_per_kind() -> None:
    assert default_draft_presentation_id(InteractionKind.PLACE_MARKER) == (
        "place_marker_draft"
    )


def test_resolve_draft_presentation_id_priority() -> None:
    g = _StubGame()
    g._active = True
    g._segment_pid = "attack_draft"
    assert (
        resolve_draft_presentation_id(
            g, mode=InteractionKind.ATTACK_PLAN, draft_active=True
        )
        == "attack_draft"
    )
    g._preview_pid = "preview_override"
    assert (
        resolve_draft_presentation_id(
            g, mode=InteractionKind.ATTACK_PLAN, draft_active=True
        )
        == "preview_override"
    )
    g._preview_pid = None
    g._segment_pid = None
    assert (
        resolve_draft_presentation_id(
            g, mode=InteractionKind.PLACE_MARKER, draft_active=True
        )
        == "place_marker_draft"
    )
