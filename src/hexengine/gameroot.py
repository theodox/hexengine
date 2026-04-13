"""
Resolve scenario paths from launch arguments and repo layout (GameRoot: loose dir or zip).

When no pack is specified, a `games/hexdemo` tree next to an ancestor of this module
(typical dev checkout) supplies the **default** scenario.

Zip archives extract to a temporary directory for import compatibility.

**Engine fallbacks removed (game-pack-first startup):**

- No silent fallback to a packaged engine-only scenario path when no game pack resolves
  or the packaged engine `test_scenario` when no `games/<pack>` layout is found —
  `resolve_scenario_path_with_game_root` raises `FileNotFoundError` instead.
- `load_game_definition_for_scenario` no longer returns generic Red/Blue rules for
  arbitrary paths; only title packs recognised today (e.g. hexdemo under
  `hexdemo/scenarios/`) load title Python — otherwise `ValueError`.
- `load_game_definition` remains for **explicit** engine test / demo schedules only
  (not inferred from a scenario path).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .gamedef.builtin import (
    InterleavedTwoFactionGameDefinition,
    SequentialTwoFactionGameDefinition,
)
from .gamedef.protocol import GameDefinition


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


def load_game_definition_for_scenario(
    scenario_path: str | Path, *, schedule: str = "interleaved"
) -> GameDefinition:
    """
    Return the `hexengine.gamedef.protocol.GameDefinition` for the resolved scenario.

    When the scenario lives under `hexdemo/scenarios/`, loads definitions via
    `hexdemo.registry.build_game_definition` (see `hexdemo.game_config` for turn
    order and factions). Other paths raise `ValueError`.
    """
    if scenario_path_indicates_hexdemo_pack(scenario_path):
        ensure_hexdemo_package_import_path(scenario_path)
        from hexdemo.registry import build_game_definition

        key = (
            "sequential" if schedule.strip().lower() == "sequential" else "interleaved"
        )
        return build_game_definition(key)
    raise ValueError(
        "No title rules are registered for this scenario path "
        f"({scenario_path!r}). Place the scenario under a supported game pack "
        "(e.g. …/hexdemo/scenarios/…) or load rules explicitly."
    )


def load_game_definition(*, schedule: str = "interleaved") -> GameDefinition:
    """
    Select turn schedule for headless / server / client parity.

    `schedule` must match the value used by the WebSocket server and other clients.

    - `"interleaved"` — `hexengine.gamedef.builtin.InterleavedTwoFactionGameDefinition` (Red/Blue)
    - `"sequential"` — `hexengine.gamedef.builtin.SequentialTwoFactionGameDefinition` (Red/Blue)

    Not used when resolving rules from a game-pack scenario; see
    `load_game_definition_for_scenario`.
    """
    if schedule.strip().lower() == "sequential":
        return SequentialTwoFactionGameDefinition()
    return InterleavedTwoFactionGameDefinition()


def add_game_launch_arguments(parser: argparse.ArgumentParser) -> None:
    """Register scenario and schedule flags (shared by server CLIs)."""
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
    parser.add_argument(
        "--schedule",
        choices=("interleaved", "sequential"),
        default="interleaved",
        help="Turn schedule (must match server and other clients)",
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


_hexdemo_loaded_banner_printed: bool = False


def reset_hexdemo_loaded_banner_for_tests() -> None:
    """Allow banner to fire again (unit tests only)."""
    global _hexdemo_loaded_banner_printed
    _hexdemo_loaded_banner_printed = False


def scenario_path_indicates_hexdemo_pack(scenario_path: str | Path) -> bool:
    """
    True when `scenario.toml` lives under a `hexdemo/scenarios/` directory.

    Used to detect the bundled hexdemo pack regardless of repo root location.
    """
    parts = Path(scenario_path).resolve().parts
    for i, part in enumerate(parts):
        if i + 1 >= len(parts):
            break
        if part.casefold() == "hexdemo" and parts[i + 1].casefold() == "scenarios":
            return True
    return False


def ensure_hexdemo_package_import_path(scenario_path: str | Path) -> None:
    """
    Prepend `…/games` to `sys.path` when the scenario is under `hexdemo/scenarios`.

    Enables `import hexdemo` without a manual `PYTHONPATH` in the typical repo layout.
    """
    if not scenario_path_indicates_hexdemo_pack(scenario_path):
        return
    path = Path(scenario_path).resolve()
    # …/games/hexdemo/scenarios/<id>/scenario.toml
    games_dir = path.parent.parent.parent.parent
    if not (games_dir / "hexdemo").is_dir():
        return
    s = str(games_dir)
    if s not in sys.path:
        sys.path.insert(0, s)


def try_hexdemo_loaded_banner(scenario_path: str | Path) -> None:
    """
    Log hexdemo's welcome line once per process after authoritative scenario load.

    Delegates to `hexdemo.boot.print_loaded_banner` (`logging`) when importable.
    """
    global _hexdemo_loaded_banner_printed
    if _hexdemo_loaded_banner_printed:
        return
    if not scenario_path_indicates_hexdemo_pack(scenario_path):
        return
    ensure_hexdemo_package_import_path(scenario_path)
    try:
        from hexdemo.boot import print_loaded_banner
    except ImportError:
        return
    print_loaded_banner()
    _hexdemo_loaded_banner_printed = True
