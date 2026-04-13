"""RNG facade appends to GameState.rng_log."""

from __future__ import annotations

import unittest

from hexengine.gamedef.rng import RngService
from hexengine.state import GameState


class TestRngService(unittest.TestCase):
    def test_d6_appends_log(self) -> None:
        s0 = GameState.create_empty()
        s1, v = RngService.roll_d6(s0)
        self.assertTrue(1 <= v <= 6)
        self.assertEqual(len(s1.rng_log), 1)
        self.assertEqual(s1.rng_log[0]["kind"], "d6")

    def test_chain_rolls(self) -> None:
        s = GameState.create_empty()
        s, _ = RngService.roll_d6(s)
        s, _ = RngService.roll_2d6(s)
        s, _ = RngService.roll_percentile(s)
        self.assertEqual(len(s.rng_log), 3)


if __name__ == "__main__":
    unittest.main()
