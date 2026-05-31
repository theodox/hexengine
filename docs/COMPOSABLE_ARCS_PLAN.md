# Composable turn arcs — implementation plan

**Status:** design / planning. Successor track to [`ENGINE_BOUNDARY_2_PLAN.md`](ENGINE_BOUNDARY_2_PLAN.md); sibling (different axis) to [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md).

**One-line goal:** Reify the *implicit* arc state machines into a single **declared** model — a turn is a composition of **arcs**, an arc is a state machine over **segments** — so the engine drives arcs generically and never reads title-shaped gate strings.

---

## Why

`ENGINE_BOUNDARY_2` pushed combat *mutations* and *wire payloads* fully into the title, but left three engine-side readers of the same hexdemo gate strings (`combat_gate`, `retreat_obligations`, `advance`):

1. **Authoritative legality** — RPC prechecks in `authority_combat_cleanup` (`combat_gate == "awaiting_advance"`, …).
2. **Affordances** — `default_primary_actions_for_viewer` / `_dock_arc_for_viewer`.
3. **Phase-advance blocking** — `default_blocks_routine_phase_advance`.

These exist because the arc's transition logic (δ) is **not declared in one place** — each reader re-derives it from gate strings. The fix is structural: declare the state machine once; have legality, affordances, and blocking all read the *current segment* of that declared machine.

See [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) for the per-dimension boundary this plan finishes.

---

## Conceptual model (adopted)

### Arcs are reified state machines

An **arc** is a finite state machine that occupies part of a turn:

| FSM element | Arc model |
|-------------|-----------|
| States Q | **segments** |
| Alphabet Σ | action types / RPCs + internal events (e.g. "obligation cleared") |
| Transition δ | **declared** transition table (today: scattered across dispatch + hooks) |
| Guards | segment `owner` + `allowed_actions` |
| Output | `StateAction` lists (existing hook returns) |
| Terminal | arc completion → resume parent / advance schedule |

Two properties the design must preserve:

- **Rewindable.** Arc/segment state lives in the undoable `GameState`; transitions are `StateAction`s. The arc cursor must be snapshot-able and revertible (works under `LOAD_SNAPSHOT` / undo).
- **Hierarchical (pushdown).** An arc can **suspend** the current owner, insert a sub-arc for another faction (e.g. retreat), then **resume**. This already exists: the movement arc snapshots `TurnState` into its payload (`turn_state_to_movement_arc_snapshot`). So the system is a hierarchical state machine with a **suspend stack**, not a flat FSM.

### The segment triple

A **segment** is fully described by:

- **owner** — who may act (a faction, or none for engine/auto steps). Replaces direct `turn.current_faction` legality checks.
- **allowed_actions** — the RPC/input types legal in this segment. Drives both server legality and client affordances.
- **resolution locus** — where the segment resolves:
  - **server-authoritative** — persisted, gated, snapshot-able (today: `routine` / `retreat_gate` / `advance_gate`).
  - **client-local draft** — composed in the browser, commits as one RPC (today: the ad-hoc `attack_draft` / `retreat_path_draft` / `place_marker_draft` override in `effective_turn_dock_arc`).

Both existing server gates and existing client drafts are instances of this one shape. Making `resolution locus` a declared property lets the client stop special-casing draft strings and the server stop special-casing gate strings.

### Drafts are nested client-local sub-arcs, not guards

A **draft** (assembling a multi-step input — pick target → pick attackers → confirm — before one commit RPC) is a **nested client-local sub-arc**, not a guard on the parent transition. The roles differ by layer:

- A **guard** answers "may this transition fire?" and must be evaluable by the enforcer. For a server-authoritative transition the enforcer is the server, so guards stay **server-evaluable** (`owner`, `allowed_actions`, legality). Draft completeness (`confirm_enabled`) is client-only and not server-evaluable, so it must not live in the authority gate (the server validates the committed RPC regardless).
- A **guard admits the event; a draft produces the event.** The draft is input construction; its terminal transition emits the authoritative RPC into the parent server segment.

Model:

- **Entering** a draft sub-arc is gated by the parent segment's guard — the draft is offered only when its commit action is in the current segment's `allowed_actions` for this owner. (This replaces client gate-string reads like `_combat_gate_blocks_attack_planning_ui`: the draft is simply not enterable when `Attack` is not currently allowed.)
- **Internal validity** (eligible attackers, `confirm_enabled`) is the sub-arc's own terminal condition — client-local, not a server guard.
- **Committing** emits the RPC; the parent segment's guard plus server validation admits or rejects it.

This degrades gracefully: a single-click action has no draft (just an allowed action that commits immediately); a draft sub-arc appears only for multi-step composition.

### Composition operators

A title composes its turn from arcs using just **two** structural operators (the HSM primitives):

- **sequence** — arc then arc (e.g. Move-arc → Combat-arc; rotate factions). Replaces the flat `turn_order()` rota.
- **interrupt / suspend** — `interrupt(owner, sub_arc)`: pause current owner, run a sub-arc for another owner, resume. Generalizes movement `awaiting_interrupt` and the combat retreat/advance gates.

There is **no `conditional` operator** — conditionality is a property of *transitions*, not a structural primitive (resolved):

- A **transition** has a **trigger kind**: *external-event* (the segment's `owner` waits for an allowed action; the chosen RPC selects the edge) or **automatic** (an ownerless segment, `owner = none`, that the engine fires itself — already latent in the attack pipeline stages and phase auto-advance).
- A **transition** may carry a **guard**: a pure predicate over `GameState`. Guards cover both kinds of conditionality:
  - **User choice** (decline an attack, activate an ability) = an event-keyed transition — a segment with several allowed actions and one outgoing edge per chosen event. No new primitive; ability resolution can open an interrupt sub-arc.
  - **Pseudo-randomness** (weather, dice) = an *automatic* transition whose effect draws from the persisted `rng_log` (never live randomness) and writes the result into state; later transitions guard on that state. Most randomness needs **no graph branch at all** — it is an effect plus guards on later transitions; an actual fork is only needed when the *flow structure* differs by outcome (a guarded automatic transition, possibly into an interrupt sub-arc).

This keeps replay/undo deterministic for the same reason as the representation decision: randomness enters state only via a logged-RNG `StateAction`, so guards stay pure functions of state.

### Why not generators as the standard

Python coroutines map seductively onto arcs (`yield` a segment, resume on the next event; `yield from` is the interrupt/sub-arc operator; sequence is sequential code; `if` is conditional). But a generator's state is an opaque, suspended Python **frame**, which collides with the non-negotiable rewindable-state requirement:

- **Not serializable / rehydratable.** A live frame can't be put on the wire, into a snapshot, or rebuilt on server restart or client reconnect. Under Pyodide this is doubly true, and frame-pickling tricks are version-fragile (a serialized frame breaks when code changes).
- **Not reversible.** Frames step forward only; there is no backward step for undo.
- **Opaque to the engine.** The full segment graph can't be inspected without executing every branch — undercutting load-time validation and publishing structure to the client.
- **Two cursors.** A generator's resume point and the `StateAction`/undo history are two competing sources of "where are we."

This is equally true for **`send`-driven** generators: the `.send()` channel is only the input side and does nothing for serialization or rewind. Driving with inputs *is* the event-sourced form — the inputs become the log you must persist while the generator stays ephemeral — and it actually raises the bar, because every sent value must be reconstructable from the persisted log or replay diverges. The codebase already chose externalized state for exactly these reasons (the movement arc serializes `TurnState` into a payload rather than holding a frame).

Decision: the **persisted representation is declarative data** (a snapshot-able cursor + event log). A generator is permitted only as an optional authoring helper implemented as a **pure, deterministic, replayed reducer** over that log (re-created and fast-forwarded via logged events on each reconstruction), never as the stored source of truth.

---

## Authoring: composable from engine-provided pieces (no runtime fallback)

This adopts the [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md) philosophy on the *flow* axis:

- The engine ships **importable, tested arc/segment builders** (e.g. a `mandatory_retreat_then_optional_advance` combat arc, a `simple_phase` arc, an `igo_ugo` turn). Authors **import and compose** them in ordinary Python — no DSL, no interpreter.
- These pieces are **authoring scaffold, not a runtime fallback**. The engine core executes whatever arcs the title composed; it has no opinion to silently fall back to. (This is the resolution of `ENGINE_BOUNDARY_2_PLAN` open decision #4 — "engine defaults exist only as scaffold.")
- **Common patterns** live in a clearly separate, importable namespace (e.g. `hexengine.arcs.patterns` / a `hexkit`-style library) so importing them is explicit and greppable, never implicit.
- **Template projects** let a new title start from working, explicit arc compositions (copy-in), rather than inheriting hidden behavior.
- Missing/invalid declarations **fail loudly at pack load** (extend `validate_title_contract`), not silently — no fallbacks means validation does the safety work.

Open for further discussion (flagged, not yet specified): exact builder API, where the patterns library lives (submodule vs separate package vs template-only), and which existing catalog defaults graduate to importable builders vs are deleted. Keep pure transport/math defaults (snapshot, wire, schedule arithmetic); only title-shape-reading defaults must go.

This revises a `RULE_COMPOSITION.md` non-goal ("hooks and **arcs** stay [as fixed substrate]; composition feeds them"): arcs are **promoted to the composition unit** for turn flow. Hooks remain the integration layer that arcs' transitions call into.

---

## What this subsumes / removes

- The triplicated gate readers (legality / dock / blocking) collapse into "read current segment."
- Engine gate-string literals in `authority_combat_cleanup` prechecks (boundary item #1/#2) — gone.
- `ClearUnitRetreatObligation`'s hardcoded `combat_gate` removal — becomes a declared transition effect.
- The client `effective_turn_dock_arc` draft override — becomes an entry-guarded client-local sub-arc.
- `default_primary_actions_for_viewer` / `default_blocks_routine_phase_advance` gate string-matching — derived from the segment instead.

---

## Decisions adopted (from design discussion)

| # | Decision |
|---|----------|
| Scope | Go for the complete declarative model, not the minimal `TurnStep` gate. No back-compat constraints. |
| Ownership | `segment.owner` is the single "who may act" authority; `TurnState.current_faction` stays as the routine schedule cursor. The `is_retreat_fulfillment` special case dissolves into a segment whose owner is the obligated faction. |
| Defaults | Engine defaults that read title-shaped state are removed; replaced by importable scaffold + templates + loud load-time validation. |
| Vocabulary | Reuse existing **arc** / **segment** terms; do not invent a parallel concept. |
| Representation | The **persisted** arc state is declarative data — a snapshot-able cursor + event log — never a live object holding control-flow state. Generators (including `send`-driven coroutines) are **not** required and are **not** the source of truth; they are allowed only as an optional, deterministic, replayed authoring helper over the event log. See "Why not generators as the standard." |

### Cursor ownership: three layers (resolved)

"Where are we" is three concerns with distinct owners; the split works because the arc position lives inside the snapshotted/reverted `GameState`:

| Layer | Owner | Notes |
|-------|-------|-------|
| Segment graph + transition table (what the segments *are*) | **Title** (declared) | Static declaration; the engine never reads gate-string literals, only looks up declared segment metadata by id |
| Intra-arc position + suspend stack (which segment; which arcs are active/suspended) | **Engine** | Stored in `GameState`, advanced/reverted **only via `StateAction`s**, so it snapshots and undoes for free |
| Undo/redo history over `StateAction`s | **Engine** (ActionManager) | The "meta-cursor" across game history |

So "the intra-arc cursor is title-centric" means **title-declared graph, engine-stored position** — not title-private mutable state (which would re-break generic legality/affordance reads and snapshot/undo).

Consistency is automatic: undo reverts `GameState` and the embedded arc position + stack revert with it (undo across an arc boundary restores a pre-arc state); `LOAD_SNAPSHOT` restores the position and the engine resumes against the title's static graph. This is the consistency the generator/frame model could not provide.

**Suspend-stack depth:** default to **depth-1** (one optional suspended frame, not an unbounded stack) — covers every current case (combat retreat, movement interrupt), keeps stored state to a single slot, and preserves arc encapsulation/reuse. Unbounded nesting (interrupt-within-interrupt) is a future extension if a title needs reaction-to-reaction. Flattening the stack into one graph with explicit return edges is rejected: it breaks reusable-arc encapsulation.

### Wire shape: a published `current_segment` descriptor (resolved)

The wire replaces server-prebaked `primary_actions` and the `dock_arc` string with a direct **per-recipient projection of the current segment** on `StateUpdate`:

| Field | Role |
|-------|------|
| `kind` | title segment label (`routine` / `retreat_gate` / `advance_gate` / …); replaces `dock_arc` |
| `owner` | faction(s) that may act (a faction, a set for simultaneous turns, or none for an automatic segment) |
| `allowed_actions` | action types legal in this segment |
| `locus` | server-authoritative vs client-local (whether an action commits immediately or opens a draft sub-arc) |

Split of responsibilities:

- **Semantics from the descriptor; presentation from client title data.** The server publishes *what* is allowed; the client renders a button per `allowed_action`, looking up label/css/payload shape from the title's client data (existing `shell_ui` path) keyed by action type. The server stops building `primary_actions` rows.
- **Per-recipient already.** `StateUpdate` is built per viewer, so the descriptor is too — "am I the owner?" and any hidden-info redaction (omit an opponent's `allowed_actions`) come for free.
- **Authority preserved.** The descriptor is a pure projection of the declared segment + cursor, authored by the authoritative server and recomputed each update (no extra persisted state). The client renders it for *display*; the server still enforces legality on commit. This does not violate "client does not compute legality from raw title state" — the client reads a server-authored descriptor, not the title bucket.
- **Control layer vs detail.** The descriptor is the control layer ("what step, who acts, what's allowed"). Finer per-unit data that is not an action type (e.g. `retreat_obligations` — which units owe how many hexes, for highlighting) stays as its own per-viewer wire field populated by the title's movement hook.

### Builder API: context-manager builder over canonical data (resolved)

- **Canonical contract = typed declarative data** (segments + transitions; the cursor spec). The engine, load-time validator, wire projector, and snapshot all consume this **data**, never a builder.
- **Default authoring surface = a context-manager builder** (`with arc(...) as a: with a.segment(...) as s: ...`) that is a thin, side-effect-free **emitter** of that data. Chosen for readability of nested/interrupt-heavy arcs, programmatic/looped construction, discoverability, localized build-time errors, and a clean seam for imported patterns (`pattern.apply(a)`).
- **Guardrail:** the canonical data type stays **public and directly usable** — authors may handcraft or machine-generate the data (tests, generated tables), and the built spec can be serialized for snapshot tests / docs / review diffs. The builder must never be the *only* way to express an arc.
- **Sugar discipline:** apply the typed-friendly sugars (derive `allowed_actions` from transitions; `branch(...)` for automatic ownerless forks; `interrupt(...)` / `resume`). **No operator-overloading or decorator magic on the canonical path** (they fight pyright on `games/*`). Operator-overloading "prettiness" may be added **later as a strictly optional** layer that emits the same data — never required.
- **Effects attach** to transitions as references to existing `StateAction`-returning functions (e.g. `combat_transitions.follow_up_after_attack`, `combat_actions.*`); guards are pure `GameState` predicates.

## Open questions (resolve before/within early phases)

1. **Patterns home** — `hexengine.arcs.patterns` submodule vs separate package vs template-only copy-in. (Authoring-ergonomics decision; can be settled within Phase 6 — does not block Phase 0.)

---

## Phased rollout

Each phase keeps pytest green (`test_combat_hexdemo`, `test_combat_transitions`, `test_authority_arcs`, `test_network`, `test_turn_action_dock`, `test_hooks_contract`).

### Phase 0 — Spec and types (no behavior change)
- **[done] 0a** — Core spec types in `hexengine/arcs/spec.py`: `Owner` (tagged union: `OwnerScope.CURRENT`/`NO_OWNER`, explicit `Faction`, title-resolved `OwnerRef`), `Trigger` (`Event` / `AUTO`), `Target` (`Goto` / `Interrupt` / `FlowEnd.DONE`/`RESUME`), `ArcContext`, `Transition` (callable `guard`/`effect`), `Segment` (the triple; derives `allowed_actions` from `Event` triggers), and `Arc` with `validate()` (the seed of load-time validation). Spec is code; only the cursor (0b) is serialized. Tests in `tests/test_arc_spec.py`.
- **0b** — Define the snapshot-able **arc cursor** (segment id + one optional suspended frame, per the depth-1 decision) stored in `engine_state` and mutated via a `StateAction`, with revert support; unit-test undo/redo of the cursor alone.
- **0c** — Provide the **context-manager builder** that emits this data (thin, side-effect-free), plus the typed sugars (`branch`, `interrupt`/`resume`, derived `allowed_actions`); keep the data type public.

Notes: the **transition** type already carries trigger kind (external-event `Event` vs automatic/ownerless `AUTO`) + optional guard predicate over `GameState`; RNG-bearing effects draw from `rng_log`.

### Phase 1 — Generic arc runner (engine mechanism)
- One engine driver that, given a declared arc + cursor, resolves the current segment, gates RPCs by `owner` + `allowed_actions`, runs transition effects (`StateAction` lists), and advances/suspends/resumes.
- No title shapes read by the engine.

### Phase 2 — Combat arc as declaration (hexdemo)
- Re-express `combat_transitions` as a declared combat arc (`attack` → `retreat_gate` interrupt → `advance_gate`), using its existing FSM table as the source of truth.
- Route `CombatAdvance` / `CombatDisruptInsteadOfRetreat` / retreat fulfillment through the generic runner; delete the gate-string prechecks in `authority_combat_cleanup`.
- Fold `ClearUnitRetreatObligation`'s gate removal into a declared transition effect.

### Phase 3 — Movement arc as declaration
- Re-express stepwise movement + `awaiting_continue`/`awaiting_interrupt`/`PassMovementInterrupt` as a declared arc with an interrupt sub-arc. Unify engine-reserved arc state with the generic cursor.

### Phase 4 — Turn schedule as arc sequence
- Replace flat `turn_order()` with a declared sequence of arcs (Move-arc, Combat-arc, …). `schedule_index` → arc/segment cursor. `get_next_phase` derives from the sequence.
- Ownership legality everywhere reads `segment.owner`; remove direct `current_faction` gate checks and the `is_retreat_fulfillment` branch.

### Phase 5 — Affordances + client from the declared segment
- Publish the per-recipient `current_segment` descriptor (`kind` / `owner` / `allowed_actions` / `locus`) on `StateUpdate`; derive dock / `dock_arc` / allowed actions / phase-blocking from it.
- Split semantics vs presentation: the descriptor carries allowed action *types*; the client renders buttons by looking up label/css/payload from title client data (`shell_ui`) per action type. Keep `retreat_obligations`-style per-unit fields as separate title-populated wire data.
- Retire `default_primary_actions_for_viewer` / `default_blocks_routine_phase_advance` gate string-matching.
- Re-express the client `effective_turn_dock_arc` draft override as **entry-guarded client-local sub-arcs** (drafts enterable only when their commit action is in the current segment's `allowed_actions`); remove client gate-string reads (`_combat_gate_blocks_attack_planning_ui`).

### Phase 6 — Importable patterns + templates + validation
- Extract the common arcs (combat, simple phase, igo-ugo) into the importable patterns namespace; hexdemo imports them.
- Remove title-shape-reading engine defaults; add loud load-time validation that every segment declares owner + allowed_actions and every referenced arc/segment exists.
- Add/refresh a template project that composes a working turn from patterns.
- (Optional, deferrable) An operator-overloading "prettiness" layer that emits the same canonical data — strictly optional, never the canonical path.

### Phase 7 — Fan-out: fix legacy docs and comments
After implementation lands, sweep the repo for now-stale references and align them with the arc-FSM model:
- Docs: `engine_game_boundary_matrix.md`, `ENGINE_BOUNDARY_2_PLAN.md`, `PACK_HOOK_CONTRACTS.md`, `TITLE_AUTHORING.md`, `TURN_ACTION_DOCK_CONTRACT.md`, `RULE_COMPOSITION.md` (reconcile the revised non-goal), `SERVER_ARCHITECTURE.md`, `STATE_SYSTEM_SUMMARY.md`, `games/hexdemo/hooks/README.md`.
- Code comments / docstrings referencing the old gate-string flow, the "arcs vs schedule = separate layers" seam, `ENGINE_DEFAULT` fallbacks for combat, and the ad-hoc client draft override.
- Grep anchors: `combat_gate`, `awaiting_`, `dock_arc`, `ENGINE_DEFAULT`, "separate layer", "effective_turn_dock_arc".

---

## Out of scope
- Mid-session title/pack switching.
- A standalone rules/flow DSL or interpreter (composition is plain Python — see `RULE_COMPOSITION.md`).
- Client-side authority (arcs stay server-authoritative; client-local segments are draft-only).

---

## Success criteria
- One declared transition table per arc; the engine reads no title gate strings.
- Legality, affordances, and phase-blocking all derive from the current declared segment.
- Combat and movement arcs are declared FSMs driven by one generic runner.
- Turn schedule is a composition of arcs; ownership is segment-owned.
- Common arcs are importable scaffold; no title-shape-reading runtime fallbacks; missing declarations fail at load.
- Legacy docs/comments reconciled (Phase 7).
