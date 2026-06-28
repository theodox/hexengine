# Rules expansion (`rules_expansion` branch)

**Status:** active development track on branch `rules_expansion`.

**Reference rules:** [Musket & Saber Standard Rules V6F (PDF)](https://gamers-hq.de/media/pdf/68/cb/cb/MSStandard-Rules_V6F-16OhWeVNFO4UDX.pdf) — primary source for what to implement in hexdemo.

**Related:** [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md) (long-term composable rule vision), [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) (how title policy hooks in today), [`ENGINE_TITLE_CHARTER.md`](ENGINE_TITLE_CHARTER.md) (engine vs title boundary).

---

## Tactical goal

Flesh out **game rules more completely** in hexdemo so the reference pack reflects a real tabletop-style wargame, not a minimal combat/movement demo.

Work **one system at a time**: read the M&S section, implement title-side policy (and engine support only where the charter says the engine must own it), add tests, then move on. Each system should be driven to a playable state before starting the next.

After each system, note **architectural implications** — new hooks, session state, arc segments, wire fields, preview kinds, or data in `GameData` / scenario TOML.

---

## Strategic goal

Use M&S implementation to **discover rule-resolution patterns** the engine must eventually support well: timing windows, conditional modifiers, die rolls and section order, exceptions, joint tests, reaction chains, and similar.

Some findings will stay in title Python (`games/hexdemo/combat/`, `movement/`, hooks). Others may show that **engine systems need reconfiguration** (arc runner, action types, RNG/logging, bucket patches, preview contracts, etc.). Capture those in this doc or in linked issues before large refactors.

Do not pre-design the whole rules engine up front. Let requirements emerge from concrete M&S systems.

---

## Working agreement

1. **Source of truth:** M&S PDF for rule behavior; hexdemo code and tests for what is actually shipped.
2. **Scope per PR / chunk:** one M&S system (or a coherent subsection), end-to-end where possible.
3. **Boundary check:** before moving logic into `hexengine`, ask whether it is title policy or reusable mechanism (charter A–F).
4. **Record friction:** when a rule is awkward to express with current hooks/arcs/wire, add a short note under [Friction log](#friction-log) below.
5. **Defer composition catalog:** prefer clear title code first; extract reusable engine pieces when the same pattern appears twice (see `RULE_COMPOSITION.md`).

---

## Systems tracker

Update as work lands. Order is tentative — adjust when dependencies appear.

| M&S area (indicative) | Hexdemo location | Status |
|----------------------|------------------|--------|
| *(none started on this branch yet)* | | |

---

## Friction log

Engine or architecture gaps discovered while implementing M&S. Each entry: **system**, **symptom**, **possible direction** (title-only vs engine change).

| System | Symptom | Possible direction |
|--------|---------|-------------------|
| *(empty)* | | ``