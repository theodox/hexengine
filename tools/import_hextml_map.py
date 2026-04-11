#!/usr/bin/env python3
"""
Import a Hextml-exported HTML map (from ``.tar.gz`` / ``.tgz``, a gzip-compressed
``.html`` (``.gz``), or a plain ``.html`` file) into hexes scenario TOML with
``[[terrain_groups]]`` (shared stats + member positions).

Hextml stores **odd-q offset** coordinates on export: ``data-x`` is the column,
``data-y`` (on ``hexline``) is the offset row, not cube ``j`` (see Red Blob Games
“offset coordinates → axial”). We convert with ``j = row - (col - (col & 1)) // 2``,
``i = col``, then shift so the map’s minimum axial ``(i, j)`` is ``(0, 0)``, and
again in odd-q ``(col, row)`` so minimum column and offset-row are both ``0`` (so
scenario ``position = [col, row]`` matches a tight top-left origin). Use ``--coords raw``
for legacy imports that were already axial.

Run from repo root::

    python tools/import_hextml_map.py path/to/export.tar.gz -o out/scenario.toml

To refresh map + ``[[terrain_groups]]`` on an existing scenario while keeping
``name``/``description``, ``[[unit_graphics]]``, ``[[unit_placements]]``, ``[[units]]``, etc.::

    python tools/import_hextml_map.py map.gz -o src/.../scenario.toml \\
        --merge-into src/.../scenario.toml

``--merge-into`` must match ``-o``. Terrain types that already exist in the file
keep their edited stats (movement cost, LOS, colors, …); new terrain types use
script defaults (``block_los`` defaults to ``false``). Stray ``[[terrain_groups]]``
after unit tables in the old file are stripped so they are not kept alongside the
new map.

Requires Python 3.11+. Expects the repo ``src`` layout (``hexengine`` on ``sys.path``);
the script prepends ``<repo>/src`` when run as a file.
"""

from __future__ import annotations

import argparse
import gzip
import sys
import tarfile
import tomllib
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from hexengine.hexes.math import shift_axial_ij_cube_coords_to_origin  # noqa: E402
from hexengine.hexes.types import Hex, HexColRow  # noqa: E402

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
        "block_los": False,
        "hex_color": "#a0a0a073",
    },
    "plain": {
        "movement_cost": 1.0,
        "assault_modifier": 0.0,
        "ranged_modifier": 0.0,
        "block_los": False,
        "hex_color": "#c8e6c873",
    },
    "beach": {
        "movement_cost": 1.5,
        "assault_modifier": 0.0,
        "ranged_modifier": 0.0,
        "block_los": False,
        "hex_color": "#e8d4a873",
    },
    "ocean": {
        "movement_cost": "inf",
        "assault_modifier": 0.0,
        "ranged_modifier": 0.0,
        "block_los": False,
        "hex_color": "#4a90c873",
    },
    "evergreen-hills": {
        "movement_cost": 2.5,
        "assault_modifier": 0.0,
        "ranged_modifier": 0.0,
        "block_los": False,
        "hex_color": "#3d6b3d73",
    },
}


def _normalize_axial_cells(
    cells: list[tuple[int, int, int, str]],
) -> list[tuple[int, int, int, str]]:
    """Shift all positions so min i and min j are zero (scenario origin)."""
    if not cells:
        return cells
    shifted = shift_axial_ij_cube_coords_to_origin((c[0], c[1], c[2]) for c in cells)
    return [(t[0], t[1], t[2], cells[i][3]) for i, t in enumerate(shifted)]


def _normalize_oddq_col_row_cells(
    cells: list[tuple[int, int, int, str]],
) -> list[tuple[int, int, int, str]]:
    """
    Shift in odd-q ``(col, row)`` so min column and min offset-row are both 0.

    Axial ``min(i), min(j)`` does not imply min odd-q row is 0; scenario TOML uses
    ``[col, row]``, so this aligns the tight bbox with editor/visual top-left.
    """
    if not cells:
        return cells
    rows: list[tuple[int, int, int, str, int, int]] = []
    for i, j, k, raw in cells:
        cr = HexColRow.from_hex(Hex(i, j, k))
        rows.append((i, j, k, raw, cr.col, cr.row))
    min_c = min(t[4] for t in rows)
    min_r = min(t[5] for t in rows)
    out: list[tuple[int, int, int, str]] = []
    for _i, _j, _k, raw, c, r in rows:
        ncr = HexColRow(col=c - min_c, row=r - min_r)
        h2 = ncr.to_hex()
        out.append((h2.i, h2.j, h2.k, raw))
    return out


def _terrain_stats(terrain: str) -> dict[str, object]:
    base = TERRAIN_DEFAULTS.get(terrain, TERRAIN_DEFAULTS["_default"])
    return dict(base)


def _terrain_overlay_from_parsed_toml(
    data: dict[str, object],
) -> dict[str, dict[str, object]]:
    """``terrain`` string -> stat fields from existing ``[[terrain_groups]]`` (no ``members``)."""
    out: dict[str, dict[str, object]] = {}
    raw = data.get("terrain_groups")
    if not isinstance(raw, list):
        return out
    for g in raw:
        if not isinstance(g, dict):
            continue
        t = g.get("terrain")
        if not isinstance(t, str):
            continue
        stats: dict[str, object] = {}
        for k in (
            "movement_cost",
            "assault_modifier",
            "ranged_modifier",
            "block_los",
            "hex_color",
        ):
            if k in g:
                stats[k] = g[k]
        out[t] = stats
    return out


def _merged_terrain_stats(
    terrain: str,
    overlay: dict[str, dict[str, object]] | None,
) -> dict[str, object]:
    """Defaults for ``terrain``, overridden by existing TOML row when names match."""
    base = _terrain_stats(terrain)
    if overlay and terrain in overlay:
        base.update(overlay[terrain])
    return base


_UNIT_TABLE_MARKERS = ("[[unit_graphics]]", "[[unit_placements]]", "[[units]]")


def _strip_terrain_groups_from_tail(tail: str) -> str:
    """
    Remove ``[[terrain_groups]]`` blocks from the preserved tail.

    If unit tables appear before all terrain (unusual) or old ``[[terrain_groups]]``
    were left *after* ``[[unit_placements]]``, those stray map tables would survive merge and
    duplicate hexes with stale positions. Only ``[[unit_graphics]]``, ``[[unit_placements]]``,
    and ``[[units]]`` belong in the tail.
    """
    lines = tail.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        s = lines[i].lstrip()
        if s.startswith("[[terrain_groups]]"):
            i += 1
            while i < len(lines):
                s2 = lines[i].lstrip()
                if s2.startswith("[["):
                    break
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "".join(out)


def _replace_name_description_lines(
    head: str,
    *,
    name: str | None,
    description: str | None,
) -> str:
    """When ``--name`` / ``--description`` are set, rewrite those lines in ``head``."""
    if name is None and description is None:
        return head
    out: list[str] = []
    for line in head.splitlines(keepends=True):
        stripped = line.strip()
        if name is not None and stripped.startswith("name ="):
            out.append(f'name = "{_escape_toml_basic(name)}"\n')
            continue
        if description is not None and stripped.startswith("description ="):
            out.append(f'description = "{_escape_toml_basic(description)}"\n')
            continue
        out.append(line)
    return "".join(out)


def _split_scenario_for_map_replace(text: str) -> tuple[str, str]:
    """
    ``(head, tail)`` where ``head`` is everything before ``[map]``, ``tail`` is
    from the first unit-related ``[[...]]`` to EOF. The slice ``[map]`` … terrain
    groups is dropped and rebuilt from Hextml.
    """
    lines = text.splitlines(keepends=True)
    map_i = None
    for i, line in enumerate(lines):
        if line.strip() == "[map]":
            map_i = i
            break
    if map_i is None:
        raise ValueError("merge target has no [map] table")
    tail_start = len(lines)
    for j in range(map_i + 1, len(lines)):
        stripped = lines[j].lstrip()
        for um in _UNIT_TABLE_MARKERS:
            if stripped.startswith(um):
                tail_start = j
                break
        if tail_start < len(lines):
            break
    head = "".join(lines[:map_i])
    tail = "".join(lines[tail_start:])
    return head, tail


def build_map_and_terrain_toml(
    *,
    parsed: dict[str, object],
    terrain_overlay: dict[str, dict[str, object]] | None = None,
) -> str:
    """``[map]`` plus ``[[terrain_groups]]`` only (no name/description/header)."""
    cells: list[tuple[int, int, int, str]] = parsed["cells"]  # type: ignore[assignment]
    by_terrain: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for i, j, k, raw in cells:
        terrain = TERRAIN_REMAP.get(raw, raw)
        by_terrain[terrain].append((i, j, k))

    lines: list[str] = [
        "[map]",
        "hex_size = 24",
        "hex_margin = 0",
        "hex_stroke = 1",
        'hex_color = "#33443344"',
        'terrain_overlay_line_color = "#33443344"',
        "terrain_overlay_line_width = 2",
        'background = "resources/test_map.png"',
        "background_crop_to_map = true",
        "unit_size_multiplier = 1.5",
    ]
    if cells:
        max_i = max(c[0] for c in cells)
        max_j = max(c[1] for c in cells)
        w = max_i + 1
        h = max_j + 1
    else:
        w = int(parsed.get("width") or 0)  # type: ignore[arg-type]
        h = int(parsed.get("height") or 0)  # type: ignore[arg-type]
    if w > 0 and h > 0:
        lines.append(f"hex_columns = {w}")
        lines.append(f"hex_rows = {h}")
    lines.append("")

    for terrain in sorted(by_terrain.keys()):
        stats = _merged_terrain_stats(terrain, terrain_overlay)
        positions = sorted(by_terrain[terrain])
        lines.append("[[terrain_groups]]")
        lines.append(f'terrain = "{_escape_toml_basic(terrain)}"')
        lines.append(f"movement_cost = {_toml_float_or_str(stats['movement_cost'])}")
        lines.append(
            f"assault_modifier = {_toml_float_or_str(stats['assault_modifier'])}"
        )
        lines.append(
            f"ranged_modifier = {_toml_float_or_str(stats['ranged_modifier'])}"
        )
        lines.append(
            "block_los = "
            + ("true" if bool(stats.get("block_los", False)) else "false")
        )
        hc = stats.get("hex_color")
        if isinstance(hc, str) and hc.strip():
            lines.append(f'hex_color = "{_escape_toml_basic(hc.strip())}"')
        lines.append("members = [")
        for i, j, k in positions:
            rc = HexColRow.from_hex(Hex(i, j, k))
            lines.append(f"  {{ position = [{rc.col}, {rc.row}] }},")
        lines.append("]")
        lines.append("")

    return "\n".join(lines)


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

    def __init__(self, *, coord_mode: str = "odd_q") -> None:
        super().__init__(convert_charrefs=True)
        if coord_mode not in ("odd_q", "raw"):
            raise ValueError("coord_mode must be 'odd_q' or 'raw'")
        self._coord_mode = coord_mode
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
            col = self._x
            row = self._y
            if self._coord_mode == "raw":
                i, j = col, row
                k = -i - j
                cells.append((i, j, k, raw))
            else:
                h = HexColRow(col=col, row=row).to_hex()
                cells.append((h.i, h.j, h.k, raw))

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


def parse_hextml_html(
    html: str,
    *,
    coord_mode: str = "odd_q",
) -> dict[str, object]:
    p = _HextmlMapParser(coord_mode=coord_mode)
    p.feed(html)
    p.close()
    sec = p.best_section()
    if sec is None:
        raise ValueError('No <section class="map"> found in HTML')
    cells = sec["cells"]
    assert isinstance(cells, list)
    axial = _normalize_axial_cells(list(cells))
    normalized = _normalize_oddq_col_row_cells(axial)
    return {
        "title": sec.get("title", ""),
        "width": sec.get("width", 0),
        "height": sec.get("height", 0),
        "cells": normalized,
    }


def _escape_toml_basic(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_scenario_toml(
    *,
    name: str,
    description: str,
    parsed: dict[str, object],
    terrain_overlay: dict[str, dict[str, object]] | None = None,
) -> str:
    header = (
        "# Generated by tools/import_hextml_map.py — tune terrain stats and remap names as needed.\n"
        "\n"
        f'name = "{_escape_toml_basic(name)}"\n'
        f'description = "{_escape_toml_basic(description)}"\n'
        "\n"
    )
    return header + build_map_and_terrain_toml(
        parsed=parsed, terrain_overlay=terrain_overlay
    )


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
        "--merge-into",
        type=Path,
        metavar="PATH",
        help=(
            "Existing scenario to merge: keep head (before [map]) and unit tables; "
            "replace [map] and [[terrain_groups]]. Must equal -o."
        ),
    )
    parser.add_argument(
        "--html",
        metavar="PATH",
        help="Path inside the archive to the HTML file (if not chosen automatically)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Scenario name (default: map title / stem, or existing file when using --merge-into)",
    )
    parser.add_argument(
        "--description",
        default=None,
        help=(
            "Scenario description (default: 'Imported from Hextml.' or existing when merging)"
        ),
    )
    parser.add_argument(
        "--coords",
        choices=("odd_q", "raw"),
        default="odd_q",
        help=(
            "How to interpret data-x/data-y: odd_q (Hextml offset, default) or "
            "raw (treat as axial i/j — legacy)"
        ),
    )
    args = parser.parse_args(argv)

    path: Path = args.input
    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        return 1

    try:
        if path.suffix.lower() in (".gz", ".tgz") or path.name.lower().endswith(
            ".tar.gz"
        ):
            html = _load_html_from_gzip_or_tar(path, args.html)
        else:
            html = _load_html_from_path(path)
        parsed = parse_hextml_html(html, coord_mode=args.coords)
    except (OSError, ValueError, tarfile.TarError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    title = str(parsed.get("title") or "").strip()
    out: Path = args.output
    merge_path = args.merge_into

    if merge_path is not None:
        if merge_path.resolve() != out.resolve():
            print(
                "error: --merge-into must be the same path as -o (safety check)",
                file=sys.stderr,
            )
            return 1
        existing_text = merge_path.read_text(encoding="utf-8")
        try:
            head, tail = _split_scenario_for_map_replace(existing_text)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        try:
            existing_data = tomllib.loads(existing_text)
        except tomllib.TOMLDecodeError as e:
            print(f"error: cannot parse merge target: {e}", file=sys.stderr)
            return 1
        overlay = _terrain_overlay_from_parsed_toml(existing_data)
        head = _replace_name_description_lines(
            head, name=args.name, description=args.description
        )
        tail = _strip_terrain_groups_from_tail(tail)
        middle = build_map_and_terrain_toml(parsed=parsed, terrain_overlay=overlay)
        toml_text = head + middle + tail
    else:
        name = args.name or title or path.stem
        desc = (
            args.description
            if args.description is not None
            else "Imported from Hextml."
        )
        toml_text = build_scenario_toml(
            name=name,
            description=desc,
            parsed=parsed,
            terrain_overlay=None,
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(toml_text, encoding="utf-8")
    ncells = len(parsed["cells"])  # type: ignore[arg-type]
    print(f"Wrote {out} ({ncells} hexes, {len(toml_text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
