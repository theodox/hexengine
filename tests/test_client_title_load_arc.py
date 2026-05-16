"""Client title-load arc pipeline and segment dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hexengine.game.arcs.client_title_load import (
    CLIENT_TITLE_LOAD_CONNECT_PIPELINE,
    CLIENT_TITLE_LOAD_READY_STEP,
    ClientTitleLoadConnectState,
    ClientTitleLoadStep,
    execute_client_title_load_connect_arc,
    execute_client_title_load_ready_segment,
)


class _FakeTitleLoadHost:
    logger: Any = None
    use_local_server = False
    local_server = None

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._splash_dismissed = False
        self.setup_continue = True

    def title_load_reset_for_connect(self) -> None:
        self.calls.append("reset")

    def title_load_resolve_scenario(self) -> Path | None:
        self.calls.append("resolve")
        return Path("/tmp/scenario.toml")

    def title_load_invoke_splash_hook(self, scenario_path: Path) -> None:
        self.calls.append(f"splash:{scenario_path}")

    def title_load_invoke_setup_hook(self, scenario_path: Path) -> bool:
        self.calls.append(f"setup:{scenario_path}")
        return self.setup_continue

    def title_load_boot_local_server(
        self, scenario_path: Path, state: ClientTitleLoadConnectState
    ) -> bool:
        self.calls.append(f"boot:{scenario_path}")
        return True

    def title_load_prepare_websocket_client(
        self, state: ClientTitleLoadConnectState
    ) -> None:
        self.calls.append("prepare_ws")

    def title_load_begin_websocket_connect(
        self, state: ClientTitleLoadConnectState
    ) -> None:
        self.calls.append("connect_ws")

    def title_load_on_connect_failed(self) -> None:
        self.calls.append("failed")

    @property
    def title_load_splash_dismissed(self) -> bool:
        return self._splash_dismissed

    def title_load_mark_splash_dismissed(self) -> None:
        self._splash_dismissed = True
        self.calls.append("mark_dismissed")


def test_connect_pipeline_order() -> None:
    assert CLIENT_TITLE_LOAD_CONNECT_PIPELINE == (
        ClientTitleLoadStep.RESOLVE_SCENARIO,
        ClientTitleLoadStep.SPLASH,
        ClientTitleLoadStep.SETUP,
        ClientTitleLoadStep.BOOT_LOCAL_SERVER,
        ClientTitleLoadStep.CONNECT_WS,
    )
    assert CLIENT_TITLE_LOAD_READY_STEP == ClientTitleLoadStep.READY


def test_connect_arc_runs_segments_in_order() -> None:
    host = _FakeTitleLoadHost()
    assert execute_client_title_load_connect_arc(host) is True
    assert host.calls[0] == "reset"
    assert host.calls[1] == "resolve"
    assert host.calls[2].startswith("splash:")
    assert host.calls[3].startswith("setup:")
    assert "prepare_ws" in host.calls
    assert host.calls[-1] == "connect_ws"


def test_connect_arc_aborts_when_setup_returns_false() -> None:
    host = _FakeTitleLoadHost()
    host.setup_continue = False
    assert execute_client_title_load_connect_arc(host) is False
    assert "failed" in host.calls
    assert "prepare_ws" not in host.calls


def test_ready_segment_marks_dismissed_once() -> None:
    host = _FakeTitleLoadHost()
    execute_client_title_load_ready_segment(host)
    assert host.title_load_splash_dismissed
    assert "mark_dismissed" in host.calls
    host.calls.clear()
    execute_client_title_load_ready_segment(host)
    assert "mark_dismissed" not in host.calls
