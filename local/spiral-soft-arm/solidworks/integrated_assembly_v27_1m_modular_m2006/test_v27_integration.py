from __future__ import annotations

import builtins
import csv
from dataclasses import replace
import hashlib
import json
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
from arm_module import _root_transition_points
from preprint_review.build_preprint_coupons import build_tendon_transition_ladder


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
            for path in self.directory.rglob("*")
            if path.is_file()
            and path.name != self.manifest.name
            and path.suffix.lower()
            in {".py", ".json", ".step", ".stl", ".png", ".md", ".docx", ".pdf"}
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
        snapshot_path = self.repo_root / "v27_electronics_snapshot" / "V27电子件快照.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        for collection in ("components", "service_clearances"):
            for component in snapshot[collection]:
                expected.add(
                    (snapshot_path.parent / component["file"])
                    .relative_to(self.repo_root)
                    .as_posix()
                )
        for source in snapshot["source_files"].values():
            expected.add(
                (self.repo_root / source["path"])
                .resolve()
                .relative_to(self.repo_root)
                .as_posix()
            )
        v26_parameters = (
            self.directory.parent
            / "integrated_assembly_v26_arm_and_v25_electronics"
            / "parameters.json"
        )
        expected.add(v26_parameters.relative_to(self.repo_root).as_posix())
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
        self.assertIn("拆下固定六边形根部护圈", text)
        self.assertIn("臂体正 Z 连续抽出扫掠", text)
        self.assertIn("驱动板负 Z 连续抽出扫掠", text)
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

    def test_preprint_review_records_both_removal_path_sweeps(self) -> None:
        review = self.directory / "preprint_review" / "V27打印前审查.md"
        text = review.read_text(encoding="utf-8")
        self.assertIn("臂体正 Z 连续抽出扫掠", text)
        self.assertIn("驱动板负 Z 连续抽出扫掠", text)
        self.assertIn("fixed_root_guard_hex", text)
        self.assertIn("69.5 mm", text)

    def test_delivery_records_measurement_matrix_and_wiring_limits(self) -> None:
        engineering = json.loads(
            (self.directory / "V27工程审计.json").read_text(encoding="utf-8")
        )
        assembly = json.loads(
            (self.directory / "V27装配审查.json").read_text(encoding="utf-8")
        )
        self.assertIn("measurement_plan", engineering)
        self.assertIn("wiring_accessibility", assembly["service"])
        review = (self.directory / "preprint_review" / "V27打印前审查.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("待实测", review)
        self.assertIn("线束", review)
        self.assertIn("弯曲半径", review)

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


class V27CoverIntegrationTests(unittest.TestCase):
    def test_flat_cover_is_present_and_clear_in_full_assembly(self) -> None:
        result = build_v27_assembly(load_contract())
        upper_panel_names = tuple(
            name for name in result.components if name.startswith("fixed_cover_upper_panel_")
        )
        lower_panel_names = tuple(
            name for name in result.components if name.startswith("fixed_cover_lower_panel_")
        )
        frame_names = tuple(
            name for name in result.components if name.startswith("fixed_cover_frame_")
        )
        self.assertEqual(len(upper_panel_names), 6)
        self.assertEqual(len(lower_panel_names), 6)
        self.assertEqual(len(frame_names), 4)
        self.assertIn("fixed_root_guard_hex", result.components)
        audit = preflight_v27(result)
        self.assertEqual(audit["collisions"]["forbidden"], [])
        self.assertTrue(audit["service"]["drive_negative_z_removal_clear"])


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
            len(
                [
                    name
                    for name in self.result.drive_component_names
                    if name in {f"removable_M2006_{index:02d}" for index in range(1, 4)}
                ]
            ),
            3,
        )
        self.assertEqual(
            len(
                [
                    name
                    for name in self.result.drive_component_names
                    if name.startswith("removable_M2006_cross_pin_")
                ]
            ),
            3,
        )
        self.assertEqual(
            len(
                [
                    name
                    for name in self.result.fixed_component_names
                    if name.startswith("fixed_spool_retainer_")
                ]
            ),
            3,
        )
        self.assertFalse(any(name.startswith("fixed_coupling_sleeve_") for name in self.result.fixed_component_names))
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
        self.assertEqual(
            len([name for name in names if "C610" in name and name.endswith("_envelope")]),
            3,
        )
        self.assertEqual(
            len([name for name in names if "C610" in name and name.endswith("_backing")]),
            3,
        )
        self.assertFalse(any("M3508" in name or "C620" in name for name in names))

    def test_no_component_name_uses_m3508(self) -> None:
        self.assertFalse(any("M3508" in name for name in self.result.components))

    def test_v26_outputs_are_not_modified(self) -> None:
        self.assertEqual(self.v26_before, snapshot_v26_outputs(self.contract))

    def test_fixed_and_removable_ownership_survives_integration(self) -> None:
        self.assertTrue(all(name.startswith("removable_") for name in self.result.drive_component_names))
        self.assertTrue(all(name.startswith("fixed_") for name in self.result.fixed_component_names))
        self.assertFalse(any("C610" in name for name in self.result.drive_component_names))

    def test_input_shaft_audit_reports_integrated_socket_and_no_loose_sleeves(self) -> None:
        interface = self.audit["service"]["m2006_coupling_interface"]
        self.assertTrue(interface["integrated_input_shaft"])
        self.assertEqual(interface["collar_diameter_mm"], 15.0)
        self.assertEqual(interface["motor_socket_diameter_mm"], 6.2)
        self.assertEqual(interface["motor_radial_nominal_clearance_mm"], 0.1)
        self.assertEqual(interface["motor_socket_profile"], "D_bore")
        self.assertEqual(interface["motor_output_flat_from_axis_mm"], 2.5)
        self.assertEqual(interface["motor_socket_flat_from_axis_mm"], 2.6)
        self.assertEqual(interface["motor_d_flat_nominal_clearance_mm"], 0.1)
        self.assertIn("not modeled", interface["motor_cross_pin_retention_status"])
        self.assertEqual(interface["motor_socket_engagement_mm"], 13.0)
        self.assertEqual(interface["socket_wall_mm"], 4.4)
        self.assertEqual(interface["collar_to_first_bearing_clearance_mm"], 0.2)
        self.assertEqual(interface["loose_coupling_sleeve_count"], 0)
        self.assertEqual(interface["coupling_set_screw_count"], 0)
        self.assertEqual(interface["removable_cross_pin_count"], 3)

    def test_wet_spool_service_sweep_is_clear_after_release_sequence(self) -> None:
        service = self.audit["service"]
        interface = service["wet_spool_interface"]
        self.assertEqual(interface["bore_shape"], "circular_clearance_bore")
        self.assertEqual(interface["bore_diameter_mm"], 10.1)
        self.assertEqual(interface["radial_drive_pin_diameter_mm"], 2.5)
        self.assertEqual(interface["radial_drive_pin_hole_diameter_mm"], 2.7)
        self.assertEqual(interface["retainer_outer_diameter_mm"], 16.0)
        paths = service["spool_removal"]
        self.assertEqual(len(paths), 3)
        for path in paths:
            index = path["axis_index"]
            self.assertTrue(path["tendon_detached_required"])
            self.assertEqual(path["direction"], "positive_spool_axis")
            self.assertEqual(path["travel_mm"], 32.0)
            self.assertEqual(
                set(path["removed_component_names"]),
                {
                    f"fixed_output_support_cartridge_{index:02d}",
                    f"fixed_output_support_cartridge_screw_{index:02d}_01",
                    f"fixed_output_support_cartridge_screw_{index:02d}_02",
                    f"fixed_bearing_outer_{index:02d}",
                    f"fixed_oil_seal_outboard_{index:02d}",
                    f"fixed_labyrinth_outboard_{index:02d}",
                    f"fixed_spool_retainer_{index:02d}",
                    f"fixed_spool_drive_pin_{index:02d}",
                },
            )
            self.assertTrue(path["passes"])
            self.assertEqual(path["collisions"], [])
            self.assertGreater(path["minimum_clearance_mm"], 0.0)
            self.assertIn(
                f"fixed_output_support_land_{path['axis_index']:02d}",
                [path["retained_support_land_name"]],
            )

        failed_audit = dict(self.audit)
        failed_service = dict(self.audit["service"])
        failed_paths = [dict(path) for path in paths]
        failed_paths[0]["passes"] = False
        failed_service["spool_removal"] = failed_paths
        failed_audit["service"] = failed_service
        with patch("generate_v27_assembly.audit_v27_assembly", return_value=failed_audit):
            with self.assertRaisesRegex(ValueError, "spool removal"):
                preflight_v27(self.result)

    def test_output_support_cartridge_removal_path_is_clear(self) -> None:
        service = self.audit["service"]
        interface = service["output_support_cartridge_interface"]
        self.assertEqual(interface["inner_diameter_mm"], 22.02)
        self.assertEqual(interface["bearing_nominal_radial_clearance_mm"], 0.01)
        self.assertEqual(interface["seal_housing_bore_diameter_mm"], 22.0)
        shoulder = interface["outboard_seal_retainer_shoulder"]
        self.assertEqual(shoulder["range_mm"], [12.0, 13.5])
        self.assertTrue(shoulder["integral_with_removable_cartridge"])
        paths = service["output_support_cartridge_removal"]
        self.assertEqual(len(paths), 3)
        for path in paths:
            index = path["axis_index"]
            self.assertEqual(path["travel_mm"], 32.0)
            self.assertEqual(
                set(path["removed_component_names"]),
                {
                    f"fixed_output_support_cartridge_screw_{index:02d}_01",
                    f"fixed_output_support_cartridge_screw_{index:02d}_02",
                    f"fixed_bearing_outer_{index:02d}",
                    f"fixed_oil_seal_outboard_{index:02d}",
                    f"fixed_labyrinth_outboard_{index:02d}",
                },
            )
            self.assertTrue(path["passes"])
            self.assertEqual(path["collisions"], [])
            self.assertEqual(path["collision_volume_threshold_mm3"], 0.02)
            self.assertEqual(path["initial_radial_clearance_mm"], 0.2)
            self.assertTrue(path["initial_face_contact_expected"])
            self.assertIn(
                f"fixed_output_support_land_{index:02d}",
                path["fixed_obstacle_names"],
            )

        failed_audit = dict(self.audit)
        failed_service = dict(self.audit["service"])
        failed_paths = [dict(path) for path in paths]
        failed_paths[0]["passes"] = False
        failed_service["output_support_cartridge_removal"] = failed_paths
        failed_audit["service"] = failed_service
        with patch("generate_v27_assembly.audit_v27_assembly", return_value=failed_audit):
            with self.assertRaisesRegex(ValueError, "output support cartridge removal"):
                preflight_v27(self.result)

    def test_no_forbidden_solid_intersections(self) -> None:
        self.assertEqual(self.audit["collisions"]["forbidden"], [])
        self.assertTrue(self.audit["collisions"]["intentional_contacts"])

    def test_arm_can_translate_out_after_fasteners_and_terminals_removed(self) -> None:
        service = self.audit["service"]
        self.assertTrue(service["arm_positive_z_removal_clear"])
        sweep = service["arm_removal_sweep"]
        self.assertEqual(sweep["direction"], "positive_z")
        self.assertTrue(sweep["passes"])
        self.assertEqual(sweep["collisions"], [])
        self.assertGreater(sweep["travel_mm"], sweep["initial_release_gap_mm"])
        self.assertGreater(sweep["minimum_clearance_mm"], 0.0)
        self.assertIn("arm_module_arm_segment_01", sweep["moving_component_names"])
        self.assertNotIn("arm_tendon_terminals", sweep["moving_component_names"])
        self.assertIn("arm_tendon_terminals", sweep["removed_before_sweep"])
        self.assertIn("fixed_root_guard_hex", sweep["removed_fixed_component_names"])
        self.assertIn("fixed_root_dowel_01", sweep["fixed_obstacle_names"])
        self.assertIn("fixed_cover_upper_panel_01", sweep["fixed_obstacle_names"])
        self.assertIn("fixed_cover_lower_panel_01", sweep["fixed_obstacle_names"])
        self.assertIn("remove_fixed_hexagonal_root_guard", service["arm_module_removal_sequence"])
        self.assertIn(
            "translate_entire_arm_module_along_positive_z",
            service["arm_module_removal_sequence"],
        )

    def test_arm_service_audit_records_selected_single_piece_keyed_guard(self) -> None:
        guard = self.audit["service"]["root_guard_attachment"]
        self.assertEqual(guard["part_count"], 1)
        self.assertEqual(guard["removal_direction"], "positive_z")
        self.assertEqual(guard["fastener_thread"], "M3")
        self.assertEqual(guard["fastener_count"], 3)
        self.assertEqual(guard["alignment_tab_count"], 2)
        self.assertEqual(guard["base_receiver"], "fixed_top_plate")

    def test_drive_plate_can_translate_out_after_cross_pins_removed(self) -> None:
        service = self.audit["service"]
        self.assertTrue(service["drive_negative_z_removal_clear"])
        self.assertEqual(service["drive_sweep_collisions"], [])
        self.assertEqual(service["drive_sweep_travel_mm"], 280.0)
        self.assertEqual(service["drive_sweep_initial_release_gap_mm"], 0.5)
        sweep = service["drive_removal_sweep"]
        self.assertEqual(sweep["direction"], "negative_z")
        self.assertTrue(sweep["passes"])
        self.assertEqual(sweep["collisions"], [])
        self.assertEqual(sweep["travel_mm"], 280.0)
        self.assertTrue(
            {
                "removable_motor_plate",
                "removable_M2006_01",
                "removable_M2006_02",
                "removable_M2006_03",
            }.issubset(sweep["moving_component_names"])
        )
        self.assertEqual(len(sweep["removed_drive_component_names"]), 3)
        self.assertEqual(len(sweep["removed_fixed_component_names"]), 7)
        self.assertAlmostEqual(
            service["drive_sweep_min_clearance_mm"], 0.1, places=6
        )
        sequence = service["drive_module_removal_sequence"]
        self.assertIn("remove_lower_cover_panels_and_bottom_frame", sequence)
        self.assertIn("remove_three_motor_cross_pins", sequence)
        self.assertIn("translate_plate_downward_to_withdraw_D6_shafts", sequence[-1])

    def test_wiring_accessibility_audits_motor_and_external_service_routes(self) -> None:
        wiring = self.audit["service"]["wiring_accessibility"]
        motor = wiring["motor_harness"]
        self.assertEqual(motor["route_count"], 3)
        self.assertEqual(motor["probe_diameter_mm"], 2.0)
        self.assertTrue(motor["clearance_passes"])
        self.assertEqual(motor["collisions"], [])
        self.assertEqual(
            [route["name"] for route in motor["routes"]],
            ["motor_harness_01", "motor_harness_02", "motor_harness_03"],
        )
        self.assertGreater(motor["checked_nonendpoint_component_count"], 20)
        self.assertTrue(motor["physical_limitations"])
        connectors = wiring["external_connectors"]
        self.assertTrue(connectors["M28_power_service"]["passes"])
        self.assertTrue(connectors["M12_typec_envelope"]["present"])
        self.assertTrue(connectors["M12_typec_envelope"]["physical_limitations"])

    def test_all_service_fasteners_have_tool_envelopes(self) -> None:
        self.assertEqual(self.audit["service"]["root_fastener_tool_envelopes"], 6)
        self.assertTrue(self.audit["service"]["all_tool_envelopes_valid"])

    def test_fixed_shafts_remain_supported_in_drive_removed_state(self) -> None:
        self.assertTrue(self.audit["service"]["fixed_shafts_supported_without_drive"])
        self.assertEqual(self.audit["service"]["fixed_shaft_support_pair_count"], 3)

    def test_export_creates_four_named_step_outputs(self) -> None:
        module_outputs = {
            self.exports[key].name
            for key in ("arm_module", "drive_module", "fixed_base", "full_assembly")
        }
        self.assertEqual(
            module_outputs,
            {
                "SpiRobs_v27_1m_四段臂体模块.step",
                "SpiRobs_v27_M2006三电机驱动模块.step",
                "SpiRobs_v27_固定传动密封基座.step",
                "SpiRobs_v27_1m模块化总装.step",
            },
        )
        segment_outputs = {
            path.name
            for key, path in self.exports.items()
            if key.startswith("print_segment_")
        }
        self.assertEqual(len(segment_outputs), 4)
        self.assertTrue(all(name.endswith(".step") for name in segment_outputs))
        self.assertTrue(all(path.is_file() and path.stat().st_size > 0 for path in self.exports.values()))

    def test_full_step_readback_has_valid_solids_and_bounds(self) -> None:
        full = cq.importers.importStep(str(self.exports["full_assembly"])).val()
        bounds = full.BoundingBox()
        self.assertTrue(full.isValid())
        self.assertGreater(len(full.Solids()), 20)
        self.assertGreaterEqual(bounds.zmax, 999.0)
        self.assertLessEqual(bounds.zmin, -239.0)

    def test_audit_contains_alignment_load_and_source_sections(self) -> None:
        for key in ("alignment", "engineering", "sources", "collisions", "service", "cover_layout"):
            self.assertIn(key, self.audit)
        self.assertEqual(len(self.audit["alignment"]), 3)
        cover = self.audit["cover_layout"]
        self.assertEqual(cover["outer_circumdiameter_mm"], 332.0)
        self.assertAlmostEqual(cover["frame_outer_circumradii_mm"][0], 104.031746, places=5)
        self.assertEqual(cover["frame_outer_circumradii_mm"][1:], [166.0, 166.0, 166.0])
        self.assertEqual(cover["frame_outer_circumradius_ranges_mm"][1:], [[166.0, 166.0]] * 3)
        self.assertEqual(cover["frame_radial_thickness_mm"], 4.0)
        self.assertEqual(cover["window_surround_reveal_mm"], 1.5)
        self.assertEqual(cover["window_surround_width_mm"], 8.0)
        self.assertEqual(cover["window_surround_proud_mm"], 2.5)
        self.assertEqual(cover["panel_profile_stations_mm"], [[-236.0, 98.0], [-110.0, 162.0], [-80.0, 162.0], [64.0, 162.0]])
        self.assertEqual(cover["motor_window_mm"], [72.0, 82.0])
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

    def test_review_images_are_nonempty(self) -> None:
        self.assertEqual(
            set(self.images),
            {
                "full_transparent",
                "exploded_modules",
                "root_quick_change",
                "drive_section",
                "drive_details",
                "electronics_bay",
                "dovetail_joints",
                "root_cover_review",
                "root_cover_only",
            },
        )
        for path in self.images.values():
            self.assertTrue(path.is_file() and path.stat().st_size > 10_000)
            with Image.open(path) as image:
                self.assertGreaterEqual(image.width, 1200)
                self.assertGreaterEqual(image.height, 800)
        with Image.open(self.images["drive_details"]) as image:
            self.assertGreaterEqual(image.width, 1600)
            self.assertGreaterEqual(image.height, 900)
        readme = (self.contract.output_directory / "README.md").read_text(encoding="utf-8")
        self.assertIn("无齿形目录包络", readme)
        self.assertIn("油封水下性能未验证", readme)


class V27PreprintCouponTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract()

    def test_tendon_transition_channels_open_through_both_host_faces(self) -> None:
        coupons = build_tendon_transition_ladder(self.contract).Solids()
        self.assertEqual(len(coupons), 3)
        controls = _root_transition_points(self.contract, 0.0)
        start, _, after_join, join = controls
        end_direction = (join - after_join).normalized()
        for index, (coupon, diameter) in enumerate(zip(coupons, (0.8, 1.0, 1.2))):
            offset_x = 55.0 * index
            radius = diameter / 2.0
            radial_start = cq.Vector(67.0 + offset_x, 0.0, float(start.z))
            radial_end = start + cq.Vector(offset_x, 0.0, 0.0)
            radial_vector = radial_end - radial_start
            radial_probe = cq.Solid.makeCylinder(
                radius, radial_vector.Length, radial_start, radial_vector.normalized()
            )
            self.assertLess(
                coupon.intersect(radial_probe).Volume(),
                0.02,
                f"coupon {index} has a blind radial entry",
            )
            top_distance = (75.0 - join.z) / end_direction.z
            axial_start = join + cq.Vector(offset_x, 0.0, 0.0)
            axial_end = axial_start + end_direction * (top_distance + 1.0)
            axial_vector = axial_end - axial_start
            axial_probe = cq.Solid.makeCylinder(
                radius, axial_vector.Length, axial_start, axial_vector.normalized()
            )
            self.assertLess(
                coupon.intersect(axial_probe).Volume(),
                0.02,
                f"coupon {index} has a blind axial exit",
            )


if __name__ == "__main__":
    unittest.main()
