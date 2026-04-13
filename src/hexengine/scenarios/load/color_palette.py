"""
Scenario `[[colors]]`: named CSS colors, referenced elsewhere as `@name`.
"""

from __future__ import annotations

import re
from typing import Any

from .rows import ensure_dict_table

# `@foo` / `@foo_bar`; not `x@y` (word char before `@`).
_COLOR_REF_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z_][A-Za-z0-9_]*)\b")


def expand_color_tokens(s: str, palette: dict[str, str], *, where: str = "?") -> str:
    """
    Replace every `@identifier` in `s` with `palette[identifier]`.

    Chained references (`@a` expands to text still containing `@b`) are resolved
    iteratively. Raises `ValueError` if a token is missing or references never settle.
    """
    if "@" not in s:
        return s
    out = s
    for _ in range(32):
        if "@" not in out:
            break

        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            if key not in palette:
                raise ValueError(f"{where}: unknown color @{key}")
            return palette[key]

        nxt = _COLOR_REF_RE.sub(repl, out)
        if nxt == out:
            if _COLOR_REF_RE.search(out):
                raise ValueError(f"{where}: unresolved color token in {out!r}")
            break
        out = nxt
    else:
        raise ValueError(f"{where}: color references did not resolve: {out!r}")
    return out


def _optional_nonempty_str(raw: dict[str, Any], key: str) -> str | None:
    if key not in raw:
        return None
    v = raw[key]
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def build_color_palette(rows: list[Any]) -> dict[str, str]:
    """
    Parse `[[colors]]` rows in order.

    Each `value` may use `@name` only for names defined on **earlier** rows
    (no forward references within the color table).
    """
    if not rows:
        return {}
    parsed: list[tuple[str, str]] = []
    for i, item in enumerate(rows):
        d = ensure_dict_table(item, f"colors[{i}]")
        n = _optional_nonempty_str(d, "name")
        if not n:
            raise ValueError(f"colors[{i}] requires non-empty name")
        v_raw = d.get("value")
        if v_raw is None:
            raise ValueError(f"colors[{i}] requires value")
        v = str(v_raw).strip()
        if not v:
            raise ValueError(f"colors[{i}] value cannot be blank")
        if n in {x[0] for x in parsed}:
            raise ValueError(f"colors[{i}] duplicate color name {n!r}")
        parsed.append((n, v))

    out: dict[str, str] = {}
    for n, v in parsed:
        out[n] = expand_color_tokens(v, out, where=f"colors[{n!r}].value")
    return out


def _deep_apply_palette(obj: Any, palette: dict[str, str]) -> None:
    """Replace `@refs` in all strings under `obj` except the `colors` table."""
    if not palette:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "colors":
                continue
            if isinstance(v, str) and "@" in v:
                obj[k] = expand_color_tokens(v, palette, where=f"field {k!r}")
            else:
                _deep_apply_palette(v, palette)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and "@" in item:
                obj[i] = expand_color_tokens(item, palette, where=f"index [{i}]")
            else:
                _deep_apply_palette(item, palette)


def materialize_color_table_values(rows: list[Any], palette: dict[str, str]) -> None:
    """Write fully expanded `value` strings back onto each color row dict."""
    for item in rows:
        if not isinstance(item, dict):
            continue
        n = _optional_nonempty_str(item, "name")
        if n and n in palette:
            item["value"] = palette[n]


def _colors_flat_table_to_rows(raw: dict[str, Any]) -> list[dict[str, str]]:
    """
    Convert a TOML `[colors]` table (name → CSS string) into `[[colors]]`-shaped
    rows, preserving key order for `@` forward-reference rules.
    """
    rows: list[dict[str, str]] = []
    for name, v in raw.items():
        if isinstance(v, dict):
            raise TypeError(
                f"colors.{name}: nested table is not allowed under [colors]; "
                'use a flat map (name = "css") or [[colors]] rows.'
            )
        if v is None:
            raise ValueError(f"colors.{name!r}: value required")
        s = str(v).strip()
        if not s:
            raise ValueError(f"colors.{name!r}: value cannot be blank")
        n = str(name).strip()
        if not n:
            raise ValueError("colors: empty key")
        rows.append({"name": n, "value": s})
    return rows


def apply_scenario_color_constants(data: dict[str, Any]) -> None:
    """
    Build palette from `data['colors']`, expand `@` tokens across `data`, and
    normalize color row values. Mutates `data` in place (before other parsing).

    `colors` may be either a list of `{name, value}` rows (`[[colors]]`) or a
    flat dict/table (`[colors]` with `grid_hex = "#..."` entries), in file key
    order.
    """
    raw = data.get("colors")
    if raw is None:
        return
    if isinstance(raw, dict):
        rows = _colors_flat_table_to_rows(raw)
        data["colors"] = rows
        raw = rows
    if raw == []:
        return
    if not isinstance(raw, list):
        raise TypeError(f"colors must be a list or table, got {type(raw).__name__}")
    palette = build_color_palette(raw)
    materialize_color_table_values(raw, palette)
    _deep_apply_palette(data, palette)
