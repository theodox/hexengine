# Pack and title hook contracts (roadmap)

Long-term direction for **all** title integration hooks: clearer author intent, **early validation** (pack discovery, server startup, and static typing where possible), and less silent best-effort behavior.

Title-load is the first manifest-driven hook surface; gameplay hooks already use a separate, stricter Python model. This document is the umbrella for converging them over time.

## Two hook systems today

| System | How titles declare | Validation today | Typical failure mode |
|--------|-------------------|------------------|----------------------|
| **`TitleHooks`** (movement, attack, UI, …) | Python: `@bind_title_hook`, `assemble_title_hooks`, `GameDefinition.hooks` | Partial — `validate_title_contract` at `GameServer` startup (e.g. combat schedule requires attack hooks); `@hook` contract metadata in engine catalog | `HookContractError` when schedule and hooks disagree |
| **Manifest hooks** (`[hooks.title_load]`, future TOML tables) | `hexengine_pack.toml` names module + callables + resources | Minimal — enabling the block wires integration; missing callables/resources are skipped or logged | Connect/load continues; easy to ship an incomplete pack |

Gameplay hooks are **typed in Python** (`MovementHook`, `AttackHook`, `UIHook`, …) and wired without stringly dispatch at call sites. Manifest hooks are still **string names + tolerant runtime** (see [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md)).

## Target model (not fully implemented)

Authors should be able to answer, without reading engine internals:

1. **Which hooks does my pack implement?** (required vs optional vs engine default)
2. **What is each hook’s signature and when does it run?** (arc segment, server RPC, client-only, …)
3. **What fails if I get it wrong?** — prefer **fail at pack load / server start / typecheck**, not mid-match or silent skip.

Planned mechanisms (apply across **both** systems over time):

### 1. Explicit contracts

- **Required vs optional** per hook point (not inferred only from “table present” in TOML).
- Document **arc segment** (engine) vs **pack hook** (title) for client flows — same vocabulary as [`hexengine.game.arcs.client_title_load`](../src/hexengine/game/arcs/client_title_load.py).
- Extend `validate_title_contract` (or siblings) for more schedule/hook combinations, not only combat/attack.

### 2. Early validation (“compile-time” in the broad sense)

- **Static typing:** hook protocols and context/result dataclasses (`TitleLoadContext`, `AttackContext`, …); titles checked with pyright/mypy in CI.
- **Discovery time:** when parsing `hexengine_pack.toml` or resolving a scenario — verify module import, callable presence, resource files on disk.
- **Server startup:** strict checks before accepting joins (build on existing `validate_title_contract`).
- **Dev vs prod:** optional strict mode (loud failures) vs production tolerance during transition.

### 3. Pack templates and stubs

Scaffolding (e.g. `games/_template/` or `hexengine init-pack`) should ship:

- Commented `hexengine_pack.toml` marking **required** and **optional** hook keys
- **Stub functions** with correct signatures and docstrings (what to fill in, what may return `ENGINE_DEFAULT`)
- Placeholder resources (`splash.html`, etc.)

Hexdemo remains the reference implementation; the template is the minimal “fill the blanks” pack.

### 4. Manifest schema evolution

For TOML-driven hooks, prefer explicit tables over implicit defaults, for example:

```toml
# Illustrative — not implemented
[hooks.title_load]
module = "mytitle.boot"
required = ["splash", "setup"]   # validated at discovery
optional = ["server_loaded"]

[hooks.title_load.splash]
html = "splash.html"
callable = "present_splash"
```

Align naming and validation rules with `TitleHooks` contract sentinels (`REQUIRED`, `PRESET`, `SINGLE_DEFAULT`) in [`hexengine.hooks.internal`](../src/hexengine/hooks/internal/contracts.py) where it makes sense.

## Hook inventory (current surfaces)

| Area | Declaration | Entry / validation | Notes |
|------|-------------|-------------------|--------|
| Movement | `TitleHooks.movement` | Server movement arc; hook catalog | `MovementHook` enum + `bind_title_hook` |
| Attack | `TitleHooks.attack` | `authority_attack` pipeline; `validate_title_contract` if schedule has combat | Required callables when schedule implies combat |
| UI | `TitleHooks.ui` | Client/server UI hook points | Overlays, popups, etc. |
| Title-load (client) | `[hooks.title_load]` | Client title-load arc; tolerant dispatch in `gameroot` | See [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md) |
| Title-load (server) | same manifest | `try_pack_title_load_server` | One-shot log hook today |
| Game definition | `[python].entry_*` | Required for pack load | Already hard-required |

Future manifest tables (lobby, setup UI sync, asset packs) should follow the same contract story from the start.

## Composable rule sets (future)

Beyond hook **contracts**, titles should eventually assemble **rule sets** from engine-provided **composable pieces** (ZOC, terrain class, morale gates, …) plus custom rules where needed — declaratively where possible, in Python where not. Patterns are not clear enough to implement yet; see **[`RULE_COMPOSITION.md`](RULE_COMPOSITION.md)** for intent, open questions, and phased evolution. Hook and rules layers stay separate: composition is policy; hooks are when the engine invokes it.

## Phased rollout (suggested)

1. **Document and template** — template pack + stub modules; keep runtime tolerant.
2. **Discovery validation** — warnings/errors for manifest hooks and expanded `validate_title_contract`.
3. **CI typing** — pyright on `games/*` against engine hook protocols.
4. **Offline audit CLI** — static checks for packs that stay within hook/arc/rules-import boundaries (server admin / registry use); see [`PACK_TRUST_MODEL.md`](PACK_TRUST_MODEL.md#offline-audit-tooling-planned).
5. **Tighten runtime** — strict mode, then default strict for new packs.

## Related docs and code

- Composable rules (planning): [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md)
- Title-load detail: [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md)
- Hook authoring: [`src/hexengine/hooks/__init__.py`](../src/hexengine/hooks/__init__.py)
- Contract validation: [`src/hexengine/hooks/internal/contracts.py`](../src/hexengine/hooks/internal/contracts.py)
- Server arcs: [`src/hexengine/server/arcs/__init__.py`](../src/hexengine/server/arcs/__init__.py)
- Game definition protocol: [`src/hexengine/gamedef/protocol.py`](../src/hexengine/gamedef/protocol.py)
