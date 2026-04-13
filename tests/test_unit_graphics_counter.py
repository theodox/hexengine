"""Unit graphics: counter render (TOML + wire dict)."""

from __future__ import annotations

from pathlib import Path

from hexengine.scenarios import load_scenario


def test_parse_unit_graphics_counter_row(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        '\nname = "t"\n'
        'description = ""\n'
        "[[terrain_types]]\n"
        'terrain = "plain"\n'
        "movement_cost = 1.0\n"
        "default = true\n"
        "[map]\n"
        "hex_columns = 2\n"
        "hex_rows = 2\n"
        "[[terrain_groups]]\n"
        'terrain = "plain"\n'
        "positions = [ [0, 0] ]\n"
        "[[unit_graphics]]\n"
        'type = "soldier"\n'
        'render = "counter"\n'
        'glyph = "X"\n'
        'caption = "9"\n'
        'counter_fill = "#112233"\n'
        'counter_fill_hover = "#334455"\n'
        'counter_fill_hilite = "#ff00aa"\n',
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert "soldier" in data.unit_graphics
    ug = data.unit_graphics["soldier"]
    assert ug.render == "counter"
    assert ug.glyph == "X"
    assert ug.caption == "9"
    assert ug.counter_fill == "#112233"
    assert ug.counter_fill_hover == "#334455"
    assert ug.counter_fill_hilite == "#ff00aa"


def test_unit_graphics_template_wire_includes_counter_fields() -> None:
    from hexengine.scenarios.schema import UnitGraphicsTemplate

    t = UnitGraphicsTemplate(
        unit_type="soldier",
        render="counter",
        glyph="G",
        caption="c",
        counter_fill="#aabbcc",
        counter_fill_hilite="#ddeeff",
    )
    w = t.to_wire_dict()
    assert w["render"] == "counter"
    assert w["glyph"] == "G"
    assert w["caption"] == "c"
    assert w["counter_fill"] == "#aabbcc"
    assert "counter_fill_hover" not in w
    assert w["counter_fill_hilite"] == "#ddeeff"
