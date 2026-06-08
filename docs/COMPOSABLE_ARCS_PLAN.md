# Composable turn arcs — implementation plan

**Status:** design / planning. Successor track to [`ENGINE_BOUNDARY_2_PLAN.md`](ENGINE_BOUNDARY_2_PLAN.md); sibling (different axis) to [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md).

**One-line goal:** Reify the *implicit* arc state machines into a single **declared** model — a turn is a composition of **arcs**, an arc is a state machine over **segments** — so the engine drives arcs generically and never reads title-shaped gate strings.

---

## Why

`ENGINE_BOUNDARY_2` pushed combat *mutations* and *wire payloads* fully into the title, but left three engine-side readers of the same hexdemo gate strings (`combat_gate`, `retreat_obligations`, `advance`):

1. **Authoritative legality** — RPC prechecks in `authority_combat_cleanup` (`combat_gate == "awaiting_advance"`, …).
2. **Affordances** — turn action dock skin (`presentation_id` from title `ENRICH_CURRENT_SEGMENT` + segment registry; engine catalog does not infer gate skins without `current_segment`).
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
| Terminal | arc completion → cursor cleared; schedule picks the next arc from `GameState` |

Two properties the design must preserve:

- **Rewindable.** Arc/segment state lives in the undoable `GameState`; transitions are `StateAction`s. The arc cursor must be snapshot-able and revertible (works under `LOAD_SNAPSHOT` / undo).
- **Hierarchical *within* an arc (pushdown, depth-1).** An arc can **suspend** to an in-arc sub-flow (e.g. a retreat gate owned by another faction), then **resume** — all inside the same arc. Cross-faction steps are just segments with a different `owner`, not a separate arc. Across arc *boundaries* the structure is flat: see "Arc boundaries are clean."

### The segment triple

A **segment** is fully described by:

- **owner** — who may act (a faction, or none for engine/auto steps). Replaces direct `turn.current_faction` legality checks.
- **allowed_actions** — the RPC/input types legal in this segment. Drives both server legality and client affordances.
- **resolution locus** — where the segment resolves:
  - **server-authoritative** — persisted, gated, snapshot-able (today: `routine` / `retreat_gate` / `advance_gate`).
  - **client-local draft** — composed in the browser, commits as one RPC (today: the ad-hoc `attack_draft` / `retreat_path_draft` / `place_marker_draft` override in `effective_turn_dock_presentation_id`).

Both existing server gates and existing client drafts are instances of this one shape. Making `resolution locus` a declared property lets the client stop special-casing draft strings and the server stop special-casing gate strings.

### Drafts are nested client-local sub-arcs, not guards

**Adopted invariant:** [`TURN_ACTION_DOCK_CONTRACT.md` § Draft locus](TURN_ACTION_DOCK_CONTRACT.md#draft-locus-invariant) — drafts are client-local until commit; preview consults per snapshot; commit authorizes.

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
- **interrupt / suspend** — *within one arc*, suspend to an in-arc sub-flow and resume at a named in-arc segment (depth-1). Generalizes movement `awaiting_interrupt` and the combat retreat/advance gates. The resume target is always a segment of the same arc — interrupt never crosses an arc boundary (see "Arc boundaries are clean").

There is **no `conditional` operator** — conditionality is a property of *transitions*, not a structural primitive (resolved):

- A **transition** has a **trigger kind**: *external-event* (the segment's `owner` waits for an allowed action; the chosen RPC selects the edge) or **automatic** (an ownerless segment, `owner = none`, that the engine fires itself — already latent in the attack pipeline stages and phase auto-advance).
- A **transition** may carry a **guard**: a pure predicate over `GameState`. Guards cover both kinds of conditionality:
  - **User choice** (decline an attack, activate an ability) = an event-keyed transition — a segment with several allowed actions and one outgoing edge per chosen event. No new primitive; ability resolution can open an interrupt sub-arc.
  - **Pseudo-randomness** (weather, dice) = an *automatic* transition whose effect draws from the persisted `rng_log` (never live randomness) and writes the result into state; later transitions guard on that state. Most randomness needs **no graph branch at all** — it is an effect plus guards on later transitions; an actual fork is only needed when the *flow structure* differs by outcome (a guarded automatic transition, possibly into an interrupt sub-arc).

This keeps replay/undo deterministic for the same reason as the representation decision: randomness enters state only via a logged-RNG `StateAction`, so guards stay pure functions of state.

### Prompt segments

A **prompt segment** is a server-authoritative arc segment that narrows `allowed_actions` until the player resolves a **player prompt** (see [`TURN_ACTION_DOCK_CONTRACT.md` § Player prompts](TURN_ACTION_DOCK_CONTRACT.md#player-prompts)). Routine turn actions (move, end phase, etc.) stay illegal until the prompt is cleared.

Same shape as combat **gate** segments (`retreat_gate`, `advance_gate`) but the name is UX-neutral: season events, scenario beats, and combat obligations all use **interrupt** plus narrowed `allowed_actions`, not a separate mechanism.

Typical authoring:

- **Enter** via automatic transition when title script fires (phase entry, bucket flag, arc effect).
- **`owner`** — faction that must acknowledge, or per-viewer policy composed in the dock hook.
- **`allowed_actions`** — only acknowledge / branch RPCs (e.g. `AcknowledgeEvent`).
- **Exit** on DECIDE commit: clear prompt state in `title_state`, resume the suspended segment or advance the cursor.
- **Not a draft** — no client-local SELECT sub-arc; validity is server-side on commit.

In title docs, prefer **prompt segment** for narrative or scripted interrupts. Reserve **gate** for segments whose segment kind or `dock_arc` is combat-shaped (`retreat_gate`, `advance_gate`) unless you explicitly mean this segment shape.

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
- The client `effective_turn_dock_presentation_id` draft override — becomes an entry-guarded client-local sub-arc.
- `default_primary_actions_for_viewer` / pre-segment gate action string-matching in the engine dock catalog — removed; skin and rows derive from `current_segment` (titles bind `ENRICH_CURRENT_SEGMENT` for gate modes).

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

### Arc boundaries are clean (resolved)

Arcs are **distinct, self-contained units**: nothing carries across an arc boundary except the resulting `GameState`, which is what terminates the previous arc. Concretely:

- The cursor tracks **exactly one active arc** at a time, plus that arc's optional intra-arc depth-1 suspend frame. There is **no cross-arc suspend stack** and no "parent arc" waiting to resume.
- **Suspend/resume is strictly intra-arc.** The suspended frame stores an in-arc resume segment id only (never an arc id), and `interrupt` resume targets are validated against the same arc's segments. Structurally a frame cannot point into another arc.
- **Arc completion clears the whole cursor** (`SetArcCursor(None)`); any suspend frame dies with it. The **schedule** then selects the next arc purely from `GameState` (the `sequence` operator is "pick the next arc from state," not "resume a suspended parent"). So undo across an arc boundary restores a clean pre-arc state with no dangling frame.
- Different-faction participation inside an arc (retreat, reaction) is expressed via per-segment `owner`, **not** by nesting a separate arc.

This keeps arcs reusable and composable: an arc's behavior depends only on the `GameState` it starts from, never on hidden carryover from whatever ran before it. (Already true in the 0a spec + 0b cursor; recorded here so Phases 3–4 don't reintroduce cross-arc carryover.)

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
- **Effects attach** to transitions as references to existing `StateAction`-returning functions (e.g. `combat_rules.BINDING` effect methods delegating to `combat_actions.*`); guards are pure predicates over `ArcContext` / `GameState`.

## Open questions (resolve before/within early phases)

1. **Patterns home** — **`hexengine.authoring`** (`patterns/`, `builder`, `validate` as siblings). Runtime must not import patterns; see Phase 6 import boundary.

---

## Phased rollout

Each phase keeps pytest green (`test_combat_hexdemo`, `test_combat_transitions`, `test_authority_arcs`, `test_network`, `test_turn_action_dock`, `test_hooks_contract`).

### Phase 0 — Spec and types (no behavior change)
- **[done] 0a** — Core spec types in `hexengine/arcs/spec.py`: `Owner` (tagged union: `OwnerScope.CURRENT`/`NO_OWNER`, explicit `Faction`, title-resolved `OwnerRef`), `Trigger` (`Event` / `AUTO`), `Target` (`Goto` / `Interrupt` / `FlowEnd.DONE`/`RESUME`), `ArcContext`, `Transition` (callable `guard`/`effect`), `Segment` (the triple; derives `allowed_actions` from `Event` triggers), and `Arc` with `validate()` (the seed of load-time validation). Spec is code; only the cursor (0b) is serialized. Tests in `tests/test_arc_spec.py`.
- **[done] 0b** — Snapshot-able **arc cursor** in `hexengine/arcs/cursor.py`: `ArcCursor` (arc id + segment id + one optional depth-1 `SuspendedFrame`) with pure transitions (`advanced_to`/`suspended_into`/`resumed`), JSON-safe `cursor_to_snapshot`/`cursor_from_snapshot`, engine-state helpers (`read_arc_cursor`/`with_arc_cursor` under reserved key `hexengine_arc_cursor`), and the `SetArcCursor` `StateAction` (undo restores the exact prior cursor entry, including the no-cursor boundary). Undo/redo of the cursor alone covered in `tests/test_arc_cursor.py`.
- **[done] 0c** — Context-manager builder in `hexengine/arcs/builder.py`: `arc(id)` / `a.segment(id, owner=, kind=)` blocks, `s.on(event, ...)` / `s.auto(...)` with keyword targets (`goto` / `done` / `resume` / `interrupt`+`resume_at`), `branch`/`auto_branch`+`case` for guarded fan-out, entry defaults to the first segment, and `build()` returns a validated `Arc`. Thin and side-effect-free — emits the canonical spec exactly (asserted by an equality test) with no operator overloading; `allowed_actions` is derived, never declared. Worked combat-arc example + sugar/validation tests in `tests/test_arc_builder.py`. **Phase 0 complete.**

Notes: the **transition** type already carries trigger kind (external-event `Event` vs automatic/ownerless `AUTO`) + optional guard predicate over `GameState`; RNG-bearing effects draw from `rng_log`.

### Phase 1 — Generic arc runner (engine mechanism) — **[done]**
- One engine driver that, given a declared arc + cursor, resolves the current segment, gates RPCs by `owner` + `allowed_actions`, runs transition effects (`StateAction` lists), and advances/suspends/resumes.
- No title shapes read by the engine.

Implemented in `hexengine/arcs/runner.py`:
- `submit_event(arc, sink, action_type=, actor=, params=, resolver=)` — gates by resolved `owner` and `allowed_actions`, picks the first transition whose `guard` passes, runs the effect, moves the cursor, then auto-advances. Returns `RunResult(ok, state, reason)`; legality failures are no-op rejections, authoring bugs raise.
- `begin_arc(arc, sink, resolver=)` — validates, sets the cursor to the entry, auto-advances leading automatic segments.
- `resolve_owner` maps `OwnerScope.CURRENT`→`turn.current_faction`, `Faction`→its name, `OwnerRef`→title `OwnerRefResolver`, `NO_OWNER`→None. `_auto_advance` fires ownerless segments (first passing guard) until an owned segment or completion, capped against declared loops.
- Mutation flows through an `ActionSink` (`ActionManager` satisfies it); each `StateAction` executes exactly once (no dry-run double-apply), so undo/redo, snapshots, and `rng_log` stay consistent. The engine reads no title shapes — only title-supplied callables (guards/effects/resolver).
- Tests in `tests/test_arc_runner.py`: full combat walk (attack → suspend into defender retreat → resume to advance → done), owner/allowed-action/guard rejections, `OwnerRef` resolution, auto-advance through ownerless segments, `auto_branch` arm selection, whole-event undo, and the loop guard.

### Phase 2 — Combat arc as declaration (hexdemo)

Goal: express hexdemo's post-`Attack` combat cleanup as one declared arc driven by the
generic runner, and make the runner authoritative for combat-RPC dispatch.

#### What "cutover" means here (migration reality)

The runner becomes authoritative for **combat-RPC dispatch and legality** (disrupt /
advance / retreat fulfillment): the dispatch-time gate-string prechecks in
`authority_combat_cleanup` and `game_server` are deleted as each RPC migrates, replaced
by `submit_event` (owner + `allowed_actions` + guards).

The `combat_gate` string is **not** deleted in Phase 2. During Phases 2–4 it is an
**effect-maintained mirror** of the cursor (transition effects keep writing it). End-Phase
blocking and dock skin now read **`current_segment`** (via `segment_blocks_routine_phase_advance`
and the segment presentation registry); legacy reads of `combat_gate` in pack RPC guards
and `attack_planning_blocked_reason` fallbacks remain until Phase 5 retirement. Removed
helpers: `blocks_routine_phase_advance`, `dock_arc_hint`, hexdemo `DOCK_ARC_*` constants.

#### The declared combat arc (target shape)

Source of truth = the existing FSM in `games/hexdemo/combat_transitions.py` +
`combat_actions.py`. Mapping the three gates and their transitions onto segments:

- `classify` — owner `NO_OWNER` (auto, the entry). Branches on the just-computed attack
  outcome to the right gate (replaces "begin at a chosen gate"): `auto_branch` →
  `retreat_or_disrupt_gate` when the attack opened the optional-disrupt gate, else
  `retreat_gate`. (Keeps `begin_arc` generic — it always starts at the declared entry.)
- `retreat_gate` — owner `OwnerRef("retreating")` (resolves to the faction holding
  `retreat_obligations`, attacker on `attacker_retreat`, defender on `defender_retreat`).
  `allowed_actions = {MoveUnit}`. `on("MoveUnit", guard=is_retreat_fulfillment, effect=…)`
  → `goto resolve`. (Replaces `GATE_AWAITING_RETREAT`.)
- `retreat_or_disrupt_gate` — same owner; `allowed_actions = {MoveUnit,
  CombatDisruptInsteadOfRetreat}`; adds `on("CombatDisruptInsteadOfRetreat",
  effect=disrupt_instead_of_retreat) → goto resolve`. (Replaces
  `GATE_AWAITING_RETREAT_OR_DISRUPT`.)
- `resolve` — owner `NO_OWNER` (auto). Handles partial/stacked retreats and the
  post-retreat advance opening without a guard needing post-effect state:
  `auto_branch` → (still pending obligations) `goto retreat_gate`; (advance available per
  `maybe_open_advance_after_retreat`) effect opens the advance payload + `goto advance_gate`;
  else `done` (clear cursor → routine).
- `advance_gate` — owner `CURRENT` (the attacker). `allowed_actions = {CombatAdvance,
  MoveUnit, CombatDeclineAdvance}`; `on("CombatAdvance", effect=resolve_combat_advance)
  → done`, `on("MoveUnit", guard=is_combat_advance_move, effect=resolve_combat_advance)
  → done`, and `on("CombatDeclineAdvance", effect=clear_advance_gate) → done` (the skip).
  (Replaces `GATE_AWAITING_ADVANCE`; covers both advance fulfillment paths plus skip.)

**Decided — Approach A (`goto`-cycling), not `interrupt`/`resume`.** Every retreat/disrupt
step goes `retreat_gate → resolve`, and the ownerless auto `resolve` re-reads state to
loop back (`goto retreat_gate`) for multi-step / stacked retreats, branch to
`advance_gate`, or finish. This is required because "did this move finish the retreat?"
is only answerable *after* the effect, and a transition guard runs *before* its effect;
`resolve` is where that post-effect decision lives. The depth-1 `interrupt` frame can't
express the loop (it would pop on the first hop), and `advance_gate` is attacker-owned
(`CURRENT`) like the routine state, so there is nothing meaningful to "resume" to. The
earlier `attack → retreat_gate interrupt → advance_gate` sketch is superseded for combat.

Effects reuse title functions (return `list[StateAction]`): `combat_rules.BINDING`
methods delegating to `combat_actions.*`; post-attack bucket handoff is
`combat_outcome.build_combat_outcome_after_applied` → `CombatOutcome` inside the arc
`attack` effect. **`combat_gate` mirror is retired**; segment `kind` on the arc cursor is authoritative.

#### New engine/title surfaces needed

- A title-provided **combat arc bundle**: the declared `Arc` + an `OwnerRefResolver`
  (`"retreating"` → faction holding obligations). Phase 2 can expose this as one small
  hexdemo hook; Phase 4 generalizes it into the arc registry/schedule.
- **Arc lookup by id** so dispatch can fetch the arc for the active `cursor.arc_id`.
- **`game_server` dispatch integration**: when a combat-arc cursor is active, route
  `CombatAdvance` / `CombatDisruptInsteadOfRetreat` and the combat `MoveUnit` paths
  (retreat fulfillment, advance fulfillment) through `submit_event`, mapping the wire
  `actor` to `player.faction` and passing `params`. Heavy, non-undoable pre-validation
  that must reject before any mutation (the stacked-retreat stacking-limit check in
  `validate_retreat_fulfillment_stack`) stays as a server pre-guard or becomes a
  transition `guard`; the actual moves/clears become the transition effect.
- **Attack RPC (Phase D, done):** `execute_authority_attack_request` sets `SEG_ATTACK` and
  `submit_event("Attack")`; the effect applies `CombatOutcome` and `classify` auto-advances.
  `restore_routine_cursor` runs when the overlay completes. `begin_combat_arc` is cleanup-only
  (tests / bucket already set).

#### Sub-steps (each keeps pytest green)

- **2a (additive, no routing) — [done].** Declared the combat arc as data in
  `games/hexdemo/combat_arc.py` (`build_combat_arc`): `classify` (auto entry) →
  `retreat_gate` / `retreat_or_disrupt_gate` (`OwnerRef("retreating")`) → auto `resolve`
  (Approach A loop) → `advance_gate` (`CURRENT`, with `CombatDeclineAdvance` skip).
  Effects/guards reference the existing title functions; `apply_retreat_step` is a 2c
  stub (raises until the retreat move/clear logic moves here). Added `resolve_owner_ref`
  (the `"retreating"` `OwnerRefResolver`) and `combat_actions.clear_advance_gate`.
  Gate-bearing segments carry their `combat_gate` string as `kind`. Parity test
  `tests/test_combat_arc_declaration.py` asserts owners, derived `allowed_actions`,
  one-to-one segment↔`GATES_BLOCKING_ROUTINE` mapping, and resolver behavior;
  `Arc.validate()` passes. No routing — all existing combat tests stay green.
- **2b (soft cutover: disrupt + advance RPCs) — [done].** Added a dedicated **`arcs` hook
  bundle** (`hexengine/hooks/arcs.py`: `ArcsHooks.combat_arc` → `ArcSpec(arc,
  owner_resolver)`), registered in `title.py` + `wiring.py`; hexdemo binds it in
  `games/hexdemo/hooks/arcs.py`. New engine bridge
  `hexengine/server/arcs/authority_arc_runtime.py` exposes `begin_combat_arc` (called from
  `execute_authority_attack_request` right after the follow-up — `classify` auto-advances
  to the matching gate, or finishes for no-cleanup outcomes) and `drive_combat_arc_event`
  (drives `submit_event`, maps acceptance → `ActionResult` + broadcast).
  `game_server` routes `CombatDisruptInsteadOfRetreat`, `CombatAdvance`, and the new
  `CombatDeclineAdvance` through the runner first. A "Skip" row at `awaiting_advance` was
  added to `default_primary_actions_for_viewer`. Tests: `tests/test_combat_arc_runner_2b.py`.

  **Deviation from strict cutover (intentional, until 2c):** because retreat fulfillment
  still runs on the legacy `MoveUnit` path (2c) and does **not** move the cursor, the
  cursor can be stale relative to the gate mirror mid-combat. So the runner is
  authoritative only when it **accepts** an event (cursor correctly positioned, owner +
  action legal); on any rejection `drive_combat_arc_event` returns False and the dispatch
  **falls back to the legacy handler** (which keeps its gate-string precheck + error
  messages as the backstop). Thus no prechecks are deleted yet, and the `MoveUnit` advance
  path is left on the legacy handler in 2b. The prechecks/handlers are deleted in 2c–2d
  once every combat RPC moves the cursor and the runner is the sole authority.
- **2c (cutover: retreat fulfillment) — [done].** Implemented
  `combat_actions.apply_retreat_fulfillment_step` + `retreat_stack_unit_ids` (stacked
  moves + `ClearUnitRetreatObligation`; primary may already be at destination for
  stepwise-path completion). Wired `apply_retreat_step` in `combat_arc.py`. Route
  retreat-fulfillment `MoveUnit` through `drive_combat_arc_event` in `game_server`
  (after `validate_retreat_fulfillment_stack` pre-guard) and at stepwise-path completion
  in `authority_movement.continue_stepwise_move_unit`. Legacy handler remains fallback
  when no arc cursor is active. Tests: `tests/test_combat_arc_runner_2c.py`.
- **2d (cleanup) — [done].** `ClearUnitRetreatObligation` is gate-agnostic (only pops the
  obligation entry). Post-Phase-B/C: neither pack nor engine writes or clears
  `combat_gate`; phase advance drops the legacy key via `PHASE_SCOPED_COMBAT_KEYS`.
  Legacy `handle_combat_*` RPC handlers and `finalize_retreat_fulfillment_stack` are
  removed. When a title binds `ArcHook.COMBAT_ARC`, `try_combat_arc_rpc` /
  `try_combat_arc_move_unit` are authoritative (errors on stale cursor or rejected
  segment). Titles with `title_state_extension_key` must declare `COMBAT_ARC`; otherwise
  combat cleanup RPCs receive `COMBAT_ARC_REQUIRED_MSG`.
  Routed advance-fulfillment `MoveUnit` through `drive_combat_arc_event`. Tests:
  `tests/test_combat_arc_runner_2d.py`.

#### Modeling questions (resolved)

1. **Two segments, not one.** `awaiting_retreat` → `retreat_gate` and
   `awaiting_retreat_or_disrupt` → `retreat_or_disrupt_gate` are modeled as two distinct
   segments (faithful to the gate table; `allowed_actions` differs only by the added
   `CombatDisruptInsteadOfRetreat`). After a retreat step, `resolve` loops back to the
   plain `retreat_gate` (the disrupt option is offered once, at gate entry).
2. **Advance is skippable (new in Phase 2).** Today the dock offers only `CombatAdvance`
   at `awaiting_advance` and End-Phase is blocked while the gate is open, so advance is
   effectively forced. We are making it skippable: add a `CombatDeclineAdvance` RPC (the
   `Combat*` family) whose effect clears the advance payload + gate mirror and finishes
   the arc (`advance_gate → done`). End-Phase remains blocked while `awaiting_advance` so
   the choice stays deliberate (advance or skip), rather than letting End-Phase
   auto-skip. New work this adds: a `CombatDeclineAdvance` dispatch branch routed through
   `submit_event` (2b), a `clear_advance_gate` title effect (clears `advance` +
   `combat_gate`, reusing the existing remove-keys patch), and a "Skip" action row at the
   advance gate (added to `default_primary_actions_for_viewer` alongside "Advance"; fully
   migrated to the segment-driven dock in Phase 5).
3. **`goto`-cycling (Approach A).** Resolved above; no `interrupt`/`resume` for combat.
4. **Stacking-limit stays a server pre-guard (for now).** The stacked-retreat
   stacking-limit check (`validate_retreat_fulfillment_stack` → specific `ValueError`)
   must reject before any mutation and carries descriptive messaging + the
   server pre-guard run before `submit_event`, so 2c keeps it as a server pre-guard run
   before `submit_event`. The runner owns segment/owner/`allowed_actions` legality; the
   stacked moves + per-unit obligation clears are the transition effect. (Candidate to
   fold into the effect later as an atomic raise-before-return, once messaging parity is
   confirmed — not required for Phase 2.)

#### Tests that must stay green
`test_combat_hexdemo`, `test_combat_transitions`, `test_attack_multi_defender`,
`test_authority_arcs`, `test_network`, `test_turn_action_dock`, plus the new 2a parity
test and 2b–2c integration tests.

### Phase 3 — Movement arc as declaration

**Status:** done (3a–3d).

Re-express stepwise movement + `awaiting_continue` / `awaiting_interrupt` /
`PassMovementInterrupt` as a declared arc with an interrupt sub-arc. The generic
`hexengine_arc_cursor` is kept in sync with the movement payload gate mirror; path/budget
data stays in `hexengine_movement_arc` until a later payload refactor.

#### Sub-steps (completed)

1. **3a — Declare movement arc as data.** `src/hexengine/arcs/movement_arc_decl.py`
   (`build_movement_arc`): segments `continue`, `step_resolve`, `interrupt`,
   `interrupt_resolve`; `kind` values match movement gate strings. Parity tests in
   `tests/test_movement_arc_declaration.py`.
2. **3b — Cursor sync + runtime bridge.** `sync_movement_cursor_from_payload` maps payload
   gate → `ArcCursor` (interrupt uses depth-1 suspend/resume). `ArcsHooks.movement_arc`
   slot added; `GameServer.movement_arc_spec()` builds the engine default with host-bound
   effects (`movement_arc_effects.py`).
3. **3c — Route RPCs through runner (soft cutover).** `PassMovementInterrupt` and stepwise
   continue `MoveUnit` offered to `drive_movement_arc_event` first; legacy
   `ResolvePassMovementInterrupt` / imperative continue remain fallback when the runner
   rejects. Integration tests in `tests/test_movement_arc_runner_3b.py`.
4. **3d — Wire payload writes.** Every `WriteHexengineMovementArc` path in
   `authority_movement.py` calls `sync_movement_cursor_from_payload` so the cursor exists
   before the next RPC.

#### Tests that must stay green

`test_movement_sequence`, `test_retreat_path`, `test_authority_arcs`, `test_network`, plus
the new 3a parity test and 3b integration tests.

### Phase 4 — Turn schedule as arc sequence

**Status:** done (4a–4d).

Replace flat `turn_order()` with a declared sequence of routine phase arcs. The generic
cursor holds the active schedule slot; overlay arcs (combat cleanup, stepwise movement)
replace it temporarily and restore the routine cursor when they finish.

#### Sub-steps (completed)

1. **4a — Schedule types + routine phase arcs.** `hexengine/arcs/schedule.py`
   (`ArcSchedule`, `ScheduleSlot`), `routine_phase.py` (`build_routine_phase_arc`),
   explicit `allowed_actions` on segments. Hexdemo declaration in
   `games/hexdemo/turn_arc_schedule.py`; parity tests in `tests/test_turn_arc_schedule.py`.
2. **4b — Turn arc registry.** `TurnArcRegistry` + `ArcsHooks.turn_arc_registry`;
   hexdemo binds via `games/hexdemo/hooks/arcs.py`. `lookup_arc_spec` merges routine,
   combat, and movement arcs.
3. **4c — Schedule-driven phase advance.** `schedule_next_phase_info` drives
   `GameServer._get_next_phase` when a registry is declared; `turn_order` wire field
   derives from the schedule. `begin_routine_slot` on server init and after each
   `NextPhase`.
4. **4d — Segment-owner legality.** `resolve_active_segment_owner` +
   `GameServer._actor_may_act` replace direct `current_faction` checks for Attack,
   MoveUnit (non-retreat), markers, and movement interrupts. Combat-arc `MoveUnit` is
   offered before the legacy retreat branch.

#### Tests that must stay green

`test_movement_sequence`, `test_combat_hexdemo`, `test_network`, plus
`tests/test_turn_arc_schedule.py`.

### Phase 5 — Affordances + client from the declared segment

**Status:** done (5a–5d).

Publish per-recipient ``current_segment`` on ``StateUpdate``; derive dock rows, End-Phase
gating, and client draft entry from it instead of ``combat_gate`` string matching.

#### Sub-steps (completed)

1. **5a — Segment wire projector.** ``hexengine/arcs/segment_wire.py`` projects
   ``arc_id``, ``segment_id``, ``kind``, ``owner``, ``allowed_actions``, and
   ``action_locus`` (``server`` vs ``client_draft``) from the active cursor.
2. **5b — StateUpdate field.** ``current_segment`` on ``StateUpdate`` (per viewer);
   ``TurnActionDockContext.current_segment`` for dock hooks.
3. **5c — Segment-driven dock + End-Phase.** ``combat_gate_panel_actions`` (title helper) builds combat
   button rows from ``allowed_actions`` + ``shell_ui`` labels. End-Phase enabled when
   ``NextPhase`` is in the segment set; ``segment_blocks_routine_phase_advance`` drives
   server ``NextPhase`` rejection before legacy hook fallback.
4. **5d — Client entry guards.** ``BrowserWebSocketClient.current_segment``; attack-plan
   draft and planning UI gated on ``Attack`` in ``allowed_actions`` instead of
   ``combat_gate`` reads.

#### Tests that must stay green

``test_turn_action_dock``, ``test_current_segment``, combat/movement arc runners, plus
existing integration tests.

### Phase 6 — Importable patterns + templates + validation

**Status:** Phases 0–7 complete. Phase 6f (builder prettiness) deferred — revisit when authoring ergonomics need it.

Author-time construction lives in **`hexengine.authoring`** (builder, patterns, validate).
Runtime code in `hexengine.arcs` + server drives frozen `Arc` / `ArcSpec` data only.

**Strict import boundary:** engine runtime modules must not import `hexengine.authoring`.
Only `hooks.internal.authoring_bridge` (movement default assembly) and
`hooks.internal.contracts` (load-time validate) may import authoring. Enforced by
`tests/test_authoring_boundary.py`.

#### Sub-steps

1. **6a — `hexengine.authoring` package.** `builder.py` moved from `arcs/`; patterns
   submodule with `phase`, `schedule`, `movement`, `combat`; `validate.py` for arc/registry
   checks.
2. **6b — Hexdemo consumes patterns.** `turn_arc_schedule.py` uses `interleaved_slots` +
   `build_turn_registry`; `combat_arc.py` uses `build_combat_cleanup_arc` with title-bound
   guards/effects and gate kind strings.
3. **6c — Load-time validation.** `validate_arc_contract` wired through
   `validate_title_contract` at `GameServer` init.
4. **6d — Movement default via bridge.** `build_movement_arc` in
   `authoring.patterns.movement`; `GameServer.movement_arc_spec()` uses
   `authoring_bridge.build_default_movement_arc_spec` (not direct authoring import).
5. **6e — Template pack (`games/template/`).** Minimal copy-in title: manifest, registry,
   move-only `turn_arc_schedule` via `authoring.patterns.schedule`, `hooks/arcs.py` with
   `TURN_ARC_REGISTRY`, scenario + game_data stubs. `tests/test_template_pack.py`.
6. **6f (deferred — revisit later)** — Operator-overloading prettiness layer on the arc builder. Skip until authoring ergonomics become a priority; plain `with arc(...) as a:` builder is the supported surface.

**Resolved:** patterns home is `hexengine.authoring` (patterns as siblings of builder
and validate), not `hexengine.arcs.patterns`.

### Phase 7 — Fan-out: docs, comments, orphaned code ✅

**Status:** Done.

- Removed engine gate-string catalog paths (`default_blocks_routine_phase_advance`, `PRIMARY_ACTIONS_FOR_VIEWER`, `BLOCKS_ROUTINE_PHASE_ADVANCE`).
- Docs updated: `PACK_HOOK_CONTRACTS.md`, `TURN_ACTION_DOCK_CONTRACT.md`, `TITLE_AUTHORING.md`, `engine_game_boundary_matrix.md`, `ENGINE_BOUNDARY_2_PLAN.md` (supersession note), `SERVER_ARCHITECTURE.md`, `hexdemo/hooks/README.md`.
- Title `combat_gate` bucket field retired (not written); engine and pack read `current_segment`.
- Client draft CSS uses `effective_turn_dock_presentation_id` (client-local sub-arcs); server hook uses idle `presentation_id` from enriched `current_segment`. Draft locus: [`TURN_ACTION_DOCK_CONTRACT.md` § Draft locus](TURN_ACTION_DOCK_CONTRACT.md#draft-locus-invariant).

**Author-facing UX (next):** segment `kind` plus a title **presentation registry** (`presentation_id`, primitive, `interaction_mode`) so hooks and templates stay insulated from wire — see [`TITLE_AUTHORING.md` § Flow vs presentation](TITLE_AUTHORING.md#flow-vs-presentation-authoring-model) and [`PACK_HOOK_CONTRACTS.md` § Authoring vs wire](PACK_HOOK_CONTRACTS.md#authoring-vs-wire).

**Author programming interface (sibling track):** [`TITLE_AUTHOR_INTERFACE_PLAN.md`](TITLE_AUTHOR_INTERFACE_PLAN.md) — collapse attack hook pipeline + combat arc binding into one title-facing API (`CombatOutcome`, single `CombatRulesBinding`); Phase D routes `Attack` through `submit_event`.

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
- Phase 6f (optional builder prettiness) explicitly deferred for later revisit.
