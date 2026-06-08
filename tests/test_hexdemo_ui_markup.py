"""Tests for hexdemo HTML templates and ui_markup helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_games_on_path() -> None:
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)


def test_hexdemo_html_templates_exist() -> None:
    root = REPO_ROOT / "games" / "hexdemo" / "resources" / "templates"
    assert (root / "phase_banner.html").is_file()
    assert (root / "unit_inspect.html").is_file()


def test_hexdemo_flag_assets_exist() -> None:
    flags = REPO_ROOT / "games" / "hexdemo" / "resources" / "flags"
    assert (flags / "union_34star.svg").is_file()
    assert (flags / "confederate_battle.svg").is_file()
    css = (REPO_ROOT / "games" / "hexdemo" / "resources" / "ui.css").read_text(
        encoding="utf-8"
    )
    assert "--hexdemo-turn-banner-flag-w" in css
    assert "hexdemo-turn-banner__flag-img" in css


def test_render_phase_banner_html_escapes_label() -> None:
    _ensure_games_on_path()
    from hexdemo.ui.markup import PACK_ROOT
    from hexengine.ui.display import (
        clear_template_cache,
        load_html_template,
    )

    clear_template_cache()
    assert "hexdemo-turn-banner" in load_html_template(
        PACK_ROOT, "templates/phase_banner.html"
    )
    from hexdemo.ui.markup import render_phase_banner_html
    from hexengine.hooks.ui import PhaseBannerContext
    from hexengine.state import GameState

    st = GameState.create_empty(initial_faction="union", initial_phase="Move")
    html = render_phase_banner_html(
        PhaseBannerContext(
            state=st,
            viewer_faction="union",
            current_faction="union",
            current_phase="Move<script>",
            schedule_index=0,
            phase_actions_remaining=2,
        )
    )
    assert "<script>" not in html
    assert "Union: Move" in html
    assert "hexdemo-turn-banner__flag--union" in html
    assert "hexdemo-turn-banner__flag-img" in html
    assert "/pack/hexdemo/flags/union_34star.svg" in html
    assert 'width="44"' in html
    assert 'height="28"' in html


def test_render_unit_inspect_html() -> None:
    _ensure_games_on_path()
    from hexdemo.ui.markup import render_unit_inspect_html
    from hexengine.hexes.types import Hex
    from hexengine.state.game_state import UnitState

    u = UnitState(
        unit_id="u1",
        unit_type="inf",
        faction="union",
        position=Hex(0, 0, 0),
        health=100,
        active=True,
    )
    html = render_unit_inspect_html(u, position="[1, 2]", hp_display="100")
    assert "hexdemo-inspect" in html
    assert "u1" in html
    assert "Union" in html


def test_render_html_template_missing_raises() -> None:
    _ensure_games_on_path()
    from hexdemo.ui.markup import PACK_ROOT
    from hexengine.ui.display import clear_template_cache, render_html_template

    clear_template_cache()
    with pytest.raises(FileNotFoundError):
        render_html_template(PACK_ROOT, "templates/no_such.html", x="y")
