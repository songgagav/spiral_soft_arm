"""End-to-end stage-A Blender generation contract."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

class BlenderGenerationTests(unittest.TestCase):
    def test_four_candidates_have_three_cable_paths_and_cut_variants(self):
        from generate_candidates import generate_candidates

        results = generate_candidates(
            str(ROOT / "candidates"),
            str(REPO / "local" / "spiral-soft-arm" / "stage-a"),
        )
        self.assertEqual({item["candidate_id"] for item in results}, {"A36", "A37", "B32", "B33"})
        for item in results:
            self.assertTrue(pathlib.Path(item["blend_path"]).is_file())
            self.assertEqual(item["cable_count"], 3)
            self.assertEqual(set(item["variants"]), {"cut_on", "cut_off"})
            for variant in item["variants"].values():
                self.assertTrue(pathlib.Path(variant["stl_path"]).is_file())
                self.assertEqual(len(variant["cable_path_angles_deg"]), 3)
                self.assertAlmostEqual(variant["cable_path_angles_deg"][1] - variant["cable_path_angles_deg"][0], 120.0)
            self.assertTrue(item["objects"]["body"])
            self.assertTrue(item["objects"]["elastic_axis"])
            names = " ".join(str(value) for value in item["objects"].values())
            self.assertNotRegex(names, r"(?i)motor|base|spool|anchor")


if __name__ == "__main__":
    unittest.main(argv=[__file__])
