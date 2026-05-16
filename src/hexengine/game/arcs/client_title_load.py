"""
Client **title-load arc**: connect-time startup before the first authoritative state.

**Arc segment** — one ordered step the engine runs (resolve scenario, boot local server,
open WebSocket, dismiss splash). Segments are not pack code; they are orchestration.

**Pack hook** — optional callable declared in `[hooks.title_load]` and invoked from
specific segments (today: splash and setup). The manifest names the module and callables;
the arc decides *when* each hook runs.

Multiplayer note: every browser client runs this connect arc independently when
`Game.connect()` runs. Pack hooks therefore run per client (splash/setup UI is local).
The server runs a separate one-shot hook (`on_server_loaded`) after authoritative load;
it does not coordinate splash timing across players yet.

See `hexengine.server.arcs` for in-match authority arcs (movement, attack, cleanup).

Hook validation is intentionally loose today; see `docs/TITLE_LOAD_HOOKS.md` and the
cross-cutting plan in `docs/PACK_HOOK_CONTRACTS.md`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class ClientTitleLoadStep(StrEnum):
    """Named segments of the client title-load arc."""

    RESOLVE_SCENARIO = "resolve_scenario"
    SPLASH = "splash"
    SETUP = "setup"
    BOOT_LOCAL_SERVER = "boot_local_server"
    CONNECT_WS = "connect_ws"
    READY = "ready"


CLIENT_TITLE_LOAD_CONNECT_PIPELINE: tuple[ClientTitleLoadStep, ...] = (
    ClientTitleLoadStep.RESOLVE_SCENARIO,
    ClientTitleLoadStep.SPLASH,
    ClientTitleLoadStep.SETUP,
    ClientTitleLoadStep.BOOT_LOCAL_SERVER,
    ClientTitleLoadStep.CONNECT_WS,
)

CLIENT_TITLE_LOAD_READY_STEP = ClientTitleLoadStep.READY


@dataclass
class ClientTitleLoadConnectState:
    """Mutable carry-over between connect arc segments on one `Game.connect()` call."""

    scenario_path: Path | None = None
    preloaded_unit_graphics: dict[str, Any] | None = None
    preloaded_marker_graphics: dict[str, Any] | None = None
    preloaded_markers: list[dict[str, Any]] | None = None
    aborted: bool = False


class ClientTitleLoadConnectHost(Protocol):
    """Surface `Game` implements for the connect-time title-load arc."""

    logger: logging.Logger
    use_local_server: bool

    @property
    def local_server(self) -> Any | None: ...

    def title_load_reset_for_connect(self) -> None: ...

    def title_load_resolve_scenario(self) -> Path | None: ...

    def title_load_invoke_splash_hook(self, scenario_path: Path) -> None: ...

    def title_load_invoke_setup_hook(self, scenario_path: Path) -> bool: ...

    def title_load_boot_local_server(
        self, scenario_path: Path, state: ClientTitleLoadConnectState
    ) -> bool: ...

    def title_load_prepare_websocket_client(
        self, state: ClientTitleLoadConnectState
    ) -> None: ...

    def title_load_begin_websocket_connect(
        self, state: ClientTitleLoadConnectState
    ) -> None: ...

    def title_load_on_connect_failed(self) -> None: ...

    @property
    def title_load_splash_dismissed(self) -> bool: ...

    def title_load_mark_splash_dismissed(self) -> None: ...


def _run_connect_segment(
    step: ClientTitleLoadStep,
    host: ClientTitleLoadConnectHost,
    state: ClientTitleLoadConnectState,
) -> bool:
    """Run one connect pipeline segment. Returns False to abort the arc."""
    match step:
        case ClientTitleLoadStep.RESOLVE_SCENARIO:
            state.scenario_path = host.title_load_resolve_scenario()
            return True
        case ClientTitleLoadStep.SPLASH:
            if state.scenario_path is not None:
                host.title_load_invoke_splash_hook(state.scenario_path)
            return True
        case ClientTitleLoadStep.SETUP:
            if state.scenario_path is None:
                return True
            return host.title_load_invoke_setup_hook(state.scenario_path)
        case ClientTitleLoadStep.BOOT_LOCAL_SERVER:
            if not host.use_local_server or host.local_server is not None:
                return True
            if state.scenario_path is None:
                state.scenario_path = host.title_load_resolve_scenario()
            if state.scenario_path is None:
                return True
            ok = host.title_load_boot_local_server(state.scenario_path, state)
            if not ok:
                state.aborted = True
            return ok
        case ClientTitleLoadStep.CONNECT_WS:
            host.title_load_prepare_websocket_client(state)
            host.title_load_begin_websocket_connect(state)
            return True
        case ClientTitleLoadStep.READY:
            return True
        case _:
            logger.warning("unknown client title-load step %r", step)
            return True


def execute_client_title_load_connect_arc(host: ClientTitleLoadConnectHost) -> bool:
    """
    Run connect-time title-load segments through WebSocket connect initiation.

    Pack hooks run only on SPLASH and SETUP segments. Returns False when setup aborts
    or local server boot fails.
    """
    host.title_load_reset_for_connect()
    state = ClientTitleLoadConnectState()
    for step in CLIENT_TITLE_LOAD_CONNECT_PIPELINE:
        if not _run_connect_segment(step, host, state):
            host.title_load_on_connect_failed()
            return False
    return True


def execute_client_title_load_ready_segment(host: ClientTitleLoadConnectHost) -> None:
    """
    Run the READY segment after the first authoritative `StateUpdate`.

    Applies title CSS first on the host, then dismisses splash (see `Game`).
    """
    if host.title_load_splash_dismissed:
        return
    host.title_load_mark_splash_dismissed()
    from ..title_load_ui import dismiss_splash_after_ready

    dismiss_splash_after_ready()


__all__ = [
    "CLIENT_TITLE_LOAD_CONNECT_PIPELINE",
    "CLIENT_TITLE_LOAD_READY_STEP",
    "ClientTitleLoadConnectHost",
    "ClientTitleLoadConnectState",
    "ClientTitleLoadStep",
    "execute_client_title_load_connect_arc",
    "execute_client_title_load_ready_segment",
]
