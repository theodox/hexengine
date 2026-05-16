# Hexdemo hooks

This folder is where **title policy** lives. The engine calls it through different wiring paths; this README is a working map (not exhaustive — it will grow with stricter contracts and templates; see `docs/PACK_HOOK_CONTRACTS.md`).

## Three lanes

| Lane | Modules here | How the engine reaches it |
|------|----------------|---------------------------|
| **`TitleHooks`** (in-match) | `movement.py`, `attack.py`, `ui.py`, `overlays.py` | `HexdemoGameDefinition.hooks` → `build_hooks()` in `__init__.py` |
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
MoveUnit / movement arc  →  MovementHook.*  →  hooks/movement.py  →  (ideally) ../movement_rules.py
Attack RPC               →  AttackHook.*     →  hooks/attack.py    →  ../combat.py
```

Hexdemo today:

| Rules (policy) | Hook adapters |
|----------------|---------------|
| `../combat.py` — CRT, retreat extension state | `attack.py`, parts of `movement.py` |
| `../movement_rules.py` — stub; future `legal_move_hexes`, budgets | `movement.py` (most movement policy lives here for now) |
| `../marker_rules.py` — `MarkerPlacementRule` factory | Injected on `GameServer`, not `TitleHooks` |

Keep **one coherent policy** in rules when it is reused (server validation + client preview + unit tests). Keep logic in `hooks/*.py` only while it is small and tied to a single hook slot.

`movement_rules.py` is explicitly **pure** until the engine delegates full legality (see `docs/engine_game_boundary_matrix.md` movement row). Until then, hooks answer slices (budget, ZoC, retreat); rules will eventually answer “all legal destination hexes” in one place.

Longer term, the engine may offer **composable rule pieces** (ZOC, terrain, morale, …) that titles assemble declaratively, with custom rules alongside — see `docs/RULE_COMPOSITION.md` (planning only; not implemented).

## `TitleHooks` modules (sketch)

| Module | Role | Wired via |
|--------|------|-----------|
| `movement.py` | Step cost, ZoC, retreat obligations, … | `@bind_title_hook(MovementHook.…)` |
| `attack.py` | Validate/resolve combat, CRT helpers | `@bind_title_hook(AttackHook.…)` |
| `ui.py` | Popups, inspect, interaction chrome | `@bind_title_hook(UIHook.…)` |
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

1. **Shared policy** — add or extend a **rules** module at pack root (`combat.py`, `movement_rules.py`, …): pure `GameState` in/out.
2. **In-match integration** — wire a **hook** in `hooks/*.py` with `bind_title_hook`; call the rules module from the hook body; ensure `build_hooks()` still assembles it.
3. **Connect / splash / lobby** — `title_load.py` or a future manifest table.
4. **Phase entry** — `turn_schedule.py` or `after_phase_transition` in `game_config.py`.

Optional future layout: `hexdemo/rules/` for policy modules and `hexdemo/hooks/` only as adapters — not required until `movement_rules` is real and wired.

## See also

- Pack overview: `../README.md`
- Policy stubs: `../movement_rules.py`, `../marker_rules.py`, `../combat.py`
- Boundary matrix (movement legality): `docs/engine_game_boundary_matrix.md`
- Engine hook authoring: `hexengine.hooks` package docstring
- Title-load detail: `docs/TITLE_LOAD_HOOKS.md`
- Contract roadmap: `docs/PACK_HOOK_CONTRACTS.md`
