"""
Resolve scenario paths from launch arguments and repo layout (GameRoot: loose dir or zip).

When no pack is specified, a games/<pack_id>/ tree next to an ancestor of this module
(typical dev checkout) supplies the **default** scenario when that pack includes
scenarios/default/scenario.toml (today: the bundled hexdemo pack).

**Temporary:** defaulting to `games/hexdemo` is deliberate while we iterate on the
authoring experience and need a stable pack to exercise it. Replace with neutral
default-pack discovery (or require explicit `--game-root` / `--scenario-file`) later.

Zip archives extract to a temporary directory for import compatibility.

**Engine fallbacks removed (game-pack-first startup):**

- No silent fallback to a packaged engine-only scenario path when no game pack resolves
  or the packaged engine `test_scenario` when no `games/<pack>` layout is found —
  `resolve_scenario_path_with_game_root` raises `FileNotFoundError` instead.
- `load_game_definition_for_scenario` no longer returns generic Red/Blue rules for
  arbitrary paths; only directories with hexengine_pack.toml (discovered under
  games/*/ or on an ancestor chain of the scenario path) load title Python —
  otherwise `ValueError`.
- `load_game_definition` remains for **explicit** engine test / demo Red/Blue schedules only
  (not inferred from a scenario path). Pack scenarios use the pack's own
  load_game_definition() from hexengine_pack.toml (no engine-passed schedule).
"""

from __future__ import annotations

import argparse
import importlib
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .gamedef.builtin import (
    InterleavedTwoFactionGameDefinition,
    SequentialTwoFactionGameDefinition,
)
from .gamedef.protocol import GameDefinition
from .gamedef.title_load import TitleLoadContext, TitleLoadResult


def initial_turn_slot_for_game_definition(game: GameDefinition) -> dict[str, Any]:
    """First slot in the flat turn rota (faction, phase, max_actions) for bootstrap."""
    order = game.turn_order()
    if not order:
        raise ValueError("GameDefinition.turn_order() returned an empty list")
    slot = order[0]
    return {
        "faction": str(slot["faction"]),
        "phase": str(slot["phase"]),
        "max_actions": int(slot["max_actions"]),
    }


def initial_faction_for_game_definition(game: GameDefinition) -> str:
    """First faction in the flat turn order (matches `scenario_to_initial_state` start)."""
    return initial_turn_slot_for_game_definition(game)["faction"]


def load_game_definition_for_scenario(scenario_path: str | Path) -> GameDefinition:
    """
    Return the hexengine.gamedef.protocol.GameDefinition for the resolved scenario.

    Dispatches via hexengine.game_packs.registry using each pack's hexengine_pack.toml
    (no engine code names individual titles). The pack's entry_callable returns the
    title's single static schedule.
    """
    from hexengine.game_packs.registry import load_game_definition_for_scenario_path

    return load_game_definition_for_scenario_path(scenario_path)


def load_game_definition(*, schedule: str = "interleaved") -> GameDefinition:
    """
    Built-in Red/Blue demo schedules for engine tests and tools (not pack scenarios).

    - interleaved — InterleavedTwoFactionGameDefinition
    - sequential — SequentialTwoFactionGameDefinition

    Pack-owned scenarios use load_game_definition_for_scenario instead; the pack
    declares its own rota via its manifest entry_callable.
    """
    if schedule.strip().lower() == "sequential":
        return SequentialTwoFactionGameDefinition()
    return InterleavedTwoFactionGameDefinition()


def add_game_launch_arguments(parser: argparse.ArgumentParser) -> None:
    """Register scenario flags (shared by server CLIs)."""
    parser.add_argument(
        "--scenario-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to a scenario.toml (if set, --game-root and --scenario-id are ignored)",
    )
    parser.add_argument(
        "--game-root",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Game pack directory or .zip (default: games/hexdemo next to repo root "
            "when that layout exists)"
        ),
    )
    parser.add_argument(
        "--scenario-id",
        default=None,
        metavar="ID",
        help=(
            "Scenario folder under scenarios/ (default id: default; may be used without "
            "--game-root when the hexdemo pack is found automatically)"
        ),
    )


def resolve_scenario_path_with_game_root(
    *,
    scenario_file: str | Path | None = None,
    game_root: str | Path | None = None,
    scenario_id: str | None = None,
) -> Path:
    """
    Resolve the scenario TOML path (no environment variables).

    Resolution order:

    1. `scenario_file` — path to a `scenario.toml` file
    2. `game_root` if set, else `games/hexdemo` discovered on an ancestor of the
       engine (typical repo checkout), then `scenarios` / `scenario_id` /
       `scenario.toml` (folder id `scenario_id` defaults to `default`)
    3. `games/hexdemo` under `pathlib.Path.cwd` when step 2 finds nothing (e.g.
       server thread cwd is the repo root but the package lives in site-packages)
    4. *(removed)* There is no fallback to the packaged engine test scenario; if no pack
       is found, `FileNotFoundError` is raised.

    `scenario_id` without a usable pack (no `--game-root`, no auto hexdemo) raises
    `ValueError`.

    If `game_root` is set but is not a directory or `.zip` file, raises `ValueError`.
    If the resolved scenario path is missing, raises `FileNotFoundError`.
    """
    if scenario_file is not None:
        p = Path(scenario_file).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"No scenario file at {p}")
        return p

    gr: Path | None
    if game_root is not None:
        gr = _game_root_from_path_value(game_root)
        if gr is None:
            raise ValueError(
                f"game_root is not a directory or .zip file: {game_root!r}"
            )
    else:
        gr = _find_bundled_hexdemo_game_root()
        if gr is None:
            gr = _find_hexdemo_game_root_from_cwd()

    if gr is not None:
        sid = scenario_id or "default"
        cand = gr / "scenarios" / sid / "scenario.toml"
        if not cand.is_file():
            raise FileNotFoundError(
                f"No scenario file at {cand} (scenario_id={sid!r}, game_root={gr})"
            )
        return cand.resolve()

    if scenario_id is not None:
        raise ValueError(
            "scenario_id requires --game-root (or use --scenario-file for a direct path)"
        )

    raise FileNotFoundError(
        "No game scenario found: set --scenario-file, --game-root, or run from a layout "
        "with games/hexdemo/scenarios/default/scenario.toml (or cwd games/hexdemo/…)."
    )


def _find_hexdemo_game_root_from_cwd() -> Path | None:
    """
    Return `games/hexdemo` under `os.getcwd` when that layout exists.

    Used when the package is not under a repo checkout (e.g. installed wheel) but
    the process was started with cwd at the project root that still contains
    `games/hexdemo`.
    """
    root = Path.cwd().resolve() / "games" / "hexdemo"
    if (root / "scenarios" / "default" / "scenario.toml").is_file():
        return root
    return None


def _find_bundled_hexdemo_game_root() -> Path | None:
    """
    Return `games/hexdemo` when it sits under an ancestor of this module (repo layout).

    Used as the default pack so `hexserver` with no arguments loads hexdemo's
    `scenarios/default/scenario.toml` when the checkout includes `games/hexdemo`.

    See module docstring: hexdemo-specific default is temporary; revisit when authoring
    defaults no longer need a fixed reference pack.
    """
    for d in Path(__file__).resolve().parents:
        root = d / "games" / "hexdemo"
        if (root / "scenarios" / "default" / "scenario.toml").is_file():
            return root
    return None


def _game_root_from_path_value(raw: str | Path) -> Path | None:
    p = Path(raw).expanduser().resolve()
    if p.is_file() and p.suffix.lower() == ".zip":
        return _ensure_zip_extracted(p)
    if p.is_dir():
        return p
    return None


_ZIP_EXTRACT_CACHE: dict[Path, Path] = {}


def _ensure_zip_extracted(zip_path: Path) -> Path:
    if zip_path in _ZIP_EXTRACT_CACHE:
        return _ZIP_EXTRACT_CACHE[zip_path]
    parent = tempfile.mkdtemp(prefix="hexes_game_zip_")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(parent)
    root = Path(parent)
    _ZIP_EXTRACT_CACHE[zip_path] = root
    return root


def cleanup_extracted_game_roots() -> None:
    """Remove temp dirs created for zip packs (best-effort; for tests/shutdown hooks)."""
    for _zp, root in list(_ZIP_EXTRACT_CACHE.items()):
        try:
            shutil.rmtree(root, ignore_errors=True)
        finally:
            pass
    _ZIP_EXTRACT_CACHE.clear()


_title_load_server_logged: bool = False


def reset_title_load_hooks_for_tests() -> None:
    """Reset one-shot server title-load hook (unit tests only)."""
    global _title_load_server_logged
    _title_load_server_logged = False


def ensure_pack_import_path_for_scenario(scenario_path: str | Path) -> None:
    """Prepend the owning pack's sys.path prefix for scenario_path (see manifest)."""
    from hexengine.game_packs.registry import (
        ensure_pack_import_path_for_scenario as _ensure,
    )

    try:
        _ensure(scenario_path)
    except ValueError:
        return


def _title_load_hooks_for_scenario(
    scenario_path: str | Path,
) -> tuple[Any, Any] | None:
    """Return `(pack_record, title_load_hooks)` or None if unset / unresolvable."""
    from hexengine.game_packs.registry import resolve_pack_for_scenario

    try:
        rec = resolve_pack_for_scenario(scenario_path)
    except ValueError:
        return None
    tl = rec.manifest.hooks_title_load
    if tl is None:
        return None
    ensure_pack_import_path_for_scenario(scenario_path)
    return rec, tl


def _import_title_load_module(module_name: str) -> Any | None:
    try:
        return importlib.import_module(module_name)
    except ImportError:
        logging.getLogger(__name__).debug(
            "title_load module %r not importable", module_name, exc_info=True
        )
        return None


def run_title_load_splash(scenario_path: str | Path) -> None:
    """
    Load splash HTML from the pack manifest and call `present_splash(html)`.

    Declared in hexengine_pack.toml under `[hooks.title_load]`.
    """
    resolved = _title_load_hooks_for_scenario(scenario_path)
    if resolved is None:
        return
    rec, tl = resolved
    from hexengine.game_packs.resources import read_pack_resource_text

    html = read_pack_resource_text(rec.root, tl.splash_html)
    if html is None:
        logging.getLogger(__name__).warning(
            "title_load splash_html %r missing under %s/resources",
            tl.splash_html,
            rec.root,
        )
        return
    mod = _import_title_load_module(tl.module)
    if mod is None:
        return
    fn = getattr(mod, tl.splash_callable, None)
    if not callable(fn):
        return
    try:
        fn(html)
    except Exception:
        logging.getLogger(__name__).debug(
            "title_load %s.%s failed",
            tl.module,
            tl.splash_callable,
            exc_info=True,
        )


def run_title_load_setup(scenario_path: str | Path) -> bool:
    """
    Call the pack setup hook before WebSocket connect.

    Returns False when the hook sets `TitleLoadResult(continue_connect=False)`.
    """
    resolved = _title_load_hooks_for_scenario(scenario_path)
    if resolved is None:
        return True
    rec, tl = resolved
    mod = _import_title_load_module(tl.module)
    if mod is None:
        return True
    fn = getattr(mod, tl.setup_callable, None)
    if not callable(fn):
        return True
    ctx = TitleLoadContext(
        pack_id=rec.manifest.pack_id,
        pack_root=rec.root,
        scenario_path=Path(scenario_path).expanduser().resolve(),
    )
    try:
        out = fn(ctx)
    except Exception:
        logging.getLogger(__name__).debug(
            "title_load %s.%s failed", tl.module, tl.setup_callable, exc_info=True
        )
        return True
    if isinstance(out, TitleLoadResult):
        return bool(out.continue_connect)
    if isinstance(out, bool):
        return out
    return True


def try_pack_title_load_server(scenario_path: str | Path) -> None:
    """
    Once per process, call the pack's server-side title-load hook (e.g. log line).

    Invoked from hexserver after authoritative pack load.
    """
    global _title_load_server_logged
    if _title_load_server_logged:
        return
    resolved = _title_load_hooks_for_scenario(scenario_path)
    if resolved is None:
        return
    _rec, tl = resolved
    mod = _import_title_load_module(tl.module)
    if mod is None:
        return
    fn = getattr(mod, tl.server_loaded_callable, None)
    if not callable(fn):
        return
    try:
        fn()
    except Exception:
        logging.getLogger(__name__).debug(
            "title_load %s.%s failed",
            tl.module,
            tl.server_loaded_callable,
            exc_info=True,
        )
        return
    _title_load_server_logged = True
