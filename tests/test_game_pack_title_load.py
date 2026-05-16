"""Pack manifest title_load hooks and resource helpers."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEXDEMO_SCENARIO = (
    REPO_ROOT / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
)


def test_read_pack_resource_text_rejects_traversal(tmp_path: Path) -> None:
    from hexengine.game_packs.resources import read_pack_resource_text

    resources = tmp_path / "resources"
    resources.mkdir()
    (resources / "ok.txt").write_text("hello", encoding="utf-8")
    assert read_pack_resource_text(tmp_path, "ok.txt") == "hello"
    assert read_pack_resource_text(tmp_path, "../ok.txt") is None
    assert read_pack_resource_text(tmp_path, "missing.txt") is None


def _ensure_games_on_path() -> None:
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)


def test_title_load_headless_callables_do_not_crash() -> None:
    _ensure_games_on_path()
    from hexdemo.hooks import title_load as boot

    from hexengine.gamedef.title_load import TitleLoadContext

    boot.present_splash("<b>test</b>")
    ctx = TitleLoadContext(
        pack_id="hexdemo",
        pack_root=REPO_ROOT / "games" / "hexdemo",
        scenario_path=HEXDEMO_SCENARIO,
    )
    out = boot.run_setup(ctx)
    assert out.continue_connect is True


def test_run_title_load_splash_headless() -> None:
    from hexengine.gameroot import run_title_load_splash

    run_title_load_splash(HEXDEMO_SCENARIO)


def test_run_title_load_setup_returns_true() -> None:
    from hexengine.gameroot import run_title_load_setup

    assert run_title_load_setup(HEXDEMO_SCENARIO) is True
