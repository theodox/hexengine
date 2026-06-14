# Pack-visible combat arc graph — plan

> **Archived — phases 1–3 shipped** (optional phase 4 tooling deferred). Author hub:
> [`TITLE_AUTHORING.md`](../TITLE_AUTHORING.md) § Interaction arc graph. Sibling archives:
> [`ENGINE_TITLE_CHARTER_PLAN.md`](ENGINE_TITLE_CHARTER_PLAN.md), [`COMPOSABLE_ARCS_PLAN.md`](COMPOSABLE_ARCS_PLAN.md),
> [`ENGINE_BOUNDARY_2_PLAN.md`](ENGINE_BOUNDARY_2_PLAN.md), [`TITLE_AUTHOR_INTERFACE_PLAN.md`](TITLE_AUTHOR_INTERFACE_PLAN.md).
> Index: [`README.md`](README.md).

**Status:** phases 1–3 done (hexdemo + docs + template stub); phase 4 (tooling) deferred.

**One-line goal:** Put the combat FSM where title authors look first — a pack module that builds the real `Arc` spec — so match flow shape is readable without opening `src/hexengine/authoring/patterns/combat.py`.

**Related:** [`TITLE_AUTHORING.md`](../TITLE_AUTHORING.md) (author hub). **Charter:** [`ENGINE_TITLE_CHARTER.md`](../ENGINE_TITLE_CHARTER.md). **Broader migration:** [`ENGINE_TITLE_CHARTER_PLAN.md`](ENGINE_TITLE_CHARTER_PLAN.md) (phase 0 includes this plan’s phase 3 docs).

**Related:** [`COMPOSABLE_ARCS_PLAN.md`](COMPOSABLE_ARCS_PLAN.md) (runtime model), [`TITLE_AUTHOR_INTERFACE_PLAN.md`](TITLE_AUTHOR_INTERFACE_PLAN.md) (rules vs hooks layering).

---

## Problem

Hooks are now easy to read: one `@bind_title_hook` adapter per slot, policy in `rules.py`. Combat flow is not.

Today hexdemo builds the graph in [`games/hexdemo/combat/graph.py`](../../games/hexdemo/combat/graph.py) and wraps it in [`combat/arc.py`](../../games/hexdemo/combat/arc.py). The engine still ships [`build_combat_cleanup_arc`](../../src/hexengine/authoring/patterns/combat.py) for template convenience and parity tests.

`combat/transitions.py` already documents gate *policy* well (state table in the module docstring). What is missing is a **visible graph construct** that corresponds 1:1 to `Arc.segments` and `Transition` edges.

---

## Goals

1. **Pack-first reading order** — `games/<pack>/combat/graph.py` (name TBD) is the file authors open to understand combat flow.
2. **Structural fidelity** — the visible construct compiles to the same `Arc` type the runner uses (`hexengine.arcs.spec`), not a parallel diagram that can drift.
3. **Policy separation** — graph module declares topology (segments, owners, `ui_mode`, triggers, gotos); `rules.py` supplies guards/effects; `transitions.py` supplies gate `ui_mode` strings.
4. **Hexdemo as reference** — template and docs point at hexdemo `graph.py`, not engine internals.
5. **No regression** — existing combat arc runner, contract validation, and segment UI tests stay green.

## Non-goals (this plan)

- YAML/JSON arc specs or a second symbolic graph language (unless phase 4 proves necessary).
- Moving CRT / `InteractionHook` paths (preview, validate, resolve) into the arc graph module.
- Rewriting turn schedule / routine phase arcs (separate readability pass).
- Forking cleanup subgraph semantics per title without strong justification (engine pattern remains the default for minimal titles).

---

## Target layout (hexdemo)

```text
games/hexdemo/combat/
  graph.py        ← builds Arc (the FSM) via authoring.builder (authoritative)
  arc.py          ← slim: ArcSpec wrapper (owner resolver, cache, SEG_* re-exports)
  rules.py        ← HexdemoCombatRules: guards, effects, attack_arc_effect
  transitions.py  ← gate ui_mode strings + phase-blocking policy table
  actions.py      ← state mutations called from binding effects
  outcome.py      ← CombatOutcome / bucket patch after attack
```

**Author question map (after change):**

| Question | Read first |
|----------|------------|
| What segments exist? What transitions? | `combat/graph.py` |
| When does a guard fire? What state changes? | `combat/rules.py` |
| Which `ui_mode` blocks End Phase / attack planning? | `combat/transitions.py` |
| How does this segment look in the UI? | `ui/segment_registry.py` |
| How is it wired into the server? | `arcs/wiring.py` |

---

## Proposed API split

Today `combat_rules_binding_to_arc_spec` combines graph build + binding validation + `ArcSpec` metadata. Split responsibilities:

| Function | Owns | Location |
|----------|------|----------|
| `build_hexdemo_combat_arc(effects, gates, *, attack_effect)` | `Arc` graph | **pack** `combat/graph.py` |
| `combat_rules_effects_adapter(binding)` | `CombatArcEffectsBinding` view of binding | engine `patterns/combat.py` (existing `_CombatRulesEffectsAdapter`, export renamed) |
| `combat_arc_to_spec(arc, *, owner_resolver, advance_move_detector)` | `ArcSpec` shell | engine `patterns/combat.py` or `arcs/runner.py` |
| `combat_rules_binding_to_arc_spec(...)` | convenience wrapper | engine — calls graph builder + `combat_arc_to_spec` (template default) |

Hexdemo path after refactor:

```python
# combat/graph.py — authoritative graph for this title
def build_hexdemo_combat_arc(effects, gates, *, attack_effect=None) -> Arc:
    with arc("combat", entry=SEG_CLASSIFY) as a:
        ...

# combat/arc.py — integration only
def build_hexdemo_combat_arc_spec() -> ArcSpec:
    effects = combat_rules_effects_adapter(BINDING)
    arc = build_hexdemo_combat_arc(
        effects,
        transitions.COMBAT_ARC_GATE_UI_MODES,
        attack_effect=BINDING.attack_arc_effect,
    )
    return combat_arc_to_spec(
        arc,
        owner_resolver=resolve_owner_ref,
        advance_move_detector=BINDING.detect_combat_advance_move,
    )
```

The builder block in `graph.py` should match today's `build_combat_cleanup_arc` body (same segment ids, owners, branches). Authors see the full FSM; hexdemo owns the reference graph.

---

## Engine pattern strategy

Two viable options — pick in phase 1 spike:

### Option A — Pack-owned graph, engine pattern as duplicate (short term)

- Copy `build_combat_cleanup_arc` body into hexdemo `graph.py`.
- Keep `build_combat_cleanup_arc` in engine for template / tests.
- **Parity test** (already exists): `test_hexdemo_combat_arc_matches_pattern` in [`tests/test_authoring_combat_pattern.py`](../../tests/test_authoring_combat_pattern.py) must stay green.

**Pros:** fastest path to pack visibility; no engine↔games import issues.  
**Cons:** two copies until consolidated.

### Option B — Engine exports graph builder, pack calls it (thin pack)

- Move graph body to `authoring/patterns/combat_cleanup_graph.py`.
- Hexdemo `graph.py` is a thin, commented wrapper calling the engine function.

**Pros:** single source of truth.  
**Cons:** graph still lives in `src/`; author must open engine file to customize topology (defeats primary goal unless they copy the module into the pack when forking).

**Recommendation:** **Option A for hexdemo** (pack-owned graph is the product). Option B only for **template** minimal titles that do not customize cleanup shape. Document: “copy `graph.py` from hexdemo when you need to read or change the FSM.”

Longer term, if drift hurts, extract shared graph body to engine and **generate or re-export into pack docs** — not replace pack ownership for hexdemo.

---

## Phases

### Phase 1 — Spike and API sketch (1 PR, no behavior change) ✅

**Deliverables:**

- [x] Add `combat_arc_to_spec(arc, ...)` to engine; `combat_rules_binding_to_arc_spec` delegates to it (refactor only).
- [x] Export `combat_rules_effects_adapter` (rename from `_CombatRulesEffectsAdapter`).
- [x] Draft `games/hexdemo/combat/graph.py` behind a feature flag or parallel build function; assert `arc == build_combat_cleanup_arc(...)` in a new test.
- [x] Module docstring at top of `graph.py`: mermaid or ASCII diagram + “policy lives in rules.py”.

**Exit criteria:** parity test passes; no hook or runner behavior change.

### Phase 2 — Hexdemo cutover (1 PR) ✅

**Deliverables:**

- [x] `build_hexdemo_combat_arc_spec` uses `graph.py` as the graph source.
- [x] Slim `arc.py`: owner resolver, spec cache, `SEG_*` re-exports (or re-export segment ids from `graph.py`).
- [x] Update [`games/hexdemo/hooks/README.md`](../../games/hexdemo/hooks/README.md) and [`games/hexdemo/README.md`](../../games/hexdemo/README.md) reading order.
- [x] Add `games/hexdemo/combat/README.md` (short): file map + link to `graph.py`.

**Exit criteria:** full test suite green; `test_hexdemo_combat_arc_matches_pattern` still passes (hexdemo graph ≡ engine pattern output).

### Phase 3 — Authoring docs and template (1 PR) ✅

**Deliverables:**

- [x] [`TITLE_AUTHORING.md`](../TITLE_AUTHORING.md): § [Interaction arc graph](../TITLE_AUTHORING.md#interaction-arc-graph) and § [Modification vs interaction](../TITLE_AUTHORING.md#modification-vs-interaction); pack reading order.
- [x] [`PACK_HOOK_CONTRACTS.md`](../PACK_HOOK_CONTRACTS.md): interaction arc author layout paths (`combat/graph.py`, `arcs/wiring.py`, …).
- [x] Template pack: stub [`games/template/combat/graph.py`](../../games/template/combat/graph.py) (comment outline + pointer to hexdemo); `build_template_combat_arc_spec` remains on engine convenience path in [`combat_arc.py`](../../games/template/combat_arc.py).

**Exit criteria:** a new author can answer “what happens after Attack?” from pack files only.

### Phase 4 — Optional tooling (follow-up)

**Deliverables:**

- [ ] `describe_arc(arc) -> str` in `hexengine.authoring` for debug/CI (segment list, edges, ui_modes).
- [ ] CLI or pytest helper: `pytest --describe-combat-arc` prints hexdemo graph (uses `describe_arc`).
- [ ] Evaluate symbolic `ArcGraphDeclaration` only if multiple titles need shared compile-time validation of graphs without copying builder blocks.

**Defer** unless customization demand appears.

---

## Testing strategy

| Test | Purpose |
|------|---------|
| `test_hexdemo_combat_arc_matches_pattern` | Graph parity with engine pattern (keep) |
| `test_hexdemo_gate_kinds_on_segments` | `ui_mode` on gate segments (keep) |
| New: `test_hexdemo_combat_graph_segment_ids` | Stable public segment ids exported from graph module |
| New: `test_combat_graph_validate` | `build_hexdemo_combat_arc(...).validate()` |
| Existing combat arc runner tests (`test_combat_arc_runner_*`, `test_authority_*`) | End-to-end regression |

No new tests that only assert comments or diagrams — structure must match `Arc` equality or validated topology.

---

## Documentation artifacts

**In `combat/graph.py` (required):**

- Entry segment and why (`classify` vs `attack`).
- Table: segment id → owner → allowed actions → `ui_mode` → binding guard/effect names (not implementations).
- Attack path one-liner: `Attack` event → `attack_arc_effect` → `classify`.

**In `combat/README.md` (phase 2, done):**

- Flow vs presentation split (link to TITLE_AUTHORING).
- Mermaid state diagram (same as plan discussion).

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Graph drift between hexdemo and engine pattern | Parity test in CI; engine pattern doc points to hexdemo as canonical |
| Authors edit graph without updating binding methods | `COMBAT_RULES_BINDING` contract check at startup; segment/guard naming table in `graph.py` |
| Duplicate `SEG_*` constants | Import segment ids from `hexengine.authoring.patterns.combat` in `graph.py` (stable public constants) |
| `combat/arc.py` re-export churn | Keep `SEG_*` and `build_combat_arc()` on `arc.py` for existing test imports |
| Increased pack file count | Justified by central product shape; README makes navigation explicit |

---

## Open decisions

1. **Module name:** `graph.py` vs `flow.py` vs `combat_arc_graph.py` — prefer `graph.py` (matches `Arc` vocabulary).
2. **Segment id exports:** stay on `arc.py` for back-compat or move to `graph.py`?
3. **Owner resolver placement:** keep `retreating_faction` / `resolve_owner_ref` on `arc.py` or move to `rules.py` as binding methods?
4. **When to delete engine `build_combat_cleanup_arc` body duplicate:** only if all packs own graphs; template may keep convenience wrapper indefinitely.

---

## Success criteria

A prospective title author can:

1. Open `games/hexdemo/combat/graph.py` and describe the combat FSM without reading `src/hexengine`.
2. Trace one transition (e.g. retreat step) from graph edge → binding method → `actions.py` mutation.
3. Customize a gate `ui_mode` knowing the three touchpoints: `transitions.py`, `graph.py` segment, `segment_registry.py`.

---

## Suggested first PR (Phase 1 + 2 combined if spike is trivial) — done

Shipped as combined phase 1–2 work:

1. Add `combat_arc_to_spec` + export effects adapter.
2. Add `games/hexdemo/combat/graph.py` with full builder block.
3. Switch `build_hexdemo_combat_arc_spec` to use it.
4. Update hexdemo README + hooks README.
5. Run full pytest suite.
