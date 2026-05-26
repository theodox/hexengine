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
class InteractionPanel:
    """One ``StateUpdate.interaction_panels`` row (schema 1)."""

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
    site_static_root: Path | None = None,
) -> str | None:
    """
    URL for a file under ``<pack_root>/resources/<rel>``.

    Prefer ``asset_base_url`` from ``turn_rules`` (``/pack/<pack_id>/``). When
    omitted, pass ``site_static_root`` for legacy repo-root paths such as
    ``/games/mytitle/resources/...``.
    """
    return pack_asset_url(
        pack_root.resolve(),
        rel,
        asset_base_url=asset_base_url,
        static_root=site_static_root.resolve() if site_static_root is not None else None,
    )


__all__ = [
    "InteractionMessage",
    "InteractionPanel",
    "clear_template_cache",
    "escape",
    "interaction_message",
    "interaction_panel",
    "load_html_template",
    "pack_asset_href",
    "panel_input",
    "render_html_template",
]
