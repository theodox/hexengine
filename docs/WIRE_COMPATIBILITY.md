# Wire compatibility (client ↔ server)

## Protocol version

- Join / state payloads may include `protocol_version` (currently `"1"`). Clients should accept unknown keys and ignore fields they do not understand.
- `server_package_version` / `package_version` identify the installed **hexes** Python package build; bump when breaking snapshot or message shapes.

## Scenario `schema_version`

- Scenario TOML may set top-level `schema_version` (integer, default `1`).
- **Additive** changes: new optional tables/fields are preferred. Breaking changes require a version bump and loader updates.

## Game state snapshot

- `game_state_to_wire_dict` / `game_state_from_wire_dict` may include optional `extension` (object) and `rng_log` (array of objects). Older clients ignore unknown top-level keys if they use a tolerant JSON parser.
- Stepwise movement **arc** state lives under extension key **`hexengine_movement_arc`** (not `hexengine_movement_flow`). Snapshots or clients using the old key need a one-time migration when upgrading.

## Game rules selection

- Turn order comes from the **pack** (`hexengine_pack.toml` → `load_game_definition()`). The server sends full rota in `StateUpdate.turn_rules` (`entries`, …); the browser rebuilds a thin `GameDefinition` from that wire for manual advance and previews—no separate CLI schedule flag.
