"""Run reproducible BREP fit checks for the v23 shared drive chamber."""
from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "generate_m3508_arm.py"
OUTPUT = HERE / "装配冲突审查.json"
ASSEMBLY_REVIEW = HERE / "装配审查.json"


def load_v23():
    spec = importlib.util.spec_from_file_location("b32_v23_fit_audit", GENERATOR)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load v23 generator: {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bounds(shape) -> tuple[float, float, float, float, float, float]:
    box = shape.BoundingBox()
    return (box.xmin, box.ymin, box.zmin, box.xmax, box.ymax, box.zmax)


def aabb_overlap(a, b, tolerance: float = 0.02) -> bool:
    return all(min(a[i + 3], b[i + 3]) - max(a[i], b[i]) > tolerance
               for i in range(3))


def aabb_distance(a, b) -> float:
    return math.sqrt(sum(max(0.0, a[i] - b[i + 3], b[i] - a[i + 3]) ** 2
                         for i in range(3)))


def exact_module_clearances(drives: dict[str, object]) -> list[dict[str, object]]:
    channels: dict[str, list[tuple[str, int, object, tuple[float, ...]]]] = collections.defaultdict(list)
    for name, shape in drives.items():
        channel = name.split("_")[1]
        for index, solid in enumerate(shape.Solids()):
            channels[channel].append((name, index, solid, bounds(solid)))

    results = []
    keys = sorted(channels)
    for index, first in enumerate(keys):
        for second in keys[index + 1:]:
            candidates = sorted(
                (aabb_distance(a[3], b[3]), a, b)
                for a in channels[first]
                for b in channels[second]
            )
            best_distance = float("inf")
            best_pair = None
            tested = 0
            for lower_bound, a, b in candidates:
                if lower_bound >= best_distance:
                    break
                distance = a[2].distance(b[2])
                tested += 1
                if distance < best_distance:
                    best_distance = distance
                    best_pair = (a, b)
            if best_pair is None:
                raise RuntimeError(f"No solids found in drive pair {first}/{second}")
            results.append({
                "channels": [first, second],
                "minimum_exact_solid_distance_mm": round(best_distance, 4),
                "closest_solids": [
                    {"component": best_pair[0][0], "solid_index": best_pair[0][1]},
                    {"component": best_pair[1][0], "solid_index": best_pair[1][1]},
                ],
                "distance_pairs_evaluated_after_AABB_pruning": tested,
            })
    return results


def exact_overlap(a, b) -> float:
    if not aabb_overlap(bounds(a), bounds(b)):
        return 0.0
    return max(0.0, float(a.intersect(b).Volume()))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def all_component_pair_audit(components: dict[str, object]) -> dict[str, object]:
    """Exact BREP overlap sweep plus global nearest clear component pair."""
    rows = [(name, shape, bounds(shape)) for name, shape in components.items()]
    candidates: list[tuple[float, int, int]] = []
    overlap_pairs: list[dict[str, object]] = []
    overlap_categories: collections.Counter[str] = collections.Counter()
    overlap_keys: set[tuple[int, int]] = set()
    aabb_overlap_count = 0
    pair_count = len(rows) * (len(rows)-1) // 2

    for i, first in enumerate(rows):
        for j in range(i+1, len(rows)):
            second = rows[j]
            lower_bound = aabb_distance(first[2], second[2])
            candidates.append((lower_bound, i, j))
            if aabb_overlap(first[2], second[2], tolerance=0.0):
                aabb_overlap_count += 1
                volume = exact_overlap(first[1], second[1])
                if volume > 0.02:
                    overlap_keys.add((i, j))
                    first_is_frozen = first[0].startswith(("v10_", "B32_v10_"))
                    second_is_frozen = second[0].startswith(("v10_", "B32_v10_"))
                    if first_is_frozen and second_is_frozen:
                        category = "inherited_v10_geometry_pair"
                    elif first_is_frozen or second_is_frozen:
                        category = "new_to_frozen_v10_interface"
                    else:
                        category = "new_v23_geometry_pair"
                    overlap_categories[category] += 1
                    overlap_pairs.append({
                        "components": [first[0], second[0]],
                        "category": category,
                        "intersection_volume_mm3": round(volume, 5),
                        "review": (
                            "inherited overlap in frozen v10 geometry; preserved and not modified"
                            if category == "inherited_v10_geometry_pair" else
                            "new-to-baseline interface overlap; inspect whether it is an intended seat or a real collision"
                            if category == "new_to_frozen_v10_interface" else
                            "new v23 overlap; inspect whether it is an intended contact or a real collision"
                        ),
                    })

    closest = None
    minimum_clearance = float("inf")
    checked_for_clearance = 0
    for lower_bound, i, j in sorted(candidates):
        if lower_bound >= minimum_clearance:
            break
        if (i, j) in overlap_keys:
            continue
        distance = float(rows[i][1].distance(rows[j][1]))
        checked_for_clearance += 1
        if distance < minimum_clearance:
            minimum_clearance = distance
            closest = (i, j)

    return {
        "component_count": len(rows),
        "unordered_component_pairs": pair_count,
        "pairs_with_overlapping_AABBs_exactly_checked": aabb_overlap_count,
        "volume_overlap_threshold_mm3": 0.02,
        "volume_overlap_pair_count": len(overlap_pairs),
        "volume_overlap_pair_count_by_category": dict(overlap_categories),
        "volume_overlap_pairs": overlap_pairs,
        "nearest_nonoverlapping_component_pair": (
            {
                "components": [rows[closest[0]][0], rows[closest[1]][0]],
                "minimum_exact_BREP_distance_mm": round(minimum_clearance, 5),
            } if closest is not None else None
        ),
        "exact_shape_distance_pairs_evaluated_after_AABB_pruning": checked_for_clearance,
    }


def main() -> None:
    v23 = load_v23()
    arm, drive_builder = v23.load_reference_generators()
    drives = v23.build_three_drives()
    chamber = v23.build_shared_drive_chamber(drives, v23.P["shared_dry_chamber"])
    shell = chamber["common_dry_chamber_shell"]
    dry = chamber["dry_cavity_reference"]
    cover = chamber["removable_bottom_service_cover"]
    canister, canister_lid, _gland = arm.make_shell_with_clear_tendon_radials()
    fairing = {name: shape for name, shape in arm.make_fairing().items()
               if name.startswith("upper_panel_")}

    upper_shell_hits = {
        name: round(exact_overlap(shell, shape), 5)
        for name, shape in fairing.items()
    }
    canister_hits = {
        name: round(exact_overlap(shell, shape), 5)
        for name, shape in (("v10_central_canister", canister),
                            ("v10_central_canister_lid", canister_lid))
    }
    motor_clearances = []
    for angle in (60, 180, 300):
        motor = drives[f"drive_{angle:03d}_DJI_M3508_P19_official_STEP"]
        motor_clearances.append({
            "channel_hole_angle_deg": angle,
            "intersection_volume_with_chamber_wall_mm3": round(exact_overlap(motor, shell), 5),
            "minimum_exact_distance_to_chamber_wall_mm": round(shell.distance(motor), 4),
            "official_motor_valid_solids": len(motor.Solids()),
        })

    gland_cfg = v23.P["shared_dry_chamber"]["output_seal_gland"]
    seal_x0, seal_x1 = (float(x) for x in gland_cfg["seal_nominal_x_range_mm"])
    seal_fit_checks = []
    for angle in (60, 180, 300):
        shaft = drives[f"drive_{angle:03d}_tangential_output_shaft_D_flat_and_M4_tap_proxy"]
        seal = drives[f"drive_{angle:03d}_SKF_10x22x7_rotary_seal_envelope"]
        journal_local = drive_builder.cyl_x(5.0, seal_x0, seal_x1, 0.0, -23.0)
        pose = v23.DRIVE_POSES[angle]
        journal = journal_local.rotate(
            (0, 0, 0), (0, 0, 1), float(pose["rotation_deg"])
        ).translate(tuple(float(x) for x in pose["translation_xyz_mm"]))
        journal_overlap = float(shaft.intersect(journal).Volume())
        seal_fit_checks.append({
            "channel_hole_angle_deg": angle,
            "seal_to_shell_intersection_mm3": round(exact_overlap(seal, shell), 5),
            "seal_to_shaft_proxy_intersection_mm3": round(exact_overlap(seal, shaft), 5),
            "full_round_journal_volume_mm3": round(float(journal.Volume()), 5),
            "round_journal_volume_present_mm3": round(journal_overlap, 5),
            "round_journal_complete": abs(journal_overlap-float(journal.Volume())) <= 0.02,
        })

    pocket_checks = []
    canister_radius = float(arm.v5.CFG["canister"]["outer_diameter_mm"]) / 2
    canister_roof_z = float(arm.v5.CFG["canister"]["top_z_mm"])
    cable_outer_radius = float(v23.P["shared_dry_chamber"][
        "tendon_pass_through"]["outer_diameter_mm"]) / 2
    cable_roof_clearance = []
    for row in v23.DRIVE_LAYOUT_AUDIT:
        angle = int(round(float(row["hole_angle_deg"])))
        wet_space = chamber[f"wet_reel_clearance_volume_{angle:03d}"]
        reel_names = [name for name in drives
                      if name.startswith(f"drive_{angle:03d}_wet_reel_")]
        reel_volume = sum(float(drives[name].Volume()) for name in reel_names)
        reel_in_wet = sum(float(drives[name].intersect(wet_space).Volume())
                          for name in reel_names)
        reel_in_dry = sum(float(drives[name].intersect(dry).Volume())
                          for name in reel_names)
        pocket_checks.append({
            "channel_hole_angle_deg": angle,
            "reel_component_count": len(reel_names),
            "total_reel_component_volume_mm3": round(reel_volume, 4),
            "reel_volume_in_wet_service_pocket_mm3": round(reel_in_wet, 4),
            "reel_volume_in_dry_cavity_mm3": round(reel_in_dry, 5),
            "wet_pocket_contains_reel": reel_in_wet >= reel_volume - 0.02,
            "reel_clear_of_dry_cavity": reel_in_dry <= 0.02,
        })

        start = row["cable_tangent_point_xyz_mm"]
        end = row["tendon_hole_center_xyz_mm"]
        r0 = math.hypot(float(start[0]), float(start[1]))
        r1 = math.hypot(float(end[0]), float(end[1]))
        fraction = (canister_radius-r0)/(r1-r0)
        z_at_canister_radius = float(start[2]) + fraction*(float(end[2])-float(start[2]))
        tube_low_z = z_at_canister_radius-cable_outer_radius
        cable_roof_clearance.append({
            "channel_hole_angle_deg": angle,
            "cable_tube_bottom_z_at_canister_radius_mm": round(tube_low_z, 4),
            "canister_roof_z_mm": canister_roof_z,
            "nominal_vertical_roof_clearance_mm": round(tube_low_z-canister_roof_z, 4),
        })

    cover_canister_intersection = exact_overlap(cover, canister)
    layout = v23.validate_layout_parameters()
    cover_cfg = v23.P["shared_dry_chamber"]["service_cover"]
    shell_bounds = v23.bounds_xyz_mm(shell)
    cover_bounds = v23.bounds_xyz_mm(cover)
    max_footprint = max(shell.BoundingBox().xlen, shell.BoundingBox().ylen,
                        cover.BoundingBox().xlen, cover.BoundingBox().ylen)
    minimum_motor_clearance = min(row["minimum_exact_distance_to_chamber_wall_mm"]
                                  for row in motor_clearances)
    minimum_roof_clearance = min(row["nominal_vertical_roof_clearance_mm"]
                                 for row in cable_roof_clearance)
    module_clearances = exact_module_clearances(drives)

    components = v23.build_v23_assembly_components()
    pair_audit = all_component_pair_audit(components)
    overlap_rows = pair_audit["volume_overlap_pairs"]
    inherited_overlaps = [
        row for row in overlap_rows
        if row["category"] == "inherited_v10_geometry_pair"
    ]
    new_overlaps = [
        row for row in overlap_rows
        if row["category"] == "new_v23_geometry_pair"
    ]
    expected_contact_tokens = (
        ("DJI_M3508_P19_official_STEP", "M5x45_axial_retaining_screw_proxy"),
        ("KHK_output_M4_set_screw_Y_proxy", "tangential_output_shaft_D_flat_and_M4_tap_proxy"),
        ("wound_tendon_turn_5_proxy", "straight_tendon_proxy"),
    )
    unexpected_new_overlaps = [
        row for row in new_overlaps
        if not any(all(any(token in name for name in row["components"])
                       for token in pair)
                   for pair in expected_contact_tokens)
    ]
    new_to_frozen_overlaps = [
        row for row in overlap_rows
        if row["category"] == "new_to_frozen_v10_interface"
    ]
    if unexpected_new_overlaps or new_to_frozen_overlaps:
        raise ValueError(
            "Unexpected v23 assembly overlap: "
            + json.dumps(unexpected_new_overlaps+new_to_frozen_overlaps, ensure_ascii=False)
        )
    step_path = v23.OUTPUT_STEP
    step_readback = v23.cq.importers.importStep(str(step_path)).val()
    if not step_readback.isValid():
        raise ValueError("v23 STEP round-trip is invalid")
    image_paths = (v23.OUTPUT_EXTERIOR_PREVIEW, v23.OUTPUT_SECTION_PREVIEW)
    from PIL import Image

    image_sizes = {path.name: list(Image.open(path).size) for path in image_paths}
    max_radial_error_deg = max(
        math.degrees(math.asin(min(1.0, abs(float(row["cable_plan_radial_cross"])))))
        for row in v23.DRIVE_LAYOUT_AUDIT
    )
    max_reel_perpendicular_error_deg = max(
        math.degrees(math.asin(min(1.0, abs(float(row["reel_axis_cable_dot"])))) )
        for row in v23.DRIVE_LAYOUT_AUDIT
    )

    assembly_review = {
        "schema_version": "1.0.0",
        "status": "geometric_integration_candidate",
        "units": "mm",
        "created_from": "audit_shared_chamber_fit.py",
        "source_manifest": v23.source_manifest(),
        "assembly": {
            "step_path": str(step_path),
            "step_sha256": sha256(step_path),
            "step_valid_after_reimport": step_readback.isValid(),
            "named_component_count": len(components),
            "source_solid_count": sum(len(shape.Solids()) for shape in components.values()),
            "reimported_solid_count": len(step_readback.Solids()),
            "bounds_xyz_minmax_mm": v23.bounds_xyz_mm(step_readback),
            "integral_top_plate_and_drive_chamber": {
                "fusion_status": "valid_single_solid_with_local_gear_relief_pockets",
                "channel_gear_clearance_checks": v23.CHAMBER_INTEGRATION_AUDIT,
            },
            "preview_pngs": {
                path.name: {"sha256": sha256(path), "size_px": image_sizes[path.name]}
                for path in image_paths
            },
        },
        "all_named_component_pair_audit": pair_audit,
        "overlap_interpretation": {
            "inherited_v10_overlap_count": len(inherited_overlaps),
            "inherited_v10_largest_intersections": sorted(
                inherited_overlaps,
                key=lambda row: row["intersection_volume_mm3"],
                reverse=True,
            )[:10],
            "new_v23_overlap_count": len(new_overlaps),
            "expected_new_v23_contact_pairs": new_overlaps,
            "unexpected_new_v23_volume_intersection_count": len(unexpected_new_overlaps),
            "new_to_frozen_interface_overlap_count": len(new_to_frozen_overlaps),
            "note": "Expected v23 intersections are motor M5 retaining screw engagement, KHK output M4 set-screw contact with the shaft flat, and continuity where each wound tendon turn joins its straight tendon proxy.",
        },
        "line_and_seal_interfaces": {
            "cable_to_hole_length_mm_each": [
                row["cable_to_hole_length_mm"] for row in v23.DRIVE_LAYOUT_AUDIT
            ],
            "tendon_liner_outer_inner_diameter_mm": [
                v23.P["shared_dry_chamber"]["tendon_pass_through"]["outer_diameter_mm"],
                v23.P["shared_dry_chamber"]["tendon_pass_through"]["inner_diameter_mm"],
            ],
            "tendon_liner_start_after_reel_tangent_mm": v23.P[
                "shared_dry_chamber"]["tendon_pass_through"][
                "liner_start_offset_after_tangent_mm"
            ],
            "tendon_liner_end_clearance_before_root_mm": v23.P[
                "shared_dry_chamber"]["tendon_pass_through"][
                "liner_end_clearance_before_root_mm"
            ],
            "oblique_top_plate_route": {
                "status": "straight upper reel tangent through a new 4.2 mm oblique bore",
                "top_exit_radius_mm": v23.P["drive_layout"]["tendon_hole_radius_mm"],
                "underside_entry_radius_mm_each": [
                    row["plate_underside_entry_radius_mm"]
                    for row in v23.DRIVE_LAYOUT_AUDIT
                ],
                "root_transition": "smooth 60 mm swept passage joins the native B32 tendon channel",
            },
            "maximum_tendon_plan_deviation_from_radial_deg": round(max_radial_error_deg, 6),
            "maximum_reel_axis_deviation_from_perpendicular_deg": round(
                max_reel_perpendicular_error_deg, 6
            ),
            "reel_axis_cable_dot_abs_each": [
                row["reel_axis_cable_dot"] for row in v23.DRIVE_LAYOUT_AUDIT
            ],
            "output_seal_candidate_mm": v23.P["seals"]["reel_output_seal_candidate_mm"],
            "seal_fit_checks_each": seal_fit_checks,
            "direct_machined_gland": {
                "nominal_bore_mm": gland_cfg["housing_bore_diameter_mm"],
                "bore_tolerance": gland_cfg["housing_bore_tolerance"],
                "seat_depth_mm": gland_cfg["seat_depth_mm"],
                "seal_width_mm": gland_cfg["seal_width_mm"],
                "depth_margin_over_width_mm": round(
                    float(gland_cfg["seat_depth_mm"])-float(gland_cfg["seal_width_mm"]), 4
                ),
                "boss_outer_diameter_mm": gland_cfg["boss_outer_diameter_mm"],
                "nominal_radial_boss_wall_mm": round(
                    (float(gland_cfg["boss_outer_diameter_mm"])-
                     float(gland_cfg["housing_bore_diameter_mm"]))/2, 4
                ),
                "machined_after_print": True,
            },
            "seat_fit_status": "nominal CAD envelope passes; H8 bore, roundness, Ra, and shaft counterface must be measured after machining",
            "water_service_status": "not approved from geometry; confirm medium, differential pressure, and rotating duty with SKF",
        },
        "localized_geometry_results": {
            "shared_chamber_report": str(OUTPUT),
            "status": "geometric_fit_candidate",
            "drive_to_drive_minimum_exact_distances_mm": [
                item["minimum_exact_solid_distance_mm"] for item in module_clearances
            ],
            "minimum_motor_to_shell_clearance_mm": round(minimum_motor_clearance, 4),
            "minimum_cable_liner_to_canister_roof_clearance_mm": round(
                minimum_roof_clearance, 4
            ),
            "wet_reel_pocket_containment_all_channels": all(
                item["wet_pocket_contains_reel"] and item["reel_clear_of_dry_cavity"]
                for item in pocket_checks
            ),
            "upper_fairing_and_canister_intersections_mm3": {
                **upper_shell_hits, **canister_hits,
            },
        },
        "not_verified": [
            "The root fairlead bend, cable wear, guide friction, liner fit, and native-channel connection need a printed coupon and loaded motion test.",
            "The SKF candidate is specified for oil/grease; water suitability, 5 m pressure margin, shaft runout, finished counterface and service life need supplier confirmation and wet testing.",
            "Bearing combined radial/axial loads, life, fits and temperature.",
            "Gear tooth geometry, backlash, mesh, rated torque and thermal performance.",
            "Printed materials, wall strength, fasteners, print orientation, slicing and assembly access.",
            "Dry-chamber pressure resistance, water ingress, connector/cable feedthrough ratings, and 5 m immersion.",
            "Dynamic tendon wear, contamination, drainage and operating-cycle performance.",
        ],
    }
    ASSEMBLY_REVIEW.write_text(
        json.dumps(assembly_review, ensure_ascii=False, indent=2)+"\n", encoding="utf-8"
    )
    print(json.dumps({
        "assembly_review": str(ASSEMBLY_REVIEW),
        "all_pair_summary": {
            key: value for key, value in pair_audit.items()
            if key != "volume_overlap_pairs"
        },
        "maximum_radial_deviation_deg": round(max_radial_error_deg, 6),
        "maximum_reel_perpendicular_error_deg": round(max_reel_perpendicular_error_deg, 6),
        "step_valid": step_readback.isValid(),
        "step_solid_count": len(step_readback.Solids()),
    }, ensure_ascii=False, indent=2))

    report = {
        "schema_version": "2.0.0",
        "status": "geometric_fit_candidate",
        "units": "mm",
        "audit_scope": "BREP collision/clearance and nominal packaging only; no pressure, material, seal-life, or print validation",
        "sources": v23.source_manifest(),
        "drive_layout": layout,
        "shared_chamber": {
            "shell_valid": shell.isValid(),
            "shell_solid_count": len(shell.Solids()),
            "shell_bounds_xyz_minmax_mm": shell_bounds,
            "service_cover_bounds_xyz_minmax_mm": cover_bounds,
            "max_xy_footprint_mm": round(max_footprint, 4),
            "printer_xy_limit_mm": 350.0,
            "outer_hex_profile_z_radius_mm": v23.P["shared_dry_chamber"]["outer_profile_z_radius_mm"],
            "nominal_wall_thickness_mm": v23.P["shared_dry_chamber"]["wall_thickness_mm"],
            "bottom_cover_central_clearance_diameter_mm": cover_cfg["central_clearance_diameter_mm"],
            "canister_outer_diameter_mm": round(2*canister_radius, 4),
            "bottom_cover_to_canister_radial_gap_mm": round(
                float(cover_cfg["central_clearance_diameter_mm"])/2-canister_radius, 4
            ),
            "bottom_cover_to_canister_exact_intersection_mm3": round(cover_canister_intersection, 5),
            "service_cover_z_clearance_to_motor_bottom_mm": round(
                min(float(drives[f"drive_{angle:03d}_DJI_M3508_P19_official_STEP"].BoundingBox().zmin)
                    for angle in (60,180,300))-float(cover_cfg["z_range_mm"][1]), 4
            ),
            "output_seal_gland": {
                "nominal_bore_mm": gland_cfg["housing_bore_diameter_mm"],
                "seat_depth_mm": gland_cfg["seat_depth_mm"],
                "boss_od_mm": gland_cfg["boss_outer_diameter_mm"],
                "nominal_wall_around_seal_mm": round(
                    (float(gland_cfg["boss_outer_diameter_mm"])-
                     float(gland_cfg["housing_bore_diameter_mm"]))/2, 4
                ),
            },
            "output_seal_fit_checks": seal_fit_checks,
            "upper_v10_fairing_exact_intersection_mm3": upper_shell_hits,
            "central_canister_exact_intersection_mm3": canister_hits,
            "official_motor_to_shell_clearances": motor_clearances,
            "minimum_motor_to_shell_clearance_mm": round(minimum_motor_clearance, 4),
            "wet_reel_service_pocket_checks": pocket_checks,
            "cable_tube_to_canister_roof_checks": cable_roof_clearance,
            "minimum_cable_tube_roof_clearance_mm": round(minimum_roof_clearance, 4),
        },
        "drive_to_drive_minimum_clearances": module_clearances,
        "channel_line_alignment": [
            {
                "channel_angle_deg": row["channel_angle_deg"],
                "hole_angle_deg": row["hole_angle_deg"],
                "reel_center_radius_mm": row["reel_center_radius_mm"],
                "cable_to_hole_length_mm": row["cable_to_hole_length_mm"],
                "reel_axis_cable_dot": row["reel_axis_cable_dot"],
                "cable_plan_radial_cross": row["cable_plan_radial_cross"],
                "tendon_hole_center_xyz_mm": row["tendon_hole_center_xyz_mm"],
            }
            for row in v23.DRIVE_LAYOUT_AUDIT
        ],
        "limits": [
            "The selected bearings have only a rough static tangential load screen; bevel-gear axial thrust, equivalent load, life, fits, and temperature remain unverified.",
            "Motor, gear, shaft, and seal geometry is nominal; actual shaft tolerances and supplier part variants were not measured.",
            "The large wet reel/tendon channels are geometric paths; dynamic tendon sealing, abrasion, debris ingress, and drainage are unverified.",
            "The shared chamber, service cover, canister gasket, and output seals remain geometric interfaces; shell strength, material, fasteners, seal pressure capability, and 5 m water tests remain unverified.",
            "The STEP motor and bearings are native/imported BREP representations; the bevel gears remain tooth-free envelopes, so mesh, torque, and thermal performance are not validated.",
            "CAD clearance does not establish print fit, slicing, assembly access, waterproofing, or functional release.",
        ],
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "output": str(OUTPUT),
        "shell_bounds": shell_bounds,
        "max_xy_footprint_mm": round(max_footprint, 4),
        "motor_shell_clearances_mm": [
            row["minimum_exact_distance_to_chamber_wall_mm"] for row in motor_clearances
        ],
        "fairing_hits_mm3": upper_shell_hits,
        "canister_hits_mm3": canister_hits,
        "wet_pocket_checks": pocket_checks,
        "cable_roof_clearance_mm": round(minimum_roof_clearance, 4),
        "drive_pair_clearance_mm": [
            row["minimum_exact_solid_distance_mm"] for row in module_clearances
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
