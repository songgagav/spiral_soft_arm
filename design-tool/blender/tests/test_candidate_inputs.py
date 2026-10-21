"""Input contract checks for the four stage-A candidates."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from geometry import local_profile_metrics  # noqa: E402

EXPECTED = {
    "A36": (36, 3.7794787730, 0.13961, 8.0, 5.0, 5.265, 5.307),
    "A37": (37, 3.4591883310, 0.14013, 8.25, 5.0, 4.846, 4.884),
    "B32": (32, 5.4367772850, 0.13699, 7.4, 7.0, 7.359, 7.421),
    "B33": (33, 4.9562457360, 0.13774, 7.5833333333, 7.0, 6.764, 6.820),
}


class CandidateInputTests(unittest.TestCase):
    def test_exactly_four_candidates_match_frozen_seeds(self):
        files = sorted((ROOT / "candidates").glob("*.json"))
        self.assertEqual({p.stem for p in files}, set(EXPECTED))
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            n, a_mm, b, theta_max_pi, target_tip, local_tip, theory_tip = EXPECTED[path.stem]
            self.assertEqual(data["candidate_id"], path.stem)
            self.assertEqual(data["num_units"], n)
            self.assertAlmostEqual(data["a_mm"], a_mm, places=5)
            self.assertAlmostEqual(data["b"], b, places=6)
            self.assertAlmostEqual(data["theta_max_pi"], theta_max_pi, places=6)
            self.assertEqual(data["delta_theta_deg"], 30)
            self.assertEqual(data["p"], 0.5)
            self.assertEqual(data["base_flange_thickness_mm"], 4.0)
            self.assertEqual(data["base_mount_hole_diameter_mm"], 3.2)
            self.assertEqual(data["base_mount_nut_pocket_af_mm"], 5.7)
            self.assertEqual(data["base_mount_nut_pocket_depth_mm"], 2.6)
            self.assertEqual(data["base_mount_hole_angles_deg"], [60.0, 180.0, 300.0])
            self.assertEqual(data["minimum_tendon_wall_mm"], 0.8)
            self.assertEqual(data["target_tip_diameter_mm"], target_tip)
            self.assertAlmostEqual(data["theory_tip_diameter_mm"], theory_tip, places=3)
            self.assertEqual(data["fit_basis"], "local_discrete_profile")
            self.assertTrue(data["clip_at_peak_planes"])

    def test_discrete_local_profile_fit_meets_print_geometry_targets(self):
        for candidate_id, expected in EXPECTED.items():
            data = json.loads((ROOT / "candidates" / f"{candidate_id}.json").read_text(encoding="utf-8"))
            target_tip = expected[4]
            metrics = local_profile_metrics(data["a_mm"], data["b"], data["num_units"], data["delta_theta_deg"])
            fitted_length_mm = metrics["discrete_axis_span_mm"]
            self.assertAlmostEqual(fitted_length_mm, 550.0, delta=0.1)
            self.assertAlmostEqual(metrics["local_base_diameter_mm"], 68.0, delta=0.01)
            self.assertAlmostEqual(metrics["local_tip_diameter_mm"], expected[5], delta=0.01)
            self.assertLessEqual(abs(metrics["local_tip_diameter_mm"] - target_tip), 0.5)

    def test_units_and_three_cable_percent_contract(self):
        for candidate_id in EXPECTED:
            data = json.loads((ROOT / "candidates" / f"{candidate_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(data["length_unit"], "mm")
            self.assertEqual(data["angle_unit"], "deg")
            self.assertEqual(data["axis"], "+Z")
            self.assertFalse(data["two_cable"])
            self.assertEqual(data["cable_count"], 3)
            self.assertEqual(data["tip_hole_pos_pct"], 50.0)
            self.assertEqual(data["base_hole_pos_pct"], 90.0)
            self.assertTrue(data["cable3_cut_enabled"])

    def test_source_lock_records_local_hashes_without_fake_commit(self):
        lock_path = ROOT / "source_lock.json"
        self.assertTrue(lock_path.exists())
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertIsNone(lock["local_git_commit"])
        self.assertEqual(lock["blender_version"], "5.2.2 LTS")
        self.assertEqual(lock["upstream_commit"], "f563e69f292a6b8cac1946dc45ad9e60d8795391")
        self.assertTrue(lock["source_files"])
        self.assertTrue(all(len(item["sha256"]) == 64 for item in lock["source_files"]))


if __name__ == "__main__":
    unittest.main(argv=[__file__])
