"""
Client-side **arcs** for browser startup (distinct from `hexengine.server.arcs`).

Server arcs are authority workflows in `GameState`. Client arcs orchestrate pre-match
UI and connect without mutating authoritative state.
"""

from __future__ import annotations

from .client_title_load import (
    CLIENT_TITLE_LOAD_CONNECT_PIPELINE,
    CLIENT_TITLE_LOAD_READY_STEP,
    ClientTitleLoadConnectHost,
    ClientTitleLoadConnectState,
    ClientTitleLoadStep,
    execute_client_title_load_connect_arc,
    execute_client_title_load_ready_segment,
)

__all__ = [
    "CLIENT_TITLE_LOAD_CONNECT_PIPELINE",
    "CLIENT_TITLE_LOAD_READY_STEP",
    "ClientTitleLoadConnectHost",
    "ClientTitleLoadConnectState",
    "ClientTitleLoadStep",
    "execute_client_title_load_connect_arc",
    "execute_client_title_load_ready_segment",
]
