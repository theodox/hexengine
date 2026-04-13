"""Unit display sizing matches map CSS --unit-width formula."""

from hexengine.map.layout import unit_display_pixel_size


def test_unit_display_pixel_size_default_multiplier() -> None:
    assert unit_display_pixel_size(24.0, 1.5) == max(1, int(24.0 * 1.5) - 2) == 34


def test_unit_display_pixel_size_hexdemo_style() -> None:
    assert unit_display_pixel_size(24.0, 1.0) == 22
