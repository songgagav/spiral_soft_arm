"""Mesh, cable-channel, unit, and STL round-trip acceptance checks."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))


class StageARoundtripTests(unittest.TestCase):
    def test_all_candidates_have_mesh_and_stl_diagnostics(self):
        from validate_candidates import validate_all

        output = REPO / "local" / "spiral-soft-arm" / "stage-a"
        report = validate_all(str(ROOT / "candidates"), str(output))
        self.assertEqual({item["candidate_id"] for item in report["candidates"]}, {"A36", "A37", "B32", "B33"})
        for candidate in report["candidates"]:
            self.assertEqual(candidate["unit_count_actual"], candidate["unit_count_target"])
            self.assertAlmostEqual(candidate["units"]["length_550mm_to_m"], 0.550, places=9)
            self.assertEqual(len(candidate["cable_channels"]), 3)
            self.assertTrue(candidate["cable_path_open_checks"]["all_three_open"])
            self.assertTrue(candidate["stl_roundtrip_status"]["cut_off_stl_roundtrip_two_manifold"])
            self.assertTrue(candidate["stl_roundtrip_status"]["cut_off_stl_single_connected_solid"])
            for variant in candidate["variants"].values():
                self.assertEqual(variant["mesh"]["nonmanifold_edge_count"], 0)
                self.assertEqual(variant["mesh"]["inconsistent_normal_edge_count"], 0)
                self.assertEqual(variant["mesh"]["connected_component_count"], 1)
                self.assertIn("minimum_wall_thickness_mm", variant)
                self.assertIn("solid_mass_kg", variant)
                self.assertLessEqual(variant["stl_roundtrip"]["bbox_max_error_mm"], 0.1)
            self.assertEqual(
                candidate["stl_roundtrip_status"]["cut_on_stl_roundtrip_two_manifold"],
                candidate["variants"]["cut_on"]["stl_roundtrip_topology_passed"],
            )
        self.assertTrue((output / "report.json").is_file())


if __name__ == "__main__":
    unittest.main(argv=[__file__])
