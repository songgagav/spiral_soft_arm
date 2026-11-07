from __future__ import annotations

import importlib.util
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


class V27ArmSegmentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        contract_module = load_local_module("v27_contract_for_arm", "model_contract.py")
        cls.contract = contract_module.load_contract()

    def get_arm_module(self):
        return load_local_module("v27_arm_module", "arm_module.py")

    def test_42_units_span_nominal_one_meter(self) -> None:
        arm = self.get_arm_module()
        planes = arm.compute_unit_planes(self.contract)
        self.assertEqual(len(planes), 43)
        self.assertAlmostEqual(planes[0], 0.0, places=9)
        self.assertAlmostEqual(planes[-1], 1000.0, places=6)
        heights = [b - a for a, b in zip(planes, planes[1:])]
        self.assertEqual(len(heights), 42)
        self.assertTrue(all(value > 0.0 for value in heights))
        self.assertTrue(all(a > b for a, b in zip(heights, heights[1:])))

    def test_four_ranges_cover_each_unit_once(self) -> None:
        arm = self.get_arm_module()
        planes = arm.compute_unit_planes(self.contract)
        ranges = arm.choose_four_segment_ranges(planes, 300.0)
        self.assertEqual(len(ranges), 4)
        flattened = [unit for start, end in ranges for unit in range(start, end + 1)]
        self.assertEqual(flattened, list(range(1, 43)))
        self.assertEqual(ranges[0][0], 1)
        self.assertEqual(ranges[-1][1], 42)
        self.assertTrue(all(left[1] + 1 == right[0] for left, right in zip(ranges, ranges[1:])))

    def test_no_segment_exceeds_print_height(self) -> None:
        arm = self.get_arm_module()
        planes = arm.compute_unit_planes(self.contract)
        ranges = arm.choose_four_segment_ranges(planes, 300.0)
        spans = [planes[end] - planes[start - 1] for start, end in ranges]
        self.assertTrue(all(span < 300.0 for span in spans), spans)
        self.assertEqual(ranges, ((1, 3), (4, 8), (9, 16), (17, 42)))
        self.assertAlmostEqual(max(spans), 264.8434050798424, places=6)

    def test_segmentation_rejects_impossible_height(self) -> None:
        arm = self.get_arm_module()
        planes = arm.compute_unit_planes(self.contract)
        longest_unit = max(b - a for a, b in zip(planes, planes[1:]))
        with self.assertRaisesRegex(ValueError, "individual unit"):
            arm.choose_four_segment_ranges(planes, longest_unit - 0.01)


class V27ArmCadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        contract_module = load_local_module("v27_contract_for_arm_cad", "model_contract.py")
        cls.contract = contract_module.load_contract()

    def build(self):
        arm = load_local_module("v27_arm_module_cad", "arm_module.py")
        if not hasattr(arm, "build_arm_module"):
            self.fail("arm_module.build_arm_module is not implemented")
        return arm.build_arm_module(self.contract)

    def test_arm_bounds_and_diameters(self) -> None:
        result = self.build()
        bounds = result.assembled_proxy.BoundingBox()
        self.assertAlmostEqual(bounds.zmin, 0.0, places=5)
        self.assertAlmostEqual(bounds.zmax, 1000.0, places=4)
        self.assertAlmostEqual(result.root_diameter_mm, 120.0, places=6)
        self.assertAlmostEqual(result.tip_diameter_mm, 5.0, places=6)
        self.assertGreaterEqual(bounds.xlen, 119.9)
        self.assertGreaterEqual(bounds.ylen, 119.9)

    def test_three_tendon_channels_are_continuous(self) -> None:
        result = self.build()
        self.assertEqual(len(result.tendon_centerlines), 3)
        for channel in result.tendon_centerlines:
            with self.subTest(channel=channel.name):
                self.assertEqual(channel.samples[0][2], 0.0)
                self.assertEqual(channel.samples[-1][2], 1000.0)
                self.assertGreaterEqual(len(channel.samples), 43)
                z_values = [point[2] for point in channel.samples]
                self.assertTrue(all(left < right for left, right in zip(z_values, z_values[1:])))
                for boundary in result.segment_boundary_z_mm:
                    hits = [point for point in channel.samples if abs(point[2] - boundary) < 1e-8]
                    self.assertEqual(len(hits), 1)

    def test_three_internal_dovetails_exist(self) -> None:
        result = self.build()
        self.assertEqual(len(result.dovetails), 3)
        self.assertEqual(
            [joint.name for joint in result.dovetails],
            ["dovetail_01", "dovetail_02", "dovetail_03"],
        )
        for joint in result.dovetails:
            self.assertTrue(joint.male.isValid())
            self.assertTrue(joint.female_cutter.isValid())
            self.assertGreater(joint.male.Volume(), 0.0)

    def test_each_dovetail_has_positive_lock(self) -> None:
        result = self.build()
        self.assertEqual(len(result.lock_features), 3)
        for lock in result.lock_features:
            self.assertTrue(lock.proxy.isValid())
            self.assertGreater(lock.proxy.Volume(), 0.0)
            self.assertEqual(lock.kind, "cross_pin")

    def test_arm_result_names_four_print_segments(self) -> None:
        result = self.build()
        self.assertEqual(
            tuple(result.print_segments),
            ("arm_segment_01", "arm_segment_02", "arm_segment_03", "arm_segment_04"),
        )
        self.assertEqual(len(result.segment_ranges), 4)
        for name, shape in result.print_segments.items():
            with self.subTest(name=name):
                self.assertTrue(shape.isValid())
                self.assertGreater(shape.Volume(), 0.0)


if __name__ == "__main__":
    unittest.main()
