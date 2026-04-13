"""GameRoot resolution and zip extraction."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from hexengine.gameroot import (
    cleanup_extracted_game_roots,
    resolve_scenario_path_with_game_root,
)
from hexengine.scenarios.load.parse import default_scenario_path


class TestGameRoot(unittest.TestCase):
    def tearDown(self) -> None:
        cleanup_extracted_game_roots()

    def test_scenario_file_argument(self) -> None:
        p = default_scenario_path()
        self.assertEqual(
            resolve_scenario_path_with_game_root(scenario_file=p).resolve(),
            p.resolve(),
        )

    def test_game_root_and_scenario_id(self) -> None:
        repo = Path(__file__).resolve().parent.parent
        game_dir = repo / "games" / "hexdemo"
        scenario_file = game_dir / "scenarios" / "skirmish" / "scenario.toml"
        if not scenario_file.is_file():
            self.skipTest("hexdemo skirmish scenario not present")

        resolved = resolve_scenario_path_with_game_root(
            game_root=game_dir,
            scenario_id="skirmish",
        )
        self.assertEqual(resolved.resolve(), scenario_file.resolve())

    def test_no_args_prefers_hexdemo_default(self) -> None:
        repo = Path(__file__).resolve().parent.parent
        expected = (
            repo / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
        )
        if not expected.is_file():
            self.skipTest("hexdemo default scenario not present")

        resolved = resolve_scenario_path_with_game_root()
        self.assertEqual(resolved.resolve(), expected.resolve())

    def test_resolve_hexdemo_from_cwd_when_bundled_lookup_fails(self) -> None:
        """Wheel in site-packages: ancestor walk misses `games/hexdemo`; cwd may still have it."""
        repo = Path(__file__).resolve().parent.parent
        src = repo / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
        if not src.is_file():
            self.skipTest("hexdemo default scenario not present")

        tmp = Path(tempfile.mkdtemp())
        try:
            dst = tmp / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
            with patch(
                "hexengine.gameroot._find_bundled_hexdemo_game_root", return_value=None
            ):
                old = os.getcwd()
                try:
                    os.chdir(tmp)
                    resolved = resolve_scenario_path_with_game_root()
                finally:
                    os.chdir(old)
            self.assertEqual(resolved.resolve(), dst.resolve())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_resolve_raises_when_no_game_pack_found(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        try:
            with (
                patch(
                    "hexengine.gameroot._find_bundled_hexdemo_game_root",
                    return_value=None,
                ),
                patch(
                    "hexengine.gameroot._find_hexdemo_game_root_from_cwd",
                    return_value=None,
                ),
            ):
                old = os.getcwd()
                try:
                    os.chdir(tmp)
                    with self.assertRaises(FileNotFoundError) as ctx:
                        resolve_scenario_path_with_game_root()
                    self.assertIn("No game scenario found", str(ctx.exception))
                finally:
                    os.chdir(old)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_scenario_id_only_uses_auto_hexdemo(self) -> None:
        repo = Path(__file__).resolve().parent.parent
        expected = (
            repo / "games" / "hexdemo" / "scenarios" / "skirmish" / "scenario.toml"
        )
        if not expected.is_file():
            self.skipTest("hexdemo skirmish scenario not present")

        resolved = resolve_scenario_path_with_game_root(scenario_id="skirmish")
        self.assertEqual(resolved.resolve(), expected.resolve())

    def test_zip_pack_resolves_scenario(self) -> None:
        repo = Path(__file__).resolve().parent.parent
        game_dir = repo / "games" / "hexdemo"
        scenario_file = game_dir / "scenarios" / "default" / "scenario.toml"
        if not scenario_file.is_file():
            self.skipTest("hexdemo scenario not present")

        zpath = Path(__file__).resolve().parent / "_tmp_hexdemo.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(
                scenario_file,
                arcname="scenarios/default/scenario.toml",
            )

        try:
            resolved = resolve_scenario_path_with_game_root(
                game_root=zpath,
                scenario_id="default",
            )
            self.assertTrue(resolved.is_file())
            self.assertEqual(resolved.name, "scenario.toml")
        finally:
            zpath.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
