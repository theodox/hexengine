"""
Hook surface for title-authored rules (`hexengine.hooks`).

**Titles:** import by area — `hexengine.hooks.movement`, `.attack`, `.bucket`, `.ui`,
`.title`, `.wiring`, `.core`.

**Wiring workflow**

1. Import hook **types** and the area **slot enum** from the matching module:
   `MovementHook` / `AttackHook` / `UIHook` (values match `MovementHooks` /
   `AttackHooks` / `UIHooks` field names).
2. Import `bind_title_hook` from `hexengine.hooks.wiring`.
3. Decorate each implementation with `@bind_title_hook(MovementHook.SOME_FIELD)` (etc.)
4. Build `TitleHooks` with `assemble_title_hooks` from your hook modules.

This package root exposes a **small convenience**: `ENGINE_DEFAULT` and `TitleHooks`.

**Engine-only:** `hexengine.hooks.internal` (catalog, `@hook`, `validate_title_contract`,
movement budget catalog entry, combat-advance default).

**Roadmap:** stricter contracts and author tooling for all hooks — `docs/PACK_HOOK_CONTRACTS.md`.
"""

from __future__ import annotations

from .core import ENGINE_DEFAULT
from .title import TitleHooks

__all__ = ["ENGINE_DEFAULT", "TitleHooks"]
