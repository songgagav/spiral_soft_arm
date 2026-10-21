"""Acceptance checks for the generated first-print mechanical package."""
from __future__ import annotations

import bmesh
import bpy
import json
import pathlib
import unittest

TESTS = pathlib.Path(__file__).resolve().parent
REPO = TESTS.parents[2]
OUTPUT = REPO / "local" / "spiral-soft-arm" / "preprint" / "v1"


def imported_mesh_metrics(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    nonmanifold = sum(not edge.is_manifold for edge in bm.edges)
    remaining = set(bm.verts)
    components = 0
    while remaining:
        components += 1
        stack = [remaining.pop()]
        while stack:
            vert = stack.pop()
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
    bm.free()
    points = [obj.matrix_world @ vert.co for vert in obj.data.vertices]
    dims = [max(point[axis] for point in points) - min(point[axis] for point in points) for axis in range(3)] if points else [0.0, 0.0, 0.0]
    return nonmanifold, components, dims


class PreprintPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = OUTPUT / "printable_parts.json"
        if not manifest.is_file():
            raise FileNotFoundError(f"run build_preprint_assembly.py first: {manifest}")
        cls.manifest = json.loads(manifest.read_text(encoding="utf-8"))
        cls.parts = cls.manifest["parts"]

    def test_b32_selection_units_and_assembly_envelopes(self):
        self.assertEqual(self.manifest["units"], "mm")
        self.assertEqual(self.manifest["recommended_first_build"], "B32")
        self.assertEqual(self.manifest["package_generator_version"], "0.1.0")
        self.assertEqual(len(self.parts), 10)
        dims = {part["file"]: part["dimensions_mm"] for part in self.parts}
        self.assertEqual(dims["01_soft_arm_B32_cut_off_550mm.stl"], [68.0, 68.0, 550.0136])
        self.assertEqual(dims["02_rigid_base_frame_280x8.stl"], [280.0, 280.0, 8.0])
        self.assertEqual(dims["09_B32_tip_80mm_process_coupon.stl"][2], 80.0)
        self.assertAlmostEqual(dims["10_B32_base_80mm_process_coupon.stl"][2], 80.0136, places=3)
        envelope = self.manifest["assembly_envelopes"]
        self.assertEqual(envelope["C610_board_mm"], [22.0, 50.0, 7.3])
        self.assertGreater(envelope["minimum_corner_post_to_board_clearance_mm"], 0.0)
        self.assertAlmostEqual(envelope["tray_nominal_board_clearance_mm"]["radial"], 0.5)
        self.assertEqual(envelope["tray_cable_exit_gap_mm"], 14.0)
        tendon = self.manifest["tendon_design"]
        self.assertEqual(tendon["count"], 3)
        self.assertGreater(tendon["theoretical_single_layer_takeup_mm"], 400.0)

    def test_every_print_stl_is_a_closed_single_solid_after_reimport(self):
        failures = []
        for part in self.parts:
            path = OUTPUT / "stl" / part["file"]
            self.assertTrue(path.is_file(), str(path))
            before = set(bpy.data.objects)
            bpy.ops.wm.stl_import(filepath=str(path), global_scale=1.0, use_scene_unit=False)
            imported = [item for item in bpy.data.objects if item not in before and item.type == "MESH"]
            self.assertEqual(len(imported), 1, f"expected one imported mesh for {part['file']}")
            obj = imported[0]
            nonmanifold, components, dims = imported_mesh_metrics(obj)
            bpy.data.objects.remove(obj, do_unlink=True)
            if nonmanifold != 0 or components != 1:
                failures.append(f"{part['file']}: nonmanifold={nonmanifold}, components={components}")
            for actual, expected in zip(dims, part["dimensions_mm"]):
                if abs(actual - expected) > 0.1:
                    failures.append(f"{part['file']}: STL bbox {dims} differs from manifest {part['dimensions_mm']}")
                    break
        self.assertFalse(failures, "\n".join(failures))

    def test_manifest_claims_closed_single_solids(self):
        invalid = [part["file"] for part in self.parts if not part["closed_single_solid"]]
        self.assertEqual(invalid, [], "invalid printable meshes: " + ", ".join(invalid))


if __name__ == "__main__":
    unittest.main(argv=[__file__])
