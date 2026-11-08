from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

import cadquery as cq
from PIL import Image

from generate_v27_assembly import (
    _polar_center,
    audit_v27_assembly,
    build_v27_assembly,
    export_v27,
    snapshot_v26_outputs,
)
from model_contract import load_contract
from render_v27 import render_v27


class V27PlacementHelperTests(unittest.TestCase):
    def test_polar_center_uses_standard_xy_rotation(self) -> None:
        x_mm, y_mm, z_mm = _polar_center(48.0, 120.0, -55.0)
        self.assertAlmostEqual(x_mm, -24.0)
        self.assertAlmostEqual(y_mm, 24.0 * 3.0**0.5)
        self.assertEqual(z_mm, -55.0)


class V27IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract()
        cls.v26_before = snapshot_v26_outputs(cls.contract)
        cls.result = build_v27_assembly(cls.contract)
        cls.audit = audit_v27_assembly(cls.result)
        cls.exports = export_v27(cls.result)
        cls.images = render_v27(cls.result)

    def test_required_three_module_components_exist(self) -> None:
        self.assertEqual(len(self.result.arm_component_names), 8)
        self.assertIn("removable_motor_plate", self.result.drive_component_names)
        self.assertEqual(
            len([name for name in self.result.drive_component_names if name.startswith("removable_M2006_")]),
            3,
        )
        self.assertEqual(
            len([name for name in self.result.fixed_component_names if name.startswith("fixed_wet_spool_")]),
            3,
        )

    def test_v25_electronics_are_selected_without_m3508_drive(self) -> None:
        names = self.result.electronics_component_names
        self.assertTrue(any("STM32" in name for name in names))
        self.assertTrue(any("21700" in name for name in names))
        self.assertEqual(len([name for name in names if "C610" in name]), 3)
        self.assertFalse(any("M3508" in name or "C620" in name for name in names))

    def test_no_component_name_uses_m3508(self) -> None:
        self.assertFalse(any("M3508" in name for name in self.result.components))

    def test_v26_outputs_are_not_modified(self) -> None:
        self.assertEqual(self.v26_before, snapshot_v26_outputs(self.contract))

    def test_fixed_and_removable_ownership_survives_integration(self) -> None:
        self.assertTrue(all(name.startswith("removable_") for name in self.result.drive_component_names))
        self.assertTrue(all(name.startswith("fixed_") for name in self.result.fixed_component_names))
        self.assertFalse(any("C610" in name for name in self.result.drive_component_names))

    def test_no_forbidden_solid_intersections(self) -> None:
        self.assertEqual(self.audit["collisions"]["forbidden"], [])
        self.assertTrue(self.audit["collisions"]["intentional_contacts"])

    def test_arm_can_translate_out_after_fasteners_and_terminals_removed(self) -> None:
        self.assertTrue(self.audit["service"]["arm_positive_z_removal_clear"])

    def test_drive_plate_can_translate_out_after_couplings_released(self) -> None:
        self.assertTrue(self.audit["service"]["drive_negative_z_removal_clear"])

    def test_all_service_fasteners_have_tool_envelopes(self) -> None:
        self.assertEqual(self.audit["service"]["root_fastener_tool_envelopes"], 6)
        self.assertTrue(self.audit["service"]["all_tool_envelopes_valid"])

    def test_fixed_shafts_remain_supported_in_drive_removed_state(self) -> None:
        self.assertTrue(self.audit["service"]["fixed_shafts_supported_without_drive"])
        self.assertEqual(self.audit["service"]["fixed_shaft_support_pair_count"], 3)

    def test_export_creates_four_named_step_outputs(self) -> None:
        self.assertEqual(
            {path.name for path in self.exports.values()},
            {
                "SpiRobs_v27_1m_四段臂体模块.step",
                "SpiRobs_v27_M2006三电机驱动模块.step",
                "SpiRobs_v27_固定传动密封基座.step",
                "SpiRobs_v27_1m模块化总装.step",
            },
        )
        self.assertTrue(all(path.is_file() and path.stat().st_size > 0 for path in self.exports.values()))

    def test_full_step_readback_has_valid_solids_and_bounds(self) -> None:
        full = cq.importers.importStep(str(self.exports["full_assembly"])).val()
        bounds = full.BoundingBox()
        self.assertTrue(full.isValid())
        self.assertGreater(len(full.Solids()), 20)
        self.assertGreaterEqual(bounds.zmax, 999.0)
        self.assertLessEqual(bounds.zmin, -239.0)

    def test_audit_contains_alignment_load_and_source_sections(self) -> None:
        for key in ("alignment", "engineering", "sources", "collisions", "service"):
            self.assertIn(key, self.audit)
        self.assertEqual(len(self.audit["alignment"]), 3)
        self.assertFalse(self.audit["engineering"]["qualified"])
        self.assertTrue(all(len(record["sha256"]) == 64 for record in self.audit["sources"].values()))

    def test_status_is_candidate_not_release(self) -> None:
        status = self.audit["status"].lower()
        self.assertIn("candidate", status)
        for forbidden in ("validated", "qualified", "print-ready", "waterproof"):
            self.assertNotIn(forbidden, status)

    def test_four_review_images_are_nonempty(self) -> None:
        self.assertEqual(
            set(self.images),
            {"full_transparent", "exploded_modules", "root_quick_change", "drive_section"},
        )
        for path in self.images.values():
            self.assertTrue(path.is_file() and path.stat().st_size > 10_000)
            with Image.open(path) as image:
                self.assertGreaterEqual(image.width, 1200)
                self.assertGreaterEqual(image.height, 800)


if __name__ == "__main__":
    unittest.main()
