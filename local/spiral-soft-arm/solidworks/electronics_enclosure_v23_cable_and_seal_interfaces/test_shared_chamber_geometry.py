"""Focused geometry gate for the v23 serviceable common drive chamber."""
from __future__ import annotations

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "generate_m3508_arm.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("b32_v23_chamber_geometry_test", GENERATOR)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load v23 generator: {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_chamber_separates_drive_and_wet_reel_spaces() -> None:
    v23 = load_generator()
    drives = v23.build_three_drives()
    chamber = v23.build_shared_drive_chamber(drives, v23.P["shared_dry_chamber"])

    required = {
        "common_dry_chamber_shell",
        "removable_bottom_service_cover",
        "bottom_cover_gasket_proxy",
        "dry_cavity_reference",
        "tendon_pass_through_060",
        "tendon_pass_through_180",
        "tendon_pass_through_300",
        "electronics_motor_wire_pass_through_000",
        "electronics_motor_wire_pass_through_120",
        "electronics_motor_wire_pass_through_240",
    }
    assert required <= set(chamber), f"Missing chamber interfaces: {sorted(required-set(chamber))}"

    for name, shape in chamber.items():
        assert shape.isValid(), f"Invalid chamber shape: {name}"
        assert shape.Solids(), f"Chamber shape has no solids: {name}"

    shell = chamber["common_dry_chamber_shell"]
    bounds = shell.BoundingBox()
    assert bounds.zmin <= -175.0 and bounds.zmax >= -8.0
    assert max(bounds.xlen, bounds.ylen) < 350.0, "Chamber exceeds printer XY envelope"
    top_radius = next(float(radius) for z, radius in v23.P["shared_dry_chamber"][
        "outer_profile_z_radius_mm"] if float(z) == -8.0)
    assert top_radius <= 125.0, "Chamber top overhangs the frozen 250 mm top plate"
    max_radius = max(float(radius) for _z, radius in v23.P["shared_dry_chamber"][
        "outer_profile_z_radius_mm"])
    assert max_radius <= 144.0, "Motor chamber is larger than the compact packaging target"
    assert float(v23.P["shared_dry_chamber"]["tendon_pass_through"][
        "outer_diameter_mm"]) <= 4.2, "Tendon liner exceeds the v10 through-bore"
    assert float(v23.P["shared_dry_chamber"]["service_cover"][
        "outer_hex_circumradius_mm"]) == max_radius

    for angle in (60, 180, 300):
        wet_space = chamber[f"wet_reel_clearance_volume_{angle:03d}"]
        dry_space = chamber["dry_cavity_reference"]
        reel_parts = [shape for name, shape in drives.items()
                      if name.startswith(f"drive_{angle:03d}_wet_reel_")]
        assert reel_parts, f"No reel parts found for channel {angle}"
        for reel in reel_parts:
            assert reel.intersect(wet_space).Volume() >= reel.Volume() - 0.02, (
                f"Channel {angle} reel is not contained by its wet-side service pocket"
            )
            assert reel.intersect(dry_space).Volume() <= 0.02, (
                f"Channel {angle} reel intrudes into the dry chamber reference volume"
            )

        motor = drives[f"drive_{angle:03d}_DJI_M3508_P19_official_STEP"]
        assert motor.intersect(shell).Volume() <= 0.02, (
            f"Channel {angle} official motor intersects the chamber wall"
        )
        assert shell.distance(motor) >= 3.0, (
            f"Channel {angle} official motor has less than 3 mm nominal wall clearance"
        )
        retainer = drives[f"drive_{angle:03d}_M4x10_wet_reel_retainer_screw_proxy"]
        assert retainer.intersect(shell).Volume() <= 0.02, (
            f"Channel {angle} reel retainer screw intersects the wet-side tunnel wall"
        )


def test_v23_base_components_preserve_the_v10_arm_and_top_plate() -> None:
    v23 = load_generator()
    components = v23.build_v10_reference_components()
    required = {
        "B32_v10_arm_sections_and_dovetails",
        "v10_hexagonal_top_plate_with_tabs",
        "v10_central_electronics_canister",
        "v10_central_electronics_canister_lid",
        "v10_shore_tether_gland_proxy",
    }
    assert required <= set(components)
    arm = components["B32_v10_arm_sections_and_dovetails"]
    plate = components["v10_hexagonal_top_plate_with_tabs"]
    assert arm.isValid() and len(arm.Solids()) == 5
    assert plate.isValid() and max(plate.BoundingBox().xlen,
                                   plate.BoundingBox().ylen) <= 250.01
    assert not any(name.startswith("wet_motor_") or name.startswith("spool_")
                   for name in components), "Legacy wet drive proxies must not survive into v23"


def test_v23_assembly_has_three_replacement_drives_and_no_old_lower_panels() -> None:
    v23 = load_generator()
    components = v23.build_v23_assembly_components()
    assert "v23_integral_top_plate_and_drive_chamber" in components
    assert "removable_bottom_service_cover" in components
    assert "B32_v10_arm_sections_and_dovetails" in components
    assert "v10_hexagonal_top_plate_with_tabs" not in components
    assert "common_dry_chamber_shell" not in components
    assert "top_interface_gasket_proxy" not in components
    integrated = components["v23_integral_top_plate_and_drive_chamber"]
    assert integrated.isValid() and len(integrated.Solids()) == 1
    assert max(integrated.BoundingBox().xlen,
               integrated.BoundingBox().ylen) < 350.0
    assert all(row["gear_remaining_intersection_with_integrated_plate_mm3"] <= 0.02
               for row in v23.CHAMBER_INTEGRATION_AUDIT)
    for angle in (60, 180, 300):
        assert f"drive_{angle:03d}_DJI_M3508_P19_official_STEP" in components
        assert f"tendon_pass_through_{angle:03d}" in components
        assert components[f"tendon_pass_through_{angle:03d}"].intersect(
            integrated
        ).Volume() <= 0.02, f"Channel {angle} tendon liner intersects the top plate"
        for name, shape in components.items():
            if name.startswith(f"drive_{angle:03d}_wound_tendon_turn_"):
                assert shape.intersect(
                    components[f"tendon_pass_through_{angle:03d}"]
                ).Volume() <= 0.02, (
                    f"Channel {angle} tendon liner overlaps a wound tendon turn"
                )
        assert any(name.startswith(f"drive_{angle:03d}_wet_reel_")
                   for name in components)
    for esc_index, port_angle in enumerate((0, 120, 240), start=1):
        assert components[f"v10_ESC_{esc_index}_envelope"].intersect(
            components[f"electronics_motor_wire_pass_through_{port_angle:03d}"]
        ).Volume() <= 0.02, (
            f"ESC {esc_index} intersects its motor wire pass-through sleeve"
        )
    battery_harness = components["v23_battery_to_BMS_two_core_harness"]
    for target in ("bottom_cover_gasket_proxy", "v10_voltage_regulator_envelope",
                   "v10_BMS_envelope", "v10_central_electronics_canister"):
        assert battery_harness.intersect(components[target]).Volume() <= 0.02, (
            f"Battery-to-BMS harness intersects {target}"
        )
    assert not any("v10_lower_panel_" in name for name in components)
    assert not any(name.startswith("wet_motor_") or name.startswith("spool_")
                   for name in components)


if __name__ == "__main__":
    test_shared_chamber_separates_drive_and_wet_reel_spaces()
    test_v23_base_components_preserve_the_v10_arm_and_top_plate()
    test_v23_assembly_has_three_replacement_drives_and_no_old_lower_panels()
    print("shared chamber geometry gate: PASS")
