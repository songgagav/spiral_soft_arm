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
                "fixed_seal_housing",
                "fixed_oil_seal",
                "fixed_labyrinth",
                "fixed_axial_retainer",
            ):
                name = f"{prefix}_{index:02d}"
                self.assertIn(name, base.components)
                self.assertNotIn(name, module.components)
                self.assertTrue(base.components[name].isValid())

    def test_motor_removal_does_not_remove_or_unseat_shafts(self) -> None:
        _, _, module, base = self.build()
        self.assertTrue(base.shafts_supported_without_drive)
        self.assertEqual(module.removal_sequence[0], "release_three_coupling_sleeves")
        self.assertEqual(module.removal_sequence[1], "translate_plate_downward")
        self.assertEqual(len(base.shaft_support_pairs), 3)
        self.assertTrue(all(len(pair) == 2 for pair in base.shaft_support_pairs))

    def test_top_plate_envelope_is_250_mm(self) -> None:
        _, _, _, base = self.build()
        bounds = base.top_plate.BoundingBox()
        self.assertAlmostEqual(base.top_plate_circumdiameter_mm, 250.0, places=6)
        self.assertAlmostEqual(bounds.xlen, 250.0, places=5)
        self.assertLessEqual(bounds.ylen, 250.0 + 1e-6)

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

    def test_spool_axis_is_perpendicular_to_tendon_direction(self) -> None:
        _, axes, _, _ = self.build()
        for axis in axes:
            dot = sum(a * b for a, b in zip(axis.shaft_axis, axis.tendon_direction))
            self.assertAlmostEqual(dot, 0.0, places=8)
            self.assertAlmostEqual(math.sqrt(sum(value * value for value in axis.shaft_axis)), 1.0, places=8)

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

    def test_three_v26_coordinate_deltas_are_recorded(self) -> None:
        _, axes, _, _ = self.build()
        self.assertEqual(len(axes), 3)
        for axis in axes:
            self.assertEqual(len(axis.delta_from_v26_local_mm), 3)
            self.assertTrue(all(math.isfinite(value) for value in axis.delta_from_v26_local_mm))


if __name__ == "__main__":
    unittest.main()
