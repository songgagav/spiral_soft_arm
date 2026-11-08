from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
import unittest

from engineering_audit import (
    compute_force_budget,
    compute_root_load,
    compute_spool_capacity,
    compute_tendon_travel,
    generate_v27_engineering_audit,
    write_engineering_report,
)
from model_contract import load_contract


class V27EngineeringFormulaTests(unittest.TestCase):
    def test_path_difference_from_sampled_centerlines(self) -> None:
        straight = (((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)),)
        curled = (
            (((0.0, 0.0, 0.0), (0.0, 6.0, 0.0)),),
            (((0.0, 0.0, 0.0), (0.0, 2.0, 0.0)),),
        )
        report = compute_tendon_travel(straight, curled)
        self.assertEqual(report.reference_lengths_mm, (5.0,))
        self.assertEqual(report.extreme_lengths_mm, ((6.0,), (2.0,)))
        self.assertEqual(report.signed_deltas_mm, ((1.0,), (-3.0,)))
        self.assertEqual(report.required_travel_mm, (4.0,))

    def test_spool_capacity_includes_twenty_percent_margin(self) -> None:
        report = compute_spool_capacity(
            required_travel_mm=100.0,
            usable_turns=2.0,
            minimum_effective_radius_mm=10.0,
            maximum_effective_radius_mm=12.0,
        )
        self.assertAlmostEqual(report.required_with_margin_mm, 120.0)
        self.assertAlmostEqual(report.available_travel_mm, 40.0 * math.pi)
        self.assertAlmostEqual(report.margin_mm, 40.0 * math.pi - 120.0)
        self.assertTrue(report.qualified)

    def test_force_equals_torque_over_effective_radius_after_losses(self) -> None:
        report = compute_force_budget(
            motor_continuous_torque_nm=1.0,
            drivetrain_efficiency=0.8,
            seal_drag_torque_nm=0.1,
            tendon_friction_efficiency=0.5,
            minimum_effective_radius_mm=10.0,
            maximum_effective_radius_mm=12.0,
        )
        self.assertAlmostEqual(report.net_spool_torque_nm, 0.7)
        self.assertAlmostEqual(report.maximum_tendon_force_n, 35.0)
        self.assertAlmostEqual(report.minimum_tendon_force_n, 0.7 / 0.012 * 0.5)
        self.assertFalse(report.qualified)

    def test_root_moment_from_force_and_lever_arm(self) -> None:
        report = compute_root_load(
            target_mass_kg=1.0,
            displaced_volume_m3=0.0,
            water_density_kg_m3=1000.0,
            lever_arm_m=0.5,
            impact_factor=2.0,
        )
        self.assertAlmostEqual(report.net_downward_force_n, 9.80665)
        self.assertAlmostEqual(report.root_moment_nm, 9.80665)


class V27EngineeringBoundaryTests(unittest.TestCase):
    def test_unknown_displacement_uses_worst_case_one_kg_weight(self) -> None:
        report = compute_root_load(
            target_mass_kg=1.0,
            displaced_volume_m3=None,
            water_density_kg_m3=1025.0,
            lever_arm_m=1.0,
            impact_factor=1.0,
        )
        self.assertEqual(report.buoyant_force_n, 0.0)
        self.assertAlmostEqual(report.net_downward_force_n, 9.80665)
        self.assertFalse(report.qualified)
        self.assertIn("target_displaced_volume", report.missing_measurements)

    def test_capacity_below_required_travel_is_not_qualified(self) -> None:
        report = compute_spool_capacity(
            required_travel_mm=100.0,
            usable_turns=1.0,
            minimum_effective_radius_mm=10.0,
            maximum_effective_radius_mm=12.0,
        )
        self.assertFalse(report.qualified)
        self.assertLess(report.margin_mm, 0.0)

    def test_nonpositive_efficiency_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compute_force_budget(
                motor_continuous_torque_nm=1.0,
                drivetrain_efficiency=0.0,
                seal_drag_torque_nm=0.1,
                tendon_friction_efficiency=0.5,
                minimum_effective_radius_mm=10.0,
                maximum_effective_radius_mm=12.0,
            )

    def test_seal_and_tendon_friction_are_never_omitted(self) -> None:
        with self.assertRaises(TypeError):
            compute_force_budget(  # type: ignore[call-arg]
                motor_continuous_torque_nm=1.0,
                drivetrain_efficiency=0.8,
                minimum_effective_radius_mm=10.0,
                maximum_effective_radius_mm=12.0,
            )
        report = compute_force_budget(
            motor_continuous_torque_nm=1.0,
            drivetrain_efficiency=0.8,
            seal_drag_torque_nm=0.1,
            tendon_friction_efficiency=0.5,
            minimum_effective_radius_mm=10.0,
            maximum_effective_radius_mm=12.0,
        )
        self.assertIn("seal_drag_torque_nm", report.assumptions)
        self.assertIn("tendon_friction_efficiency", report.assumptions)

    def test_report_never_claims_hardware_validation(self) -> None:
        audit = generate_v27_engineering_audit(load_contract())
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_engineering_report(audit, Path(temp_dir) / "audit.json")
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(payload["hardware_validated"])
        self.assertNotIn("hardware validated", json.dumps(payload).lower())
        self.assertFalse(payload["qualified"])
        self.assertTrue(payload["missing_measurements"])
        self.assertTrue(math.isfinite(payload["root_load"]["root_moment_nm"]))
        self.assertGreater(max(payload["tendon_travel"]["required_travel_mm"]), 30.0)
        self.assertAlmostEqual(payload["force_budget"]["minimum_tendon_force_n"], 46.6666666667, places=6)
        self.assertIn("arm_wet_mass_and_buoyancy", payload["missing_measurements"])
        self.assertIn("bolt_group_capacity", payload["missing_measurements"])


if __name__ == "__main__":
    unittest.main()
