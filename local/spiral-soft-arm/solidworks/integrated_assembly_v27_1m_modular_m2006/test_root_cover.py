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

    def test_cover_builds_six_upper_and_six_lower_service_panels(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        self.assertEqual(len(result.panel_names), 12)
        self.assertEqual(
            result.lower_panel_names,
            tuple(f"fixed_cover_lower_panel_{index:02d}" for index in range(1, 7)),
        )
        self.assertEqual(
            result.upper_panel_names,
            tuple(f"fixed_cover_upper_panel_{index:02d}" for index in range(1, 7)),
        )
        self.assertEqual(result.band_centers_mm, (-232.0, -84.0, -76.0, 60.0))
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
        expected_z_bounds = {
            **{name: (-236.0, -80.0) for name in result.lower_panel_names},
            **{name: (-80.0, 64.0) for name in result.upper_panel_names},
        }
        for name in result.panel_names:
            panel = result.components[name]
            self.assertTrue(panel.isValid())
            box = panel.BoundingBox()
            expected_z0, expected_z1 = expected_z_bounds[name]
            self.assertAlmostEqual(box.zmin, expected_z0, places=5)
            self.assertAlmostEqual(box.zmax, expected_z1, places=5)
            self.assertAlmostEqual(box.zlen, expected_z1 - expected_z0, places=5)
            self.assertLessEqual(box.xlen, 350.0)
            self.assertLessEqual(box.ylen, 350.0)
            self.assertLess(panel.Volume(), 180.0 * 2.4 * 300.0)
        self.assertEqual(result.nominal_profile_envelope_mm[2], 300.0)
        self.assertAlmostEqual(result.nominal_profile_circumdiameter_mm, 324.0)
        self.assertAlmostEqual(result.nominal_profile_envelope_mm[0], 324.0)
        self.assertAlmostEqual(result.actual_panel_max_radial_diameter_mm, 332.0, places=3)
        for actual, expected in zip(
            result.actual_panel_assembly_bounds_mm,
            (332.0, 287.52, 300.0),
        ):
            self.assertAlmostEqual(actual, expected, places=3)
        self.assertLessEqual(result.nominal_profile_envelope_mm[0], 350.0)

    def test_cover_restores_four_stepped_armor_bands(self) -> None:
        cover_module = load_module("v27_cover_stepped_bands_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        self.assertFalse(
            any(name.startswith("fixed_cover_frame_") for name in result.components),
            "closed armor rings must be fused into the removable face panels",
        )
        frame_centers = tuple(
            float(value)
            for value in self.contract.integration["root_cover"]["frame_z_centers_mm"]
        )
        expected_z_bounds = (
            (-236.0, -228.0),
            (-88.0, -80.0),
            (-80.0, -72.0),
            (56.0, 64.0),
        )
        self.assertEqual(
            tuple((center - 4.0, center + 4.0) for center in frame_centers),
            expected_z_bounds,
        )

        profile = result.profile_stations_mm
        for region_names, centers in (
            (result.lower_panel_names, frame_centers[:2]),
            (result.upper_panel_names, frame_centers[2:]),
        ):
            for panel_index, normal_deg in enumerate(
                (30.0, 90.0, 150.0, 210.0, 270.0, 330.0)
            ):
                panel = result.components[region_names[panel_index]]
                self.assertTrue(panel.isValid(), msg=region_names[panel_index])
                self.assertEqual(len(panel.Solids()), 1, msg=region_names[panel_index])
                for center_z in centers:
                    radius = next(
                        ra + (rb - ra) * (center_z - za) / (zb - za)
                        for (za, ra), (zb, rb) in zip(profile, profile[1:])
                        if za <= center_z <= zb
                    )
                    face_apothem = radius * math.cos(math.radians(30.0))
                    rib_probe = cover_module._face_box(
                        normal_deg,
                        face_apothem + 3.15,
                        0.0,
                        center_z,
                        5.0,
                        0.25,
                        1.0,
                    )
                    self.assertGreater(
                        panel.intersect(rib_probe).Volume(),
                        0.1,
                        msg=f"{region_names[panel_index]} lacks the band at z={center_z}",
                    )

        def max_radius(shape: cq.Shape) -> float:
            return max(
                math.hypot(vertex.Center().x, vertex.Center().y)
                for vertex in shape.Vertices()
            )

        expected_band_radii = (106.063, 166.0, 166.0, 166.0)
        for band_index, (center_z, expected_radius) in enumerate(
            zip(frame_centers, expected_band_radii)
        ):
            z0, z1 = center_z - 4.0, center_z + 4.0
            region_names = result.lower_panel_names if band_index < 2 else result.upper_panel_names
            band_vertices = [
                vertex
                for name in region_names
                for vertex in result.components[name].Vertices()
                if z0 - 1e-5 <= vertex.Z <= z1 + 1e-5
            ]
            self.assertTrue(band_vertices)
            self.assertAlmostEqual(
                max(math.hypot(vertex.X, vertex.Y) for vertex in band_vertices),
                expected_radius,
                places=2,
            )

    def test_armor_bands_are_fused_into_each_removable_panel(self) -> None:
        cover_module = load_module("v27_cover_integrated_ribs_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        self.assertFalse(
            any(name.startswith("fixed_cover_frame_") for name in result.components),
            "a closed frame must not remain after integrating the face ribs",
        )
        profile = result.profile_stations_mm
        for region_names, centers in (
            (
                result.lower_panel_names,
                self.contract.integration["root_cover"]["frame_z_centers_mm"][:2],
            ),
            (
                result.upper_panel_names,
                self.contract.integration["root_cover"]["frame_z_centers_mm"][2:],
            ),
        ):
            for panel_index, normal_deg in enumerate(
                (30.0, 90.0, 150.0, 210.0, 270.0, 330.0)
            ):
                panel_name = region_names[panel_index]
                panel = result.components[panel_name]
                self.assertTrue(panel.isValid(), msg=panel_name)
                self.assertEqual(len(panel.Solids()), 1, msg=panel_name)
                for center_z in centers:
                    radius = next(
                        ra + (rb - ra) * (center_z - za) / (zb - za)
                        for (za, ra), (zb, rb) in zip(profile, profile[1:])
                        if za <= center_z <= zb
                    )
                    rib_probe = cover_module._face_box(
                        normal_deg,
                        radius * math.cos(math.radians(30.0)) + 3.15,
                        0.0,
                        center_z,
                        5.0,
                        0.25,
                        1.0,
                    )
                    self.assertGreater(
                        panel.intersect(rib_probe).Volume(),
                        0.1,
                        msg=f"{panel_name} has no integrated armor rib at z={center_z}",
                    )

    def test_center_armor_bands_have_a_visible_recessed_seam(self) -> None:
        cover_module = load_module("v27_cover_center_band_seam_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        config = self.contract.integration["root_cover"]
        self.assertEqual(config["central_band_seam_height_mm"], 2.0)
        self.assertEqual(config["central_band_seam_radial_recess_mm"], 1.2)
        seam_probe = cover_module._face_box(
            90.0,
            143.4,
            0.0,
            -80.0,
            20.0,
            0.1,
            0.5,
        )
        seam_lower = result.components["fixed_cover_lower_panel_02"]
        seam_upper = result.components["fixed_cover_upper_panel_02"]
        self.assertLess(
            seam_lower.intersect(seam_probe).Volume()
            + seam_upper.intersect(seam_probe).Volume(),
            1e-3,
            msg="integrated center band segments have no visible recessed break",
        )

    def test_split_cover_panels_keep_all_service_openings(self) -> None:
        cover_module = load_module("v27_cover_service_openings_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        self.assertEqual(len(result.panel_names), 12)
        self.assertEqual(
            result.motor_window_panels,
            ("fixed_cover_upper_panel_02", "fixed_cover_upper_panel_04", "fixed_cover_upper_panel_06"),
        )
        self.assertEqual(
            result.observation_window_panels,
            ("fixed_cover_lower_panel_01", "fixed_cover_lower_panel_03", "fixed_cover_lower_panel_05"),
        )
        self.assertEqual(result.type_c_service_panel, "fixed_cover_lower_panel_05")
        cfg = self.contract.integration["root_cover"]
        opening_specs = (
            ("fixed_cover_upper_panel_02", 90.0, "motor_window_center_z_mm", "motor_window_mm"),
            ("fixed_cover_upper_panel_04", 210.0, "motor_window_center_z_mm", "motor_window_mm"),
            ("fixed_cover_upper_panel_06", 330.0, "motor_window_center_z_mm", "motor_window_mm"),
            ("fixed_cover_lower_panel_01", 30.0, "observation_window_center_z_mm", "observation_window_mm"),
            ("fixed_cover_lower_panel_03", 150.0, "observation_window_center_z_mm", "observation_window_mm"),
            ("fixed_cover_lower_panel_05", 270.0, "observation_window_center_z_mm", "observation_window_mm"),
            ("fixed_cover_lower_panel_05", 270.0, "m12_service_window_center_z_mm", "m12_service_window_mm"),
        )
        for panel_name, normal_deg, center_key, size_key in opening_specs:
            center_z = float(cfg[center_key])
            width_mm, height_mm = (float(value) for value in cfg[size_key])
            probe = cover_module._face_box(
                normal_deg,
                cfg["outer_circumradius_mm"] * math.cos(math.radians(30.0))
                - cfg["panel_thickness_mm"] / 2.0,
                0.0,
                center_z,
                width_mm - 0.02,
                20.0,
                height_mm - 0.02,
            )
            self.assertLess(
                result.components[panel_name].intersect(probe).Volume(),
                1e-3,
                msg=f"{panel_name} {size_key} opening is blocked",
            )

    def test_cover_frames_fit_printer_and_root_guard_clears_arm(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        self.assertEqual(len(result.band_centers_mm), 4)
        self.assertFalse(any(name.startswith("fixed_cover_frame_") for name in result.components))
        extents = [result.components[name].BoundingBox() for name in result.panel_names]
        cover_box = cq.Compound.makeCompound(
            [result.components[name] for name in result.panel_names]
        ).BoundingBox()
        self.assertAlmostEqual(cover_box.xlen, 332.0, places=3)
        self.assertAlmostEqual(cover_box.ylen, 287.52, places=2)
        self.assertLessEqual(max(box.xlen for box in extents), 350.0)
        self.assertLessEqual(max(box.ylen for box in extents), 350.0)
        self.assertTrue(result.components[result.root_guard_name].isValid())
        self.assertEqual(result.root_guard_name, "fixed_root_guard_hex")

    def test_taper_following_base_band_does_not_intersect_side_panels(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        self.assertFalse(any(name.startswith("fixed_cover_frame_") for name in result.components))
        for panel_name in result.panel_names:
            self.assertTrue(result.components[panel_name].isValid(), msg=panel_name)
            self.assertEqual(len(result.components[panel_name].Solids()), 1, msg=panel_name)

    def test_faceted_armor_bands_add_service_bezels_without_reducing_apertures(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        cfg = self.contract.integration["root_cover"]

        self.assertEqual(len(result.panel_names), 12)
        self.assertEqual(cfg["frame_z_centers_mm"], [-232.0, -84.0, -76.0, 60.0])
        self.assertAlmostEqual(cfg["frame_radial_thickness_mm"], 4.0)
        self.assertAlmostEqual(cfg["window_surround_reveal_mm"], 1.5)
        self.assertAlmostEqual(result.nominal_profile_circumdiameter_mm, 324.0)
        self.assertAlmostEqual(result.nominal_profile_envelope_mm[0], 324.0)
        for name in result.panel_names:
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
        self.assertEqual(len(result.panel_names), 12)
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

    def test_window_must_fit_full_height_panel_bounds(self) -> None:
        cover_module = load_module("v27_cover_for_tests", "root_cover.py")
        cfg = self.contract.integration["root_cover"]
        original = cfg["motor_window_center_z_mm"]
        cfg["motor_window_center_z_mm"] = 65.0
        try:
            with self.assertRaisesRegex(ValueError, "assigned panel Z bounds"):
                cover_module.build_root_cover(self.contract)
        finally:
            cfg["motor_window_center_z_mm"] = original

    def test_cover_fasteners_share_m3_clearance_and_supported_holes(self) -> None:
        cover_module = load_module("v27_cover_m3_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        cfg = self.contract.integration["root_cover"]
        self.assertAlmostEqual(cfg["panel_fastener_diameter_mm"], 3.4)
        self.assertAlmostEqual(cfg["root_guard_fastener_clearance_diameter_mm"], 3.4)
        normals = (30.0, 90.0, 150.0, 210.0, 270.0, 330.0)
        panel_thickness = float(cfg["panel_thickness_mm"])
        profile = result.profile_stations_mm

        def face_slope(z_mm: float) -> float:
            for (za, ra), (zb, rb) in zip(profile, profile[1:]):
                if za <= z_mm <= zb:
                    return math.cos(math.radians(30.0)) * (rb - ra) / (zb - za)
            raise AssertionError(f"no profile slope at z={z_mm}")

        regions = (
            (
                result.lower_panel_names,
                (cfg["frame_z_centers_mm"][0], cfg["frame_z_centers_mm"][1]),
                (0, 1),
            ),
            (
                result.upper_panel_names,
                (cfg["frame_z_centers_mm"][2], cfg["frame_z_centers_mm"][3]),
                (2, 3),
            ),
        )
        for region_names, support_z_values, frame_indices in regions:
            for panel_index, normal_deg in enumerate(normals, start=1):
                panel_name = (
                    result.lower_panel_names[panel_index - 1]
                    if region_names is result.lower_panel_names
                    else result.upper_panel_names[panel_index - 1]
                )
                panel = result.components[panel_name]
                for center_z, frame_index in zip(support_z_values, frame_indices):
                    radius = next(
                        ra + (rb - ra) * (center_z - za) / (zb - za)
                        for (za, ra), (zb, rb) in zip(
                            result.profile_stations_mm, result.profile_stations_mm[1:]
                        )
                        if za <= center_z <= zb
                    )
                    for tangent_offset in cfg["panel_fastener_tangent_offsets_mm"]:
                        radial = cq.Vector(
                            math.cos(math.radians(normal_deg)),
                            math.sin(math.radians(normal_deg)),
                            0.0,
                        )
                        tangent = cq.Vector(
                            math.cos(math.radians(normal_deg + 90.0)),
                            math.sin(math.radians(normal_deg + 90.0)),
                            0.0,
                        )
                        slope = face_slope(center_z)
                        outward = cq.Vector(radial.x, radial.y, -slope).normalized()
                        face_apothem = radius * math.cos(math.radians(30.0))
                        face_point = (
                            radial * face_apothem
                            + tangent * tangent_offset
                            + cq.Vector(0.0, 0.0, center_z)
                        )
                        screw_axis_probe = cq.Solid.makeCylinder(
                            1.6,
                            panel_thickness / outward.dot(radial) + 0.2,
                            face_point + outward * 0.1,
                            -outward,
                        )
                        self.assertLess(
                            panel.intersect(screw_axis_probe).Volume(),
                            1e-3,
                            msg=f"{panel_name} M3 axis is not normal to its panel face",
                        )
                        frame_outer_apothem = (
                            radius + float(cfg["frame_radial_thickness_mm"])
                        ) * math.cos(math.radians(30.0))
                        normal_offset = (
                            frame_outer_apothem - face_apothem
                        ) / math.sqrt(1.0 + slope * slope)
                        frame_outer_point = face_point + outward * normal_offset
                        frame_axis_probe = cq.Solid.makeCylinder(
                            1.6,
                            18.0,
                            frame_outer_point + outward * 0.1,
                            -outward,
                        )
                        self.assertLess(
                            panel.intersect(frame_axis_probe).Volume(),
                            1e-3,
                            msg=f"integrated band {frame_index + 1} M3 axis is blocked",
                        )

                        tool_recess = cq.Solid.makeCylinder(
                            4.0,
                            2.0,
                            frame_outer_point,
                            -outward,
                        )
                        self.assertLess(
                            panel.intersect(tool_recess).Volume(),
                            1e-3,
                            msg=(
                                f"M3 outer Ø8 x 2 mm access recess for {panel_name}, "
                                f"face {normal_deg}, tangent {tangent_offset}, "
                                f"z={center_z} is blocked"
                            ),
                        )
                        counterbore_floor = cq.Solid.makeCylinder(
                            4.0,
                            0.5,
                            frame_outer_point - outward * 2.1,
                            -outward,
                        )
                        self.assertGreater(
                            panel.intersect(counterbore_floor).Volume(),
                            5.0,
                            msg=(
                                f"integrated band {frame_index + 1} M3 head seat has no material "
                                f"beneath its 2 mm counterbore at face {normal_deg}, "
                                f"tangent {tangent_offset}, z={center_z}"
                            ),
                        )
                        tool_shaft = cq.Solid.makeCylinder(
                            1.25,
                            18.0,
                            frame_outer_point + outward * 0.1,
                            -outward,
                        )
                        self.assertLess(
                            panel.intersect(tool_shaft).Volume(),
                            1e-3,
                            msg=f"M3 driver shaft is blocked by {panel_name}",
                        )
                        self.assertLess(
                            panel.intersect(tool_shaft).Volume(),
                            1e-3,
                            msg=f"M3 driver shaft is blocked by {panel_name}",
                        )

    def test_cover_armor_frames_extend_four_mm_beyond_panel_envelope(self) -> None:
        cover_module = load_module("v27_cover_external_frames_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        cfg = self.contract.integration["root_cover"]

        def radius_at(z_mm: float) -> float:
            for (za, ra), (zb, rb) in zip(
                result.profile_stations_mm, result.profile_stations_mm[1:]
            ):
                if za <= z_mm <= zb:
                    return ra + (rb - ra) * (z_mm - za) / (zb - za)
            self.fail(f"support frame z={z_mm} is outside the cover profile")

        normals = (30.0, 90.0, 150.0, 210.0, 270.0, 330.0)
        frame_bounds = (
            (-236.0, -228.0),
            (-88.0, -80.0),
            (-80.0, -72.0),
            (56.0, 64.0),
        )
        for band_index, (z0, z1) in enumerate(frame_bounds):
            region_names = result.lower_panel_names if band_index < 2 else result.upper_panel_names
            for z_mm in (z0, z1):
                if abs(z_mm - float(cfg["central_band_seam_z_mm"])) < 1e-6:
                    continue  # the dedicated seam test checks the recessed split itself
                target_apothem = (radius_at(z_mm) + float(cfg["frame_radial_thickness_mm"])) * math.cos(math.radians(30.0))
                for normal_deg in normals:
                    angle = math.radians(normal_deg)
                    panel_index = normals.index(normal_deg)
                    panel = result.components[region_names[panel_index]]
                    probe = cover_module._face_box(normal_deg, target_apothem - 0.05, 0.0, z_mm, 8.0, 0.1, 0.2)
                    self.assertGreater(
                        panel.intersect(probe).Volume(),
                        0.01,
                        msg=f"band {band_index + 1} lacks the expected outer profile at face {normal_deg}, z={z_mm}",
                    )

    def test_cover_parts_fit_nominal_printer_bounds(self) -> None:
        cover_module = load_module("v27_cover_printer_bounds_for_tests", "root_cover.py")
        result = cover_module.build_root_cover(self.contract)
        part_names = (*result.panel_names, result.root_guard_name)
        for name in part_names:
            box = result.components[name].BoundingBox()
            self.assertLessEqual(box.xlen, 350.0 + 1e-5, msg=name)
            self.assertLessEqual(box.ylen, 350.0 + 1e-5, msg=name)
            self.assertLessEqual(box.zlen, 320.0 + 1e-5, msg=name)


if __name__ == "__main__":
    unittest.main()
