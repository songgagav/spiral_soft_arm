"""Targeted geometry checks for the v23 seal shaft and gland seat."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "generate_m3508_arm.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("b32_v23_seal_geometry_test", GENERATOR)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load v23 generator: {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V23SealInterfaceTests(unittest.TestCase):
    def test_output_shaft_has_full_round_counterface_under_rotary_seal(self) -> None:
        v23 = load_generator()
        _arm, drive = v23.load_reference_generators()
        shaft_name = "tangential_output_shaft_D_flat_and_M4_tap_proxy"
        shaft_key = "drive_060_" + shaft_name
        shaft = v23.build_three_drives()[shaft_key]
        seal_x0, seal_x1 = (float(x) for x in v23.P["drive_layout"][
            "output_seal_local_x_range_mm"
        ])
        journal = drive.cyl_x(5.0, seal_x0, seal_x1, 0.0, -23.0)
        pose = v23.DRIVE_POSES[60]
        angle = float(pose["rotation_deg"])
        tx, ty, tz = (float(x) for x in pose["translation_xyz_mm"])
        journal = journal.rotate((0, 0, 0), (0, 0, 1), angle).translate((tx, ty, tz))
        self.assertLessEqual(
            abs(shaft.intersect(journal).Volume() - journal.Volume()), 0.02,
            "The output shaft must remain a complete Ø10 mm cylinder across the seal lip track",
        )


    def test_shared_shell_contains_direct_machined_seal_gland_for_each_channel(self) -> None:
        v23 = load_generator()
        drives = v23.build_three_drives()
        chamber = v23.build_shared_drive_chamber(drives, v23.P["shared_dry_chamber"])
        gland = v23.P["shared_dry_chamber"]["output_seal_gland"]
        self.assertEqual(gland["housing_bore_diameter_mm"], 22.0)
        self.assertGreaterEqual(gland["seat_depth_mm"], gland["seal_width_mm"]+0.3)
        shell = chamber["common_dry_chamber_shell"]
        arm, _drive = v23.load_reference_generators()
        canister = arm.make_shell_with_clear_tendon_radials()[0]
        self.assertLessEqual(
            shell.intersect(canister).Volume(), 0.02,
            "The integrated seal gland must clear the central electronics canister",
        )
        self.assertGreaterEqual(
            shell.distance(canister),
            float(gland["minimum_nominal_clearance_to_central_canister_mm"])-0.05,
        )
        for angle in (60, 180, 300):
            seal = drives[f"drive_{angle:03d}_SKF_10x22x7_rotary_seal_envelope"]
            self.assertTrue(seal.isValid() and seal.Solids())
            self.assertLessEqual(
                seal.intersect(shell).Volume(), 0.02,
                f"Channel {angle} seal envelope must fit in the integrated Ø22 gland seat",
            )


if __name__ == "__main__":
    unittest.main()
