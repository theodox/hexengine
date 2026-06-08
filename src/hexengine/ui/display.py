"""
Title UI markup helpers (Track A5 — tier 4 skinning API).

Build wire-shaped dicts and HTML from pack ``resources/`` templates with escaped
placeholders. HTML is trusted title content; always escape dynamic values.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from html import escape as escape_html
from pathlib import Path
from typing import Any

from ..game_packs.resources import pack_asset_url, read_pack_resource_text

# Re-export for titles that ``from hexengine.ui.display import escape``.
escape = escape_html


@dataclass(frozen=True, slots=True)
class InteractionMessage:
    """One ``StateUpdate.interaction_messages`` row (schema 1)."""

    kind: str
    text: str
    html: str | None = None
    schema: int = 1
    dedupe_key: str | None = None
    ttl_ms: int | None = None
    css_class: str | None = None

    def to_wire_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": int(self.schema),
            "kind": str(self.kind).strip(),
            "text": str(self.text),
        }
        if self.html is not None and str(self.html).strip():
            out["html"] = str(self.html)
        if self.dedupe_key is not None and str(self.dedupe_key).strip():
            out["dedupe_key"] = str(self.dedupe_key).strip()
        if self.ttl_ms is not None:
            out["ttl_ms"] = int(self.ttl_ms)
        if self.css_class is not None and str(self.css_class).strip():
            out["css_class"] = str(self.css_class).strip()
        return out


@dataclass(frozen=True, slots=True)
class PanelAction:
    """One turn action dock ``actions[]`` row (schema 1)."""

    id: str
    action_type: str
    label: str
    enabled: bool
    schema: int = 1
    title: str | None = None
    payload: dict[str, Any] | None = None
    css_class: str | None = None
    group: str | None = None
    order: int | None = None

    def to_wire_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": int(self.schema),
            "id": str(self.id).strip(),
            "action_type": str(self.action_type).strip(),
            "label": str(self.label),
            "enabled": bool(self.enabled),
            "payload": dict(self.payload) if isinstance(self.payload, dict) else {},
        }
        if self.title is not None and str(self.title).strip():
            out["title"] = str(self.title).strip()
        if self.css_class is not None and str(self.css_class).strip():
            out["css_class"] = str(self.css_class).strip()
        if self.group is not None and str(self.group).strip():
            out["group"] = str(self.group).strip()
        if self.order is not None:
            out["order"] = int(self.order)
        return out


@dataclass(frozen=True, slots=True)
class TurnDockPanel:
    """Turn action dock panel (``StateUpdate.interaction_panels`` row, schema 1)."""

    presentation_id: str
    actions: tuple[PanelAction, ...]
    id: str = "turn_actions"
    host: str = "user-controls"
    headline: str = ""
    html: str | None = None
    css_class: str | None = None
    inputs: tuple[dict[str, Any], ...] = ()
    schema: int = 1

    def to_wire_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": int(self.schema),
            "id": str(self.id).strip(),
            "host": str(self.host).strip() or "user-controls",
            "presentation_id": str(self.presentation_id).strip(),
            "headline": str(self.headline),
            "actions": [a.to_wire_dict() for a in self.actions],
            "inputs": [dict(i) for i in self.inputs if isinstance(i, dict)],
        }
        if self.html is not None and str(self.html).strip():
            out["html"] = str(self.html)
        if self.css_class is not None and str(self.css_class).strip():
            out["css_class"] = str(self.css_class).strip()
        return out


@dataclass(frozen=True, slots=True)
class InformPopup:
    """Map callout popup (``ui_popup`` wire); server sets anchor ``hex``."""

    text: str
    kind: str = "info"
    html: str | None = None
    ttl_ms: int | None = 800
    css_class: str | None = None

    def to_wire_dict(self) -> dict[str, Any]:
        txt = str(self.text).strip()
        html = None if self.html is None else str(self.html).strip()
        if not txt and not html:
            raise ValueError("InformPopup requires non-empty text or html")
        out: dict[str, Any] = {"kind": str(self.kind).strip() or "info", "text": txt}
        if html:
            out["html"] = html
        if self.ttl_ms is not None:
            out["ttl_ms"] = max(0, int(self.ttl_ms))
        if self.css_class is not None and str(self.css_class).strip():
            out["css_class"] = str(self.css_class).strip()
        return out


@dataclass(frozen=True, slots=True)
class MapSelectionPreview:
    """Map-selection preview (``map_selection_preview`` wire); server sets ``request_id``."""

    kind: str
    status_text: str
    confirm_enabled: bool
    panel_actions: tuple[PanelAction, ...] = ()
    valid_target_hexes: tuple[dict[str, int], ...] | None = None
    eligible_attacker_ids: tuple[str, ...] | None = None
    commit_payload: dict[str, Any] | None = None
    legal_next_hexes: tuple[dict[str, int], ...] | None = None
    preview_path_hexes: tuple[dict[str, int], ...] | None = None
    through_hexes: tuple[dict[str, int], ...] | None = None
    disable_end_phase: bool | None = None
    draft_presentation_id: str | None = None

    def to_wire_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": str(self.kind).strip(),
            "status_text": str(self.status_text),
            "confirm_enabled": bool(self.confirm_enabled),
            "panel_actions": [a.to_wire_dict() for a in self.panel_actions],
        }
        if self.valid_target_hexes is not None:
            out["valid_target_hexes"] = [
                dict(h) for h in self.valid_target_hexes if isinstance(h, dict)
            ]
        if self.eligible_attacker_ids is not None:
            out["eligible_attacker_ids"] = [
                str(uid).strip()
                for uid in self.eligible_attacker_ids
                if str(uid).strip()
            ]
        if self.commit_payload is not None:
            out["commit_payload"] = dict(self.commit_payload)
        if self.legal_next_hexes is not None:
            out["legal_next_hexes"] = [
                dict(h) for h in self.legal_next_hexes if isinstance(h, dict)
            ]
        if self.preview_path_hexes is not None:
            out["preview_path_hexes"] = [
                dict(h) for h in self.preview_path_hexes if isinstance(h, dict)
            ]
        if self.through_hexes is not None:
            out["through_hexes"] = [
                dict(h) for h in self.through_hexes if isinstance(h, dict)
            ]
        if isinstance(self.disable_end_phase, bool):
            out["disable_end_phase"] = bool(self.disable_end_phase)
        if self.draft_presentation_id is not None and str(
            self.draft_presentation_id
        ).strip():
            out["draft_presentation_id"] = str(self.draft_presentation_id).strip()
        return out


@dataclass(frozen=True, slots=True)
class InteractionPanel:
    """Generic ``interaction_panels`` row without turn-dock fields (schema 1)."""

    id: str
    host: str = "user-controls"
    html: str | None = None
    css_class: str | None = None
    actions: tuple[dict[str, Any], ...] = ()
    inputs: tuple[dict[str, Any], ...] = ()
    schema: int = 1

    def to_wire_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": int(self.schema),
            "id": str(self.id).strip(),
            "host": str(self.host).strip() or "user-controls",
            "actions": [dict(a) for a in self.actions if isinstance(a, dict)],
            "inputs": [dict(i) for i in self.inputs if isinstance(i, dict)],
        }
        if self.html is not None and str(self.html).strip():
            out["html"] = str(self.html)
        if self.css_class is not None and str(self.css_class).strip():
            out["css_class"] = str(self.css_class).strip()
        return out


def panel_input(
    *,
    id: str,
    kind: str,
    label: str,
    name: str | None = None,
    default: Any = None,
    options: tuple[dict[str, str], ...] = (),
) -> dict[str, Any]:
    """Build one panel ``inputs[]`` wire dict."""
    row: dict[str, Any] = {
        "id": str(id).strip(),
        "kind": str(kind).strip().lower(),
        "label": str(label),
        "name": str(name).strip() if name else str(id).strip(),
    }
    if default is not None:
        row["default"] = default
    if options:
        row["options"] = [{"value": o["value"], "label": o["label"]} for o in options]
    return row


def panel_action(
    *,
    id: str,
    action_type: str,
    label: str,
    enabled: bool = True,
    title: str | None = None,
    payload: dict[str, Any] | None = None,
    css_class: str | None = None,
    group: str | None = None,
    order: int | None = None,
    schema: int = 1,
) -> PanelAction:
    """Build one dock action row (author-facing; converted to wire by the engine)."""
    return PanelAction(
        id=id,
        action_type=action_type,
        label=label,
        enabled=enabled,
        title=title,
        payload=payload,
        css_class=css_class,
        group=group,
        order=order,
        schema=schema,
    )


def panel_actions_from_dicts(rows: list[dict[str, Any]]) -> tuple[PanelAction, ...]:
    """Wrap engine-built action dicts (e.g. segment gate rows) as ``PanelAction``."""
    out: list[PanelAction] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        out.append(
            PanelAction(
                id=str(raw.get("id", "")).strip(),
                action_type=str(raw.get("action_type", "")).strip(),
                label=str(raw.get("label", "")),
                enabled=bool(raw.get("enabled", True)),
                title=(
                    str(raw["title"]).strip() if raw.get("title") is not None else None
                ),
                payload=(
                    dict(raw["payload"]) if isinstance(raw.get("payload"), dict) else {}
                ),
                css_class=(
                    str(raw["css_class"]).strip()
                    if raw.get("css_class") is not None
                    else None
                ),
                group=(
                    str(raw["group"]).strip() if raw.get("group") is not None else None
                ),
                order=(int(raw["order"]) if raw.get("order") is not None else None),
                schema=int(raw.get("schema", 1)),
            )
        )
    return tuple(out)


def turn_dock_panel(
    *,
    presentation_id: str,
    actions: tuple[PanelAction, ...] | list[PanelAction],
    id: str = "turn_actions",
    host: str = "user-controls",
    headline: str = "",
    html: str | None = None,
    css_class: str | None = None,
    inputs: list[dict[str, Any]] | None = None,
    schema: int = 1,
) -> TurnDockPanel:
    """Build one turn action dock panel (author-facing)."""
    act = tuple(actions) if isinstance(actions, tuple) else tuple(actions)
    return TurnDockPanel(
        presentation_id=presentation_id,
        actions=act,
        id=id,
        host=host,
        headline=headline,
        html=html,
        css_class=css_class,
        inputs=tuple(inputs or ()),
        schema=schema,
    )


def inform_popup(
    *,
    text: str,
    kind: str = "info",
    html: str | None = None,
    ttl_ms: int | None = 800,
    css_class: str | None = None,
) -> InformPopup:
    """Build one map callout popup (author-facing)."""
    return InformPopup(
        text=text,
        kind=kind,
        html=html,
        ttl_ms=ttl_ms,
        css_class=css_class,
    )


def map_selection_preview(
    *,
    kind: str,
    status_text: str,
    confirm_enabled: bool,
    panel_actions: tuple[PanelAction, ...] | list[PanelAction] = (),
    valid_target_hexes: list[dict[str, int]] | None = None,
    eligible_attacker_ids: list[str] | None = None,
    commit_payload: dict[str, Any] | None = None,
    legal_next_hexes: list[dict[str, int]] | None = None,
    preview_path_hexes: list[dict[str, int]] | None = None,
    through_hexes: list[dict[str, int]] | None = None,
    disable_end_phase: bool | None = None,
    draft_presentation_id: str | None = None,
) -> MapSelectionPreview:
    """Build one map-selection preview (author-facing)."""
    actions = (
        tuple(panel_actions)
        if isinstance(panel_actions, tuple)
        else tuple(panel_actions)
    )

    def _hex_tuple(rows: list[dict[str, int]] | None) -> tuple[dict[str, int], ...] | None:
        if rows is None:
            return None
        return tuple(dict(h) for h in rows if isinstance(h, dict))

    return MapSelectionPreview(
        kind=kind,
        status_text=status_text,
        confirm_enabled=confirm_enabled,
        panel_actions=actions,
        valid_target_hexes=_hex_tuple(valid_target_hexes),
        eligible_attacker_ids=(
            tuple(str(uid).strip() for uid in eligible_attacker_ids)
            if eligible_attacker_ids is not None
            else None
        ),
        commit_payload=(
            dict(commit_payload) if isinstance(commit_payload, dict) else None
        ),
        legal_next_hexes=_hex_tuple(legal_next_hexes),
        preview_path_hexes=_hex_tuple(preview_path_hexes),
        through_hexes=_hex_tuple(through_hexes),
        disable_end_phase=disable_end_phase,
        draft_presentation_id=draft_presentation_id,
    )


def empty_map_selection_preview(kind: str) -> MapSelectionPreview:
    """Unsupported kind or unbound hook — confirm disabled, no highlights."""
    k = str(kind or "").strip() or "unknown"
    return MapSelectionPreview(
        kind=k,
        status_text="",
        confirm_enabled=False,
        valid_target_hexes=(),
        eligible_attacker_ids=(),
        commit_payload=None,
        panel_actions=(),
    )


def interaction_panel(
    *,
    id: str,
    host: str = "user-controls",
    html: str | None = None,
    css_class: str | None = None,
    actions: list[dict[str, Any]] | None = None,
    inputs: list[dict[str, Any]] | None = None,
    schema: int = 1,
) -> dict[str, Any]:
    """Build one ``interaction_panels`` wire dict."""
    return InteractionPanel(
        id=id,
        host=host,
        html=html,
        css_class=css_class,
        actions=tuple(actions or ()),
        inputs=tuple(inputs or ()),
        schema=schema,
    ).to_wire_dict()


def interaction_message(
    *,
    kind: str,
    text: str,
    html: str | None = None,
    schema: int = 1,
    dedupe_key: str | None = None,
    ttl_ms: int | None = None,
    css_class: str | None = None,
) -> dict[str, Any]:
    """Build one ``interaction_messages`` wire dict (dual-field rule: ``text`` + optional ``html``)."""
    return InteractionMessage(
        kind=kind,
        text=text,
        html=html,
        schema=schema,
        dedupe_key=dedupe_key,
        ttl_ms=ttl_ms,
        css_class=css_class,
    ).to_wire_dict()


@lru_cache(maxsize=32)
def load_html_template(pack_root: Path, rel: str) -> str:
    """Load UTF-8 HTML/text from ``<pack_root>/resources/<rel>``."""
    root = pack_root.resolve()
    text = read_pack_resource_text(root, rel)
    if text is None:
        msg = f"pack template missing: resources/{rel} under {root}"
        raise FileNotFoundError(msg)
    return text


def clear_template_cache() -> None:
    """Clear the ``load_html_template`` LRU cache (for tests)."""
    load_html_template.cache_clear()


def render_html_template(pack_root: Path, rel: str, /, **values: Any) -> str:
    """Format a pack template; all placeholder values are HTML-escaped."""
    tpl = load_html_template(pack_root, rel)
    safe = {k: escape(str(v)) for k, v in values.items()}
    return tpl.format(**safe)


def pack_asset_href(
    pack_root: Path,
    rel: str,
    *,
    asset_base_url: str | None = None,
) -> str | None:
    """
    URL for a file under ``<pack_root>/resources/<rel>``.

    Requires ``asset_base_url`` from ``turn_rules`` (``/pack/<pack_id>/``).
    """
    return pack_asset_url(
        pack_root.resolve(),
        rel,
        asset_base_url=asset_base_url,
    )


__all__ = [
    "InformPopup",
    "InteractionMessage",
    "InteractionPanel",
    "MapSelectionPreview",
    "PanelAction",
    "TurnDockPanel",
    "clear_template_cache",
    "empty_map_selection_preview",
    "escape",
    "inform_popup",
    "interaction_message",
    "interaction_panel",
    "load_html_template",
    "map_selection_preview",
    "pack_asset_href",
    "panel_action",
    "panel_actions_from_dicts",
    "panel_input",
    "render_html_template",
    "turn_dock_panel",
]
