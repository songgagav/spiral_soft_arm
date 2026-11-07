from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


class V26ParameterContractTests(unittest.TestCase):
    def load_params(self) -> dict:
        path = HERE / "parameters.json"
        self.assertTrue(path.is_file(), "V26 parameters must exist")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_contract_names_original_arm_and_v25_source(self) -> None:
        params = self.load_params()
        arm = params["original_arm"]
        self.assertEqual(arm["component_name"],
                         "B32_v10_arm_sections_and_dovetails")
        self.assertEqual(arm["solid_count"], 5)
        self.assertEqual(arm["root_z"], 0.0)
        self.assertTrue(params["source_generator"].endswith(
            "electronics_enclosure_v25_power_input_and_m28/generate_power_input.py"
        ))

    def test_contract_requires_three_drives_and_excludes_service_volume(self) -> None:
        params = self.load_params()
        self.assertEqual(params["required_drive_prefixes"],
                         ["drive_060_", "drive_180_", "drive_300_"])
        self.assertEqual(params["observation_only_components"],
                         ["v25_M28_service_clearance"])


class V26GeometryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = HERE / "generate_integrated_assembly.py"
        cls.generator_path = path
        cls.generator = None
        cls.components = None
        cls.body_names = None
        if path.is_file():
            spec = importlib.util.spec_from_file_location(
                "b32_v26_test_generator", path
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            cls.generator = module
            cls.components, cls.body_names = module.build_v26_components()

    def require_generator(self):
        self.assertTrue(self.generator_path.is_file(),
                        "V26 integration generator must exist")
        self.assertIsNotNone(self.generator)
        return self.generator

    def test_integrated_components_preserve_original_arm_geometry(self) -> None:
        generator = self.require_generator()
        components = self.components
        arm = components["B32_v10_arm_sections_and_dovetails"]
        bounds = arm.BoundingBox()
        self.assertEqual(len(arm.Solids()), 5)
        self.assertAlmostEqual(bounds.xmin, -33.945, places=2)
        self.assertAlmostEqual(bounds.xmax, 25.5, places=2)
        self.assertAlmostEqual(bounds.ymin, -33.328, places=2)
        self.assertAlmostEqual(bounds.ymax, 33.328, places=2)
        self.assertAlmostEqual(bounds.zmin, 0.0, places=3)
        self.assertAlmostEqual(bounds.zmax, 550.014, places=2)

    def test_integrated_components_include_v25_and_all_three_drives(self) -> None:
        generator = self.require_generator()
        components = self.components
        required = generator.P["required_components"]
        self.assertTrue(set(required).issubset(components))
        for prefix in generator.P["required_drive_prefixes"]:
            self.assertTrue(any(name.startswith(prefix) for name in components),
                            prefix)

    def test_physical_export_omits_observation_only_volume(self) -> None:
        generator = self.require_generator()
        components = self.components
        physical = generator.physical_v26_components(components)
        self.assertNotIn("v25_M28_service_clearance", physical)
        self.assertIn("v25_M28_socket_body", physical)

    def test_audit_reports_preserved_coordinates_and_required_parts(self) -> None:
        generator = self.require_generator()
        audit = generator.audit_v26_integration(
            self.components, self.body_names
        )
        self.assertEqual(audit["missing_required_components"], [])
        self.assertEqual(audit["missing_drive_prefixes"], [])
        self.assertEqual(audit["original_arm_solids"], 5)
        self.assertAlmostEqual(audit["arm_root_z_mm"], 0.0, places=3)
        self.assertAlmostEqual(audit["arm_to_electronics_gap_mm"], 8.0,
                               places=3)


if __name__ == "__main__":
    unittest.main()
