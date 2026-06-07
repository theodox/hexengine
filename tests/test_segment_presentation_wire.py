"""current_segment presentation enrichment (P3)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
SRC = str(REPO_ROOT / "src")
for p in (GAMES, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from hexengine.game.arcs.client_interaction_panels import (
    effective_turn_dock_presentation_id,
)


def test_client_effective_presentation_id_uses_interaction_mode() -> None:
    assert (
        effective_turn_dock_presentation_id(
            "attack_ready",
            "attack_plan",
            interaction_draft_active=True,
        )
        == "attack_draft"
    )
    assert (
        effective_turn_dock_presentation_id(
            "retreat_gate",
            "retreat_path",
            interaction_draft_active=False,
        )
        == "retreat_gate"
    )


def test_hexdemo_enrich_hook_wired() -> None:
    from games.hexdemo.hooks import build_hooks

    assert build_hooks().ui.enrich_current_segment is not None


def test_hexdemo_enrich_projects_attack_plan_from_registry() -> None:
    from games.hexdemo.hooks import build_hooks
    from games.hexdemo.hooks.segment_presentation import enrich_current_segment

    from hexengine.arcs.segment_wire import enrich_current_segment_wire
    from hexengine.state import GameState
    from types import SimpleNamespace

    st = GameState.create_empty()
    segment = {
        "schema": 1,
        "kind": "combat",
        "allowed_actions": ["Attack", "NextPhase"],
        "action_locus": {"Attack": "client_draft", "NextPhase": "server"},
    }
    host = SimpleNamespace(hooks=build_hooks())
    wire = enrich_current_segment_wire(
        host,
        segment,
        st,
        viewer_faction="union",
        viewer_may_act=True,
    )
    assert wire["presentation_id"] == "attack_ready"
    assert wire["interaction_mode"] == "attack_plan"
    assert enrich_current_segment is not None
