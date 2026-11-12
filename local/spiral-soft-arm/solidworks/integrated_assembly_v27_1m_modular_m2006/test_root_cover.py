from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import unittest

import cadquery as cq


HERE = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class V27RootCoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_module("v27_contract_for_cover", "model_contract.py").load_contract()

    def test_cover_is_twelve_tapered_printable_panels_with_service_openings(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        self.assertEqual(len(result.panel_names), 12)
        self.assertEqual(len(result.upper_panel_names), 6)
        self.assertEqual(len(result.lower_panel_names), 6)
        self.assertEqual(len(result.motor_window_panels), 3)
        self.assertEqual(len(result.observation_window_panels), 3)
        self.assertEqual(result.type_c_service_panel, "fixed_cover_lower_panel_05")
        self.assertEqual(
            self.contract.integration["root_cover"]["panel_profile_stations_mm"],
            [[-236.0, 98.0], [-110.0, 162.0], [-80.0, 162.0], [64.0, 162.0]],
        )
        self.assertEqual(
            self.contract.integration["root_cover"]["motor_window_mm"], [72.0, 82.0]
        )
        for name in result.panel_names:
            panel = result.components[name]
            self.assertTrue(panel.isValid())
            box = panel.BoundingBox()
            self.assertLessEqual(box.zlen, 160.0 + 1e-5)
            self.assertLessEqual(box.xlen, 350.0)
            self.assertLessEqual(box.ylen, 350.0)
            self.assertLess(panel.Volume(), 180.0 * 2.4 * 160.0)
        self.assertEqual(result.print_envelope_mm[2], 300.0)
        self.assertAlmostEqual(result.outer_circumdiameter_mm, 332.0)
        self.assertAlmostEqual(result.print_envelope_mm[0], 332.0)
        self.assertLessEqual(result.print_envelope_mm[0], 350.0)

    def test_cover_frames_fit_printer_and_root_guard_clears_arm(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        self.assertEqual(len(result.frame_names), 4)
        extents = [result.components[name].BoundingBox() for name in result.frame_names]
        self.assertAlmostEqual(max(box.xlen for box in extents), 332.0, places=5)
        self.assertLessEqual(max(box.xlen for box in extents), 350.0)
        self.assertLessEqual(max(box.ylen for box in extents), 350.0)
        self.assertTrue(result.components[result.root_guard_name].isValid())
        self.assertEqual(result.root_guard_name, "fixed_root_guard_hex")

    def test_taper_following_base_band_does_not_intersect_lower_panels(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        base_band = result.components[result.frame_names[0]]
        for panel_name in result.lower_panel_names:
            overlap = base_band.intersect(result.components[panel_name]).Volume()
            self.assertLess(
                overlap,
                1e-3,
                msg=f"base armor band intersects {panel_name} by {overlap:.4f} mm^3",
            )

    def test_faceted_armor_bands_add_service_bezels_without_reducing_apertures(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        cfg = self.contract.integration["root_cover"]

        self.assertEqual(len(result.panel_names), 12)
        self.assertEqual(cfg["frame_z_centers_mm"], [-232.0, -84.0, -76.0, 60.0])
        self.assertAlmostEqual(cfg["frame_radial_thickness_mm"], 4.0)
        self.assertAlmostEqual(cfg["window_surround_reveal_mm"], 1.5)
        self.assertAlmostEqual(result.outer_circumdiameter_mm, 332.0)
        self.assertAlmostEqual(result.print_envelope_mm[0], 332.0)
        for name in result.frame_names:
            self.assertTrue(result.components[name].isValid(), msg=name)

        def radius_at(z_mm: float) -> float:
            for (za, ra), (zb, rb) in zip(
                result.profile_stations_mm, result.profile_stations_mm[1:]
            ):
                if za <= z_mm <= zb:
                    return ra + (rb - ra) * (z_mm - za) / (zb - za)
            self.fail(f"test window z={z_mm} is outside the profile")

        windows = [
            ("fixed_cover_upper_panel_02", 90.0, "motor_window_center_z_mm", "motor_window_mm"),
            ("fixed_cover_upper_panel_04", 210.0, "motor_window_center_z_mm", "motor_window_mm"),
            ("fixed_cover_upper_panel_06", 330.0, "motor_window_center_z_mm", "motor_window_mm"),
            ("fixed_cover_lower_panel_01", 30.0, "observation_window_center_z_mm", "observation_window_mm"),
            ("fixed_cover_lower_panel_03", 150.0, "observation_window_center_z_mm", "observation_window_mm"),
            ("fixed_cover_lower_panel_05", 270.0, "observation_window_center_z_mm", "observation_window_mm"),
            ("fixed_cover_lower_panel_05", 270.0, "m12_service_window_center_z_mm", "m12_service_window_mm"),
        ]
        for panel_name, normal_deg, center_key, size_key in windows:
            center_z = float(cfg[center_key])
            width_mm, height_mm = (float(value) for value in cfg[size_key])
            face_apothem = radius_at(center_z) * math.cos(math.radians(30.0))
            panel = result.components[panel_name]
            bezel_probe = cover_module._face_box(
                normal_deg,
                face_apothem + 1.25,
                width_mm / 2.0 + cfg["window_surround_width_mm"] / 2.0,
                center_z,
                0.8,
                0.4,
                0.8,
            )
            self.assertGreater(
                panel.intersect(bezel_probe).Volume(),
                0.01,
                msg=f"{panel_name} has no proud clipped-corner surround",
            )

        for panel_name, normal_deg in (
            ("fixed_cover_upper_panel_02", 90.0),
            ("fixed_cover_upper_panel_04", 210.0),
            ("fixed_cover_upper_panel_06", 330.0),
        ):
            opening_probe = cover_module._face_box(
                normal_deg,
                cfg["outer_circumradius_mm"] * math.cos(math.radians(30.0))
                - cfg["panel_thickness_mm"] / 2.0,
                0.0,
                cfg["motor_window_center_z_mm"],
                2.0,
                8.0,
                2.0,
            )
            self.assertLess(
                result.components[panel_name].intersect(opening_probe).Volume(),
                1e-3,
                msg=f"{panel_name} motor opening is obstructed",
            )

    def test_single_piece_root_guard_has_keyed_mounting_and_three_m3_clearances(self) -> None:
        cover_module = load_module("v27_keyed_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        cfg = self.contract.integration["root_cover"]
        guard = result.components[result.root_guard_name]

        self.assertEqual(len(guard.Solids()), 1)
        self.assertEqual(cfg["root_guard_fastener_angles_deg"], [60.0, 180.0, 300.0])
        self.assertEqual(cfg["root_guard_alignment_tab_angles_deg"], [45.0, 165.0])
        self.assertAlmostEqual(cfg["root_guard_fastener_clearance_diameter_mm"], 3.4)
        self.assertAlmostEqual(cfg["root_guard_alignment_slot_clearance_mm"], 0.3)

        z0, z1 = cfg["root_guard_z_bounds_mm"]
        radius = cfg["root_guard_fastener_center_radius_mm"]
        for angle_deg in cfg["root_guard_fastener_angles_deg"]:
            angle = math.radians(angle_deg)
            probe = cq.Solid.makeCylinder(
                1.45,
                z1 - z0 + 0.4,
                cq.Vector(radius * math.cos(angle), radius * math.sin(angle), z0 - 0.2),
                cq.Vector(0.0, 0.0, 1.0),
            )
            self.assertLess(guard.intersect(probe).Volume(), 1e-3)

        for angle_deg in cfg["root_guard_alignment_tab_angles_deg"]:
            tab_probe = cover_module._face_box(
                angle_deg,
                cfg["root_guard_alignment_tab_center_radius_mm"],
                0.0,
                0.0,
                cfg["root_guard_alignment_tab_tangent_width_mm"] - 0.4,
                cfg["root_guard_alignment_tab_radial_width_mm"] - 0.4,
                7.5,
            )
            self.assertGreater(guard.intersect(tab_probe).Volume(), 1.0)

    def test_lower_observation_and_typec_windows_cut_through_sloped_panels(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        cfg = self.contract.integration["root_cover"]
        profile = result.profile_stations_mm

        def radius_at(z_mm: float) -> float:
            for (za, ra), (zb, rb) in zip(profile, profile[1:]):
                if za <= z_mm <= zb:
                    return ra + (rb - ra) * (z_mm - za) / (zb - za)
            self.fail(f"test window z={z_mm} is outside the profile")

        checks = [
            ("fixed_cover_lower_panel_01", 30.0, "observation_window_center_z_mm", "observation_window_mm"),
            ("fixed_cover_lower_panel_03", 150.0, "observation_window_center_z_mm", "observation_window_mm"),
            ("fixed_cover_lower_panel_05", 270.0, "observation_window_center_z_mm", "observation_window_mm"),
            ("fixed_cover_lower_panel_05", 270.0, "m12_service_window_center_z_mm", "m12_service_window_mm"),
        ]
        thickness = float(cfg["panel_thickness_mm"])
        for panel_name, normal_deg, center_key, size_key in checks:
            center_z = float(cfg[center_key])
            width = float(cfg[size_key][0])
            height = float(cfg[size_key][1])
            face_center = radius_at(center_z) * math.cos(math.radians(30.0)) - thickness / 2.0
            near_full_opening_gauge = cover_module._face_box(
                normal_deg,
                face_center,
                0.0,
                center_z,
                width - 0.02,
                30.0,
                height - 0.02,
            )
            gauge_overlap = result.components[panel_name].intersect(
                near_full_opening_gauge
            ).Volume()
            self.assertLess(
                gauge_overlap,
                1e-3,
                msg=f"{panel_name} surround narrows the full radial opening by {gauge_overlap:.4f} mm^3",
            )
            for z_mm in (center_z - height / 2.0 + 1.0, center_z + height / 2.0 - 1.0):
                face_center = radius_at(z_mm) * 3.0**0.5 / 2.0 - thickness / 2.0
                probe = cover_module._face_box(
                    normal_deg, face_center, 0.0, z_mm, 2.0, 8.0, 1.0
                )
                overlap = result.components[panel_name].intersect(probe).Volume()
                self.assertLess(
                    overlap,
                    1e-3,
                    msg=f"{panel_name} window is not open through at z={z_mm} mm",
                )

    def test_nonfinite_cover_profile_station_is_rejected(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        cfg = self.contract.integration["root_cover"]
        original = cfg["panel_profile_stations_mm"]
        cfg["panel_profile_stations_mm"] = [
            [-236.0, 98.0],
            [-110.0, float("nan")],
            [-80.0, 162.0],
            [64.0, 162.0],
        ]
        try:
            with self.assertRaisesRegex(ValueError, "finite"):
                cover_module.build_root_cover(self.contract)
        finally:
            cfg["panel_profile_stations_mm"] = original

    def test_window_must_fit_its_assigned_panel_segment(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        cfg = self.contract.integration["root_cover"]
        original = cfg["motor_window_center_z_mm"]
        cfg["motor_window_center_z_mm"] = -75.0
        try:
            with self.assertRaisesRegex(ValueError, "assigned panel Z bounds"):
                cover_module.build_root_cover(self.contract)
        finally:
            cfg["motor_window_center_z_mm"] = original


if __name__ == "__main__":
    unittest.main()
