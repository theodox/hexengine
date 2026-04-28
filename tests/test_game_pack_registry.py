"""Manifest-driven game pack discovery (hexengine.game_packs.registry)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hexengine.game_packs import registry


@pytest.fixture(autouse=True)
def _reset_pack_registry() -> None:
    registry.reset_game_pack_registry_for_tests()
    yield
    registry.reset_game_pack_registry_for_tests()


def test_resolve_pack_prefers_longest_root(tmp_path: Path) -> None:
    outer = tmp_path / "outergame"
    inner = outer / "innergame"
    (inner / "scenarios" / "s").mkdir(parents=True)
    scenario = inner / "scenarios" / "s" / "scenario.toml"
    scenario.write_text("# stub", encoding="utf-8")

    (outer / "hexengine_pack.toml").write_text(
        textwrap.dedent(
            """
            manifest_version = 1
            [pack]
            id = "outergame"
            title = "Outer"
            [python]
            path_add = "."
            entry_module = "dummy"
            entry_callable = "load_game_definition"
            """
        ).strip(),
        encoding="utf-8",
    )
    (inner / "hexengine_pack.toml").write_text(
        textwrap.dedent(
            """
            manifest_version = 1
            [pack]
            id = "innergame"
            title = "Inner"
            [python]
            path_add = "."
            entry_module = "dummy"
            entry_callable = "load_game_definition"
            """
        ).strip(),
        encoding="utf-8",
    )

    rec = registry.resolve_pack_for_scenario(scenario)
    assert rec.manifest.pack_id == "innergame"


def test_load_game_definition_via_manifest_entry(tmp_path: Path) -> None:
    root = tmp_path / "minipack"
    (root / "scenarios" / "one").mkdir(parents=True)
    scenario = root / "scenarios" / "one" / "scenario.toml"
    scenario.write_text("# stub", encoding="utf-8")

    (root / "minipack_py").mkdir()
    eng = root / "minipack_py" / "engine_entry.py"
    eng.write_text(
        textwrap.dedent(
            """
            from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition

            def load_game_definition():
                return InterleavedTwoFactionGameDefinition()
            """
        ).strip(),
        encoding="utf-8",
    )
    (root / "minipack_py" / "__init__.py").write_text("", encoding="utf-8")

    (root / "hexengine_pack.toml").write_text(
        textwrap.dedent(
            f"""
            manifest_version = 1
            [pack]
            id = "minipack"
            title = "Mini"
            [python]
            path_add = "."
            entry_module = "minipack_py.engine_entry"
            entry_callable = "load_game_definition"
            """
        ).strip(),
        encoding="utf-8",
    )

    gd = registry.load_game_definition_for_scenario_path(scenario)
    assert gd.available_factions() == ["Red", "Blue"]
