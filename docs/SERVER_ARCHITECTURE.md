# Multiplayer Server Architecture

## Overview

The game uses a **server-authoritative** architecture where:
- Server owns the canonical `GameState` via `ActionManager`
- Clients send action requests to server
- Server validates and executes actions
- Server broadcasts state updates to all clients
- Clients render the state they receive

This architecture works identically for single-player (client connects to local server) and multiplayer (multiple clients connect to remote server).

## Components

### Server Layer (`hexengine.server`)

**`GameServer`** - Transport-agnostic game logic
- Owns `ActionManager` (single source of truth)
- Validates action requests (turn order, legality)
- Executes actions and broadcasts state
- Manages player connections and faction assignments
- Requires a **`game_definition`** (`GameDefinition` keyword argument): turn schedule, phases, and `available_factions()` come from the title (or from a built-in demo definition in tests), not from implicit engine defaults.

**`WebSocketGameServer`** - WebSocket transport layer
- Wraps `GameServer` with WebSocket handling
- Routes messages between clients and `GameServer`
- Manages WebSocket connections
- Passes **`game_definition=`** through to `GameServer` (required).

**`protocol.py`** - Communication protocol
- Defines message types (ACTION_REQUEST, STATE_UPDATE, etc.)
- Serialization/deserialization (JSON)
- Message structures (ActionRequest, StateUpdate, etc.)

## Message Flow

### Client Sends Action

```
Client                    WebSocket Server              GameServer
  |                              |                           |
  |--MoveUnit action------------>|                           |
  |                              |--handle_message()--------->|
  |                              |                           |
  |                              |                      Validate turn
  |                              |                      Execute action
  |                              |                           |
  |<-ActionResult(success)-------|<--------------------------|
  |                              |                           |
  |<-StateUpdate (new state)-----|<--broadcast_state_update--|
  |                              |                           |
```

### Player Joins Game

```
Client                    WebSocket Server              GameServer
  |                              |                           |
  |--JoinGameRequest------------>|                           |
  |                              |--handle_message()--------->|
  |                              |                           |
  |                              |                    Assign faction
  |                              |                    Register player
  |                              |                           |
  |<-StateUpdate (full state)----|<--------------------------|
  |                              |                           |
  |                              |--broadcast_player_joined->|
  |                              |                           |
```

## Protocol Messages

### Client → Server

**JOIN_GAME**
```json
{
  "type": "join_game",
  "payload": {
    "player_name": "Alice",
    "faction": "Blue"  // optional, auto-assigned if null
  }
}
```

**ACTION_REQUEST**
```json
{
  "type": "action_request",
  "payload": {
    "action_type": "MoveUnit",
    "player_id": "player-uuid",
    "params": {
      "unit_id": "tank-1",
      "from_hex": {"i": 0, "j": 0, "k": 0},
      "to_hex": {"i": 1, "j": 0, "k": -1}
    }
  }
}
```

### Server → Client

**STATE_UPDATE**
```json
{
  "type": "state_update",
  "payload": {
    "game_state": {
      "board": { ... },
      "turn": { ... }
    },
    "sequence_number": 42
  }
}
```

**ACTION_RESULT**
```json
{
  "type": "action_result",
  "payload": {
    "success": true,
    "action_id": "action-uuid"
  }
}
```

**ERROR**
```json
{
  "type": "error",
  "payload": {
    "error": "Not your turn (current: Blue)"
  }
}
```

## Server Validation

The server validates every action:

1. **Authentication** - Is the player in the game?
2. **Turn Order** - Is it this player's turn?
3. **Action Legality** - Is the action valid in current state?
4. **State Consistency** - Does the action match expected state?

Invalid actions are rejected with an error message.

## Single Player Setup

For single-player, [`Game`](../src/hexengine/game/game.py) with `use_local_server=True` resolves a game pack scenario, builds a `GameDefinition` from that pack, constructs initial state and presentation dicts, and starts [`LocalServerManager`](../src/hexengine/client/local_server.py) with **`game_definition=`** set. The client then connects to `localhost` over the same WebSocket protocol as multiplayer.

Each [`StateUpdate`](../src/hexengine/server/protocol.py) includes **`turn_rules`** (schedule, factions, movement budget) so the client can build a matching builtin `GameDefinition` for UI such as manual phase advance without resolving game files on disk. Switching to another title is assumed to be a rare, prepared event (full reload or new session).

If no supported game pack / scenario can be resolved (for example no `games/hexdemo` on disk when using defaults), startup fails rather than falling back to engine-packaged demo scenarios.

## Running the Server

### Standalone WebSocket Server

```bash
python -m hexengine.server.websocket_server
```

Listens on **`ws://0.0.0.0:8765`** (all interfaces). The module resolves a scenario via [`resolve_scenario_path_with_game_root`](../src/hexengine/gameroot.py) (optional CLI: `--scenario-file`, `--game-root`, `--scenario-id`, `--schedule`), loads title rules with [`load_game_definition_for_scenario`](../src/hexengine/gameroot.py), then starts `WebSocketGameServer` with that definition. If resolution or title loading fails, the process exits with an error.

### Custom Setup

**Typical (title pack + scenario on disk)** — mirror of [`websocket_server.main`](../src/hexengine/server/websocket_server.py):

```python
import asyncio

from hexengine.gameroot import (
    initial_faction_for_game_definition,
    load_game_definition_for_scenario,
    resolve_scenario_path_with_game_root,
)
from hexengine.scenarios import load_scenario
from hexengine.scenarios.loader import scenario_to_initial_state
from hexengine.server import GameServer, WebSocketGameServer

scenario_path = resolve_scenario_path_with_game_root()
scenario_data = load_scenario(scenario_path)
game_def = load_game_definition_for_scenario(scenario_path, schedule="interleaved")
first_faction = initial_faction_for_game_definition(game_def)
initial_state = scenario_to_initial_state(
    scenario_data,
    initial_faction=first_faction,
    initial_phase="Movement",
    phase_actions_remaining=2,
)

map_d = scenario_data.map_display.to_wire_dict()
styles_d = scenario_data.global_styles.to_wire_dict()
units_d = scenario_data.unit_graphics_to_wire_dict()
markers_d = scenario_data.marker_graphics_to_wire_dict()
markers_list = scenario_data.markers_to_wire_list()

# Transport-agnostic headless server
game_server = GameServer(
    initial_state,
    map_display=map_d,
    global_styles=styles_d,
    unit_graphics=units_d,
    marker_graphics=markers_d,
    markers=markers_list,
    game_definition=game_def,
)

# WebSocket server (same state + presentation + definition)
ws_server = WebSocketGameServer(
    host="0.0.0.0",
    port=8765,
    initial_state=initial_state,
    map_display=map_d,
    global_styles=styles_d,
    unit_graphics=units_d,
    marker_graphics=markers_d,
    markers=markers_list,
    game_definition=game_def,
)
asyncio.run(ws_server.start())
```

**Minimal (engine tests / Red–Blue schedule only)** — no title pack; use [`InterleavedTwoFactionGameDefinition`](../src/hexengine/gamedef/builtin.py) and an empty or hand-built `GameState`:

```python
from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition
from hexengine.server import GameServer
from hexengine.state import GameState

game_def = InterleavedTwoFactionGameDefinition()
initial_state = GameState.create_empty()
game_server = GameServer(initial_state, game_definition=game_def)
```

## Client Integration

The client needs minimal changes:

1. **Connect to server** (local or remote)
2. **Send actions** instead of executing directly
3. **Listen for state updates** and render
4. **Preview locally** (same as before, just don't send invalid actions)

```python
# OLD: Direct execution
action_mgr.execute(MoveUnit(...))

# NEW: Send to server
action_request = ActionRequest(
    action_type="MoveUnit",
    params={...},
    player_id=my_id
)
send_to_server(action_request.to_message())

# Listen for response
on_state_update(new_state):
    display_mgr.sync_from_state(new_state)
```

## Security Considerations

Current implementation is basic. For production:

- [ ] Add authentication/authorization
- [ ] Encrypt WebSocket connection (WSS)
- [ ] Rate limiting
- [ ] Input validation
- [ ] Session management
- [ ] Reconnection handling with state sync

## Dependencies

The `hexes` package declares **`websockets>=12.0`** as a core dependency in `pyproject.toml`. Optional **`dev`** extras include `pytest` and `ruff` for working on the repo.

## Next Steps

1. Create client-side WebSocket wrapper
2. Update mouse handlers to send actions to server
3. Add reconnection logic
4. Implement spectator mode
5. Add game lobby for matchmaking
