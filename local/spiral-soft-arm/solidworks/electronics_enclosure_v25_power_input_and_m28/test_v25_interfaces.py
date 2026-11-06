from __future__ import annotations

import json
import importlib.util
import sys
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


class V25GeometryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = HERE / "generate_power_input.py"
        if not path.is_file():
            cls.generator = None
            return
        spec = importlib.util.spec_from_file_location("b32_v25_test_generator", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls.generator = module
        cls.components, cls.body_names = module.build_v25_components()

    def require_generator(self):
        self.assertIsNotNone(self.generator, "v25 geometry generator must exist")
        return self.generator

    def test_m28_cutter_has_drawing_flat_width_and_height(self) -> None:
        cutter = self.require_generator().build_m28_opening_cutter(-241.0, -226.0)
        bounds = cutter.BoundingBox()
        self.assertAlmostEqual(bounds.xlen, 26.2, places=3)
        self.assertAlmostEqual(bounds.ylen, 28.0, places=3)

    def test_recess_leaves_five_millimetre_mounting_land(self) -> None:
        generator = self.require_generator()
        lid = self.components["v25_bottom_lid_with_M28_recess"]
        probe = generator.cyl(0.2, -242.0, -228.0, 13.5, 0.0)
        material = lid.intersect(probe)
        self.assertAlmostEqual(material.BoundingBox().zlen, 5.0, places=2)

    def test_buck_and_m28_service_parts_are_named_and_valid(self) -> None:
        self.require_generator()
        components, bodies = self.components, self.body_names
        required = {
            "v25_buck_5v_envelope",
            "v25_buck_5v_shelf",
            "v25_M28_socket_body",
            "v25_M28_inside_flange",
            "v25_M28_male_plug_envelope",
            "v25_M28_service_clearance",
        }
        self.assertTrue(required.issubset(components))
        self.assertIn("v25_buck_5v_envelope", bodies)
        for name in required:
            self.assertTrue(components[name].isValid(), name)
        self.assertTrue(self.generator.build_m28_load_ring().isValid())

    def test_rear_mount_flange_and_load_ring_stay_inside_lid(self) -> None:
        self.require_generator()
        flange = self.components["v25_M28_inside_flange"].BoundingBox()
        ring = self.generator.build_m28_load_ring().BoundingBox()
        self.assertAlmostEqual(flange.zmin, -235.0, places=3)
        self.assertAlmostEqual(flange.zmax, -230.0, places=3)
        self.assertAlmostEqual(ring.zmin, -235.0, places=3)
        self.assertAlmostEqual(ring.zmax, -230.0, places=3)

    def test_full_audit_has_no_unexpected_volume_overlap(self) -> None:
        generator = self.require_generator()
        self.assertTrue(hasattr(generator, "audit_v25_components"),
                        "v25 generator must expose the final overlap audit")
        audit = generator.audit_v25_components(
            self.components, self.body_names
        )
        self.assertEqual(audit["hardware_to_hardware_volume_overlaps"], [])
        self.assertEqual(audit["internal_to_shell_volume_overlaps"], {})
        self.assertEqual(audit["buck_to_v24_hardware_volume_overlaps"], [])
        self.assertEqual(audit["m28_mount_land_mm"], 5.0)

    def test_export_reimports_both_step_files(self) -> None:
        generator = self.require_generator()
        self.assertTrue(hasattr(generator, "export_v25"),
                        "v25 generator must export and reimport both STEP files")
        result = generator.export_v25()
        self.assertTrue(result["electronics_step_valid"])
        self.assertTrue(result["full_assembly_step_valid"])
        self.assertGreater(result["electronics_step_solids"], 0)
        self.assertGreater(result["full_assembly_step_solids"], 0)
        for key in ("electronics_step", "full_assembly_step", "preview",
                    "m28_detail", "layout", "audit"):
            self.assertTrue((HERE / result[key]).is_file(), key)


if __name__ == "__main__":
    unittest.main()
