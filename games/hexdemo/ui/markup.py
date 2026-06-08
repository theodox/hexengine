"""
Hexdemo HTML templates and small markup helpers (tier 2–3 skinning reference).

Templates live under ``resources/templates/``. Uses :mod:`hexengine.ui.display` for
template load/render; game-specific copy stays here.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from hexengine.game_packs.resources import pack_asset_base_url
from hexengine.hexes.types import HexColRow
from hexengine.hooks.ui import PhaseBannerContext
from hexengine.state import GameState
from hexengine.state.game_state import UnitState
from hexengine.authoring.present import InformPopup, inform_popup
from hexengine.ui.display import (
    load_html_template,
    pack_asset_href,
    render_html_template,
)

PACK_ROOT = Path(__file__).resolve().parent.parent
PACK_ID = "hexdemo"
_ASSET_BASE_URL = pack_asset_base_url(PACK_ID)

# Mirror [faction_display_names] in resources/game_data.toml.
FACTION_LABEL: dict[str, str] = {
    "union": "Union",
    "confederate": "Confederate",
}

# CSS modifiers on the flag slot (image src is resolved separately).
FACTION_FLAG_CLASS: dict[str, str] = {
    "union": "hexdemo-turn-banner__flag--union",
    "confederate": "hexdemo-turn-banner__flag--confederate",
}

FACTION_FLAG_REL: dict[str, str] = {
    "union": "flags/union_34star.svg",
    "confederate": "flags/confederate_battle.svg",
}

# Keep in sync with --hexdemo-turn-banner-flag-* in resources/ui.css.
TURN_BANNER_FLAG_WIDTH_PX = 44
TURN_BANNER_FLAG_HEIGHT_PX = 28

_TEMPLATE_PHASE_BANNER = "templates/phase_banner.html"
_TEMPLATE_UNIT_INSPECT = "templates/unit_inspect.html"
_TEMPLATE_DOCK_GATE = "templates/dock_gate.html"


def faction_label(faction_id: str) -> str:
    key = str(faction_id).strip().lower()
    return FACTION_LABEL.get(key, str(faction_id).strip())


def phase_banner_label(ctx: PhaseBannerContext) -> str:
    fac = faction_label(ctx.current_faction)
    phase = str(ctx.current_phase).strip()
    actions = int(ctx.phase_actions_remaining)
    return f"{fac}: {phase} (actions: {actions})"


def faction_flag_href(faction_id: str) -> str:
    """Root-absolute URL for a faction flag SVG (``/pack/hexdemo/flags/...``)."""
    key = str(faction_id).strip().lower()
    rel = FACTION_FLAG_REL.get(key)
    if not rel:
        return ""
    href = pack_asset_href(PACK_ROOT, rel, asset_base_url=_ASSET_BASE_URL)
    if not href:
        return ""
    if not href.startswith(("/", "http://", "https://")):
        return f"/{href}"
    return href


def render_phase_banner_html(ctx: PhaseBannerContext) -> str:
    fac_key = str(ctx.current_faction).strip().lower()
    flag_mod = FACTION_FLAG_CLASS.get(fac_key, "hexdemo-turn-banner__flag--neutral")
    src = faction_flag_href(fac_key)
    # {flag_img} is inserted unescaped; only src/attributes are escaped here.
    w, h = TURN_BANNER_FLAG_WIDTH_PX, TURN_BANNER_FLAG_HEIGHT_PX
    flag_img = (
        f'<img class="hexdemo-turn-banner__flag-img" src="{escape(src)}" alt="" '
        f'width="{w}" height="{h}" />'
        if src
        else ""
    )
    tpl = load_html_template(PACK_ROOT, _TEMPLATE_PHASE_BANNER)
    return (
        tpl.replace("{flag_mod}", escape(flag_mod))
        .replace("{label}", escape(phase_banner_label(ctx)))
        .replace("{flag_img}", flag_img)
    )


def render_dock_gate_panel_html(hint: str) -> str:
    """Decorative hint HTML for retreat/advance gate dock arcs."""
    return render_html_template(PACK_ROOT, _TEMPLATE_DOCK_GATE, hint=hint)


def unit_inspect_plain_text(u: UnitState, position: str) -> str:
    return " | ".join([u.unit_id, u.unit_type, u.faction, position])


def render_unit_inspect_html(
    u: UnitState,
    *,
    position: str,
    hp_display: str,
) -> str:
    return render_html_template(
        PACK_ROOT,
        _TEMPLATE_UNIT_INSPECT,
        unit_id=u.unit_id,
        unit_type=u.unit_type,
        faction_label=faction_label(u.faction),
        position=position,
        hp=hp_display,
    )


def unit_inspect_popup(
    state: GameState,
    viewer_faction: str | None,
    unit_id: str,
) -> InformPopup:
    """Build one unit inspect callout for ``INFORM_POPUP``."""
    u = state.board.units.get(unit_id)
    if u is None:
        return inform_popup(text=f"{unit_id} (missing)", kind="error", ttl_ms=1200)

    cr = HexColRow.from_hex(u.position)
    pos_s = f"[{cr.col}, {cr.row}]"
    own = viewer_faction is not None and viewer_faction == u.faction
    hp_s = str(int(u.health)) if own else "?"
    text = unit_inspect_plain_text(u, pos_s)
    html = render_unit_inspect_html(u, position=pos_s, hp_display=hp_s)
    return inform_popup(text=text, html=html, kind="info", ttl_ms=1500)


__all__ = [
    "FACTION_FLAG_CLASS",
    "FACTION_FLAG_REL",
    "FACTION_LABEL",
    "PACK_ROOT",
    "TURN_BANNER_FLAG_HEIGHT_PX",
    "TURN_BANNER_FLAG_WIDTH_PX",
    "faction_flag_href",
    "faction_label",
    "phase_banner_label",
    "render_phase_banner_html",
    "render_dock_gate_panel_html",
    "render_unit_inspect_html",
    "unit_inspect_plain_text",
    "unit_inspect_popup",
]
