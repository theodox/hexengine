# Hexdemo hooks

This folder is where **title policy** lives. The engine calls it through different wiring paths.

**Start:** [`docs/TITLE_AUTHORING.md`](../../../docs/TITLE_AUTHORING.md) (author hub). This README is a **pack-local map**; wire detail is in [`docs/PACK_HOOK_CONTRACTS.md`](../../../docs/PACK_HOOK_CONTRACTS.md) and [`docs/TURN_ACTION_DOCK_CONTRACT.md`](../../../docs/TURN_ACTION_DOCK_CONTRACT.md).

## Three lanes

| Lane | Modules here | How the engine reaches it |
|------|----------------|---------------------------|
| **`TitleHooks`** (in-match) | `movement.py`, `attack.py`, `ui.py`, `overlays.py`, `arcs.py` | `HexdemoGameDefinition.hooks` → `build_hooks()` in `__init__.py` |
| **Manifest title-load** | `title_load.py` | `hexengine_pack.toml` `[hooks.title_load]` + client connect arc (`SPLASH` / `SETUP` segments) |
| **Turn schedule** | `turn_schedule.py` | `HexdemoGameDefinition.after_phase_transition` (not `TitleHooks`) |

**Arc segments** (resolve scenario, boot local server, WebSocket, dismiss splash) are engine-owned in `hexengine.game.arcs.client_title_load`. Only the title-load **hooks** above are pack Python.

## Rules vs hooks

These are **layers**, not two different species of title code.

| | **Rules** (policy) | **Hooks** (integration) |
|--|-------------------|-------------------------|
| **Answers** | What is legal? What does movement cost? | When does the engine ask, and in what API shape? |
| **Style** | Pure functions: `GameState` (+ args) → values / sets / violations | Named slots on `TitleHooks`, manifest title-load, or server injectables |
| **Depends on** | State and title data only (no WebSocket, DOM, `GameServer`) | Arcs, RPC handlers, connect pipeline, phase callbacks |
| **Testing** | Direct tests on `GameState` | Often needs hook assembly or server host |
| **Opt out** | N/A — this *is* the title law when invoked | May return `ENGINE_DEFAULT` for engine catalog defaults |

**Healthy pattern:** hooks stay thin; they call into **rules** modules.

```text
MoveUnit / movement arc  →  MovementHook.*  →  hooks/movement.py  →  ../combat.py (retreat state)
Attack RPC               →  AttackHook.*     →  hooks/attack.py    →  ../combat.py
```

Hexdemo today:

| Rules (policy) | Hook adapters |
|----------------|---------------|
| `../combat.py` — CRT, retreat extension state | `attack.py`, `movement.py` |
| `../marker_rules.py` — `MarkerPlacementRule` factory | Injected on `GameServer`, not `TitleHooks` |

Keep **one coherent policy** in pack-root modules when it is reused (server validation + client preview + unit tests). Movement legality slices (budget, ZoC, retreat) live in `movement.py` for now; see `docs/engine_game_boundary_matrix.md` and `docs/RULE_COMPOSITION.md` for future delegation.

Longer term, the engine may offer **composable rule pieces** (ZOC, terrain, morale, …) that titles assemble declaratively, with custom rules alongside — see `docs/RULE_COMPOSITION.md` (planning only; not implemented).

## `TitleHooks` modules (sketch)

| Module | Role | Wired via |
|--------|------|-----------|
| `movement.py` | Step cost, ZoC, retreat obligations, … | `@bind_title_hook(MovementHook.…)` |
| `attack.py` | Validate/resolve combat, CRT helpers | `@bind_title_hook(AttackHook.…)` |
| `ui.py` | Banners, inspect (`POPUP_MESSAGE`), inform callouts (`INFORM_POPUP`) | `@bind_title_hook(UIHook.…)` |
| `../inform_popups.py` | `InformPopup` hook adapter | Used by `ui.inform_popup_for_viewer` |
| `../presentation/inform.py` | INFORM copy + TTL keyed by `inform_profile` + `reason` | Used by `inform_popups.py` |
| `turn_action_dock.py` | Commit dock — returns `TurnDockPanel` from `hexengine.authoring.present`; copy via [`segment_ui.py`](../segment_ui.py) + [`presentation/`](../presentation/) | `@bind_title_hook(UIHook.TURN_ACTION_DOCK_FOR_VIEWER)` |
| `segment_presentation.py` | `presentation_id` / `interaction_mode` on `current_segment` wire | `@bind_title_hook(UIHook.ENRICH_CURRENT_SEGMENT)` |
| `segment_ui_registry.py` | Exposes `PRESENTATION_BY_SEGMENT_KIND` for P5 load-time validation | `@bind_title_hook(UIHook.SEGMENT_PRESENTATION_REGISTRY)` |
| `arcs.py` | Turn arc registry + combat arc declarations | `@bind_title_hook(ArcHook.…)` |
| `markers.py` | Place-marker map-selection preview | `@bind_title_hook(UIHook.PLACE_MARKER_PREVIEW)` |
| `../ui_markup.py` | HTML templates + flag URLs (tier 2–3; `hexengine.ui.display`) | Imported by `ui.py`, `turn_action_dock.py` |
| `../resources/templates/` | `phase_banner.html`, `unit_inspect.html`, `dock_gate.html` | Loaded by `ui_markup` |
| `../resources/flags/` | Example faction SVGs (banner `<img>`, optional `unit_graphics`) | See `flags/README.md` |
| `overlays.py` | Map overlay glyphs | UI hooks |

Implementations may return `hexengine.hooks.ENGINE_DEFAULT` to defer to engine catalog defaults. Combat schedules that include an attack/combat phase need `validate_attack` and `resolve_attack` present (see `validate_title_contract`).

## Manifest title-load (`title_load.py`)

Declared in `hexengine_pack.toml`:

- `present_splash(html)` — client; HTML from `resources/splash.html`
- `run_setup(ctx) -> TitleLoadResult` — client; v1 always continues connect
- `on_server_loaded()` — server; one-shot after authoritative pack load

Today the engine is **fault-tolerant** if a callable is missing; future packs should treat manifest keys as explicit contracts (`docs/TITLE_LOAD_HOOKS.md`).

## Turn schedule (`turn_schedule.py`)

Callbacks when the committed turn enters a phase (e.g. `before_union_move`). Extend here for round-start effects that are not movement/attack/UI hook points.

## Adding title behavior

1. **Shared policy** — add or extend a pack-root module (`combat.py`, …): pure `GameState` in/out.
2. **In-match integration** — wire a **hook** in `hooks/*.py` with `bind_title_hook`; call the rules module from the hook body; ensure `build_hooks()` still assembles it.
3. **Connect / splash / lobby** — `title_load.py` or a future manifest table.
4. **Phase entry** — `turn_schedule.py` or `after_phase_transition` in `game_config.py`.

Optional future layout: `hexdemo/rules/` for policy modules and `hexdemo/hooks/` only as adapters.

## See also

- Author hub: [`docs/TITLE_AUTHORING.md`](../../../docs/TITLE_AUTHORING.md)
- Pack overview: `../README.md`
- Policy modules: `../marker_rules.py`, `../combat.py`
- Boundary matrix (movement legality): `docs/engine_game_boundary_matrix.md`
- Engine hook authoring: `hexengine.hooks` package docstring
- Title-load detail: `docs/TITLE_LOAD_HOOKS.md`
- Contract roadmap: `docs/PACK_HOOK_CONTRACTS.md`
