from __future__ import annotations

import importlib.util
import re
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


def load_contract_module():
    module_path = HERE / "model_contract.py"
    if not module_path.is_file():
        raise AssertionError(f"missing V27 contract loader: {module_path}")
    spec = importlib.util.spec_from_file_location("v27_model_contract", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load V27 contract module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V27ParameterContractTests(unittest.TestCase):
    def get_contract(self):
        module = load_contract_module()
        return module, module.load_contract()

    def test_candidate_identity_and_version_boundary(self) -> None:
        _, contract = self.get_contract()
        self.assertEqual(contract.candidate_id, "V27-1M-M2006")
        self.assertEqual(contract.schema_version, "27.0.0")
        self.assertIn("candidate", contract.release_status.lower())
        self.assertEqual(contract.output_directory, HERE)
        self.assertNotIn("integrated_assembly_v26", str(contract.output_directory))

    def test_paper_geometry_contract(self) -> None:
        _, contract = self.get_contract()
        arm = contract.arm
        self.assertEqual(arm.nominal_length_mm, 1000.0)
        self.assertEqual(arm.unit_count, 42)
        self.assertEqual(arm.segment_count, 4)
        self.assertEqual(arm.tendon_count, 3)
        self.assertEqual(arm.tip_diameter_mm, 5.0)
        self.assertEqual(arm.root_diameter_mm, 120.0)
        self.assertEqual(arm.tendon_material, "UHMWPE")
        self.assertEqual(arm.tendon_diameter_mm, 0.5)
        self.assertEqual(arm.max_segment_height_mm, 300.0)

    def test_modular_interface_contract(self) -> None:
        _, contract = self.get_contract()
        root = contract.root_interface
        drive = contract.drive
        self.assertEqual(root.top_plate_circumdiameter_mm, 250.0)
        self.assertEqual(root.register_diameter_mm, 130.0)
        self.assertEqual(root.register_height_mm, 5.0)
        self.assertEqual(root.dowel_count, 2)
        self.assertEqual(root.dowel_diameter_mm, 6.0)
        self.assertEqual(root.fastener_count, 6)
        self.assertEqual(root.fastener_thread, "M5")
        self.assertEqual(root.fastener_pcd_mm, 160.0)
        self.assertEqual(drive.motor_model, "DJI RoboMaster M2006 P36")
        self.assertEqual(drive.motor_count, 3)
        self.assertFalse(drive.c610_part_of_removable_module)
        self.assertEqual(
            set(drive.fixed_transmission_members),
            {"seal_housings", "bearings", "shafts", "wet_spools", "integrated_input_shafts"},
        )

    def test_integrated_motor_input_shaft_and_seal_fits_are_explicitly_reviewed(self) -> None:
        _, contract = self.get_contract()
        integration = contract.integration
        socket = integration["m2006_input_shaft_socket_diameter_mm"]
        collar = integration["m2006_input_shaft_collar_diameter_mm"]
        collar_bearing_clearance = integration[
            "m2006_input_shaft_collar_bearing_clearance_mm"
        ]
        socket_depth = integration["m2006_input_shaft_socket_depth_mm"]
        motor_flat = integration["m2006_motor_d6_flat_from_axis_mm"]
        socket_flat = integration["m2006_input_shaft_socket_flat_from_axis_mm"]
        pin = integration["m2006_input_shaft_cross_pin_diameter_mm"]
        pin_hole = integration["m2006_input_shaft_cross_pin_hole_diameter_mm"]
        fixed_shaft = integration["fixed_shaft_diameter_mm"]
        seal = integration["pressure_seal_dimensions_mm"]
        self.assertEqual(socket, 6.2)
        self.assertEqual(collar, 15.0)
        self.assertEqual(collar_bearing_clearance, 0.2)
        self.assertEqual(socket_depth, 13.0)
        self.assertEqual(motor_flat, 2.5)
        self.assertEqual(socket_flat, 2.6)
        self.assertAlmostEqual(socket_flat - motor_flat, 0.1)
        self.assertEqual(collar - socket, 8.8)
        self.assertEqual(pin, 2.8)
        self.assertEqual(pin_hole, 3.2)
        self.assertEqual(fixed_shaft, 10.0)
        self.assertNotIn("motor_coupling_set_screw_diameter_mm", integration)
        self.assertEqual(seal, [10.0, 22.0, 7.0])
        self.assertEqual(integration["pressure_seal_housing_bore_tolerance"], "H8")
        self.assertEqual(integration["pressure_seal_shaft_tolerance"], "h11")
        self.assertEqual(integration["pressure_seal_housing_axial_overrun_mm"], 0.5)
        self.assertEqual(integration["wet_spool_inboard_shoulder_diameter_mm"], 10.8)
        self.assertEqual(integration["wet_spool_inboard_shoulder_width_mm"], 0.8)
        self.assertEqual(integration["wet_spool_retainer_groove_diameter_mm"], 9.6)
        self.assertEqual(integration["wet_spool_retainer_groove_width_mm"], 1.0)
        self.assertEqual(integration["wet_spool_retainer_outer_diameter_mm"], 16.0)
        self.assertEqual(integration["wet_spool_side_clearance_mm"], 0.2)
        self.assertEqual(integration["wet_spool_drive_pin_diameter_mm"], 2.5)
        self.assertEqual(integration["wet_spool_drive_pin_hole_diameter_mm"], 2.7)
        self.assertEqual(integration["wet_spool_drive_pin_length_mm"], 19.0)
        self.assertEqual(
            integration["output_shaft_seal_ranges_mm"], [[-12.0, -5.0], [5.0, 12.0]]
        )
        self.assertEqual(
            integration["output_shaft_labyrinth_ranges_mm"],
            [[-13.1, -12.1], [12.1, 13.1]],
        )

    def test_selected_catalog_gear_and_stepped_8mm_journal(self) -> None:
        _, contract = self.get_contract()
        review = contract.integration["gear_hardware_review"]
        self.assertEqual(review["installed_geometry_status"], "catalog_envelope_proxy_no_tooth_profile")
        self.assertEqual(review["selected_pair"], "KHK SM1.25-25H x 2 per drive")
        self.assertEqual(review["gear_module_mm"], 1.25)
        self.assertEqual(review["tooth_count_per_gear"], 25)
        self.assertEqual(review["ratio"], 1.0)
        self.assertEqual(review["bore_diameter_mm"], 8.0)
        self.assertEqual(review["outside_diameter_mm"], 33.02)
        self.assertEqual(review["catalog_surface_durability_torque_H_Nm"], 1.35)
        self.assertEqual(review["gear_journal_diameter_mm"], 8.0)
        self.assertEqual(review["gear_journal_flat_from_axis_mm"], 3.2)
        self.assertEqual(review["set_screw_diameter_mm"], 4.0)
        self.assertFalse(review["tooth_profile_imported"])
        self.assertEqual(review["candidate_fit_status"], "compact_candidate_layout_reworked_review_required")

    def test_water_and_payload_contract(self) -> None:
        _, contract = self.get_contract()
        environment = contract.environment
        self.assertEqual(environment.media, ("freshwater", "seawater"))
        self.assertEqual(environment.max_depth_m, 5.0)
        self.assertEqual(environment.run_time_min, 30.0)
        self.assertEqual(environment.payload_mass_kg, 1.0)
        self.assertEqual(environment.motion_profile, "low_speed_full_travel")
        self.assertFalse(environment.high_speed_whipping_required)

    def test_all_sources_exist(self) -> None:
        module, contract = self.get_contract()
        manifest = module.build_source_manifest(contract)
        expected_roles = {
            "paper_pdf",
            "m2006_step",
            "c610_step",
            "electronics_snapshot_manifest",
        }
        self.assertEqual(set(manifest), expected_roles)
        for role, source in manifest.items():
            with self.subTest(role=role):
                self.assertTrue(source.path.is_file())
                self.assertGreater(source.size_bytes, 0)
                self.assertRegex(source.sha256, re.compile(r"^[0-9a-f]{64}$"))
                self.assertEqual(source.role, role)


if __name__ == "__main__":
    unittest.main()
