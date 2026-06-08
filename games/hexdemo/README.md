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
| `hooks/` | Title policy adapters — see [`hooks/README.md`](hooks/README.md) (`TitleHooks`, title-load, turn schedule) |
| `hooks/title_load.py` | Splash/setup/server-log (`[hooks.title_load]` in manifest) |
| `presentation/` | Viewer copy (`dock.py`, `inform.py`, `interaction_messages.py`) |
| `segment_ui.py` | Segment `ui_mode` → presentation registry (`PRESENTATION_BY_UI_MODE`) |
| `arc_segment.py` | Project `current_segment` per viewer; `phase_advance_blocked` for auto-advance |
| `combat_rules.py` | `HexdemoCombatRules` / `BINDING` — CRT, validate, arc guards/effects, `attack_arc_effect` |
| `combat_outcome.py` | Post-attack `CombatOutcome` / `BucketPatch` builder |
| `combat_arc.py` | `combat_rules_binding_to_arc_spec` + owner resolver → `ArcHook.COMBAT_ARC` |
| `hooks/turn_action_dock.py` | Commit dock — `combat_gate_panel_actions` + End Phase + segment presentation |
| `combat_transitions.py` | Gate kind strings, phase-scoped bucket clear, attack-planning block reason |
| `combat_actions.py` | Pack-local cleanup state actions (disrupt, advance, retreat step) |
| `movement_rules.py` | Movement policy (`MovementRulesBinding`); `hooks/movement.py` adapts |
| `combat_planning.py` | Attack plan preview (shared by `hooks/attack` and tests) |
| `session_state.py` | Session-state reads (`bucket()`, retreat obligations, advance offer) |
| `turn_arc_schedule.py` | Turn arc registry builder (move/combat schedule slots) |
| `focus.py` | Suggested unit focus after state sync |
| `shell_ui.py` | Shell UI string keys for dock and previews |
| `constants.py` | `PACK_SESSION_STATE_KEY`, `HEXDEMO_FACTIONS` |
| `resources/splash.html` | HTML fragment for the client loading overlay |
| `resources/flags/` | Example faction flag SVGs (turn banner + unit art) |
| `resources/templates/` | HTML shells for phase banner, inspect popup, panels |
| `resources/ui.css` | Pack skin modifiers (including SEQUENCE draft steps) |
| `ui_markup.py` | Template render helpers + flag URLs (skinning tier 2–3; see `docs/SKINNING_AFFORDANCES_PLAN.md`) |
| `game_config.py` | **Match config** (`HexdemoMatchConfig`), schedule wrapper, `focus_unit_id_after_state_sync` |
| `registry.py` | `build_game_definition()` (uses `game_config`) |
| `engine_entry.py` | Manifest `load_game_definition` entry |
| `marker_rules.py` | Optional `MarkerPlacementRule` hook |

Movement and combat policy live in **`movement_rules.py`** and **`combat_rules.py`**; **`TitleHooks`** (`hooks/movement.py`, `hooks/attack.py`, `hooks/arcs.py`) are thin adapters. Attack resolution runs through the **combat arc `attack` segment** (`BINDING.attack_arc_effect`), not a separate engine handoff path. The server resolves rules through `GameDefinition.hooks` only.

## Zip packs

Zip the `hexdemo` folder so extracted paths still contain `hexdemo/scenarios/.../scenario.toml`; the banner and imports rely on that layout.
