# Engine / title charter

**Status:** normative target for pack authoring and engine refactors. The codebase may lag this document in places; prefer updating code toward the charter, or note exceptions here when migration is in progress.

**Audience:** title authors and engine maintainers.

**Related:** [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) (how-to), [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) (inventory), [`COMBAT_ARC_GRAPH_PLAN.md`](COMBAT_ARC_GRAPH_PLAN.md) (hexdemo combat graph work), [`archive/COMPOSABLE_ARCS_PLAN.md`](archive/COMPOSABLE_ARCS_PLAN.md) (arc runtime history).

---

## Purpose

This charter states **who owns what** between `hexengine` (authoritative server, wire, arc runner, rendering affordances) and a **title pack** (flow, rules, presentation content). It is the design north star for:

- what must stay out of title code (server internals, wire assembly),
- what titles must be able to read and reason about (arcs, segments, registries),
- when incomplete packs should **fail fast** vs when omitted features are **valid**.

---

## Design principles

1. **Titles do not own server mechanics.** The title supplies policy, declared flow, and presentation content. The engine owns authoritative state, arc cursors, RPC routing, undo, and projection to clients.

2. **Titles must be able to reason about overall game shape.** Arcs and segments frame match flow. Turn rota and overlay graphs are pack-local, readable artifacts (see [`games/hexdemo/arcs/README.md`](../games/hexdemo/arcs/README.md), [`games/hexdemo/combat/graph.py`](../games/hexdemo/combat/graph.py)).

3. **Titles own presentation content; the engine owns affordances.** Copy, templates, CSS keys, and segment skin metadata live in the pack. The engine provides generic lanes (dock panel, inform popup, map selection preview, interaction messages) and renders title-supplied DTOs.

4. **Explicit opt-in, solid reference patterns.** Incomplete wiring for a **declared** feature should fail at startup (contract validation). Omitted features are valid (e.g. no interaction). Common behaviors live in **reference packs or borrow-only pattern modules**, not as silent engine fallbacks shaped like hexdemo.

5. **Title-owned vocabulary.** Arc ids, segment ids, `ui_mode`, and `presentation_id` strings are free-form within a pack. The engine does not require names like `combat`, `attack`, or `awaiting_retreat`. Consistency is the title’s responsibility; the engine checks **registry completeness**, not semantics.

---

## Core mechanisms: modification vs interaction

Two interaction **families** frame hook and RPC design:

| Family | Meaning | Typical wire verb | Hook bundle (today → direction) |
|--------|---------|-------------------|----------------------------------|
| **Modification** | One entity’s state on the board changes (chiefly locomotion) | `MoveUnit` | `MovementHook` → locomotion / modification hooks |
| **Interaction** | Two or more parties; resolution may produce many follow-up changes | `Attack` (one kind among possible future kinds) | `AttackHook` → interaction hooks |

**Modification** is the hex-engine baseline: most titles need legal unit movement. **Interaction** is optional: a title may have no wargame combat, no `Attack` segment, and no interaction arc.

Follow-up moves (retreat, combat advance) are **modifications** authorized by an **interaction aftermath** arc segment, not a second interaction.

A third family, **board modification** (markers, terrain, placement), remains separate today (marker rules, placement hooks). It is not folded into movement hooks.

---

## Arc in control

**Authoritative flow is the arc cursor and active segment**, not parallel models:

| Concern | Source of truth |
|---------|-----------------|
| What actions are legal now? | Active segment `allowed_actions` and owner |
| End phase / advance turn | Segment allows `NextPhase`; routine schedule via **`TurnArcRegistry`** |
| Interaction commit | Segment accepts `Attack` (or future interaction action types) on the title’s declared arc |
| Aftermath moves | Overlay segments authorize `MoveUnit` with title guards |
| Auto-advance after modification | Modification hooks + segment blocking (e.g. `phase_advance_blocked`) |

Legacy **`StaticScheduleGameDefinition`** tables and **phase-name heuristics** (e.g. treating `"Combat"` in `turn.current_phase` as “attacks required”) are not the target model. For extension-key titles, **`TurnArcRegistry` is authoritative** for routine turn flow.

A **move-only title** is a registry of routine modification segments only — no overlay arc, no interaction — still fully arc-driven.

Display fields such as `turn.current_phase` on wire may remain for banners, but **must not drive legality** once migration is complete.

---

## ArcSpec in charge (E)

The engine discovers capabilities from the **`ArcSpec` the title registers**, not from engine-global segment or arc ids.

| Do | Don’t |
|----|--------|
| Find segments that accept `Event("Attack")` (or listed action types) on the registered interaction arc | Require segment id `attack` or arc id `combat` |
| Route RPCs through `submit_event` when the active segment allows the action type | Special-case title-shaped RPC lists in `GameServer` when the arc could gate |
| Use the arc id and graph the title supplied via `ArcHook` | Import pattern constants in authority modules |

Titles may name arcs `fighting`, segments `strike`, and `ui_mode` `awaiting_withdrawal` — consistent within the pack.

Optional future enhancement: explicit metadata on `ArcSpec` (e.g. interaction commit action types) for fast lookup — still **declared on the spec**, not hardcoded in the engine.

---

## Presentation keys (F)

**`ui_mode`, `presentation_id`, `inform_profile`, and related keys are free-form.** The engine:

- copies `ui_mode` from segments onto `current_segment`,
- invokes UI hooks with segment context,
- validates that every `ui_mode` used in declared arcs appears in the title’s **segment presentation registry** (when that contract is enabled).

The engine does **not** maintain a canonical list of mode names or interpret their meaning.

---

## Opt-in bundles and validation (B)

| Title declares | Expected behavior |
|----------------|-----------------|
| Nothing about interaction | No interaction arc, no `Attack` segments → **valid**. No attack hooks required. |
| Client sends `Attack` or interaction-aftermath RPCs with no matching segment | **Reject** as illegal for current segment (same as illegal move), not “title misconfigured.” |
| Interaction arc + `session_state_key` + full UI contract | **Fail at startup** if graph, binding, presentation registry, or turn registry is incomplete. |

**Incomplete** means **declared but broken**, not **did not declare wargame combat**.

Contract validation should not infer combat from phase **names** in a static turn table.

---

## Reference patterns, not engine runtime (C)

Graph shapes, schedule helpers, and interaction aftermath templates belong in **reference material** titles copy or import:

- [`games/hexdemo/`](../games/hexdemo/) — reference implementation,
- [`games/template/`](../games/template/) — minimal scaffold,
- future [`games/reference/`](../games/reference/) or sibling package if shared helpers grow.

**Rule:** `GameServer` and authority modules do **not** import pattern packages. Only the title’s hook and arc providers do.

The engine may retain:

- arc **runner** and **spec types**,
- generic **`Arc.validate`** and registry consistency checks,
- **builder DSL** that compiles to `Arc` without title semantics,
- **hook slot** definitions and wire routing.

The engine should **not** silently build title-shaped graphs (e.g. default movement arc from a combat-era pattern) unless the title opts in via hooks.

A **static four-phase rota** for prototypes is a **pattern that emits `TurnArcRegistry`**, not a second runtime `GameDefinition` class the server depends on.

---

## Responsibility split

### Title owns

- **`TurnArcRegistry`** and overlay **`ArcSpec`** graphs (routine + interaction).
- **Modification policy** (locomotion, retreat constraints, step cost) and **interaction policy** (validate/resolve, guards/effects on bindings).
- **Session-state conventions** under `session_state_key` (bucket keys are pack contracts).
- **Presentation registry** and content (`shell_ui`, templates, CSS, `presentation/`).
- **`TitleHooks`** wiring (`@bind_title_hook` adapters calling into rules modules).
- **Manifest title-load** hooks (`[hooks.title_load]`).
- **Phase-scoped cleanup** via `GameDefinition.after_phase_transition` when needed.

### Engine owns

- **Authoritative `GameState`**, undo, RNG log.
- **Arc cursor**, `submit_event`, routine vs overlay cursor restore.
- **RPC envelope** and stable core verbs (`MoveUnit`, `NextPhase`, …).
- **Segment projection** (`current_segment` on wire).
- **Presentation affordances** (merge DTOs → `StateUpdate`, `ui_popup`, previews).
- **Generic validation** (arc graph well-formedness, registry/UI consistency when enabled).

### Shared wire verbs (A)

- **`MoveUnit`** — core **modification** mechanism; titles configure when and how, not whether the engine understands locomotion.
- **`Attack`** — one **interaction** mechanism for wargame-style resolution; optional for the title.
- Additional verbs (markers, future interaction kinds) are added deliberately when multiple titles need the same mechanism.

---

## Author reading order (flow-centric)

| Order | Pack path | Question |
|-------|-----------|----------|
| 1 | [`arcs/turn_schedule.py`](../games/hexdemo/arcs/turn_schedule.py) | When does each faction act? |
| 2 | [`combat/graph.py`](../games/hexdemo/combat/graph.py) (if interaction) | What happens after interaction commit? |
| 3 | [`arcs/wiring.py`](../games/hexdemo/arcs/wiring.py) | How is flow exposed on `TitleHooks.arcs`? |
| 4 | `movement/rules.py`, `combat/rules.py` | Modification and interaction policy |
| 5 | [`ui/segment_registry.py`](../games/hexdemo/ui/segment_registry.py) | What does each `ui_mode` look like? |
| 6 | [`hooks/`](../games/hexdemo/hooks/) | Hook adapters only |

---

## Decision summary (A–F)

| Id | Decision |
|----|----------|
| **A** | **Modification** (`MoveUnit`) is core; **interaction** is optional. |
| **B** | Omitted interaction is valid; fail only on incomplete **opt-in** bundles. |
| **C** | Patterns live outside engine runtime; titles borrow explicitly. |
| **D** | **`TurnArcRegistry` + arc cursor** control turn flow; static schedule is a pattern only. |
| **E** | **`ArcSpec` in charge** — capabilities from segments and action types, not engine ids. |
| **F** | **Free-form** presentation keys; title ensures arc ↔ registry consistency. |

---

## Migration backlog (engine and hexdemo)

Work toward this charter may proceed in any order, but these are the main known gaps:

1. **Retire dual turn model in hexdemo** — single `TurnArcRegistry`; stop wrapping `StaticScheduleGameDefinition` for authoritative flow.
2. **Decouple authority from pattern ids** — remove `SEG_ATTACK` / `"combat"` requirements; discover interaction commit from `ArcSpec`.
3. **Generic RPC routing** — reduce dedicated `GameServer` branches for interaction-aftermath action types where the active segment can gate.
4. **Soften or remove phase-name contract heuristics** — do not require attack hooks based on schedule phase strings.
5. **Move pattern modules toward reference packs** — stop server bridge from building default title-shaped movement graphs silently.
6. **Strip client/engine hexdemo fallbacks** — CSS class prefixes, default coaching copy; use wire `presentation_id` and title `shell_ui`.
7. **Document terminology** — modification / interaction in [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) (hook renames are optional and later).

---

## Load path (reminder)

```text
scenario.toml → pack manifest → registry.build_game_definition()
  → HexdemoGameDefinition (hooks, game_data, lifecycle)
  → GameServer binds TitleHooks, validates contract, runs arc-controlled match
```

Title-load hooks are manifest-driven and **not** part of `TitleHooks`. See [`TITLE_AUTHORING.md` § Three ways title code is wired](TITLE_AUTHORING.md#high-level-three-ways-title-code-is-wired).

---

## When this charter and code disagree

1. Treat this document as the **intended boundary**.
2. File or implement refactors toward it.
3. If a temporary exception is required, add a one-line note under **Migration backlog** with the issue or PR link.
