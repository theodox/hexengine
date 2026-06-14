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
- `hexdemo.game_config.game_definition_from_config` — builds `HexdemoGameDefinition`.

**Turn rota (when each faction acts):** edit [`arcs/turn_schedule.py`](arcs/turn_schedule.py) — `build_hexdemo_turn_arc_registry` is authoritative; wired via [`arcs/wiring.py`](arcs/wiring.py).

The manifest entry `hexdemo.registry.build_game_definition()` returns that definition; the engine does not pass a schedule from the CLI.

- `hexdemo.registry.build_game_definition()` — manifest entry callable.

Faction ids are **`confederate`** and **`union`** (see `hexdemo.constants.HEXDEMO_FACTIONS`); scenario `faction =` on units must use these strings.

When you run `hexserver` (or `start_servers`) with a scenario under `games/hexdemo/scenarios/`, the engine loads definitions via `load_game_definition_for_scenario(scenario_path)` so join/turn order matches the title. The browser uses `StateUpdate.turn_rules` from the server for manual advance and previews.

## Layout (model package)

| Path | Purpose |
|------|---------|
| `hooks/` | Title policy adapters — see [`hooks/README.md`](hooks/README.md) (`TitleHooks`, title-load, turn schedule) |
| `hooks/title_load.py` | Splash/setup/server-log (`[hooks.title_load]` in manifest) |
| `presentation/` | Viewer copy (`dock.py`, `inform.py`, `interaction_messages.py`) |
| `ui/segment_registry.py` | Segment `ui_mode` → presentation registry (`PRESENTATION_BY_UI_MODE`) |
| `arcs/` | Turn schedule, segment helpers, `ArcHook` wiring — see [`arcs/README.md`](arcs/README.md) |
| `combat/graph.py` | **Combat arc FSM** — read first; builds `Arc` via `authoring.builder` |
| `combat/rules.py` | `HexdemoCombatRules` / `BINDING` — CRT, validate, arc guards/effects, `attack_arc_effect` |
| `combat/outcome.py` | Post-attack `CombatOutcome` / `BucketPatch` builder |
| `combat/arc.py` | `ArcSpec` wrapper (owner resolver); wired via `arcs/wiring.py` |
| `hooks/turn_action_dock.py` | Commit dock — `combat_gate_panel_actions` + End Phase + segment presentation |
| `combat/transitions.py` | Gate `ui_mode` strings, phase-scoped session-state clear, attack-planning block reason |
| `combat/actions.py` | Pack-local cleanup state actions (disrupt, advance, retreat step) |
| `movement/rules.py` | Movement policy (`MovementRulesBinding`); `hooks/modification.py` adapts |
| `movement/retreat_preview.py` | Retreat path map-selection preview |
| `combat/planning.py` | Attack plan preview (shared by `hooks/interaction` and tests) |
| `state/session_state.py` | Session-state reads (`bucket()`, retreat obligations, advance offer) |
| `arcs/segment.py` | Project `current_segment` per viewer; `phase_advance_blocked` for auto-advance |
| `ui/focus.py` | Suggested unit focus after state sync |
| `ui/markup.py` | Template render helpers + flag URLs (skinning tier 2–3) |
| `ui/previews/place_marker.py` | Place-marker map-selection preview |
| `ui/marker_rules.py` | Optional `MarkerPlacementRule` hook |
| `constants.py` | `PACK_SESSION_STATE_KEY`, `HEXDEMO_FACTIONS` |
| `resources/splash.html` | HTML fragment for the client loading overlay |
| `resources/flags/` | Example faction flag SVGs (turn banner + unit art) |
| `resources/templates/` | HTML shells for phase banner, inspect popup, panels |
| `resources/ui.css` | Pack skin modifiers (including SEQUENCE draft steps) |
| `game_config.py` | **Match config** (`HexdemoMatchConfig`), lifecycle hooks, `focus_unit_id_after_state_sync` |
| `registry.py` | Manifest `build_game_definition()` (uses `game_config`) |

Movement and combat policy live in **`movement/`** and **`combat/`**; match flow graphs and **`ArcHook`** wiring live in **`arcs/`** and **`combat/graph.py`**. **`TitleHooks`** adapters are in **`hooks/`** (`modification.py`, `interaction.py`, `ui.py`, …). Attack resolution runs through the **combat arc `attack` segment** (`BINDING.attack_arc_effect`), not a separate engine handoff path.

## Zip packs

Zip the `hexdemo` folder so extracted paths still contain `hexdemo/scenarios/.../scenario.toml`; the banner and imports rely on that layout.
