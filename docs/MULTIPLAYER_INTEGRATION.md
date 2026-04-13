# Multiplayer Integration Guide

## Overview

The multiplayer system treats all games identically - whether single-player or multiplayer, the client always communicates with a server. The only difference is whether the server is local (same process) or remote (network).

## Quick Start

### Single Player (Local Server)

```python
from hexengine.game import NetworkGame

game = NetworkGame(
    server_url="ws://localhost:8765",
    player_name="Alice",
    preferred_faction="union",  # must match server title, e.g. hexdemo: confederate | union
    use_local_server=True  # resolves game pack, builds GameDefinition, starts local server
)

await game.connect()
```

### Multiplayer (Remote Server)

```python
game = NetworkGame(
    server_url="ws://game-server.com:8765",
    player_name="Bob",
    use_local_server=False  # Connect to remote
)

await game.connect()
```

## Architecture

```
Single Player:
┌─────────┐
│  Client │ ──────┐
│   UI    │       │
└─────────┘       │
                  ↓
            ┌──────────┐
            │  Local   │
            │  Server  │
            └──────────┘

Multiplayer:
┌─────────┐         ┌──────────┐
│ Client  │────────→│          │
│  (P1)   │←────────│  Remote  │
└─────────┘         │  Server  │
                    │          │
┌─────────┐         │          │
│ Client  │────────→│          │
│  (P2)   │←────────│          │
└─────────┘         └──────────┘
```

## Key Classes

### `NetworkGame` (Client)

Extends the base `Game` class to send actions to server instead of executing locally.

**Key Methods:**
- `connect()` - Connect to server and join game
- `disconnect()` - Disconnect from server
- `execute_action(action)` - Override that sends action to server
- `is_my_turn()` - Check if it's your turn

**Key Callbacks:**
- `on_state_update` - Called when server sends new state
- `on_connection_change` - Called when connection status changes
- `on_error` - Called on errors
- `on_action_result` - Called when server responds to your action

### `WebSocketClient`

Handles WebSocket communication with server.

**Features:**
- Automatic connection management
- Message serialization/deserialization
- Turn validation
- State synchronization

### `LocalServerManager`

Starts a local server for single-player. It constructs a [`WebSocketGameServer`](../src/hexengine/server/websocket_server.py), so you must pass a title (or test) **`GameDefinition`** as a keyword argument, same as the standalone server.

**Usage (mirrors what `NetworkGame` does when `use_local_server=True`):**

```python
from hexengine.client.local_server import LocalServerManager
from hexengine.gameroot import (
    initial_faction_for_game_definition,
    load_game_definition_for_scenario,
    resolve_scenario_path_with_game_root,
)
from hexengine.scenarios import load_scenario
from hexengine.scenarios.loader import scenario_to_initial_state

scenario_path = resolve_scenario_path_with_game_root()
scenario_data = load_scenario(scenario_path)
game_def = load_game_definition_for_scenario(scenario_path, schedule="interleaved")
first = initial_faction_for_game_definition(game_def)
initial_state = scenario_to_initial_state(
    scenario_data,
    initial_faction=first,
    initial_phase="Movement",
    phase_actions_remaining=2,
)

manager = LocalServerManager(
    initial_state=initial_state,
    map_display=scenario_data.map_display.to_wire_dict(),
    global_styles=scenario_data.global_styles.to_wire_dict(),
    unit_graphics=scenario_data.unit_graphics_to_wire_dict(),
    marker_graphics=scenario_data.marker_graphics_to_wire_dict(),
    markers=scenario_data.markers_to_wire_list(),
    game_definition=game_def,
)
manager.start(port=8765)
```

For headless tests with no title pack, use [`InterleavedTwoFactionGameDefinition`](../src/hexengine/gamedef/builtin.py) and `GameState.create_empty()`, then `LocalServerManager(..., game_definition=InterleavedTwoFactionGameDefinition())`.

## How Actions Work

### Old (Direct Execution)

```python
# Action executed immediately on client
action = MoveUnit(unit_id, from_hex, to_hex)
game.action_mgr.execute(action)
```

### New (Server-Authoritative)

```python
# Action sent to server
action = MoveUnit(unit_id, from_hex, to_hex)
game.execute_action(action)  # Sends to server

# Server validates:
# - Is it your turn?
# - Is the move legal?
# - Does the unit exist?

# If valid:
# - Server executes action
# - Server broadcasts new state to all clients
# - Clients update displays

# If invalid:
# - Server sends error
# - Client shows error to user
# - State unchanged
```

## Mouse Handler Integration

The mouse handlers already work correctly! They call `game.execute_action()`, which:

1. **Before (local):** Executed action immediately via ActionManager
2. **Now (network):** Sends action to server, waits for state update

No changes needed to mouse handlers - they're transport-agnostic.

## Turn Validation

Server validates turn order:

```python
# Server checks:
if player.faction != current_state.turn.current_faction:
    send_error("Not your turn")
    return

# Client can pre-validate for UX:
if not game.is_my_turn():
    show_message("Wait for your turn")
    return
```

## State Synchronization

```python
# Server broadcasts state after each action
StateUpdate {
    game_state: {...},  # Full GameState
    sequence_number: 42  # For ordering
}

# Client receives and updates display
def _handle_state_update(new_state):
    self.display_mgr.sync_from_state(new_state)
```

## Preview System

Preview system works identically:

```python
# During drag (local only, not sent to server):
game.ui_state.update_drag(pixel_x, pixel_y, target_hex)
game.display_mgr.show_preview(...)

# On drop (sent to server):
if preview.is_valid:
    action = MoveUnit(...)
    game.execute_action(action)  # → Server
```

## Error Handling

### Connection Errors

```python
client.on_error = lambda error: show_error_popup(error)
```

### Action Errors

```python
client.on_action_result = lambda success, error: (
    show_success() if success else show_error(error)
)
```

### Connection Loss

Server marks player as disconnected but preserves their state. When reconnecting:

```python
# Server sends full state on reconnect
await client.connect()  # Rejoins with same player_id
```

## Running the Server

### Standalone Server

```bash
# Terminal 1: Start server (requires a resolvable game pack / scenario; see [SERVER_ARCHITECTURE.md](SERVER_ARCHITECTURE.md))
python -m hexengine.server.websocket_server

# Terminal 2: Start client 1
python main.py  # Connect to localhost:8765

# Terminal 3: Start client 2
python main.py  # Also connect to localhost:8765
```

### Embedded Server (Single Player)

```python
# Server starts automatically
game = NetworkGame(use_local_server=True)
await game.connect()  # Starts server, then connects
```

## Migration Checklist

- [x] Create server infrastructure (GameServer, WebSocketServer)
- [x] Create client infrastructure (WebSocketClient)
- [x] Create NetworkGame class
- [x] LocalServerManager for single-player
- [ ] Update main entry point to use NetworkGame
- [ ] Add UI for connection status
- [ ] Add UI for "not your turn" feedback
- [ ] Add reconnection logic
- [ ] Add game lobby/matchmaking

## Next Steps

1. **Update `__main__.py`** to instantiate `NetworkGame` instead of `Game`
2. **Add connection UI** showing connected players
3. **Add turn indicator** showing whose turn it is
4. **Test with two clients** connecting to same server
5. **Deploy server** for remote multiplayer

## Example Usage

See [`tests/test_network.py`](../tests/test_network.py) for headless `GameServer` construction (with `game_definition=`) and protocol-level join/action tests. For end-to-end browser flow, use `NetworkGame` with `use_local_server=True` against a repo checkout that includes `games/hexdemo`.

## Dependencies

```bash
# Required for networking
pip install websockets
```

The `hexes` package already depends on `websockets` for the server and client; optional **`dev`** extras add `pytest` and `ruff`.
