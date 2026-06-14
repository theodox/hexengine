# Composable rule sets (planning — not implemented)

**Status:** vision / design note only. Patterns are not stable enough to build yet. This doc captures intent so movement delegation, hook contracts, and pack layout evolve in the right direction.

## Intent

Titles should be able to assemble **rule sets** from **small, reusable engine pieces** where that fits, and still plug in **custom rules** when declarative composition is not enough.

Example (illustrative, not API):

> In my game, **ZOC stops movement**, and a unit with **low morale cannot enter difficult terrain**.

Today hexdemo encodes much of this imperatively in `hooks/modification.py` and stubs in `movement_rules.py`. Long term we want:

1. **Engine catalog** — tested, **pure functions** on `GameState` that authors **import** (ZOC, terrain class, morale gates, reachability helpers, …). Many already live under `hexengine.state.logic` in ad hoc form.
2. **Title composition in Python** — authors assemble catalog pieces and custom code with normal Python (call, pipe, `and`, loops). **No separate rules DSL or runtime** is required for composition itself.
3. **Optional data binding** — scenario/title parameters (morale threshold, terrain tags) from `GameData` or TOML; composition logic stays in Python.

Hooks remain the **integration layer** (when the server asks); composed **rules** are the **policy layer** hooks call into. See [`games/hexdemo/hooks/README.md`](../games/hexdemo/hooks/README.md) (rules vs hooks).

**Composable arcs (shipped):** turn/combat/movement flow is declared as arc graphs in `hexengine.authoring` and driven by the generic runner; hooks supply title-bound effects. See [`archive/COMPOSABLE_ARCS_PLAN.md`](archive/COMPOSABLE_ARCS_PLAN.md).

## Preferred model: import and compose (not a DSL)

Authors should not need a new construct to mix engine and custom behavior. The engine exposes **small, documented pure functions**; titles write ordinary Python that calls them.

Illustrative shape only (names and helpers TBD):

```python
from hexengine.rules.movement import (  # future package — not implemented
    reachable_hexes,
    block_hexes_in_zoc,
    forbid_hexes_when,
)
from hexdemo.rules import morale_below

def legal_move_hexes(state, unit_id, *, budget: float):
    hexes = reachable_hexes(state, unit_id, budget=budget)
    hexes = block_hexes_in_zoc(state, unit_id, hexes)
    hexes = forbid_hexes_when(
        hexes,
        lambda h: morale_below(state, unit_id, threshold=2)
        and terrain_is_difficult(state, h),
    )
    hexes = hexdemo_custom_border_filter(state, hexes)  # title-owned
    return hexes
```

**Custom rules** are just more functions in the same pipeline — same types, same tests, no “escape hatch” tier.

Optional **combinators** (`pipe_filters`, `intersect_constraints`) are themselves thin pure helpers in the engine catalog; authors can ignore them and write explicit steps.

A **TOML/manifest rules DSL** is not the default path. If we add declarative config later, it should deserialize into this Python composition (or into plain data passed into catalog functions), not a second execution model.

**Why this fits hexengine**

- Pyodide packs are already Python modules; import + compose matches `bind_title_hook` and `movement_rules.py` purity goals.
- Static typing (pyright on `games/*`) applies to composed rules without parsing a DSL.
- Authors debug with familiar stack traces, not a rule interpreter.
- Engine pieces stay **tested once** in `tests/`; titles compose in `games/<pack>/rules/`.

## Why this is reasonable

- Matches how board games are described: modular constraints (ZOC, terrain, capacity) plus exceptions.
- Keeps **authority on the server**: catalog pieces run in one place; client preview consumes the same composed rule set (or server-published legal hexes) to avoid drift.
- Fits **rewind / pure state**: pieces should be `GameState` → bool / cost / set, same as current `movement_rules.py` direction.
- **Composition without locking authors in**: catalog covers 80%; custom code handles the rest.

## Open design questions (defer implementation until these have answers)

| Topic | Question |
|-------|----------|
| **Composition model** | Pipeline (filter hexes in order) vs constraint solver vs sum of costs? Different domains (movement vs combat vs markers) may need different models. |
| **Order** | “ZOC then terrain” vs “terrain then ZOC” — need explicit precedence or commutative semantics per piece type. |
| **Parameters** | How do thresholds/tags bind to `GameData` or scenario data when passed into imported catalog functions? |
| **Combinators** | Minimal set of `pipe` / `filter_hexes` helpers vs authors writing explicit steps only? |
| **Validation** | Static check that declared pieces exist and parameters are valid at pack load. |
| **Hooks vs catalog** | Which hook slots become thin wrappers over a composed `MovementRules` object vs stay ad hoc? |
| **Wire / preview** | Publish full legal sets vs re-run composition on client — ties to `engine_game_boundary_matrix.md` movement row. |

## Non-goals (for now)

- A **standalone rules DSL** (TOML or otherwise) as the primary authoring surface before movement is composed once in Python.
- Replacing `TitleHooks` with a single mega-rules engine — hooks and arcs stay; composition feeds them.
- A custom rule **interpreter** — only functions and plain data.

## Suggested evolution (when patterns emerge)

1. Curate **`hexengine.rules.*`** (or stable re-exports from `state.logic`) — pure catalog functions with tests and docstrings.
2. Add **small combinators** only where they reduce repetition (e.g. filter a hex set by predicate); keep them optional.
3. Title **`rules/`** modules import catalog + define `legal_move_hexes` (etc.); **`hooks/`** call into `rules/`.
4. Wire **one** server path (`MoveUnit` / legal hex preview) through the title’s composed function; align client preview.
5. **Optional:** manifest or `game_data.toml` supplies **parameters** to catalog functions, not executable rule programs.

## Related docs

- Pack hook contracts (validation, templates): [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md)
- Engine / title boundary (movement legality): [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md)
- Hexdemo rules vs hooks: [`games/hexdemo/hooks/README.md`](../games/hexdemo/hooks/README.md)
