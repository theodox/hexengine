"""Map selection client handler registry."""

from __future__ import annotations

from hexengine.game.arcs.client_map_selection_registry import (
    map_selection_preview_handlers,
)


class _AttackOnly:
    def _apply_attack_plan_preview(self, payload: dict) -> None:
        pass


class _AttackAndRetreat(_AttackOnly):
    def _apply_retreat_path_preview(self, payload: dict) -> None:
        pass


class _AllKinds(_AttackAndRetreat):
    def _apply_place_marker_preview(self, payload: dict) -> None:
        pass


def test_registry_includes_attack_when_mixin_present() -> None:
    from hexengine.gamedef.interactions import InteractionKind

    handlers = map_selection_preview_handlers(_AttackOnly())
    assert InteractionKind.ATTACK_PLAN in handlers
    assert InteractionKind.RETREAT_PATH not in handlers


def test_registry_includes_retreat_when_mixin_present() -> None:
    from hexengine.gamedef.interactions import InteractionKind

    handlers = map_selection_preview_handlers(_AttackAndRetreat())
    assert InteractionKind.RETREAT_PATH in handlers


def test_registry_includes_place_marker_when_mixin_present() -> None:
    from hexengine.gamedef.interactions import InteractionKind

    handlers = map_selection_preview_handlers(_AllKinds())
    assert InteractionKind.PLACE_MARKER in handlers
