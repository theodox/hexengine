"""
Discover game packs from games/*/hexengine_pack.toml and load GameDefinition by manifest.

The engine does not name individual titles; each pack declares entry_module /
entry_callable and a sys.path prefix via path_add (relative to the pack root).
"""

from __future__ import annotations

import importlib
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hexengine.gamedef.game_data import GameData
from hexengine.gamedef.game_data_toml import (
    game_data_from_mapping,
    merged_gamedata_dict_from_manifest,
)
from hexengine.gamedef.protocol import GameDefinition

_MANIFEST_NAME = "hexengine_pack.toml"


@dataclass(frozen=True, slots=True)
class PackPythonSpec:
    path_add: str
    entry_module: str
    entry_callable: str


@dataclass(frozen=True, slots=True)
class PackTitleLoadHooks:
    """
    Browser/client hooks from `[hooks.title_load]` in hexengine_pack.toml.

    Enabling this block wires title-load; missing callables are not validated at
    parse time (see `docs/TITLE_LOAD_HOOKS.md`).
    """

    module: str
    splash_html: str
    splash_callable: str = "present_splash"
    setup_callable: str = "run_setup"
    server_loaded_callable: str = "on_server_loaded"


@dataclass(frozen=True, slots=True)
class PackManifest:
    manifest_version: int
    pack_id: str
    title: str
    python: PackPythonSpec
    hooks_title_load: PackTitleLoadHooks | None = None


@dataclass(frozen=True, slots=True)
class PackRecord:
    """One installable pack (directory containing hexengine_pack.toml)."""

    root: Path
    manifest: PackManifest
    #: Declarative title data from `[gamedata]` in the manifest (optional file + overrides).
    game_data: GameData


_records: list[PackRecord] = []
_discovered: bool = False


def _candidate_games_directories() -> list[Path]:
    """games directories to scan for child packs (deduped, resolved)."""
    seen: set[Path] = set()
    out: list[Path] = []
    for d in Path(__file__).resolve().parents:
        g = d / "games"
        if g.is_dir():
            r = g.resolve()
            if r not in seen:
                seen.add(r)
                out.append(r)
    cwd_games = (Path.cwd() / "games").resolve()
    if cwd_games.is_dir() and cwd_games not in seen:
        out.append(cwd_games)
    return out


def _parse_manifest(pack_root: Path, raw: dict[str, Any]) -> PackManifest:
    ver = raw.get("manifest_version", 1)
    if int(ver) != 1:
        raise ValueError(
            f"Unsupported hexengine_pack.toml manifest_version {ver!r} in {pack_root}"
        )
    pack = raw.get("pack")
    if not isinstance(pack, dict):
        raise ValueError(f"Missing [pack] table in manifest under {pack_root}")
    pack_id = str(pack.get("id", "")).strip()
    if not pack_id:
        raise ValueError(f"Missing pack.id in manifest under {pack_root}")
    if pack_root.name != pack_id:
        raise ValueError(
            f"pack.id {pack_id!r} must match directory name {pack_root.name!r} ({pack_root})"
        )
    title = str(pack.get("title", pack_id)).strip() or pack_id

    py = raw.get("python")
    if not isinstance(py, dict):
        raise ValueError(f"Missing [python] table in manifest under {pack_root}")
    path_add = str(py.get("path_add", "..")).strip() or "."
    entry_module = str(py.get("entry_module", "")).strip()
    entry_callable = str(py.get("entry_callable", "")).strip()
    if not entry_module or not entry_callable:
        raise ValueError(
            f"python.entry_module and python.entry_callable required in manifest under {pack_root}"
        )
    hooks_title_load: PackTitleLoadHooks | None = None
    hooks = raw.get("hooks")
    if isinstance(hooks, dict):
        tl = hooks.get("title_load")
        if isinstance(tl, dict):
            mod = str(tl.get("module", "")).strip()
            splash = str(tl.get("splash_html", "")).strip()
            if mod and splash:
                splash_fn = str(tl.get("splash_callable", "present_splash")).strip()
                setup_fn = str(tl.get("setup_callable", "run_setup")).strip()
                server_fn = str(
                    tl.get("server_loaded_callable", "on_server_loaded")
                ).strip()
                hooks_title_load = PackTitleLoadHooks(
                    module=mod,
                    splash_html=splash,
                    splash_callable=splash_fn or "present_splash",
                    setup_callable=setup_fn or "run_setup",
                    server_loaded_callable=server_fn or "on_server_loaded",
                )
    return PackManifest(
        manifest_version=1,
        pack_id=pack_id,
        title=title,
        python=PackPythonSpec(
            path_add=path_add,
            entry_module=entry_module,
            entry_callable=entry_callable,
        ),
        hooks_title_load=hooks_title_load,
    )


def _load_pack_record(pack_root: Path) -> PackRecord:
    mf = pack_root / _MANIFEST_NAME
    data = tomllib.loads(mf.read_text(encoding="utf-8"))
    manifest = _parse_manifest(pack_root, data)
    merged = merged_gamedata_dict_from_manifest(pack_root.resolve(), data)
    game_data = game_data_from_mapping(merged)
    return PackRecord(root=pack_root.resolve(), manifest=manifest, game_data=game_data)


def discover_game_packs(*, force: bool = False) -> None:
    """
    Scan games/<pack_id>/hexengine_pack.toml under known games roots and register packs.

    Idempotent unless force=True (clears and re-scans).
    """
    global _records, _discovered
    if _discovered and not force:
        return
    _records = []
    seen: set[Path] = set()
    for games_dir in _candidate_games_directories():
        if not games_dir.is_dir():
            continue
        for child in sorted(games_dir.iterdir(), key=lambda p: p.name.casefold()):
            if not child.is_dir():
                continue
            manifest_path = child / _MANIFEST_NAME
            if not manifest_path.is_file():
                continue
            rec = _load_pack_record(child)
            if rec.root in seen:
                continue
            seen.add(rec.root)
            _records.append(rec)
    _discovered = True


def _register_ancestor_packs_for_scenario(p: Path) -> None:
    """If an ancestor of p contains hexengine_pack.toml, register that pack root."""
    discover_game_packs()
    start = p if p.is_dir() else p.parent
    known: set[Path] = {r.root for r in _records}
    for anc in [start, *start.parents]:
        if not (anc / _MANIFEST_NAME).is_file():
            continue
        try:
            rec = _load_pack_record(anc)
        except (OSError, TypeError, ValueError, KeyError):
            continue
        if rec.root not in known:
            known.add(rec.root)
            _records.append(rec)


def reset_game_pack_registry_for_tests() -> None:
    """Clear discovery state (unit tests)."""
    global _records, _discovered
    _records = []
    _discovered = False


def registered_packs() -> tuple[PackRecord, ...]:
    discover_game_packs()
    return tuple(_records)


def resolve_pack_for_scenario(scenario_path: str | Path) -> PackRecord:
    """
    Pick the owning pack for scenario_path (longest pack.root prefix wins).
    """
    p = Path(scenario_path).expanduser().resolve()
    _register_ancestor_packs_for_scenario(p)
    candidates = [rec for rec in _records if p.is_relative_to(rec.root)]
    if not candidates:
        raise ValueError(
            "No registered game pack owns this scenario path "
            f"({p!r}). Add hexengine_pack.toml under games/<pack_id>/ or set --game-root."
        )
    return max(candidates, key=lambda r: len(r.root.parts))


def ensure_pack_import_path_for_scenario(scenario_path: str | Path) -> None:
    """Prepend the pack's configured sys.path entry so entry_module can import."""
    rec = resolve_pack_for_scenario(scenario_path)
    add = (rec.root / rec.manifest.python.path_add).resolve()
    if add.is_dir():
        s = str(add)
        if s not in sys.path:
            sys.path.insert(0, s)


def load_game_definition_for_scenario_path(scenario_path: str | Path) -> GameDefinition:
    """Resolve pack from scenario path, adjust sys.path, import entry, return definition."""
    rec = resolve_pack_for_scenario(scenario_path)
    add = (rec.root / rec.manifest.python.path_add).resolve()
    if add.is_dir():
        s = str(add)
        if s not in sys.path:
            sys.path.insert(0, s)
    mod = importlib.import_module(rec.manifest.python.entry_module)
    fn = getattr(mod, rec.manifest.python.entry_callable, None)
    if not callable(fn):
        raise TypeError(
            f"{rec.manifest.python.entry_module}.{rec.manifest.python.entry_callable} "
            f"is not callable (pack {rec.manifest.pack_id!r})"
        )
    return fn()
