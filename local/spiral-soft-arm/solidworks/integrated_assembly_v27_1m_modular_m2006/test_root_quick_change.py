from __future__ import annotations

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


class V27RootQuickChangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        contract_module = load_local_module("v27_contract_for_root", "model_contract.py")
        arm_module = load_local_module("v27_arm_for_root", "arm_module.py")
        cls.contract = contract_module.load_contract()
        cls.arm = arm_module.build_arm_module(cls.contract)

    def build(self):
        root = load_local_module("v27_root_quick_change", "root_quick_change.py")
        if not hasattr(root, "build_root_interface"):
            self.fail("root_quick_change.build_root_interface is not implemented")
        result = root.build_root_interface(self.contract, self.arm)
        return root, result

    def test_register_sets_centering_not_screws(self) -> None:
        root, result = self.build()
        audit = root.audit_root_interface(result)
        self.assertEqual(result.centering_feature, "register")
        self.assertFalse(result.fasteners_define_centering)
        self.assertEqual(result.register_diameter_mm, self.contract.root_interface.register_diameter_mm)
        self.assertEqual(result.register_height_mm, self.contract.root_interface.register_height_mm)
        self.assertTrue(audit["positive_register_engagement"])

    def test_two_dowels_are_asymmetric(self) -> None:
        root, result = self.build()
        audit = root.audit_root_interface(result)
        self.assertEqual(len(result.dowel_proxies), 2)
        self.assertEqual(result.dowel_angles_deg, self.contract.root_interface.dowel_angles_deg)
        separation = (result.dowel_angles_deg[1] - result.dowel_angles_deg[0]) % 360.0
        self.assertNotAlmostEqual(separation, 180.0)
        self.assertNotAlmostEqual(separation, 120.0)
        self.assertTrue(audit["asymmetric_dowels"])
        for pin in result.dowel_proxies:
            self.assertAlmostEqual(pin.BoundingBox().xlen if pin.BoundingBox().xlen < 7 else pin.BoundingBox().ylen, 6.0, delta=0.05)

    def test_six_m5_holes_on_160_pcd(self) -> None:
        _, result = self.build()
        self.assertEqual(result.fastener_thread, "M5")
        self.assertEqual(len(result.fastener_centers), 6)
        for x_mm, y_mm, _ in result.fastener_centers:
            self.assertAlmostEqual(math.hypot(x_mm, y_mm) * 2.0, 160.0, places=6)

    def test_flange_envelope_within_180(self) -> None:
        _, result = self.build()
        bounds = result.arm_side_flange.BoundingBox()
        self.assertLessEqual(bounds.xlen, self.contract.root_interface.flange_max_diameter_mm + 1e-6)
        self.assertLessEqual(bounds.ylen, self.contract.root_interface.flange_max_diameter_mm + 1e-6)
        self.assertTrue(result.arm_side_flange.isValid())
        self.assertTrue(result.base_side_receiver.isValid())
        self.assertTrue(result.metal_backing_proxy.isValid())

    def test_tool_clearance_for_all_fasteners(self) -> None:
        root, result = self.build()
        audit = root.audit_root_interface(result)
        self.assertEqual(len(result.tool_envelopes), 6)
        self.assertTrue(all(shape.isValid() for shape in result.tool_envelopes))
        self.assertGreaterEqual(audit["minimum_tool_envelope_diameter_mm"], 8.0)
        self.assertTrue(audit["all_fasteners_tool_accessible"])

    def test_three_tendon_terminals_are_keyed(self) -> None:
        root, result = self.build()
        audit = root.audit_root_interface(result)
        self.assertEqual(len(result.tendon_terminals), 3)
        self.assertEqual(len({item.key_code for item in result.tendon_terminals}), 3)
        self.assertEqual([item.angle_deg for item in result.tendon_terminals], [0.0, 120.0, 240.0])
        for terminal in result.tendon_terminals:
            angle = math.radians(terminal.angle_deg)
            expected = (math.cos(angle), math.sin(angle), 0.0)
            self.assertAlmostEqual(terminal.axis_direction[0], expected[0], places=7)
            self.assertAlmostEqual(terminal.axis_direction[1], expected[1], places=7)
            self.assertAlmostEqual(terminal.axis_direction[2], 0.0, places=7)
        self.assertTrue(audit["tendon_terminals_do_not_cross"])

    def test_terminal_secondary_retention_exists(self) -> None:
        _, result = self.build()
        for terminal in result.tendon_terminals:
            self.assertTrue(terminal.capture_block.isValid())
            self.assertTrue(terminal.secondary_retention.isValid())
            self.assertGreater(terminal.adjustment_stroke_mm, 0.0)
            self.assertGreaterEqual(terminal.future_load_cell_straight_length_mm, 20.0)

    def test_arm_capture_sleeve_transfers_load_without_gap(self) -> None:
        _, result = self.build()
        first_segment = self.arm.print_segments["arm_segment_01"]
        self.assertTrue(result.arm_capture_sleeve.isValid())
        self.assertGreater(result.arm_capture_sleeve.intersect(first_segment).Volume(), 1.0)
        self.assertAlmostEqual(result.arm_capture_sleeve.distance(first_segment), 0.0, places=6)

    def test_terminal_blocks_clear_the_tpu_root(self) -> None:
        _, result = self.build()
        first_segment = self.arm.print_segments["arm_segment_01"]
        for terminal in result.tendon_terminals:
            self.assertLess(terminal.capture_block.intersect(first_segment).Volume(), 0.02)

    def test_terminal_entry_direction_comes_from_actual_channel(self) -> None:
        _, result = self.build()
        for terminal, channel in zip(result.tendon_terminals, self.arm.tendon_centerlines):
            delta = tuple(b - a for a, b in zip(channel.samples[0], channel.samples[1]))
            norm = math.sqrt(sum(value * value for value in delta))
            expected = tuple(value / norm for value in delta)
            for actual, target in zip(terminal.axis_direction, expected):
                self.assertAlmostEqual(actual, target, places=7)


if __name__ == "__main__":
    unittest.main()
