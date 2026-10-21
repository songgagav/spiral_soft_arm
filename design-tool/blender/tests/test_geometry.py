"""Theory, boundary-count, and unit conversion regression checks."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from geometry import (  # noqa: E402
    count_units,
    build_body_profile_polygons,
    kg_mm2_to_kg_m2,
    local_profile_metrics,
    mm3_to_m3,
    mm_to_m,
    paper_metrics,
    percent_to_fraction,
)

CASES = (
    ("A35", 3.74959, 0.139608, 35, 5.265),
    ("A36", 3.43438, 0.140105, 36, 4.848),
    ("B31", 5.37465, 0.137107, 31, 7.345),
    ("B32", 4.90484, 0.137820, 32, 6.755),
)

FITTED_CASES = (
    ("A36", 3.7794787730, 0.13961, 36, 5.0, 5.265),
    ("A37", 3.4591883310, 0.14013, 37, 5.0, 4.846),
    ("B32", 5.4367772850, 0.13699, 32, 7.0, 7.359),
    ("B33", 4.9562457360, 0.13774, 33, 7.0, 6.764),
)


class GeometryTests(unittest.TestCase):
    def test_theta_boundary_counts_integer_units(self):
        for turns_pi, expected in ((7.3, 31), (7.4, 32), (7.9, 35), (8.0, 36)):
            self.assertEqual(count_units(turns_pi, 30), expected)

    def test_paper_seed_dimensions(self):
        for _name, a, b, n, tip in CASES:
            result = paper_metrics(a, b, n, 30)
            self.assertAlmostEqual(result["tip_diameter_mm"], tip, delta=0.01)
            self.assertAlmostEqual(result["base_diameter_mm"], 68.0, delta=0.01)
            self.assertAlmostEqual(result["centerline_length_mm"], 550.0, delta=0.01)

    def test_explicit_unit_conversions(self):
        self.assertEqual(percent_to_fraction(50.0), 0.5)
        self.assertAlmostEqual(mm_to_m(550.0), 0.550)
        self.assertAlmostEqual(mm3_to_m3(1_000_000.0), 0.001)
        self.assertAlmostEqual(kg_mm2_to_kg_m2(1.0), 1e-6)
        with self.assertRaises(ValueError):
            percent_to_fraction(101.0)

    def test_physical_body_uses_tip_and_base_peak_planes(self):
        for _name, a, b, n, target_tip, expected_tip in FITTED_CASES:
            metrics = local_profile_metrics(a, b, n, 30)
            self.assertAlmostEqual(metrics["discrete_axis_span_mm"], 550.0, delta=0.05)
            self.assertAlmostEqual(metrics["local_base_diameter_mm"], 68.0, delta=0.01)
            self.assertAlmostEqual(metrics["local_tip_diameter_mm"], expected_tip, delta=0.01)
            self.assertLessEqual(abs(metrics["local_tip_diameter_mm"] - target_tip), 0.5)
            polygons = build_body_profile_polygons(a, b, 30, 0.5, n)
            self.assertAlmostEqual(min(x for poly in polygons for x, _y in poly), 0.0, places=6)
            self.assertAlmostEqual(max(x for poly in polygons for x, _y in poly), 550.0, delta=0.05)


if __name__ == "__main__":
    unittest.main(argv=[__file__])
