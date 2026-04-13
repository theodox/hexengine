"""Scenario TOML load errors surface source line context."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hexengine.scenarios import load_scenario


def test_load_scenario_valueerror_includes_line_and_caret(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "broken"
            bad_token = not_a_valid_toml_value
            """
        ).strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as ei:
        load_scenario(p)
    msg = str(ei.value)
    assert "TOML syntax error" in msg
    assert str(p.resolve()) in msg or str(p) in msg
    assert "bad_token" in msg
    assert "Line 2:" in msg
    assert "^" in msg
