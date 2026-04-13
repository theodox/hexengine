# Operator checklist: third-party game packs (zip)

Before loading an untrusted zip on the game server:

1. **Source** — Obtain packs from known authors or verify checksums / signatures if your org publishes them.
2. **Inspect** — Unzip to a scratch directory and review Python entrypoints (`game.toml` / `pack.toml`), imports, and filesystem access.
3. **Static pass** — List `import` lines and search for `subprocess`, `os.system`, raw sockets, or unexpected paths.
4. **Run** — Prefer a staging server; monitor logs during load and first match.
5. **Sandboxing** — For production with arbitrary uploads, use process isolation or a dedicated worker (see project roadmap).

This document is a stub; expand with tooling as audit automation lands in the engine.
