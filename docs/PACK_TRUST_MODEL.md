# Pack trust model (planning)

**Status:** architectural notes — not enforced today. Complements [`SERVER_ARCHITECTURE.md`](SERVER_ARCHITECTURE.md) security checklist.

## Can authors monkeypatch engine code?

**Yes, in Python they can.** There is no technical barrier today.

Packs are imported into the **same interpreter** as `hexengine` (client Pyodide, local server thread, or `hexserver` process). A title module can, after import:

```python
import hexengine.state.logic as logic
logic.compute_valid_moves = my_replacement  # example only
```

or mutate `GameServer`, hook bundles, arc handlers, etc. `sys.path` prepend only affects **import order**, not immutability.

Official extension surfaces (`TitleHooks`, manifest title-load, future `hexengine.rules.*` imports) are **conventions**. They are not a sandbox.

## Client vs server

| Runtime | Who runs pack Python | Sandbox | Effect of malicious pack |
|---------|----------------------|---------|---------------------------|
| **Browser (Pyodide)** | Pack + engine in one JS/WASM sandbox | No host FS/network beyond what the page allows | Break UI, patch client hooks, send arbitrary **wire messages** — server must still reject illegal actions |
| **Local server (solo)** | Same process as browser client (typical) | Same as browser | Same as client; easier to patch “server” in-process |
| **`hexserver` (host)** | Pack hooks run inside server process | **None** — full OS user as the server | Cheat, bypass validation, read/modify all match state in memory, DoS host, arbitrary code as server user |

**Client sandbox ≠ server trust.** Server-authoritative rules only hold if the server does not execute untrusted code with full privileges. Today, **running a pack on hexserver means trusting the pack author like any other server-side plugin.**

## Pros of allowing patch-level freedom (good-faith)

- **Rapid experimentation** — exotic arc variation before a new hook exists.
- **Private hotfix** — forked engine behavior for one title without publishing engine changes.
- **Deep integration** — rare titles that genuinely need to wrap low-level reachability or protocol edges.

These are valuable for **trusted** authors (your own packs, local dev, curated registry).

## Cons / risks

- **Multiplayer integrity** — patched validation or hooks can cheat if the server runs the patch.
- **Supportability** — “works on my machine” when engine version + hidden patches differ.
- **Upgrade fragility** — internal engine symbols move; monkeypatches break silently or worse, partially.
- **Security** — untrusted pack on shared `hexserver` is equivalent to running untrusted Python on the host.
- **Confusion with rules composition** — patching bypasses the import-and-compose model in [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md).

## Desirable subset (direction, not implemented)

Goal: give **good-faith** authors power for unknown arc variants **without** open mutation of engine internals.

| Mechanism | Role |
|-----------|------|
| **Documented hooks + arcs** | Supported extension; versioned contracts (`PACK_HOOK_CONTRACTS.md`). |
| **`hexengine.rules.*` pure catalog** | Compose behavior by import, not patch. |
| **Optional title-provided arc steps** | Register extra segment handlers via protocol (future), not `GameServer.__dict__` surgery. |
| **Engine defaults** | `ENGINE_DEFAULT` and catalog for everything else. |

**Discouraged / unsupported:** replacing arbitrary `hexengine.*` module attributes; document as break-glass for trusted local dev only.

## Limits for non-good-faith authors (options to revisit)

Not chosen yet; increasing cost/complexity:

1. **Trust tiers** — curated packs vs “local only”; hexserver refuses unknown pack hashes / signatures.
2. **Separate worker** — match logic in subprocess with pack code only (still Python RCE unless further sandboxed).
3. **Restricted execution** — subset of Python for pack policy (heavy; may fight Pyodide parity).
4. **Server runs engine only; pack only on client** — only works if **all** authority stays server-side and pack never runs on host (hooks that affect legality must be engine-reimplemented or sent as data — hard for rich titles).
5. **Offline audit tooling** — see below (for server admins and curated registries; not runtime enforcement).
6. **Capability manifest** — pack declares `capabilities = ["movement_hooks"]`; loader refuses imports outside allowlist (weak against malice, good for clarity).

For **hosted multiplayer**, assume: **only run packs you trust on the server process**, same as server-side mods in other games.

## Offline audit tooling (planned)

We can provide **offline** checks (CLI / CI, no pack execution on the match host) so **server admins** review a pack before allowing it on `hexserver`. Goal: flag code that steps outside the **strict hook / arc / rules-import** model without replacing runtime sandboxing.

**Not implemented** — document intent so pack layout and contracts stay auditable.

Possible checks:

| Signal | Example |
|--------|---------|
| **Import allowlist** | `games/foo` imports only `hexengine.hooks.*`, `hexengine.gamedef.*`, `hexengine.rules.*`, own package — not `hexengine.server.game_server` internals. |
| **Assignment / monkeypatch** | AST or regex: assignment to `hexengine.<module>.<attr>`, `setattr` on engine modules, `@patch`-style wrappers. |
| **Manifest vs code** | `[hooks.title_load]` declared but no `present_splash`; `TitleHooks` slots empty while schedule implies combat. |
| **Hook wiring** | Movement/attack/UI callables use `bind_title_hook` / `assemble_title_hooks` rather than replacing `TitleHooks` fields after the fact. |
| **Rules surface** | Policy modules under `rules/` or `*_rules.py` call catalog imports; flag direct edits to engine reachability from pack code (policy TBD). |
| **Pack fingerprint** | Hash of audited tree + engine version for admin allowlists (“only run packs passing audit at commit X”). |

**Pros for admins**

- Review untrusted or third-party packs **before** deploy.
- Catch accidental internal imports (support burden), not only malice.
- Enforce registry policy (“must pass `hexengine audit-pack`”) without Python sandbox R&D.

**Limits**

- Determined authors can fool naive AST rules; audit is **due diligence**, not proof.
- Does not replace **trust tiers** or process isolation for high-stakes hosted play.
- Should align with [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) as the definition of “in bounds.”

Authors can run the same tool in CI; admins run it on submitted zips before listing a pack.

For **browser-only harm**, rely on wire protocol + server validation; treat client patches as UX/cheat-client risk, not source of truth.

## Related

- [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) — supported hook surfaces
- [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md) — compose via imports, not patch
- [`SERVER_ARCHITECTURE.md`](SERVER_ARCHITECTURE.md) — authoritative server
