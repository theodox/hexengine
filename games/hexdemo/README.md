# Hexdemo game pack

Authoritative layout: `scenarios/<id>/scenario.toml`, `resources/`, and Python title code in this package (`import hexdemo`).

**Title authoring:** [`docs/TITLE_AUTHORING.md`](../../docs/TITLE_AUTHORING.md) (start here — summaries + API index). This pack is the reference implementation cited there.

**Also:** [`docs/SKINNING_AFFORDANCES_PLAN.md`](../../docs/SKINNING_AFFORDANCES_PLAN.md) (roadmap/status), [`docs/SKINNING_CLIENT_INVENTORY.md`](../../docs/SKINNING_CLIENT_INVENTORY.md) (client modules).

## Importing the title package

Add the repository’s `games` directory to `PYTHONPATH` so `hexdemo` resolves:

```bash
# POSIX
export PYTHONPATH="/path/to/hexes/games:$PYTHONPATH"

# PowerShell
$env:PYTHONPATH = "D:\prj\hexes\games;$env:PYTHONPATH"
```

When you run `hexserver` (or start the local WebSocket server) with a scenario under `games/hexdemo/scenarios/…`, the engine prepends `games` to `sys.path` if needed. Title-load hooks in `hexengine_pack.toml` (`[hooks.title_load]`) drive:

- **Browser splash** — `resources/splash.html` injected during the client title-load arc (`SPLASH` segment) via `hooks.title_load.present_splash`.
- **Setup (v1)** — `hooks.title_load.run_setup` on the `SETUP` segment; returns immediately (`continue_connect=True`); reserved for future pre-game UI.
- **Server log** — `hooks.title_load.on_server_loaded` logs **`welcome to hexdemo`** once at INFO after authoritative load.

## Game definitions and turn order

**Configure the match** in `hexdemo.game_config`:

- `hexdemo.game_config.HexdemoMatchConfig` — factions and `movement_budget`.
- `hexdemo.game_config.hexdemo_four_phase_entries` / `game_definition_from_config` — define the single static rota (Union/Confederate Move/Combat) wrapped by `HexdemoGameDefinition`.

The manifest entry `hexdemo.engine_entry.load_game_definition()` returns that definition; the engine does not pass a schedule from the CLI.

- `hexdemo.registry.build_game_definition()` — same as the manifest entry (convenience for tests).

Faction ids are **`confederate`** and **`union`** (see `hexdemo.constants.HEXDEMO_FACTIONS`); scenario `faction =` on units must use these strings.

When you run `hexserver` (or `start_servers`) with a scenario under `games/hexdemo/scenarios/`, the engine loads definitions via `load_game_definition_for_scenario(scenario_path)` so join/turn order matches the title. The browser uses `StateUpdate.turn_rules` from the server for manual advance and previews.

## Layout (model package)

| Path | Purpose |
|------|---------|
| `hooks/` | Title policy — see [`hooks/README.md`](hooks/README.md) (`TitleHooks`, title-load, turn schedule) |
| `hooks/title_load.py` | Splash/setup/server-log (`[hooks.title_load]` in manifest) |
| `hooks/turn_schedule.py` | Phase-entry callbacks from `HexdemoGameDefinition` |
| `resources/splash.html` | HTML fragment for the client loading overlay |
| `resources/flags/` | Example faction flag SVGs (turn banner + unit art) |
| `resources/templates/` | HTML shells for phase banner, inspect popup, panels |
| `ui_markup.py` | Template render helpers + flag URLs (skinning tier 2–3; see `docs/SKINNING_AFFORDANCES_PLAN.md`) |
| `game_config.py` | **Match config** (`HexdemoMatchConfig`) and `GameDefinition` construction |
| `registry.py` | `build_game_definition()` (uses `game_config`) |
| `engine_entry.py` | Manifest `load_game_definition` entry |
| `movement_rules.py` | Stubs for future `MovementRules` |
| `marker_rules.py` | Optional `MarkerPlacementRule` hook |

## Zip packs

Zip the `hexdemo` folder so extracted paths still contain `hexdemo/scenarios/.../scenario.toml`; the banner and imports rely on that layout.
