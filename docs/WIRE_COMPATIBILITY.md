# Wire compatibility (client ↔ server)

## Protocol version

- Join / state payloads may include `protocol_version` (currently `"1"`). Clients should accept unknown keys and ignore fields they do not understand.
- `server_package_version` / `package_version` identify the installed **hexes** Python package build; bump when breaking snapshot or message shapes.

## Scenario `schema_version`

- Scenario TOML may set top-level `schema_version` (integer, default `1`).
- **Additive** changes: new optional tables/fields are preferred. Breaking changes require a version bump and loader updates.

## Game state snapshot

- `game_state_to_wire_dict` / `game_state_from_wire_dict` may include optional `extension` (object) and `rng_log` (array of objects). Older clients ignore unknown top-level keys if they use a tolerant JSON parser.

## Game rules selection

- Server and browser client must agree on turn schedule when using **manual advance** or client-side previews: start the WebSocket server with the same `--schedule` value (`interleaved` or `sequential`) that the client logic assumes (today the in-browser client uses the default interleaved schedule when advancing turns locally).
