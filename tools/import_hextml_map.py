#!/usr/bin/env python3
"""
Import a Hextml-exported HTML map (from ``.tar.gz`` / ``.tgz``, a gzip-compressed
``.html`` (``.gz``), or a plain ``.html`` file) into hexes scenario TOML with
``[[terrain_groups]]`` (shared stats + member positions).

Coordinate mapping matches hexengine ``HexRowCol``: Hextml ``data-x`` → cube ``i``,
``data-y`` → ``j``, ``k = -i - j``.

Run from repo root::

    python tools/import_hextml_map.py path/to/export.tar.gz -o out/scenario.toml

Requires Python 3.11+ (stdlib only).
"""

from __future__ import annotations

import argparse
import gzip
import sys
import tarfile
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path


# Stub stats for Hextml CSS terrain classes → scenario ``terrain`` string is the
# class slug unless remapped here. Authors should tune in generated TOML.
TERRAIN_REMAP: dict[str, str] = {
    # "evergreen-hills": "forest",
}

# Default gameplay stats per output terrain name (after remap). Unknown terrains
# use ``_default``.
TERRAIN_DEFAULTS: dict[str, dict[str, object]] = {
    "_default": {
        "movement_cost": 1.0,
        "assault_modifier": 0.0,
        "ranged_modifier": 0.0,
        "block_los": True,
        "hex_color": "#a0a0a0",
    },
    "plain": {
        "movement_cost": 1.0,
        "assault_modifier": 0.0,
        "ranged_modifier": 0.0,
        "block_los": True,
        "hex_color": "#c8e6c8",
    },
    "beach": {
        "movement_cost": 1.5,
        "assault_modifier": 0.0,
        "ranged_modifier": 0.0,
        "block_los": True,
        "hex_color": "#e8d4a8",
    },
    "ocean": {
        "movement_cost": "inf",
        "assault_modifier": 0.0,
        "ranged_modifier": 0.0,
        "block_los": True,
        "hex_color": "#4a90c8",
    },
    "evergreen-hills": {
        "movement_cost": 2.5,
        "assault_modifier": 0.0,
        "ranged_modifier": 0.0,
        "block_los": True,
        "hex_color": "#3d6b3d",
    },
}


def _terrain_stats(terrain: str) -> dict[str, object]:
    base = TERRAIN_DEFAULTS.get(terrain, TERRAIN_DEFAULTS["_default"])
    return dict(base)


def _toml_float_or_str(v: object) -> str:
    if v == "inf" or (isinstance(v, float) and v == float("inf")):
        return '"inf"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    return str(float(v))


class _HextmlMapParser(HTMLParser):
    """Collect hex cells from ``section.map`` … ``article.hexline`` … ``hexBlock``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._sections: list[dict[str, object]] = []
        self._cur: dict[str, object] | None = None
        self._section_depth = 0
        self._y = 0
        self._x = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        cls = a.get("class", "")
        parts = cls.split()

        if tag == "section":
            if "map" in parts:
                if self._cur is None:
                    self._cur = {
                        "title": a.get("data-title", "").strip(),
                        "width": int(a.get("data-width", "0") or 0),
                        "height": int(a.get("data-height", "0") or 0),
                        "cells": [],
                    }
                    self._section_depth = 1
                else:
                    self._section_depth += 1
            elif self._cur is not None:
                self._section_depth += 1
            return

        cur = self._cur
        if cur is None:
            return

        if tag == "article" and "hexline" in parts:
            self._y = int(a.get("data-y", "0"))
            return

        if tag == "div" and any(p.lower() == "hexblock" for p in parts):
            self._x = int(a.get("data-x", "0"))
            return

        if tag == "div" and "hexagon-in2" in parts:
            extra = [p for p in parts if p != "hexagon-in2"]
            raw = extra[0] if extra else "plain"
            cells = cur["cells"]
            assert isinstance(cells, list)
            i, j = self._x, self._y
            k = -i - j
            cells.append((i, j, k, raw))

    def handle_endtag(self, tag: str) -> None:
        if tag != "section" or self._cur is None:
            return
        self._section_depth -= 1
        if self._section_depth <= 0:
            self._sections.append(self._cur)
            self._cur = None
            self._section_depth = 0

    def best_section(self) -> dict[str, object] | None:
        if not self._sections:
            return None
        return max(self._sections, key=lambda s: len(s["cells"]))  # type: ignore[arg-type]


def _read_html_bytes(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _load_html_from_path(path: Path) -> str:
    """Read a single local HTML file (not an archive)."""
    return _read_html_bytes(path.read_bytes())


def _load_html_from_gzip_or_tar(path: Path, inner: str | None) -> str:
    """
    ``.tar.gz`` / ``.tgz`` → tar archive. A lone ``.gz`` tries tar first, then
    treats the whole file as gzip-compressed HTML (some Hextml exports use this).
    """
    name = path.name.lower()
    if name.endswith(".tar.gz") or path.suffix.lower() == ".tgz":
        with tarfile.open(path, "r:*") as tf:
            return _read_html_from_tar(tf, inner)
    if path.suffix.lower() == ".gz":
        try:
            with tarfile.open(path, "r:*") as tf:
                return _read_html_from_tar(tf, inner)
        except (OSError, tarfile.ReadError):
            with gzip.open(path, "rb") as zf:
                return _read_html_bytes(zf.read())
    raise ValueError(f"Expected .gz / .tgz / .tar.gz, got {path}")


def _read_html_from_tar(tf: tarfile.TarFile, inner: str | None) -> str:
    members = [m for m in tf.getmembers() if m.isfile()]
    if inner:
        m = tf.getmember(inner)
        if not m.isfile():
            raise FileNotFoundError(f"Not a file in archive: {inner!r}")
        f = tf.extractfile(m)
        if f is None:
            raise OSError(f"Cannot read archive member: {inner!r}")
        return _read_html_bytes(f.read())

    html_members = [m for m in members if m.name.lower().endswith(".html")]
    if not html_members:
        raise FileNotFoundError("No .html file found in archive; use --html PATH")
    # Prefer common names, else largest file (main export vs tiny stubs)
    preferred = ("index.html", "hxtml.html", "map.html")
    for pref in preferred:
        for m in html_members:
            if m.name.lower().endswith(pref) or m.name.split("/")[-1].lower() == pref:
                f = tf.extractfile(m)
                if f:
                    return _read_html_bytes(f.read())
    biggest = max(html_members, key=lambda m: m.size)
    f = tf.extractfile(biggest)
    if f is None:
        raise OSError(f"Cannot read {biggest.name!r}")
    return _read_html_bytes(f.read())


def parse_hextml_html(html: str) -> dict[str, object]:
    p = _HextmlMapParser()
    p.feed(html)
    p.close()
    sec = p.best_section()
    if sec is None:
        raise ValueError("No <section class=\"map\"> found in HTML")
    cells = sec["cells"]
    assert isinstance(cells, list)
    return {
        "title": sec.get("title", ""),
        "width": sec.get("width", 0),
        "height": sec.get("height", 0),
        "cells": cells,
    }


def _escape_toml_basic(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_scenario_toml(
    *,
    name: str,
    description: str,
    parsed: dict[str, object],
) -> str:
    cells: list[tuple[int, int, int, str]] = parsed["cells"]  # type: ignore[assignment]
    by_terrain: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for i, j, k, raw in cells:
        terrain = TERRAIN_REMAP.get(raw, raw)
        by_terrain[terrain].append((i, j, k))

    lines: list[str] = [
        "# Generated by tools/import_hextml_map.py — tune terrain stats and remap names as needed.",
        "",
        f'name = "{_escape_toml_basic(name)}"',
        f'description = "{_escape_toml_basic(description)}"',
        "",
        "[map]",
        "hex_size = 24",
        "hex_margin = 0",
        "hex_stroke = 1",
        'hex_color = "#33443344"',
        'background = "resources/test_map.png"',
        "unit_size_multiplier = 1.5",
    ]
    w = int(parsed.get("width") or 0)  # type: ignore[arg-type]
    h = int(parsed.get("height") or 0)  # type: ignore[arg-type]
    if w > 0 and h > 0:
        lines.append(f"hex_columns = {w}")
        lines.append(f"hex_rows = {h}")
    lines.append("")

    for terrain in sorted(by_terrain.keys()):
        stats = _terrain_stats(terrain)
        positions = sorted(by_terrain[terrain])
        lines.append("[[terrain_groups]]")
        lines.append(f'terrain = "{_escape_toml_basic(terrain)}"')
        lines.append(f"movement_cost = {_toml_float_or_str(stats['movement_cost'])}")
        lines.append(f"assault_modifier = {_toml_float_or_str(stats['assault_modifier'])}")
        lines.append(f"ranged_modifier = {_toml_float_or_str(stats['ranged_modifier'])}")
        lines.append(
            "block_los = "
            + ("true" if bool(stats.get("block_los", True)) else "false")
        )
        hc = stats.get("hex_color")
        if isinstance(hc, str) and hc.strip():
            lines.append(f'hex_color = "{_escape_toml_basic(hc.strip())}"')
        lines.append("members = [")
        for i, j, k in positions:
            lines.append(f"  {{ position = [{i}, {j}, {k}] }},")
        lines.append("]")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        type=Path,
        help="Hextml export: .tar.gz / .tgz, gzip-compressed .html (.gz), or .html",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Write scenario TOML here",
    )
    parser.add_argument(
        "--html",
        metavar="PATH",
        help="Path inside the archive to the HTML file (if not chosen automatically)",
    )
    parser.add_argument(
        "--name",
        help="Scenario name (default: map data-title or input stem)",
    )
    parser.add_argument(
        "--description",
        default="Imported from Hextml.",
        help="Scenario description",
    )
    args = parser.parse_args(argv)

    path: Path = args.input
    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        return 1

    try:
        if (
            path.suffix.lower() in (".gz", ".tgz")
            or path.name.lower().endswith(".tar.gz")
        ):
            html = _load_html_from_gzip_or_tar(path, args.html)
        else:
            html = _load_html_from_path(path)
        parsed = parse_hextml_html(html)
    except (OSError, ValueError, tarfile.TarError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    title = str(parsed.get("title") or "").strip()
    name = args.name or title or path.stem
    toml_text = build_scenario_toml(
        name=name,
        description=args.description,
        parsed=parsed,
    )
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(toml_text, encoding="utf-8")
    ncells = len(parsed["cells"])  # type: ignore[arg-type]
    print(f"Wrote {out} ({ncells} hexes, {len(toml_text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
