from __future__ import annotations

import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


class V25ParameterContractTests(unittest.TestCase):
    def load_params(self) -> dict:
        path = HERE / "parameters.json"
        self.assertTrue(path.is_file(), "v25 parameters.json must exist")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_buck_envelope_matches_selected_module(self) -> None:
        buck = self.load_params()["hardware"]["buck_5v"]
        self.assertEqual(buck["size"], [42.0, 24.0, 5.0])
        self.assertEqual(buck["input_voltage_v"], [5.0, 35.0])
        self.assertEqual(buck["rated_current_a_user_confirmed"], 20.0)
        self.assertEqual(buck["output_role"], "STM32 5 V supply")

    def test_m28_panel_interface_matches_supplied_drawing(self) -> None:
        m28 = self.load_params()["hardware"]["m28_power"]
        self.assertEqual(m28["panel_opening_flat_width"], 26.2)
        self.assertEqual(m28["panel_opening_height"], 28.0)
        self.assertEqual(m28["mounting_body_diameter"], 27.8)
        self.assertEqual(m28["outside_flange_diameter"], 36.0)
        self.assertEqual(m28["effective_panel_thickness"], 5.0)

    def test_m28_service_envelope_matches_supplied_drawing(self) -> None:
        m28 = self.load_params()["hardware"]["m28_power"]
        self.assertEqual(m28["socket_axial_envelope"], 38.5)
        self.assertEqual(m28["plug_envelope"], [33.0, 71.5])
        self.assertEqual(m28["wire_section_mm2"], [2.5, 6.0])


if __name__ == "__main__":
    unittest.main()
