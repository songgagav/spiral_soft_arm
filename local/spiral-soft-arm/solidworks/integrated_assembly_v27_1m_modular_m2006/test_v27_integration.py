from __future__ import annotations

import builtins
import csv
from dataclasses import replace
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import cadquery as cq
from PIL import Image

from generate_v27_assembly import (
    _polar_center,
    _select_v25_electronics,
    audit_v27_assembly,
    build_v27_assembly,
    export_v27,
    preflight_v27,
    snapshot_v26_outputs,
)
from model_contract import load_contract
from render_v27 import render_v27


class V27ZZDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = Path(__file__).resolve().parent
        cls.repo_root = cls.directory.parents[3]
        cls.local_readme = cls.directory / "README.md"
        cls.root_readme = cls.repo_root / "README.md"
        cls.manifest = cls.directory / "来源与SHA256.csv"

    def test_delivery_manifest_is_complete_and_hashes_match(self) -> None:
        self.assertTrue(self.manifest.is_file())
        with self.manifest.open("r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        paths = [row["relative_path"] for row in rows]
        self.assertEqual(paths, sorted(paths))
        expected = {
            path.relative_to(self.repo_root).as_posix()
            for path in self.directory.iterdir()
            if path.is_file()
            and path.name != self.manifest.name
            and path.suffix.lower() in {".py", ".json", ".step", ".png", ".md"}
        }
        expected.add("README.md")
        contract = load_contract()
        for spec in contract.source_specs.values():
            expected.add(
                (contract.output_directory / spec["path"])
                .resolve()
                .relative_to(self.repo_root)
                .as_posix()
            )
        self.assertEqual(set(paths), expected)
        for row in rows:
            path = self.repo_root / row["relative_path"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(row["sha256"], digest)
            self.assertEqual(int(row["size_bytes"]), path.stat().st_size)

    def test_readme_lists_arm_and_drive_swap_sequences(self) -> None:
        text = self.local_readme.read_text(encoding="utf-8")
        self.assertIn("更换整根四段臂体模块", text)
        self.assertIn("更换三台 M2006 整板驱动模块", text)
        self.assertIn("零位/预紧标定", text)
        self.assertIn("C610 固定在电子/控制侧", text)
        self.assertIn("固定密封边界", text)

    def test_readme_lists_unverified_physical_gates(self) -> None:
        text = self.local_readme.read_text(encoding="utf-8")
        self.assertIn(
            "CAD does not prove printing, strength, 5 m water-tightness, 30-minute thermal behavior or 1 kg task success.",
            text,
        )
        for item in ("切片", "打印", "强度", "5 m", "30 分钟", "1 kg"):
            self.assertIn(item, text)

    def test_root_readme_links_v27_without_replacing_v26(self) -> None:
        text = self.root_readme.read_text(encoding="utf-8")
        self.assertIn("integrated_assembly_v27_1m_modular_m2006", text)
        self.assertIn("integrated_assembly_v26_arm_and_v25_electronics", text)


class V27PlacementHelperTests(unittest.TestCase):
    def test_polar_center_uses_standard_xy_rotation(self) -> None:
        x_mm, y_mm, z_mm = _polar_center(48.0, 120.0, -55.0)
        self.assertAlmostEqual(x_mm, -24.0)
        self.assertAlmostEqual(y_mm, 24.0 * 3.0**0.5)
        self.assertEqual(z_mm, -55.0)


class V27StepDeterminismTests(unittest.TestCase):
    def test_step_headers_use_frozen_timestamp(self) -> None:
        directory = Path(__file__).resolve().parent
        for name in (
            "SpiRobs_v27_1m_四段臂体模块.step",
            "SpiRobs_v27_M2006三电机驱动模块.step",
            "SpiRobs_v27_固定传动密封基座.step",
            "SpiRobs_v27_1m模块化总装.step",
        ):
            header = (directory / name).read_text(encoding="utf-8")[:512]
            self.assertIn("'2000-01-01T00:00:00'", header)


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
        self.assertTrue(
            {
                "arm_dovetail_lock_01",
                "arm_tip_tendon_anchor_01",
                "arm_terminal_adjustment_01",
                "arm_terminal_secondary_retention_01",
            }.issubset(self.result.arm_component_names)
        )
        self.assertIn("removable_motor_plate", self.result.drive_component_names)
        self.assertEqual(
            len([name for name in self.result.drive_component_names if name.startswith("removable_M2006_")]),
            3,
        )
        self.assertEqual(
            len([name for name in self.result.fixed_component_names if name.startswith("fixed_root_dowel_")]),
            2,
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
        self.assertGreaterEqual(self.audit["service"]["drive_sweep_sample_count"], 15)
        self.assertGreaterEqual(self.audit["service"]["drive_sweep_min_clearance_mm"], 0.25)

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
        audit_path = self.contract.output_directory / "V27装配审查.json"
        self.assertTrue(audit_path.is_file())

    def test_clean_checkout_electronics_selection_avoids_ignored_dependencies(self) -> None:
        real_open = builtins.open

        def guarded_open(file, *args, **kwargs):
            text = str(file).replace("\\", "/")
            if any(part in text for part in ("/motor_mount_v2/", "/paper_v1/", "/simulation/v3/")):
                raise AssertionError(f"ignored dependency opened: {text}")
            return real_open(file, *args, **kwargs)

        with patch("builtins.open", guarded_open):
            selected = _select_v25_electronics(self.contract)
        self.assertTrue(selected)

    def test_export_preflight_rejects_forbidden_collision(self) -> None:
        components = dict(self.result.components)
        components["removable_motor_plate"] = components["fixed_top_plate"]
        bad = replace(self.result, components=components)
        with self.assertRaisesRegex(ValueError, "preflight"):
            preflight_v27(bad)

    def test_same_group_and_rotating_pairs_are_audited(self) -> None:
        collisions = self.audit["collisions"]
        self.assertGreater(collisions["checked_pair_count"], 100)
        self.assertTrue(any("fixed_wet_spool" in pair[0] for pair in collisions["checked_same_group_pairs"]))

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
