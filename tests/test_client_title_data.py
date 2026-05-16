"""Tests for `ClientTitleData` parsing of `StateUpdate.turn_rules`."""

from __future__ import annotations

import unittest

from hexengine.gamedef.client_title_data import ClientTitleData, FactionUiRow


class ClientTitleDataTests(unittest.TestCase):
    def test_empty_wire(self) -> None:
        self.assertEqual(ClientTitleData.from_turn_rules(None), ClientTitleData.empty())
        self.assertEqual(ClientTitleData.from_turn_rules({}), ClientTitleData.empty())

    def test_max_stack_and_keys(self) -> None:
        td = ClientTitleData.from_turn_rules(
            {
                "max_active_units_per_hex": 3,
                "movement_budget_attribute": " movement ",
                "title_state_extension_key": "hexdemo",
            }
        )
        self.assertEqual(td.max_active_units_per_hex, 3)
        self.assertEqual(td.movement_budget_attribute_key, "movement")
        self.assertEqual(td.title_state_extension_key, "hexdemo")

    def test_max_stack_invalid_omitted(self) -> None:
        for bad in (0, -1, "x", None):
            td = ClientTitleData.from_turn_rules({"max_active_units_per_hex": bad})
            self.assertIsNone(td.max_active_units_per_hex)

    def test_ui_highlight_classes(self) -> None:
        td = ClientTitleData.from_turn_rules(
            {
                "ui": {
                    "schema": 1,
                    "move_hex_class": " m ",
                    "retreat_hex_class": "r",
                    "retreat_through_hex_class": "rt",
                    "marker_hex_class": "mk",
                }
            }
        )
        hi = td.hex_highlights
        self.assertEqual(hi.move_hex_class, "m")
        self.assertEqual(hi.retreat_hex_class, "r")
        self.assertEqual(hi.retreat_through_hex_class, "rt")
        self.assertEqual(hi.marker_hex_class, "mk")

    def test_faction_ui_rows_and_css(self) -> None:
        td = ClientTitleData.from_turn_rules(
            {
                "faction_ui": {
                    "schema": 1,
                    "factions": [
                        {"id": "a", "label": "Alpha", "css_class": "c-a"},
                        {"id": "b", "label": "Bravo", "css_class": " c-b "},
                        {"bogus": True},
                        {"id": "", "label": "skip"},
                    ],
                    "css": " .x{}\n ",
                    "css_href": " /t.css ",
                }
            }
        )
        assert td.faction_ui is not None
        self.assertEqual(len(td.faction_ui.rows), 2)
        self.assertEqual(td.faction_ui.rows[0], FactionUiRow("a", "Alpha", "c-a"))
        self.assertEqual(td.faction_ui.rows[1], FactionUiRow("b", "Bravo", "c-b"))
        self.assertEqual(td.faction_ui.css_inline, ".x{}")
        self.assertEqual(td.faction_ui.css_href, "/t.css")
        self.assertIs(td.faction_ui.row_for("a"), td.faction_ui.rows[0])
        self.assertIsNone(td.faction_ui.row_for("z"))

    def test_faction_display_contract_error_dict_or_string(self) -> None:
        td = ClientTitleData.from_turn_rules(
            {
                "faction_display_contract_error": {
                    "schema": 1,
                    "text": " Missing labels ",
                }
            }
        )
        self.assertEqual(td.faction_display_contract_error, "Missing labels")
        td2 = ClientTitleData.from_turn_rules(
            {"faction_display_contract_error": " plain error "}
        )
        self.assertEqual(td2.faction_display_contract_error, "plain error")

    def test_client_contract_features(self) -> None:
        td = ClientTitleData.from_turn_rules(
            {
                "client_contract": {
                    "schema": 1,
                    "features": [
                        "retreat_obligations",
                        "",
                        "  zoc_hexes_for_unit  ",
                        3,
                    ],
                }
            }
        )
        self.assertEqual(
            td.client_contract_features,
            frozenset({"retreat_obligations", "zoc_hexes_for_unit"}),
        )


if __name__ == "__main__":
    unittest.main()
