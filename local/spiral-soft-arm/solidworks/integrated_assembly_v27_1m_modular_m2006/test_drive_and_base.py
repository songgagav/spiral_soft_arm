from __future__ import annotations

from dataclasses import replace
import importlib.util
import math
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parent


def load_local_module(name: str, filename: str):
    path = HERE / filename
    if not path.is_file():
        raise AssertionError(f"missing module: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class V27DriveAndBaseTests(unittest.TestCase):
    cache = None

    @classmethod
    def setUpClass(cls) -> None:
        contract_module = load_local_module("v27_contract_for_drive", "model_contract.py")
        arm_module = load_local_module("v27_arm_for_drive", "arm_module.py")
        root_module = load_local_module("v27_root_for_drive", "root_quick_change.py")
        cls.contract = contract_module.load_contract()
        cls.arm = arm_module.build_arm_module(cls.contract)
        cls.root = root_module.build_root_interface(cls.contract, cls.arm)

    def build(self):
        if self.__class__.cache is None:
            drive = load_local_module("v27_drive_and_base", "drive_and_base.py")
            if not hasattr(drive, "build_drive_module"):
                self.fail("drive_and_base.build_drive_module is not implemented")
            axes = drive.optimize_drive_axes(self.contract, self.root)
            module = drive.build_drive_module(self.contract, self.root, axes)
            base = drive.build_fixed_base(self.contract, self.root, axes)
            self.__class__.cache = (drive, axes, module, base)
        return self.__class__.cache

    def test_three_motors_share_one_removable_plate(self) -> None:
        _, axes, module, _ = self.build()
        self.assertEqual(len(axes), 3)
        self.assertEqual(module.motor_names, ("removable_M2006_01", "removable_M2006_02", "removable_M2006_03"))
        self.assertEqual(module.plate_name, "removable_motor_plate")
        self.assertTrue(module.components[module.plate_name].isValid())
        self.assertEqual(module.positioning_source, "plate_register_and_dowels")
        self.assertEqual(module.official_step_solid_count, 0)
        self.assertEqual(module.installed_geometry_mode, "published_envelope_proxy")

    def test_c610_not_part_of_removable_plate(self) -> None:
        _, _, module, _ = self.build()
        names = tuple(module.components)
        self.assertFalse(any("C610" in name for name in names))
        self.assertFalse(self.contract.drive.c610_part_of_removable_module)

    def test_spools_shafts_bearings_and_seals_belong_to_fixed_base(self) -> None:
        _, _, module, base = self.build()
        for index in range(1, 4):
            for prefix in (
                "fixed_wet_spool",
                "fixed_shaft",
                "fixed_bearing_inner",
                "fixed_bearing_outer",
            ):
                name = f"{prefix}_{index:02d}"
                self.assertIn(name, base.components)
                self.assertNotIn(name, module.components)
                self.assertTrue(base.components[name].isValid())
            for side in ("drive_side", "outboard"):
                for family in ("fixed_oil_seal", "fixed_labyrinth"):
                    name = f"{family}_{side}_{index:02d}"
                    self.assertIn(name, base.components)
                    self.assertNotIn(name, module.components)
                    self.assertTrue(base.components[name].isValid())
            self.assertNotIn(f"fixed_coupling_sleeve_{index:02d}", base.components)
            self.assertNotIn(f"fixed_coupling_lock_screw_{index:02d}", base.components)
            for station, housing_name in (
                ("inner", "fixed_bevel_pod_01"),
                ("outer", "fixed_output_support_cartridge_01"),
            ):
                bearing = base.components[f"fixed_bearing_{station}_{index:02d}"]
                pod = base.components[
                    housing_name.replace("01", f"{index:02d}")
                ]
                self.assertLess(bearing.intersect(pod).Volume(), 0.02)
                self.assertLessEqual(bearing.distance(pod), 0.2)
        self.assertIn("fixed_common_motor_chamber", base.components)

    def test_integrated_input_shaft_preserves_motor_socket_and_pin_interface(self) -> None:
        drive, axes, module, base = self.build()
        axis = axes[0]
        shaft = base.components["fixed_shaft_01"]
        socket_depth_mm = 13.0
        socket_radius_mm = 6.2 / 2.0
        motor_flat_from_axis_mm = self.contract.integration[
            "m2006_motor_d6_flat_from_axis_mm"
        ]
        socket_flat_from_axis_mm = self.contract.integration[
            "m2006_input_shaft_socket_flat_from_axis_mm"
        ]
        collar_radius_mm = 15.0 / 2.0
        socket_start_z = self.contract.drive.m2006_output_tip_z_mm - socket_depth_mm
        socket_probe = drive._vertical_d_bore(
            axis.motor_center,
            socket_radius_mm - 0.1,
            motor_flat_from_axis_mm,
            axis.angle_deg,
            socket_start_z + 0.1,
            socket_start_z + 2.0,
        )
        self.assertLess(shaft.intersect(socket_probe).Volume(), 1e-4)
        circular_only_probe = drive._vertical_cylinder(
            axis.motor_center,
            self.contract.drive.m2006_output_shaft_diameter_mm / 2.0,
            socket_start_z + 0.1,
            socket_start_z + 2.0,
        )
        self.assertGreater(shaft.intersect(circular_only_probe).Volume(), 0.0)
        motor = module.components["removable_M2006_01"]
        radial = drive._unit_radial(axis.angle_deg)
        flat_point = __import__("cadquery").Vertex.makeVertex(
            axis.motor_center[0] + radial[0] * 2.7,
            axis.motor_center[1] + radial[1] * 2.7,
            self.contract.drive.m2006_output_tip_z_mm - 2.0,
        )
        self.assertAlmostEqual(motor.distance(flat_point), 0.2, places=5)
        self.assertAlmostEqual(socket_flat_from_axis_mm - motor_flat_from_axis_mm, 0.1, places=6)
        self.assertAlmostEqual(collar_radius_mm - socket_radius_mm, 4.4, places=6)

        collar_surface = __import__("cadquery").Vertex.makeVertex(
            axis.motor_center[0] + radial[0] * (collar_radius_mm - 0.01),
            axis.motor_center[1] + radial[1] * (collar_radius_mm - 0.01),
            socket_start_z + 1.0,
        )
        self.assertAlmostEqual(shaft.distance(collar_surface), 0.01, places=5)

        crosshole_z = (
            self.contract.drive.m2006_output_tip_z_mm
            - self.contract.drive.m2006_crosshole_center_from_tip_mm
        )
        pin_probe = drive._radial_cylinder_at(
            axis.motor_center,
            axis.angle_deg,
            1.5,
            -collar_radius_mm - 0.1,
            collar_radius_mm + 0.1,
            crosshole_z,
        )
        self.assertLess(shaft.intersect(pin_probe).Volume(), 1e-4)
        self.assertTrue(module.components["removable_M2006_cross_pin_01"].isValid())

    def test_input_shaft_is_single_fixed_part_without_loose_coupler(self) -> None:
        _, _, module, base = self.build()
        self.assertFalse(any(name.startswith("fixed_coupling_sleeve_") for name in base.components))
        self.assertFalse(any(name.startswith("fixed_coupling_lock_screw_") for name in base.components))
        for index in range(1, 4):
            shaft = base.components[f"fixed_shaft_{index:02d}"]
            self.assertTrue(shaft.isValid())
            self.assertEqual(len(shaft.Solids()), 1)
            self.assertNotIn(f"fixed_shaft_{index:02d}", module.components)

    def test_input_shaft_change_preserves_drive_datums(self) -> None:
        drive, axes, _, base = self.build()
        for axis in axes:
            index = axis.axis_index
            self.assertEqual(axis.motor_axis, (0.0, 0.0, 1.0))
            self.assertAlmostEqual(
                sum(a * b for a, b in zip(axis.motor_axis, axis.spool_axis)),
                0.0,
                places=8,
            )
            shaft = base.components[f"fixed_shaft_{index:02d}"]
            for station in (1, 2):
                bearing = base.components[f"fixed_input_bearing_{station}_{index:02d}"]
                self.assertAlmostEqual(shaft.distance(bearing), 0.05, places=5)
            gear = self.contract.integration["gear_hardware_review"]
            outer_depth = 0.5 * gear["pitch_diameter_mm"]
            inner_depth = outer_depth - gear["face_width_mm"] / math.sqrt(2.0)
            total_depth = outer_depth + gear["hub_width_mm"]
            journal_probe = drive._vertical_cylinder(
                axis.motor_center,
                3.0,
                axis.spool_center[2] - total_depth,
                axis.spool_center[2] - inner_depth,
            )
            self.assertGreater(shaft.intersect(journal_probe).Volume(), 0.0)
        alignment = drive.audit_tendon_alignment(self.contract, self.root, axes, base.components)
        self.assertTrue(all(item.passes for item in alignment))

    def test_motor_removal_does_not_remove_or_unseat_shafts(self) -> None:
        _, _, module, base = self.build()
        self.assertTrue(base.shafts_supported_without_drive)
        self.assertEqual(
            module.removal_sequence[:9],
            (
                "deenergize_all_power_sources_and_unload_tendons",
                "remove_24_M3_lower_cover_fasteners",
                "remove_fixed_cover_lower_panel_01",
                "remove_fixed_cover_lower_panel_02",
                "remove_fixed_cover_lower_panel_03",
                "remove_fixed_cover_lower_panel_04",
                "remove_fixed_cover_lower_panel_05",
                "remove_fixed_cover_lower_panel_06",
                "remove_bottom_cover_frame_01",
            ),
        )
        self.assertEqual(module.removal_sequence[9], "disconnect_motor_harnesses")
        self.assertEqual(module.removal_sequence[10], "remove_three_motor_cross_pins")
        self.assertIn("withdraw_D6_shafts", module.removal_sequence[11])
        self.assertEqual(len(base.shaft_support_pairs), 3)
        self.assertTrue(all(len(pair) == 2 for pair in base.shaft_support_pairs))

    def test_top_plate_envelope_is_250_mm(self) -> None:
        _, _, _, base = self.build()
        bounds = base.top_plate.BoundingBox()
        self.assertAlmostEqual(base.top_plate_circumdiameter_mm, 250.0, places=6)
        self.assertAlmostEqual(bounds.xlen, 250.0, places=5)
        self.assertLessEqual(bounds.ylen, 250.0 + 1e-6)

    def test_top_plate_receives_guard_insert_pockets_and_alignment_tabs(self) -> None:
        drive, _, _, base = self.build()
        cfg = self.contract.integration["root_cover"]
        plate = base.components["fixed_top_plate"]
        pocket_radius = 0.5 * cfg["root_guard_insert_pocket_diameter_mm"] - 0.2
        for angle_deg in cfg["root_guard_fastener_angles_deg"]:
            radial = (math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg)))
            center = (
                cfg["root_guard_fastener_center_radius_mm"] * radial[0],
                cfg["root_guard_fastener_center_radius_mm"] * radial[1],
                0.0,
            )
            pocket = drive._vertical_cylinder(center, pocket_radius, -5.8, -0.1)
            self.assertLess(plate.intersect(pocket).Volume(), 1e-3)
        for angle_deg in cfg["root_guard_alignment_tab_angles_deg"]:
            radial = (math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg)))
            center = (
                cfg["root_guard_alignment_tab_center_radius_mm"] * radial[0],
                cfg["root_guard_alignment_tab_center_radius_mm"] * radial[1],
                -2.0,
            )
            slot = drive._oriented_box(
                center,
                cfg["root_guard_alignment_tab_radial_width_mm"],
                cfg["root_guard_alignment_tab_tangent_width_mm"],
                3.5,
                angle_deg,
            )
            self.assertLess(plate.intersect(slot).Volume(), 1e-3)

    def test_wet_spools_clear_root_flange(self) -> None:
        _, axes, _, _ = self.build()
        flange_radius = 0.5 * self.contract.root_interface.flange_max_diameter_mm
        spool_outer_radius = 12.0
        for axis in axes:
            center_radius = math.hypot(axis.spool_center[0], axis.spool_center[1])
            self.assertGreaterEqual(center_radius - spool_outer_radius - flange_radius, 0.25)

    def test_each_spool_tangent_hits_matching_root_inlet(self) -> None:
        drive, axes, _, _ = self.build()
        audit = drive.audit_tendon_alignment(self.contract, self.root, axes)
        self.assertEqual(len(audit), 3)
        for item in audit:
            self.assertLessEqual(item.lateral_error_mm, 0.25)
            self.assertEqual(item.channel_index, item.axis_index)
            self.assertTrue(item.passes)

    def test_motor_and_spool_axes_are_perpendicular_in_generated_geometry(self) -> None:
        _, axes, module, base = self.build()
        for axis in axes:
            self.assertAlmostEqual(
                sum(a * b for a, b in zip(axis.motor_axis, axis.spool_axis)),
                0.0,
                places=8,
            )
            self.assertAlmostEqual(
                sum(a * b for a, b in zip(axis.spool_axis, axis.tendon_direction)),
                0.0,
                places=8,
            )
            motor = module.components[f"removable_M2006_{axis.axis_index:02d}"]
            motor_bounds = motor.BoundingBox()
            self.assertGreater(motor_bounds.zlen, 2.0 * max(motor_bounds.xlen, motor_bounds.ylen))
            spool = base.components[f"fixed_wet_spool_{axis.axis_index:02d}"]
            local_spool = spool.rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), -axis.angle_deg)
            spool_bounds = local_spool.BoundingBox()
            self.assertLess(spool_bounds.ylen, 0.65 * max(spool_bounds.xlen, spool_bounds.zlen))

    def test_motor_axis_intersects_tangential_spool_axis_at_the_gear_apex(self) -> None:
        _, axes, _, _ = self.build()
        for axis in axes:
            radial = (math.cos(math.radians(axis.angle_deg)), math.sin(math.radians(axis.angle_deg)), 0.0)
            delta = (
                axis.motor_center[0] - axis.spool_center[0],
                axis.motor_center[1] - axis.spool_center[1],
                0.0,
            )
            perpendicular_offset = abs(sum(a * b for a, b in zip(delta, radial)))
            self.assertLessEqual(perpendicular_offset, 1e-6)

    def test_tendon_tangent_is_derived_from_actual_spool_surface(self) -> None:
        drive, axes, _, base = self.build()
        cq = __import__("cadquery")
        for axis in axes:
            spool = base.components[f"fixed_wet_spool_{axis.axis_index:02d}"]
            surface_contact = (
                axis.spool_center[0],
                axis.spool_center[1],
                axis.spool_center[2] - float(self.contract.drive.spool_core_radius_mm),
            )
            surface_probe = cq.Vertex.makeVertex(*surface_contact)
            self.assertLessEqual(spool.distance(surface_probe), 1e-5)
            cable_centerline = (
                surface_contact[0],
                surface_contact[1],
                surface_contact[2] - float(self.contract.arm.tendon_diameter_mm) / 2.0,
            )
            self.assertAlmostEqual(axis.tangent_point[2], cable_centerline[2], places=7)
            self.assertAlmostEqual(axis.tangent_point[0], cable_centerline[0], places=7)
            self.assertAlmostEqual(axis.tangent_point[1], cable_centerline[1], places=7)
        audit = drive.audit_tendon_alignment(self.contract, self.root, axes, base.components)
        self.assertTrue(all(item.passes for item in audit))

    def test_fixed_right_angle_gear_envelopes_and_spool_pockets_exist(self) -> None:
        _, axes, _, base = self.build()
        plate = base.components["fixed_top_plate"]
        for axis in axes:
            input_gear = base.components[
                f"fixed_bevel_input_envelope_{axis.axis_index:02d}"
            ]
            output_gear = base.components[
                f"fixed_bevel_output_envelope_{axis.axis_index:02d}"
            ]
            self.assertTrue(input_gear.isValid())
            self.assertTrue(output_gear.isValid())
            self.assertGreater(input_gear.Volume(), 0.0)
            self.assertGreater(output_gear.Volume(), 0.0)
            self.assertLess(plate.intersect(input_gear).Volume(), 0.02)
            self.assertLess(plate.intersect(output_gear).Volume(), 0.02)
            spool = base.components[f"fixed_wet_spool_{axis.axis_index:02d}"]
            self.assertLess(plate.intersect(spool).Volume(), 0.02)

    def test_plan_and_side_alignment_both_pass(self) -> None:
        drive, axes, _, _ = self.build()
        audit = drive.audit_tendon_alignment(self.contract, self.root, axes)
        self.assertTrue(all(item.plan_error_mm <= 0.25 for item in audit))
        self.assertTrue(all(item.side_error_mm <= 0.25 for item in audit))
        self.assertTrue(all(item.perpendicular_error_deg <= 0.5 for item in audit))
        wrong_point = (*axes[0].tangent_point[:2], axes[0].tangent_point[2] + 2.0)
        wrong_axis = replace(axes[0], tangent_point=wrong_point)
        wrong_audit = drive.audit_tendon_alignment(
            self.contract, self.root, (wrong_axis, axes[1], axes[2])
        )
        self.assertGreater(wrong_audit[0].side_error_mm, 0.25)
        self.assertFalse(wrong_audit[0].passes)

    def test_alignment_uses_actual_arm_entry_direction(self) -> None:
        drive, axes, _, _ = self.build()
        audit = drive.audit_tendon_alignment(self.contract, self.root, axes)
        self.assertTrue(all(item.entry_direction_error_deg <= 0.5 for item in audit))
        wrong_terminal = replace(
            self.root.tendon_terminals[0],
            axis_direction=(0.0, 0.0, 1.0),
        )
        wrong_root = replace(
            self.root,
            tendon_terminals=(wrong_terminal, *self.root.tendon_terminals[1:]),
        )
        wrong = drive.audit_tendon_alignment(self.contract, wrong_root, axes)
        self.assertGreater(wrong[0].entry_direction_error_deg, 0.5)
        self.assertFalse(wrong[0].passes)

    def test_rotating_spools_clear_stationary_seals_and_labyrinths(self) -> None:
        _, _, _, base = self.build()
        for index in range(1, 4):
            spool = base.components[f"fixed_wet_spool_{index:02d}"]
            for stationary in (
                "fixed_oil_seal_drive_side",
                "fixed_oil_seal_outboard",
                "fixed_labyrinth_drive_side",
                "fixed_labyrinth_outboard",
            ):
                other = base.components[f"{stationary}_{index:02d}"]
                self.assertLess(spool.intersect(other).Volume(), 0.02)

    def test_wet_spool_round_clearance_bore_and_radial_pin_drive(self) -> None:
        drive, axes, _, base = self.build()
        cfg = self.contract.integration
        for index, axis in enumerate(axes, start=1):
            spool = base.components[f"fixed_wet_spool_{index:02d}"]
            shaft = base.components[f"fixed_output_shaft_{index:02d}"]
            pin = base.components[f"fixed_spool_drive_pin_{index:02d}"]
            radial = drive._unit_radial(axis.angle_deg)
            tangent = axis.spool_axis
            bore_probe = __import__("cadquery").Vertex.makeVertex(
                axis.spool_center[0] + 2.0 * tangent[0] + radial[0] * 5.02,
                axis.spool_center[1] + 2.0 * tangent[1] + radial[1] * 5.02,
                axis.spool_center[2] + 2.0 * tangent[2],
            )
            self.assertAlmostEqual(spool.distance(bore_probe), 0.03, places=5)
            self.assertLess(spool.intersect(shaft).Volume(), 0.02)
            self.assertLess(spool.intersect(pin).Volume(), 0.02)
            self.assertLess(shaft.intersect(pin).Volume(), 0.02)
            self.assertTrue(pin.isValid())
            self.assertAlmostEqual(
                pin.Volume(),
                math.pi * (cfg["wet_spool_drive_pin_diameter_mm"] / 2.0) ** 2
                * cfg["wet_spool_drive_pin_length_mm"],
                places=4,
            )
            for side in ("drive_side", "outboard"):
                labyrinth = base.components[f"fixed_labyrinth_{side}_{index:02d}"]
                self.assertGreaterEqual(spool.distance(labyrinth), 0.19)
        self.assertEqual(cfg["wet_spool_bore_diameter_mm"], 10.1)

    def test_wet_spool_drive_pin_entry_channel_opens_through_both_faces(self) -> None:
        drive, axes, _, base = self.build()
        cfg = self.contract.integration
        pin_radius = 0.5 * cfg["wet_spool_drive_pin_diameter_mm"]
        core_radius = self.contract.drive.spool_core_radius_mm
        for index, axis in enumerate(axes, start=1):
            spool = base.components[f"fixed_wet_spool_{index:02d}"]
            full_radial_entry_path = drive._radial_cylinder_at(
                axis.spool_center,
                axis.angle_deg,
                pin_radius,
                -core_radius - 0.2,
                core_radius + 0.2,
                axis.spool_center[2],
            )
            self.assertLess(
                spool.intersect(full_radial_entry_path).Volume(),
                0.02,
                f"spool {index} traps the pin behind a blind radial-hole end",
            )

    def test_fixed_output_support_land_has_a_removable_cartridge(self) -> None:
        drive, axes, _, base = self.build()
        cfg = self.contract.integration
        self.assertEqual(
            cfg["output_support_cartridge_inner_diameter_mm"],
            cfg["bearing_outer_seat_diameter_mm"],
        )
        cartridge_radius = 0.5 * cfg["output_support_cartridge_outer_diameter_mm"]
        for index, axis in enumerate(axes, start=1):
            land = base.components[f"fixed_output_support_land_{index:02d}"]
            cartridge = base.components[f"fixed_output_support_cartridge_{index:02d}"]
            through_bore_probe = drive._axis_cylinder(
                axis.spool_center,
                axis.spool_axis,
                cartridge_radius,
                cfg["far_support_pod_tangent_bounds_mm"][0] - 0.2,
                cfg["far_support_pod_tangent_bounds_mm"][1] + 0.2,
            )
            self.assertLess(land.intersect(through_bore_probe).Volume(), 0.02)
            self.assertTrue(cartridge.isValid())
            self.assertGreater(cartridge.Volume(), 0.0)
            self.assertLess(land.intersect(cartridge).Volume(), 0.02)
            self.assertEqual(len(cartridge.Solids()), 1)
            top_plate = base.components["fixed_top_plate"]
            self.assertLess(
                top_plate.intersect(cartridge).Volume(),
                0.02,
                f"cartridge {index} overlaps the fixed top plate",
            )
            for screw_index in range(1, 3):
                screw = base.components[
                    f"fixed_output_support_cartridge_screw_{index:02d}_{screw_index:02d}"
                ]
                self.assertLess(
                    top_plate.intersect(screw).Volume(),
                    0.02,
                    f"cartridge screw {index}/{screw_index} overlaps the fixed top plate",
                )

    def test_seal_housing_seat_uses_22mm_nominal_bore(self) -> None:
        drive, axes, _, base = self.build()
        axis = axes[0]
        radial = drive._unit_radial(axis.angle_deg)
        center = (
            axis.spool_center[0] + radial[0] * 11.01,
            axis.spool_center[1] + radial[1] * 11.01,
            axis.spool_center[2],
        )
        probe = drive._axis_cylinder(center, axis.spool_axis, 0.02, -8.0, -7.9)
        housing = base.components["fixed_bevel_pod_01"]
        self.assertGreater(probe.intersect(housing).Volume(), 0.0)

    def test_each_output_seal_has_an_integral_dry_side_shoulder(self) -> None:
        drive, axes, _, base = self.build()
        for index in range(1, 4):
            axis = axes[index - 1]
            radial = drive._unit_radial(axis.angle_deg)
            pod = base.components[f"fixed_bevel_pod_{index:02d}"]
            far_pod = base.components[f"fixed_output_support_cartridge_{index:02d}"]
            for s0, s1, housing in (
                (-12.5, -12.4, pod),
                (12.4, 12.5, far_pod),
            ):
                probe_center = (
                    axis.spool_center[0] + radial[0] * 10.8,
                    axis.spool_center[1] + radial[1] * 10.8,
                    axis.spool_center[2],
                )
                probe = drive._axis_cylinder(probe_center, axis.spool_axis, 0.05, s0, s1)
                self.assertGreater(probe.intersect(housing).Volume(), 0.0)

    def test_spool_retainer_and_seal_stack_have_clearance(self) -> None:
        drive, axes, _, base = self.build()
        integration = self.contract.integration
        shoulder_radius = integration["wet_spool_inboard_shoulder_diameter_mm"] / 2.0
        ring_outer_radius = integration["wet_spool_retainer_outer_diameter_mm"] / 2.0
        ring_inner_radius = integration["wet_spool_retainer_groove_diameter_mm"] / 2.0
        side_clearance = integration["wet_spool_side_clearance_mm"]
        for axis in axes:
            index = axis.axis_index
            spool = base.components[f"fixed_wet_spool_{index:02d}"]
            shaft = base.components[f"fixed_output_shaft_{index:02d}"]
            retainer = base.components[f"fixed_spool_retainer_{index:02d}"]
            pin = base.components[f"fixed_spool_drive_pin_{index:02d}"]
            drive_pod = base.components[f"fixed_bevel_pod_{index:02d}"]
            outboard_pod = base.components[f"fixed_output_support_land_{index:02d}"]
            radial = drive._unit_radial(axis.angle_deg)
            shoulder = drive._axis_cylinder(
                axis.spool_center, axis.spool_axis, shoulder_radius,
                -4.5, -3.7,
            )
            self.assertEqual(len(spool.Solids()), 1)
            self.assertAlmostEqual(spool.distance(shoulder), side_clearance, places=5)
            self.assertAlmostEqual(spool.distance(retainer), side_clearance, places=5)
            self.assertLess(spool.intersect(shaft).Volume(), 0.02)
            self.assertLess(retainer.intersect(shaft).Volume(), 0.02)
            self.assertLess(spool.intersect(pin).Volume(), 0.02)
            self.assertLess(shaft.intersect(pin).Volume(), 0.02)
            self.assertLess(drive_pod.intersect(shaft).Volume(), 0.02)
            self.assertLess(outboard_pod.intersect(shaft).Volume(), 0.02)
            self.assertAlmostEqual(
                retainer.Volume(), math.pi * (ring_outer_radius**2 - ring_inner_radius**2), places=4
            )
            groove_probe = __import__("cadquery").Vertex.makeVertex(
                axis.spool_center[0] + axis.spool_axis[0] * 4.2 + radial[0] * 4.75,
                axis.spool_center[1] + axis.spool_axis[1] * 4.2 + radial[1] * 4.75,
                axis.spool_center[2] + axis.spool_axis[2] * 4.2 + radial[2] * 4.75,
            )
            self.assertAlmostEqual(shaft.distance(groove_probe), 0.05, places=5)
            shaft_point = __import__("cadquery").Vertex.makeVertex(
                axis.spool_center[0] + axis.spool_axis[0] * 4.2 + radial[0] * 4.85,
                axis.spool_center[1] + axis.spool_axis[1] * 4.2 + radial[1] * 4.85,
                axis.spool_center[2] + axis.spool_axis[2] * 4.2 + radial[2] * 4.85,
            )
            self.assertAlmostEqual(shaft.distance(shaft_point), 0.05, places=5)
            for side in ("drive_side", "outboard"):
                seal = base.components[f"fixed_oil_seal_{side}_{index:02d}"]
                labyrinth = base.components[f"fixed_labyrinth_{side}_{index:02d}"]
                self.assertTrue(seal.isValid())
                self.assertTrue(labyrinth.isValid())
                self.assertLess(seal.intersect(labyrinth).Volume(), 0.02)
                self.assertGreaterEqual(seal.distance(labyrinth), 0.09)

    def test_bearing_outer_races_have_fixed_housings(self) -> None:
        _, _, _, base = self.build()
        for index in range(1, 4):
            for station, housing_name in (
                ("inner", f"fixed_bevel_pod_{index:02d}"),
                ("outer", f"fixed_output_support_cartridge_{index:02d}"),
            ):
                bearing = base.components[f"fixed_bearing_{station}_{index:02d}"]
                housing = base.components[housing_name]
                self.assertLess(bearing.intersect(housing).Volume(), 0.02)
                self.assertLessEqual(bearing.distance(housing), 0.02)

    def test_drive_plate_register_and_dowels_have_fixed_mates(self) -> None:
        drive, _, module, base = self.build()
        cfg = self.contract.integration
        z0, z1 = (float(value) for value in cfg["drive_register_z_mm"])
        register = drive._vertical_ring(
            (0.0, 0.0, 0.0),
            float(cfg["drive_register_outer_radius_mm"]),
            float(cfg["drive_register_inner_radius_mm"]),
            z0,
            z1,
        )
        plate = module.components[module.plate_name]
        receiver = base.components["fixed_drive_plate_register_seat"]
        self.assertLessEqual(register.cut(plate).Volume(), 0.02)
        self.assertAlmostEqual(register.distance(receiver), 0.25, places=6)
        for index in range(1, 3):
            pin = module.components[f"removable_plate_dowel_{index:02d}"]
            socket = base.components[f"fixed_drive_plate_dowel_socket_{index:02d}"]
            self.assertAlmostEqual(pin.distance(socket), 0.25, places=6)

    def test_root_fastener_axes_are_open_through_fixed_base(self) -> None:
        _, _, _, base = self.build()
        for x_mm, y_mm, _ in self.root.fastener_centers:
            probe = __import__("cadquery").Solid.makeCylinder(
                2.75,
                20.0,
                __import__("cadquery").Vector(x_mm, y_mm, -9.0),
                __import__("cadquery").Vector(0.0, 0.0, 1.0),
            )
            self.assertLess(base.components["fixed_top_plate"].intersect(probe).Volume(), 0.02)

    def test_three_v26_coordinate_deltas_are_recorded(self) -> None:
        _, axes, _, _ = self.build()
        self.assertEqual(len(axes), 3)
        for axis in axes:
            self.assertEqual(len(axis.delta_from_v26_local_mm), 3)
            self.assertTrue(all(math.isfinite(value) for value in axis.delta_from_v26_local_mm))


if __name__ == "__main__":
    unittest.main()
