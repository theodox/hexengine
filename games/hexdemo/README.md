# Hexdemo game pack

Authoritative layout: `scenarios/<id>/scenario.toml`, `resources/`, and Python title code in this package (`import hexdemo`).

## Importing the title package

Add the repository’s `games` directory to `PYTHONPATH` so `hexdemo` resolves:

```bash
# POSIX
export PYTHONPATH="/path/to/hexes/games:$PYTHONPATH"

# PowerShell
$env:PYTHONPATH = "D:\prj\hexes\games;$env:PYTHONPATH"
```

When you run `hexserver` (or start the local WebSocket server) with a scenario under `games/hexdemo/scenarios/…`, the engine prepends `games` to `sys.path` if needed and logs **`welcome to hexdemo`** once after load at INFO on the `hexdemo.boot` logger (see `boot.py`).

## Game definitions and turn order

**Configure the match** in `hexdemo.game_config`:

- `hexdemo.game_config.HexdemoMatchConfig` — factions, `schedule` (`interleaved` or
  `sequential`), `movement_budget`.
- `hexdemo.game_config.game_definition_from_config` — builds the engine
  `GameDefinition` from that config.

The CLI still selects schedule via `hexserver --schedule` / `Game(..., game_schedule=...)`,
which maps to registry keys; defaults for each key are produced by
`HexdemoMatchConfig.from_registry_key`.

- `hexdemo.registry.build_game_definition("interleaved")` — default demo schedule
- `hexdemo.registry.build_game_definition("sequential")` — matches `--schedule sequential`

Faction ids are **`confederate`** and **`union`** (see `hexdemo.constants.HEXDEMO_FACTIONS`); scenario `faction =` on units must use these strings.

When you run `hexserver` (or `start_servers`) with a scenario under `games/hexdemo/scenarios/`, the engine loads definitions via `load_game_definition_for_scenario` so join/turn order matches the title. Pass the same schedule to `Game(..., game_schedule=...)` as to `hexserver --schedule` when using sequential mode with an embedded local server.

## Layout (model package)

| Module | Purpose |
|--------|---------|
| `boot.py` | Console banner after authoritative load |
| `game_config.py` | **Match config** (`HexdemoMatchConfig`) and `GameDefinition` construction |
| `registry.py` | Named ids → `build_game_definition` (uses `game_config`) |
| `movement_rules.py` | Stubs for future `MovementRules` |
| `marker_rules.py` | Optional `MarkerPlacementRule` hook |

## Zip packs

Zip the `hexdemo` folder so extracted paths still contain `hexdemo/scenarios/.../scenario.toml`; the banner and imports rely on that layout.
