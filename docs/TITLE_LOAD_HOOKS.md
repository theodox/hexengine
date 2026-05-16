# Title-load hooks and client arc

Pack integration for browser startup and server load is declared in `hexengine_pack.toml` under `[hooks.title_load]` and orchestrated by the **client title-load arc** (`hexengine.game.arcs.client_title_load`).

## Arc segments vs pack hooks

| Kind | Owner | Examples |
|------|--------|----------|
| **Arc segment** | Engine pipeline | `resolve_scenario`, `boot_local_server`, `connect_ws`, `ready` |
| **Pack hook** | Title module (manifest names module + callables) | `present_splash`, `run_setup`, `on_server_loaded` |

Only **splash** and **setup** segments invoke pack hooks today. See `games/hexdemo/hooks/title_load.py` and `games/hexdemo/resources/splash.html` for the reference pack.

## Current behavior (intentionally fault-tolerant)

Declaring `[hooks.title_load]` with `module` + `splash_html` **enables** title-load wiring; it does **not** assert that callables exist or succeed.

At runtime the engine generally **skips or continues** when:

- the hook module fails to import
- a named callable is missing or raises
- `splash_html` is missing under `resources/` (warning only)

This keeps headless tests, partial packs, and Pyodide import edge cases from hard-failing connect.

Callable names in TOML default to `present_splash`, `run_setup`, and `on_server_loaded` if omitted.

## Revisit: stricter contracts

Title-load is the first **manifest-driven** hook surface; it is intentionally fault-tolerant today (see above).

Broader plan — validation, stub templates, static typing, and aligning manifest hooks with `TitleHooks` — lives in **[`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md)**. That doc applies to **all** hook areas over time, not only title-load.

Until then, treat TOML as **“turn on this integration”**, not **“I have implemented every named callable.”**

## Related code

- Manifest parsing: `hexengine.game_packs.registry` (`PackTitleLoadHooks`)
- Hook dispatch: `hexengine.gameroot` (`run_title_load_splash`, `run_title_load_setup`, `try_pack_title_load_server`)
- Client arc: `hexengine.game.arcs.client_title_load`
- Hook types: `hexengine.gamedef.title_load` (`TitleLoadContext`, `TitleLoadResult`)
- DOM: `hexengine.game.title_load_ui`

## Multiplayer note

Each browser client runs the full connect arc independently; splash/setup hooks are **per client**. Server `on_server_loaded` is one-shot per hexserver process. Coordinating splash timing across players is out of scope until a server-driven or synced contract is designed.
