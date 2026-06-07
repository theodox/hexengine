"""Tests for hexengine.ui.display (Track A5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hexengine.ui.display import (
    InteractionMessage,
    clear_template_cache,
    interaction_message,
    load_html_template,
    pack_asset_href,
    render_html_template,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
HEXDEMO_ROOT = REPO_ROOT / "games" / "hexdemo"


def test_interaction_message_to_wire_dict_minimal() -> None:
    row = interaction_message(kind="phase", text="Union: move (actions: 1)")
    assert row == {"schema": 1, "kind": "phase", "text": "Union: move (actions: 1)"}


def test_interaction_message_to_wire_dict_with_html() -> None:
    msg = InteractionMessage(
        kind="phase",
        text="fallback",
        html="<span>rich</span>",
        dedupe_key="phase:0",
        ttl_ms=4000,
        css_class="interaction-msg--phase",
    )
    row = msg.to_wire_dict()
    assert row["html"] == "<span>rich</span>"
    assert row["dedupe_key"] == "phase:0"
    assert row["ttl_ms"] == 4000
    assert row["css_class"] == "interaction-msg--phase"


def test_render_html_template_escapes_placeholders() -> None:
    clear_template_cache()
    html = render_html_template(
        HEXDEMO_ROOT,
        "templates/phase_banner.html",
        flag_class="hexdemo-turn-banner__flag",
        flag_mod="",
        flag_img="",
        label="Union<script>alert(1)</script>",
    )
    assert "<script>" not in html
    assert "Union" in html
    assert "hexdemo-turn-banner" in html


def test_load_html_template_missing_raises() -> None:
    clear_template_cache()
    with pytest.raises(FileNotFoundError, match="no_such"):
        load_html_template(HEXDEMO_ROOT, "templates/no_such.html")


def test_pack_asset_href_pack_route() -> None:
    href = pack_asset_href(
        HEXDEMO_ROOT,
        "flags/union_34star.svg",
        asset_base_url="/pack/hexdemo/",
    )
    assert href == "/pack/hexdemo/flags/union_34star.svg"


def test_pack_asset_href_without_asset_base_url_returns_none() -> None:
    assert pack_asset_href(HEXDEMO_ROOT, "ui.css") is None


def test_pack_resource_site_href_rejects_traversal() -> None:
    from hexengine.game_packs.resources import pack_resource_site_href

    assert (
        pack_resource_site_href(
            HEXDEMO_ROOT,
            "../secrets.txt",
            static_root=REPO_ROOT,
        )
        is None
    )
