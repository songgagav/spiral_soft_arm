from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from itertools import combinations
from typing import Any, Iterable

import cadquery as cq

from arm_module import ArmBuildResult, build_arm_module, make_root_transition_passage
from drive_and_base import (
    DriveModuleResult,
    FixedBaseResult,
    audit_tendon_alignment,
    build_drive_module,
    build_fixed_base,
    optimize_drive_axes,
)
from engineering_audit import generate_v27_engineering_audit
from model_contract import V27Contract, build_source_manifest
from root_quick_change import RootInterfaceResult, build_root_interface
from root_cover import build_root_cover
from spiral_parameters import derive_from_contract


@dataclass(frozen=True)
class V27AssemblyResult:
    contract: V27Contract
    components: dict[str, cq.Shape]
    arm_component_names: tuple[str, ...]
    drive_component_names: tuple[str, ...]
    fixed_component_names: tuple[str, ...]
    electronics_component_names: tuple[str, ...]
    electronics_audit: dict[str, Any]
    service_clearance_shapes: dict[str, cq.Shape]
    arm: ArmBuildResult
    root: RootInterfaceResult
    drive: DriveModuleResult
    fixed: FixedBaseResult
    intentional_contacts: tuple[tuple[str, str], ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_v26_outputs(contract: V27Contract) -> dict[str, str]:
    directory = contract.output_directory.parent / "integrated_assembly_v26_arm_and_v25_electronics"
    snapshot: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".json", ".step", ".png", ".md", ".csv"}:
            continue
        snapshot[path.relative_to(directory).as_posix()] = _sha256(path)
    return snapshot


def _box_from_center(
    size_x: float, size_y: float, size_z: float, center: tuple[float, float, float]
) -> cq.Shape:
    return cq.Solid.makeBox(
        size_x,
        size_y,
        size_z,
        cq.Vector(center[0] - size_x / 2.0, center[1] - size_y / 2.0, center[2] - size_z / 2.0),
    )


def _polar_center(radius_mm: float, angle_deg: float, z_mm: float) -> tuple[float, float, float]:
    angle = math.radians(angle_deg)
    return radius_mm * math.cos(angle), radius_mm * math.sin(angle), z_mm


def _select_v25_electronics(
    contract: V27Contract,
) -> tuple[dict[str, cq.Shape], dict[str, Any], dict[str, cq.Shape]]:
    """Load frozen, individually hashed electronic parts for reproducible builds."""
    manifest_path = (
        contract.output_directory
        / contract.source_specs["electronics_snapshot_manifest"]["path"]
    ).resolve()
    snapshot_directory = manifest_path.parent
    snapshot = json.loads(manifest_path.read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != "1.0.0":
        raise ValueError("unsupported V27 electronics snapshot schema")

    selected: dict[str, cq.Shape] = {}
    service_clearances: dict[str, cq.Shape] = {}
    for collection, target in (
        ("components", selected),
        ("service_clearances", service_clearances),
    ):
        for record in snapshot.get(collection, []):
            step_path = snapshot_directory / record["file"]
            if not step_path.is_file():
                raise FileNotFoundError(step_path)
            if _sha256(step_path) != record["sha256"]:
                raise ValueError(f"electronics snapshot hash mismatch: {step_path.name}")
            imported = cq.importers.importStep(str(step_path))
            solids = imported.solids().vals()
            if len(solids) != 1 or not solids[0].isValid():
                raise ValueError(
                    f"electronics snapshot must contain one valid solid: {step_path.name}"
                )
            target[record["name"]] = solids[0]

    source_audit = snapshot.get("source_v25_audit", {})
    expected_names = set(source_audit.get("selected_component_names", []))
    if set(selected) != expected_names:
        raise ValueError("electronics snapshot component names do not match the frozen audit")
    for audit_key in (
        "hardware_to_hardware_volume_overlaps",
        "internal_to_shell_volume_overlaps",
        "buck_to_v24_hardware_volume_overlaps",
        "m28_to_hardware_volume_overlaps",
    ):
        if source_audit.get(audit_key):
            raise ValueError(
                f"frozen V25 electronics fit audit failed for {audit_key}: "
                f"{source_audit[audit_key]}"
            )
    electronics_audit = {
        **source_audit,
        "source_snapshot_manifest": manifest_path.name,
        "source_snapshot_sha256": _sha256(manifest_path),
        "runtime_note": snapshot["runtime_note"],
        "selected_component_count": len(selected),
        "selected_component_names": sorted(selected),
        "service_clearance_count": len(service_clearances),
        "v27_electronics_adaptations": snapshot["v27_electronics_adaptations"],
    }
    return selected, electronics_audit, service_clearances


def _arm_components(arm: ArmBuildResult, root: RootInterfaceResult) -> dict[str, cq.Shape]:
    components = {
        f"arm_module_{name}": shape for name, shape in arm.print_segments.items()
    }
    terminal_compound = cq.Compound.makeCompound(
        [terminal.capture_block for terminal in root.tendon_terminals]
    )
    components.update(
        {
            "arm_root_flange": root.arm_side_flange,
            "arm_root_backing": root.metal_backing_proxy,
            "arm_register": root.register_proxy,
            "arm_capture_sleeve": root.arm_capture_sleeve,
            "arm_tendon_terminals": terminal_compound,
        }
    )
    for index, lock in enumerate(arm.lock_features, start=1):
        components[f"arm_dovetail_lock_{index:02d}"] = lock.proxy
    for index, anchor in enumerate(arm.tip_anchors, start=1):
        components[f"arm_tip_tendon_anchor_{index:02d}"] = anchor.proxy
    for index, terminal in enumerate(root.tendon_terminals, start=1):
        components[f"arm_terminal_adjustment_{index:02d}"] = terminal.adjustment_envelope
        components[f"arm_terminal_secondary_retention_{index:02d}"] = terminal.secondary_retention
    return components


def build_v27_assembly(contract: V27Contract) -> V27AssemblyResult:
    arm = build_arm_module(contract)
    root = build_root_interface(contract, arm)
    axes = optimize_drive_axes(contract, root)
    drive = build_drive_module(contract, root, axes)
    fixed = build_fixed_base(contract, root, axes)
    cover = build_root_cover(contract)
    arm_components = _arm_components(arm, root)
    drive_components = dict(drive.components)
    fixed_components = dict(fixed.components)
    fixed_components.update(cover.components)
    for index, dowel in enumerate(root.dowel_proxies, start=1):
        fixed_components[f"fixed_root_dowel_{index:02d}"] = dowel
    (
        electronics_components,
        electronics_audit,
        service_clearance_shapes,
    ) = _select_v25_electronics(contract)
    components = {
        **arm_components,
        **drive_components,
        **fixed_components,
        **electronics_components,
    }
    if len(components) != sum(
        len(group)
        for group in (arm_components, drive_components, fixed_components, electronics_components)
    ):
        raise ValueError("component names must be globally unique")
    intentional = [
        ("arm_root_flange", "fixed_root_receiver"),
        ("arm_capture_sleeve", "arm_module_arm_segment_01"),
        ("arm_root_flange", "arm_module_arm_segment_01"),
        ("arm_root_flange", "arm_capture_sleeve"),
        ("arm_root_flange", "arm_root_backing"),
        ("arm_root_flange", "arm_register"),
        ("arm_root_backing", "arm_capture_sleeve"),
        ("arm_root_flange", "arm_tendon_terminals"),
    ]
    for index in range(1, 4):
        intentional.extend(
            [
                ("arm_module_arm_segment_04", f"arm_tip_tendon_anchor_{index:02d}"),
                ("arm_root_flange", f"arm_terminal_adjustment_{index:02d}"),
                ("arm_root_flange", f"arm_terminal_secondary_retention_{index:02d}"),
                ("arm_tendon_terminals", f"arm_terminal_adjustment_{index:02d}"),
                ("arm_tendon_terminals", f"arm_terminal_secondary_retention_{index:02d}"),
                (f"arm_terminal_adjustment_{index:02d}", f"arm_terminal_secondary_retention_{index:02d}"),
            ]
        )
        # The top plate, chamber wall, input bearing post, and two gear pods
        # are modeled as overlapping lands for a single integrated fixed base.
        intentional.extend(
            [
                ("fixed_top_plate", f"fixed_bevel_pod_{index:02d}"),
                ("fixed_top_plate", f"fixed_output_support_land_{index:02d}"),
                ("fixed_common_motor_chamber", f"fixed_bevel_pod_{index:02d}"),
                (
                    "fixed_common_motor_chamber",
                    f"fixed_output_support_land_{index:02d}",
                ),
                (
                    f"fixed_input_support_post_{index:02d}",
                    f"fixed_bevel_pod_{index:02d}",
                ),
            ]
        )
    for index in range(1, 4):
        intentional.extend(
            [
                (f"fixed_shaft_{index:02d}", f"removable_M2006_{index:02d}"),
                (f"fixed_shaft_{index:02d}", f"removable_M2006_cross_pin_{index:02d}"),
                (
                    f"removable_M2006_{index:02d}",
                    f"removable_M2006_cross_pin_{index:02d}",
                ),
                (
                    f"removable_motor_cradle_{index:02d}",
                    f"removable_M2006_{index:02d}",
                ),
                (
                    f"removable_motor_cradle_{index:02d}",
                    "removable_motor_plate",
                ),
                # These toothless conical solids are pitch-envelope proxies;
                # their expected overlap is not a verified gear mesh.
                (
                    f"fixed_bevel_input_envelope_{index:02d}",
                    f"fixed_bevel_output_envelope_{index:02d}",
                ),
            ]
        )
    return V27AssemblyResult(
        contract=contract,
        components=components,
        arm_component_names=tuple(arm_components),
        drive_component_names=tuple(drive_components),
        fixed_component_names=tuple(fixed_components),
        electronics_component_names=tuple(electronics_components),
        electronics_audit=electronics_audit,
        service_clearance_shapes=service_clearance_shapes,
        arm=arm,
        root=root,
        drive=drive,
        fixed=fixed,
        intentional_contacts=tuple(intentional),
    )


def _aabb_overlap(first: cq.Shape, second: cq.Shape) -> bool:
    a = first.BoundingBox()
    b = second.BoundingBox()
    return not (
        a.xmax <= b.xmin
        or b.xmax <= a.xmin
        or a.ymax <= b.ymin
        or b.ymax <= a.ymin
        or a.zmax <= b.zmin
        or b.zmax <= a.zmin
    )


def _component_group(result: V27AssemblyResult, name: str) -> str:
    for label, names in (
        ("arm", result.arm_component_names),
        ("drive", result.drive_component_names),
        ("fixed", result.fixed_component_names),
        ("electronics", result.electronics_component_names),
    ):
        if name in names:
            return label
    raise KeyError(name)


def _all_component_collisions(result: V27AssemblyResult) -> tuple[list[dict[str, Any]], int, list[list[str]]]:
    intentional = {frozenset(pair) for pair in result.intentional_contacts}
    collisions: list[dict[str, Any]] = []
    checked_same_group: list[list[str]] = []
    names = tuple(result.components)
    for first_name, second_name in combinations(names, 2):
        if _component_group(result, first_name) == _component_group(result, second_name):
            checked_same_group.append([first_name, second_name])
        if frozenset((first_name, second_name)) in intentional:
            continue
        first = result.components[first_name]
        second = result.components[second_name]
        if not _aabb_overlap(first, second):
            continue
        volume = first.intersect(second).Volume()
        if volume > 0.02:
            collisions.append(
                {
                    "components": [first_name, second_name],
                    "volume_mm3": round(volume, 4),
                }
            )
    return collisions, len(names) * (len(names) - 1) // 2, checked_same_group


def _drive_removal_sweep(result: V27AssemblyResult) -> dict[str, Any]:
    """Exact swept volume for the current Z-prismatic removable motor module."""
    removed_drive_names = tuple(
        name for name in result.drive_component_names if "cross_pin" in name
    )
    moving_names = tuple(
        name
        for name in result.drive_component_names
        if "cross_pin" not in name
    )
    removable_cover_names = {
        name
        for name in result.fixed_component_names
        if name.startswith("fixed_cover_lower_panel_")
    }
    obstacles = tuple(
        name
        for name in (*result.fixed_component_names, *result.electronics_component_names)
        if name not in removable_cover_names
    )
    travel_mm = 280.0
    initial_release_gap_mm = 0.5
    minimum_clearance = float("inf")
    collisions: list[dict[str, Any]] = []
    for moving_name in moving_names:
        moving = result.components[moving_name].translate(
            cq.Vector(0.0, 0.0, -initial_release_gap_mm)
        )
        sweep_travel_mm = travel_mm - initial_release_gap_mm
        sweep_faces = []
        for face in moving.Faces():
            if face.geomType() != "PLANE":
                continue
            normal = face.normalAt()
            if abs(abs(normal.z) - 1.0) > 1.0e-7:
                continue
            sweep_faces.append(
                cq.Solid.extrudeLinear(
                    face.outerWire(),
                    list(face.innerWires()),
                    cq.Vector(0.0, 0.0, -sweep_travel_mm),
                )
            )
        if not sweep_faces:
            raise ValueError(
                f"continuous removal sweep lacks horizontal faces: {moving_name}"
            )
        swept = moving.fuse(*sweep_faces).clean()
        if not swept.isValid():
            raise ValueError(f"invalid continuous removal sweep for {moving_name}")
        swept_box = swept.BoundingBox()
        for obstacle_name in obstacles:
            obstacle = result.components[obstacle_name]
            obstacle_box = obstacle.BoundingBox()
            dx = max(obstacle_box.xmin - swept_box.xmax, swept_box.xmin - obstacle_box.xmax, 0.0)
            dy = max(obstacle_box.ymin - swept_box.ymax, swept_box.ymin - obstacle_box.ymax, 0.0)
            dz = max(obstacle_box.zmin - swept_box.zmax, swept_box.zmin - obstacle_box.zmax, 0.0)
            lower_bound = math.sqrt(dx * dx + dy * dy + dz * dz)
            if minimum_clearance > 0.0 and lower_bound >= minimum_clearance:
                continue
            volume = swept.intersect(obstacle).Volume()
            if volume > 0.02:
                collisions.append(
                    {
                        "moving_component": moving_name,
                        "fixed_component": obstacle_name,
                        "volume_mm3": round(volume, 4),
                    }
                )
                minimum_clearance = 0.0
            else:
                minimum_clearance = min(minimum_clearance, swept.distance(obstacle))
    return {
        "direction": "negative_z",
        "sweep_type": "exact horizontal-face extrusion after removing six lower service panels, then withdrawing M2006 cross-pins",
        "travel_mm": travel_mm,
        "initial_release_gap_mm": initial_release_gap_mm,
        "moving_component_count": len(moving_names),
        "moving_component_names": list(moving_names),
        "removed_drive_component_names": list(removed_drive_names),
        "removed_fixed_component_names": sorted(removable_cover_names),
        "fixed_obstacle_count": len(obstacles),
        "fixed_obstacle_names": list(obstacles),
        "minimum_clearance_mm": minimum_clearance,
        "collisions": collisions,
        "passes": not collisions,
    }


def _sampled_translation_path(
    result: V27AssemblyResult,
    moving_names: tuple[str, ...],
    removed_before: set[str],
    direction: cq.Vector,
    travel_mm: float,
    *,
    step_mm: float = 1.0,
    initial_release_gap_mm: float = 0.5,
) -> dict[str, Any]:
    """Check translated CAD positions at a dense, documented interval."""
    if step_mm <= 0.0 or travel_mm <= initial_release_gap_mm:
        raise ValueError("translation path needs positive step and travel")
    moving_shapes = [(name, result.components[name]) for name in moving_names]
    excluded = set(moving_names) | set(removed_before)
    obstacle_names = tuple(
        name
        for name in (*result.fixed_component_names, *result.electronics_component_names)
        if name not in excluded
    )
    obstacle_boxes = {
        name: result.components[name].BoundingBox() for name in obstacle_names
    }
    moving_xy_boxes = {
        name: shape.BoundingBox() for name, shape in moving_shapes
    }
    unit_direction = direction.normalized()
    travel_vector = unit_direction * travel_mm

    def swept_bounds(box: Any) -> tuple[float, float, float, float, float, float]:
        return (
            box.xmin + min(0.0, travel_vector.x),
            box.xmax + max(0.0, travel_vector.x),
            box.ymin + min(0.0, travel_vector.y),
            box.ymax + max(0.0, travel_vector.y),
            box.zmin + min(0.0, travel_vector.z),
            box.zmax + max(0.0, travel_vector.z),
        )

    moving_swept_bounds = {
        name: swept_bounds(box) for name, box in moving_xy_boxes.items()
    }
    candidates = tuple(
        name
        for name in obstacle_names
        if any(
            obstacle_boxes[name].xmax >= bounds[0]
            and obstacle_boxes[name].xmin <= bounds[1]
            and obstacle_boxes[name].ymax >= bounds[2]
            and obstacle_boxes[name].ymin <= bounds[3]
            and obstacle_boxes[name].zmax >= bounds[4]
            and obstacle_boxes[name].zmin <= bounds[5]
            for bounds in moving_swept_bounds.values()
        )
    )
    distances = [
        initial_release_gap_mm + index * step_mm
        for index in range(
            int(math.floor((travel_mm - initial_release_gap_mm) / step_mm)) + 1
        )
    ]
    if not distances or distances[-1] < travel_mm - 1e-8:
        distances.append(travel_mm)
    collisions: list[dict[str, Any]] = []
    minimum_clearance = float("inf")
    for distance_mm in distances:
        translation = direction.normalized() * distance_mm
        for moving_name, shape in moving_shapes:
            moved = shape.translate(translation)
            moved_box = moved.BoundingBox()
            for obstacle_name in candidates:
                obstacle_box = obstacle_boxes[obstacle_name]
                if (
                    moved_box.xmax < obstacle_box.xmin
                    or moved_box.xmin > obstacle_box.xmax
                    or moved_box.ymax < obstacle_box.ymin
                    or moved_box.ymin > obstacle_box.ymax
                    or moved_box.zmax < obstacle_box.zmin
                    or moved_box.zmin > obstacle_box.zmax
                ):
                    continue
                obstacle = result.components[obstacle_name]
                volume = moved.intersect(obstacle).Volume()
                if volume > 0.02:
                    collisions.append(
                        {
                            "distance_mm": round(distance_mm, 3),
                            "moving_component": moving_name,
                            "fixed_component": obstacle_name,
                            "volume_mm3": round(volume, 4),
                        }
                    )
                    continue
                dx = max(
                    obstacle_box.xmin - moved_box.xmax,
                    moved_box.xmin - obstacle_box.xmax,
                    0.0,
                )
                dy = max(
                    obstacle_box.ymin - moved_box.ymax,
                    moved_box.ymin - obstacle_box.ymax,
                    0.0,
                )
                dz = max(
                    obstacle_box.zmin - moved_box.zmax,
                    moved_box.zmin - obstacle_box.zmax,
                    0.0,
                )
                minimum_clearance = min(
                    minimum_clearance, math.sqrt(dx * dx + dy * dy + dz * dz)
                )
    return {
        "direction": (
            "negative_z"
            if direction.z < -1e-8
            else "positive_z"
            if direction.z > 1e-8
            else "radial_outward"
        ),
        "path_type": "translated-position CAD intersection samples",
        "sample_step_mm": step_mm,
        "travel_mm": travel_mm,
        "initial_release_gap_mm": initial_release_gap_mm,
        "moving_components": list(moving_names),
        "removed_before": sorted(removed_before),
        "obstacle_count": len(obstacle_names),
        "candidate_obstacle_count": len(candidates),
        "minimum_sampled_aabb_clearance_lower_bound_mm": (
            round(minimum_clearance, 4)
            if math.isfinite(minimum_clearance)
            else None
        ),
        "collisions": collisions,
        "passes": not collisions,
    }


def _lower_cover_removal_paths(result: V27AssemblyResult) -> dict[str, Any]:
    """Audit one face-normal pull-out path for each independently removable panel."""
    lower_panels = tuple(
        f"fixed_cover_lower_panel_{index:02d}" for index in range(1, 7)
    )
    normals = (30.0, 90.0, 150.0, 210.0, 270.0, 330.0)
    panel_removals = [
        {
            "component": panel_name,
            "face_normal_deg": normal_deg,
            **_sampled_translation_path(
                result,
                (panel_name,),
                set(),
                cq.Vector(
                    math.cos(math.radians(normal_deg)),
                    math.sin(math.radians(normal_deg)),
                    0.0,
                ),
                120.0,
            ),
        }
        for panel_name, normal_deg in zip(lower_panels, normals)
    ]
    return {
        "direction": "radial_outward",
        "path_type": "six independent face-normal extractions",
        "sample_step_mm": 1.0,
        "independent_fastener_removal_required": 24,
        "receiver_hardware_status": "not modeled; remove the four M3 fasteners on the selected panel before extraction",
        "panel_removals": panel_removals,
        "passes": all(item["passes"] for item in panel_removals),
    }


def _top_plate_cover_attachment_audit(result: V27AssemblyResult) -> dict[str, Any]:
    """Check ear seating, fastener access and panel extraction at the top plate."""
    cfg = result.contract.integration["root_cover"]
    normals = tuple(float(value) for value in cfg["top_plate_attachment_normals_deg"])
    hole_radius = float(cfg["top_plate_attachment_hole_radius_mm"])
    hole_diameter = float(cfg["top_plate_attachment_hole_diameter_mm"])
    ear_z0, ear_z1 = (
        float(value) for value in cfg["top_plate_attachment_z_bounds_mm"]
    )
    panel_overlap = float(cfg["top_plate_attachment_panel_overlap_mm"])
    inner_radius = float(cfg["top_plate_attachment_inner_radius_mm"])
    tangent_width = float(cfg["top_plate_attachment_tangent_width_mm"])
    top_plate = result.components["fixed_top_plate"]
    plate_box = top_plate.BoundingBox()
    plate_top_z = plate_box.zmax
    plate_bottom_z = plate_box.zmin
    normal_to_index = {
        30.0 + 60.0 * index: index + 1 for index in range(6)
    }
    attachments: list[dict[str, Any]] = []

    plate_hole_diameter_mm = 3.2

    def probe_blockers(probe: cq.Shape) -> list[str]:
        blocked: list[str] = []
        for component_name, component in result.components.items():
            if not _aabb_overlap(probe, component):
                continue
            if probe.intersect(component).Volume() > 0.02:
                blocked.append(component_name)
        return blocked

    for normal_deg in normals:
        panel_name = f"fixed_cover_upper_panel_{normal_to_index[normal_deg]:02d}"
        panel = result.components[panel_name]
        radial = (math.cos(math.radians(normal_deg)), math.sin(math.radians(normal_deg)))
        x_mm, y_mm = hole_radius * radial[0], hole_radius * radial[1]
        hole_center = [round(x_mm, 3), round(y_mm, 3), 0.0]
        plate_hole_center_xy, hole_center_error = _nearest_circular_hole_center_xy(
            top_plate,
            target_center_xy=(x_mm, y_mm),
            diameter_mm=plate_hole_diameter_mm,
            z_planes_mm=(plate_bottom_z, plate_top_z),
        )
        bolt_probe = cq.Solid.makeCylinder(
            1.5,
            ear_z1 - plate_bottom_z + 0.2,
            cq.Vector(x_mm, y_mm, plate_bottom_z - 0.1),
            cq.Vector(0.0, 0.0, 1.0),
        )
        bolt_blockers = probe_blockers(bolt_probe)
        coaxial = hole_center_error is not None and hole_center_error <= 0.01
        bolt_probe_passes = not bolt_blockers

        contact_center_radius = 104.0
        contact_x = contact_center_radius * radial[0]
        contact_y = contact_center_radius * radial[1]
        contact_probe = cq.Solid.makeBox(
            2.0,
            2.0,
            0.2,
            cq.Vector(contact_x - 1.0, contact_y - 1.0, -0.1),
        )
        panel_contact_volume = panel.intersect(contact_probe).Volume()
        plate_contact_volume = top_plate.intersect(contact_probe).Volume()
        unintended_overlap = panel.intersect(top_plate).Volume()
        seat_probe_passes = panel_contact_volume > 0.1 and plate_contact_volume > 0.1
        seating = {
            "ear_bottom_z_mm": ear_z0,
            "top_plate_top_z_mm": round(plate_top_z, 3),
            "plane_delta_mm": round(ear_z0 - plate_top_z, 6),
            "contact_probe_location_radial_mm": contact_center_radius,
            "contact_probe_passes": seat_probe_passes
            and abs(ear_z0 - plate_top_z) <= 1e-6,
            "unintended_volume_overlap_mm3": round(unintended_overlap, 6),
            "probe_contact_volume_mm3": {
                "ear_panel": round(panel_contact_volume, 6),
                "top_plate": round(plate_contact_volume, 6),
            },
        }

        driver_diameter = 8.0
        driver_z0 = ear_z1 + 0.05
        driver_z1 = driver_z0 + 12.0
        driver_probe = cq.Solid.makeCylinder(
            driver_diameter / 2.0,
            driver_z1 - driver_z0,
            cq.Vector(x_mm, y_mm, driver_z0),
            cq.Vector(0.0, 0.0, 1.0),
        )
        driver_blockers = probe_blockers(driver_probe)

        receiver_diameter = 6.5
        receiver_height = 2.4
        receiver_z0 = plate_bottom_z - receiver_height
        receiver_probe = cq.Solid.makeCylinder(
            receiver_diameter / 2.0,
            receiver_height,
            cq.Vector(x_mm, y_mm, receiver_z0),
            cq.Vector(0.0, 0.0, 1.0),
        )
        receiver_blockers = probe_blockers(receiver_probe)

        radial_panel_removal = _sampled_translation_path(
            result,
            (panel_name,),
            set(),
            cq.Vector(radial[0], radial[1], 0.0),
            120.0,
        )
        radial_panel_removal["released_fasteners"] = {
            "existing_panel_m3_fasteners": 4,
            "top_plate_retention_m3_fastener": 1,
        }
        radial_panel_removal["required_sequence"] = [
            "release_four_existing_upper_panel_M3_fasteners",
            "remove_top_plate_retention_M3_fastener",
            "pull_upper_panel_radially_outward",
        ]

        attachments.append(
            {
                "panel_name": panel_name,
                "face_normal_deg": normal_deg,
                "hole_center_mm": hole_center,
                "plate_hole_center_mm": (
                    [round(plate_hole_center_xy[0], 6), round(plate_hole_center_xy[1], 6)]
                    if plate_hole_center_xy is not None
                    else None
                ),
                "hole_center_error_mm": (
                    round(hole_center_error, 6) if hole_center_error is not None else None
                ),
                "coaxial_with_top_plate_hole": coaxial,
                "m3_bolt_probe_passes": bolt_probe_passes,
                "m3_bolt_probe_diameter_mm": 3.0,
                "m3_bolt_blocking_component_names": bolt_blockers,
                "coaxial_tolerance_mm": 0.01,
                "hole_center_detection": {
                    "source": "fixed_top_plate circular B-rep edges on top and bottom planes",
                    "diameter_mm": plate_hole_diameter_mm,
                },
                "seating": seating,
                "driver_corridor": {
                    "diameter_mm": driver_diameter,
                    "z_bounds_mm": [round(driver_z0, 3), round(driver_z1, 3)],
                    "blocked_component_names": driver_blockers,
                    "passes": not driver_blockers,
                },
                "underside_receiver": {
                    "nominal_envelope_mm": [
                        receiver_diameter,
                        receiver_diameter,
                        receiver_height,
                    ],
                    "z_bounds_mm": [round(receiver_z0, 3), round(plate_bottom_z, 3)],
                    "blocked_component_names": receiver_blockers,
                    "passes": not receiver_blockers,
                    "status": "nominal M3 receiver envelope only; exact hardware is not selected",
                },
                "radial_removal": radial_panel_removal,
            }
        )

    all_pass = all(
        item["coaxial_with_top_plate_hole"]
        and item["m3_bolt_probe_passes"]
        and item["seating"]["contact_probe_passes"]
        and item["seating"]["unintended_volume_overlap_mm3"] < 1e-3
        and item["driver_corridor"]["passes"]
        and item["underside_receiver"]["passes"]
        and item["radial_removal"]["passes"]
        for item in attachments
    )
    return {
        "host_panel_names": [item["panel_name"] for item in attachments],
        "attachment_count": len(attachments),
        "nominal_ear_dimensions_mm": {
            "tangential_width": tangent_width,
            "vertical_height": ear_z1 - ear_z0,
            "inner_radius": inner_radius,
        },
        "panel_overlap_mm": panel_overlap,
        "mating_plane_z_mm": round(plate_top_z, 3),
        "attachments": attachments,
        "passes": all_pass,
        "load_qualification": "nominal CAD geometry only; joint strength and fastener preload are not qualified",
    }


def _nearest_circular_hole_center_xy(
    shape: cq.Shape,
    *,
    target_center_xy: tuple[float, float],
    diameter_mm: float,
    z_planes_mm: tuple[float, float],
    radius_tolerance_mm: float = 1e-5,
    plane_tolerance_mm: float = 0.02,
) -> tuple[tuple[float, float] | None, float | None]:
    """Return the closest center from circular B-rep edges at the given Z planes."""
    radius_mm = diameter_mm / 2.0
    centers: list[tuple[float, float]] = []
    for edge in shape.Edges():
        if edge.geomType() != "CIRCLE":
            continue
        if abs(float(edge.radius()) - radius_mm) > radius_tolerance_mm:
            continue
        center = edge.Center()
        if min(abs(center.z - z_plane) for z_plane in z_planes_mm) > plane_tolerance_mm:
            continue
        candidate = (float(center.x), float(center.y))
        if not any(math.dist(candidate, known) <= 1e-4 for known in centers):
            centers.append(candidate)

    if not centers:
        return None, None
    nearest_center = min(
        centers,
        key=lambda center: math.dist(center, target_center_xy),
    )
    return nearest_center, math.dist(nearest_center, target_center_xy)


def _arm_removal_sweep(result: V27AssemblyResult) -> dict[str, Any]:
    """Audit the complete positive-Z arm extraction after its root hardware is released."""
    removed_names = tuple(
        name
        for name in result.arm_component_names
        if name == "arm_tendon_terminals"
        or name.startswith("arm_terminal_adjustment_")
        or name.startswith("arm_terminal_secondary_retention_")
    )
    removed = set(removed_names)
    moving_names = tuple(
        name for name in result.arm_component_names if name not in removed
    )
    removed_fixed_names = ("fixed_root_guard_hex",)
    removed_fixed = set(removed_fixed_names)
    obstacle_names = tuple(
        name
        for name in (
            *result.fixed_component_names,
            *result.drive_component_names,
            *result.electronics_component_names,
        )
        if name not in removed and name not in removed_fixed
    )
    initial_release_gap_mm = 0.5
    final_clearance_mm = 0.5
    highest_obstacle_z_mm = max(
        result.components[name].BoundingBox().zmax for name in obstacle_names
    )
    lowest_moving_z_mm = min(
        result.components[name].BoundingBox().zmin for name in moving_names
    )
    travel_mm = max(
        initial_release_gap_mm,
        highest_obstacle_z_mm - lowest_moving_z_mm + final_clearance_mm,
    )
    sweep_travel_mm = travel_mm - initial_release_gap_mm
    minimum_clearance_mm = float("inf")
    collisions: list[dict[str, Any]] = []
    swept_names: list[str] = []

    for moving_name in moving_names:
        original = result.components[moving_name]
        original_box = original.BoundingBox()
        # Parts that begin above every fixed obstacle only move farther away.
        if original_box.zmin >= highest_obstacle_z_mm:
            continue
        clip_height_mm = highest_obstacle_z_mm - original_box.zmin
        if clip_height_mm <= 1.0e-6:
            continue
        clip = cq.Solid.makeBox(
            max(original_box.xlen, 1.0) + 2.0,
            max(original_box.ylen, 1.0) + 2.0,
            clip_height_mm,
            cq.Vector(original_box.xmin - 1.0, original_box.ymin - 1.0, original_box.zmin),
        )
        sweep_source = original.intersect(clip)
        if sweep_source.isNull() or sweep_source.Volume() <= 1.0e-9:
            continue
        moving = sweep_source.translate(cq.Vector(0.0, 0.0, initial_release_gap_mm))
        sweep_faces = []
        for face in moving.Faces():
            if face.geomType() != "PLANE":
                continue
            normal = face.normalAt()
            if abs(abs(normal.z) - 1.0) > 1.0e-7:
                continue
            sweep_faces.append(
                cq.Solid.extrudeLinear(
                    face.outerWire(),
                    list(face.innerWires()),
                    cq.Vector(0.0, 0.0, sweep_travel_mm),
                )
            )
        if not sweep_faces:
            raise ValueError(
                f"continuous arm removal sweep lacks horizontal faces: {moving_name}"
            )
        swept = moving.fuse(*sweep_faces).clean()
        if not swept.isValid():
            raise ValueError(f"invalid continuous arm removal sweep for {moving_name}")
        swept_names.append(moving_name)
        swept_box = swept.BoundingBox()
        for obstacle_name in obstacle_names:
            obstacle = result.components[obstacle_name]
            if not _aabb_overlap(swept, obstacle):
                continue
            obstacle_box = obstacle.BoundingBox()
            dx = max(obstacle_box.xmin - swept_box.xmax, swept_box.xmin - obstacle_box.xmax, 0.0)
            dy = max(obstacle_box.ymin - swept_box.ymax, swept_box.ymin - obstacle_box.ymax, 0.0)
            dz = max(obstacle_box.zmin - swept_box.zmax, swept_box.zmin - obstacle_box.zmax, 0.0)
            lower_bound = math.sqrt(dx * dx + dy * dy + dz * dz)
            if lower_bound >= minimum_clearance_mm:
                continue
            volume = swept.intersect(obstacle).Volume()
            if volume > 0.02:
                collisions.append(
                    {
                        "moving_component": moving_name,
                        "fixed_component": obstacle_name,
                        "volume_mm3": round(volume, 4),
                    }
                )
                minimum_clearance_mm = 0.0
            else:
                minimum_clearance_mm = min(
                    minimum_clearance_mm, swept.distance(obstacle)
                )

    if not math.isfinite(minimum_clearance_mm):
        minimum_clearance_mm = None
    return {
        "direction": "positive_z",
        "sweep_type": "continuous horizontal-face extrusion after removing the root guard; side cover retained",
        "travel_mm": round(travel_mm, 3),
        "initial_release_gap_mm": initial_release_gap_mm,
        "final_clearance_mm": final_clearance_mm,
        "moving_component_names": list(moving_names),
        "swept_component_names": swept_names,
        "removed_before_sweep": list(removed_names),
        "removed_fixed_component_names": list(removed_fixed_names),
        "fixed_obstacle_names": list(obstacle_names),
        "fixed_obstacle_count": len(obstacle_names),
        "minimum_clearance_mm": minimum_clearance_mm,
        "collisions": collisions,
        "passes": not collisions and bool(swept_names),
    }


def _cylinder_between(
    radius_mm: float,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
) -> cq.Shape:
    direction = cq.Vector(
        end[0] - start[0], end[1] - start[1], end[2] - start[2]
    )
    return cq.Solid.makeCylinder(
        radius_mm, direction.Length, cq.Vector(*start), direction.normalized()
    )


def _tendon_root_route_audit(result: V27AssemblyResult) -> dict[str, Any]:
    radius = 0.5 * float(result.contract.arm.tendon_diameter_mm)
    hits: list[dict[str, Any]] = []
    route_count = 0
    for axis in result.fixed.axes:
        route_count += 1
        lead = _cylinder_between(radius, axis.root_inlet, axis.tangent_point)
        blend = make_root_transition_passage(
            result.contract, axis.angle_deg, radius
        )
        route = lead.fuse(blend).clean()
        own_spool = f"fixed_wet_spool_{axis.axis_index:02d}"
        for component_name, component in result.components.items():
            if component_name == own_spool or not _aabb_overlap(route, component):
                continue
            overlap = route.intersect(component).Volume()
            if overlap > 0.01:
                hits.append(
                    {
                        "route_index": axis.axis_index,
                        "component": component_name,
                        "overlap_mm3": round(overlap, 5),
                    }
                )
    return {
        "route_count": route_count,
        "route_definition": "straight spool tangent to arm root, followed by a 60 mm swept fairlead",
        "cable_diameter_mm": 2.0 * radius,
        "clearance_to_non_spool_components": not hits,
        "hits": hits,
    }


def _motor_port_harness_audit(result: V27AssemblyResult) -> dict[str, Any]:
    """Check three 2 mm cable probes through the motor-port reliefs.

    The straight probes represent only the rigidly constrained portion between
    the electronics-canister wall and motor-chamber side.  They deliberately
    exclude connector tails and flexible service loops from the claim.
    """
    integration = result.contract.integration
    z_mm = float(integration["canister_motor_port_relief_z_mm"])
    start_radius, end_radius = (
        float(value)
        for value in integration["canister_motor_port_relief_radial_range_mm"]
    )
    angles = tuple(
        float(value) for value in integration["canister_motor_port_relief_angles_deg"]
    )
    backings = tuple(
        name
        for name in result.electronics_component_names
        if name.startswith("v27_C610_controller_") and name.endswith("_backing")
    )
    hits: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    checked_nonendpoint_names: set[str] = set()
    for route_index, angle_deg in enumerate(angles, start=1):
        angle = math.radians(angle_deg)
        start = (
            start_radius * math.cos(angle),
            start_radius * math.sin(angle),
            z_mm,
        )
        end = (
            end_radius * math.cos(angle),
            end_radius * math.sin(angle),
            z_mm,
        )
        harness = _cylinder_between(1.0, start, end)
        endpoint_names = {
            f"v27_C610_controller_{route_index:02d}_envelope",
            f"v27_C610_controller_{route_index:02d}_backing",
            f"removable_M2006_{route_index:02d}",
        }
        route_hits: list[dict[str, Any]] = []
        obstacle_names = tuple(
            name for name in result.components if name not in endpoint_names
        )
        checked_nonendpoint_names.update(obstacle_names)
        for obstacle_name in obstacle_names:
            obstacle = result.components[obstacle_name]
            if not _aabb_overlap(harness, obstacle):
                continue
            overlap = harness.intersect(obstacle).Volume()
            if overlap > 0.01:
                hit = {
                    "route_index": route_index,
                    "component": obstacle_name,
                    "overlap_mm3": round(overlap, 5),
                }
                hits.append(hit)
                route_hits.append(hit)
        routes.append(
            {
                "name": f"motor_harness_{route_index:02d}",
                "angle_deg": angle_deg,
                "endpoint_components": sorted(endpoint_names),
                "collisions": route_hits,
            }
        )
    return {
        "route_count": len(angles),
        "checked_backing_count": len(backings),
        "checked_nonendpoint_component_count": len(checked_nonendpoint_names),
        "probe_diameter_mm": 2.0,
        "clearance_passes": not hits,
        "hits": hits,
        "collisions": hits,
        "routes": routes,
        "physical_limitations": [
            "probe covers only the constrained straight relief passage",
            "production wire outer diameter, bend radius, connector tails and strain relief require physical verification",
        ],
    }


def _wiring_accessibility_audit(
    result: V27AssemblyResult, motor_harness: dict[str, Any]
) -> dict[str, Any]:
    components = result.components
    m28_clearances = tuple(
        name for name in result.service_clearance_shapes if "M28" in name
    )
    m12_components = tuple(name for name in components if "M12_USB_C" in name)
    return {
        "motor_harness": motor_harness,
        "external_connectors": {
            "M28_power_service": {
                "passes": not result.electronics_audit[
                    "m28_to_hardware_volume_overlaps"
                ],
                "service_clearance_shapes": list(m28_clearances),
                "physical_limitations": [
                    "production M28 plug tail, cable bend radius and strain relief require physical verification"
                ],
            },
            "M12_typec_envelope": {
                "present": bool(m12_components),
                "component_names": list(m12_components),
                "physical_limitations": [
                    "no mating plug sweep or cable bend-radius model is included",
                    "panel gasket compression and service access require physical verification",
                ],
            },
        },
    }


def _spool_removal_sweeps(result: V27AssemblyResult) -> list[dict[str, Any]]:
    """Sweep each wet spool along its output axis after releasing outboard hardware."""
    travel_mm = 32.0
    paths: list[dict[str, Any]] = []
    for axis in result.fixed.axes:
        index = axis.axis_index
        spool_name = f"fixed_wet_spool_{index:02d}"
        removed_names = [
            f"fixed_output_support_cartridge_{index:02d}",
            f"fixed_output_support_cartridge_screw_{index:02d}_01",
            f"fixed_output_support_cartridge_screw_{index:02d}_02",
            f"fixed_bearing_outer_{index:02d}",
            f"fixed_oil_seal_outboard_{index:02d}",
            f"fixed_labyrinth_outboard_{index:02d}",
            f"fixed_spool_retainer_{index:02d}",
            f"fixed_spool_drive_pin_{index:02d}",
        ]
        missing = [name for name in removed_names if name not in result.components]
        if missing:
            raise ValueError(f"spool {index} removal prerequisites are missing: {missing}")
        removed = set(removed_names)
        obstacles = tuple(
            name
            for name in result.components
            if name != spool_name and name not in removed
        )
        direction = cq.Vector(*axis.spool_axis)
        if abs(direction.Length - 1.0) > 1e-7:
            direction = direction.normalized()
        sweep_faces = []
        spool = result.components[spool_name]
        for face in spool.Faces():
            if face.geomType() != "PLANE":
                continue
            normal = face.normalAt()
            dot = normal.x * direction.x + normal.y * direction.y + normal.z * direction.z
            if abs(abs(dot) - 1.0) > 1e-7:
                continue
            sweep_faces.append(
                cq.Solid.extrudeLinear(
                    face.outerWire(),
                    list(face.innerWires()),
                    direction.multiply(travel_mm),
                )
            )
        if not sweep_faces:
            raise ValueError(f"spool {index} has no end faces for an axial service sweep")
        swept = spool.fuse(*sweep_faces).clean()
        if not swept.isValid():
            raise ValueError(f"invalid axial service sweep for spool {index}")
        collisions: list[dict[str, Any]] = []
        minimum_clearance = float("inf")
        for obstacle_name in obstacles:
            obstacle = result.components[obstacle_name]
            if not _aabb_overlap(swept, obstacle):
                continue
            overlap = swept.intersect(obstacle).Volume()
            if overlap > 0.02:
                collisions.append(
                    {
                        "moving_component": spool_name,
                        "fixed_component": obstacle_name,
                        "volume_mm3": round(overlap, 4),
                    }
                )
                minimum_clearance = 0.0
            else:
                minimum_clearance = min(
                    minimum_clearance, swept.distance(obstacle)
                )
        if not math.isfinite(minimum_clearance):
            minimum_clearance = None
        paths.append(
            {
                "axis_index": index,
                "tendon_detached_required": True,
                "removed_component_names": removed_names,
                "direction": "positive_spool_axis",
                "travel_mm": travel_mm,
                "minimum_clearance_mm": minimum_clearance,
                "collisions": collisions,
                "passes": not collisions,
                "fixed_obstacle_names": list(obstacles),
                "retained_support_land_name": f"fixed_output_support_land_{index:02d}",
                "sweep_type": "continuous axial extrusion of spool end profiles",
            }
        )
    return paths


def _output_support_cartridge_removal_sweeps(
    result: V27AssemblyResult,
    top_plate_cover_attachment: dict[str, Any],
) -> list[dict[str, Any]]:
    """Sweep each outboard support cartridge out of its fixed through-bored land."""
    travel_mm = float(
        result.contract.integration["output_support_cartridge_service_travel_mm"]
    )
    paths: list[dict[str, Any]] = []
    for axis in result.fixed.axes:
        index = axis.axis_index
        cartridge_name = f"fixed_output_support_cartridge_{index:02d}"
        required_panel_normal = (axis.angle_deg + 30.0) % 360.0
        required_panel_attachment = next(
            (
                item
                for item in top_plate_cover_attachment["attachments"]
                if abs(
                    (item["face_normal_deg"] - required_panel_normal + 180.0)
                    % 360.0
                    - 180.0
                )
                <= 1e-6
            ),
            None,
        )
        cover_panel_name = (
            required_panel_attachment["panel_name"]
            if required_panel_attachment is not None
            else None
        )
        cover_panel_removal_passes = bool(
            required_panel_attachment
            and required_panel_attachment["radial_removal"]["passes"]
        )
        removed_names = [
            f"fixed_output_support_cartridge_screw_{index:02d}_01",
            f"fixed_output_support_cartridge_screw_{index:02d}_02",
            f"fixed_bearing_outer_{index:02d}",
            f"fixed_oil_seal_outboard_{index:02d}",
            f"fixed_labyrinth_outboard_{index:02d}",
        ]
        if cover_panel_name is not None and cover_panel_removal_passes:
            removed_names.append(cover_panel_name)
        missing = [name for name in [cartridge_name, *removed_names] if name not in result.components]
        if missing:
            raise ValueError(f"output support cartridge {index} removal prerequisites are missing: {missing}")
        removed = set(removed_names)
        obstacles = tuple(
            name
            for name in result.components
            if name != cartridge_name and name not in removed
        )
        direction = cq.Vector(*axis.spool_axis).normalized()
        cartridge = result.components[cartridge_name]
        end_faces = []
        for face in cartridge.Faces():
            if face.geomType() != "PLANE":
                continue
            normal = face.normalAt()
            dot = normal.x * direction.x + normal.y * direction.y + normal.z * direction.z
            if abs(abs(dot) - 1.0) > 1e-7:
                continue
            end_faces.append(
                cq.Solid.extrudeLinear(
                    face.outerWire(),
                    list(face.innerWires()),
                    direction.multiply(travel_mm),
                )
            )
        if not end_faces:
            raise ValueError(f"output support cartridge {index} has no axial end face for service sweep")
        swept = cartridge.fuse(*end_faces).clean()
        if not swept.isValid():
            raise ValueError(f"invalid output support cartridge {index} extraction sweep")
        collisions: list[dict[str, Any]] = []
        minimum_clearance = float("inf")
        for obstacle_name in obstacles:
            obstacle = result.components[obstacle_name]
            if not _aabb_overlap(swept, obstacle):
                continue
            overlap = swept.intersect(obstacle).Volume()
            if overlap > 0.02:
                collisions.append(
                    {
                        "moving_component": cartridge_name,
                        "fixed_component": obstacle_name,
                        "volume_mm3": round(overlap, 4),
                    }
                )
                minimum_clearance = 0.0
            else:
                minimum_clearance = min(minimum_clearance, swept.distance(obstacle))
        if not math.isfinite(minimum_clearance):
            minimum_clearance = None
        paths.append(
            {
                "axis_index": index,
                "removed_component_names": removed_names,
                "direction": "positive_spool_axis",
                "travel_mm": travel_mm,
                "minimum_clearance_mm": minimum_clearance,
                "collisions": collisions,
                "collision_volume_threshold_mm3": 0.02,
                "passes": not collisions,
                "fixed_obstacle_names": list(obstacles),
                "retained_support_land_name": f"fixed_output_support_land_{index:02d}",
                "initial_face_contact_expected": True,
                "cover_panel_removal_required_first": cover_panel_name,
                "cover_panel_removal_path_passes": cover_panel_removal_passes,
                "cover_panel_retention_fasteners_to_release": 5,
                "cover_panel_service_sequence": [
                    "release_four_existing_upper_panel_M3_fasteners",
                    "remove_top_plate_retention_M3_fastener",
                    "pull_paired_upper_panel_radially_outward_120_mm",
                ],
                "initial_radial_clearance_mm": round(
                    (
                        float(
                            result.contract.integration[
                                "output_support_cartridge_bore_diameter_mm"
                            ]
                        )
                        - float(
                            result.contract.integration[
                                "output_support_cartridge_outer_diameter_mm"
                            ]
                        )
                    )
                    / 2.0,
                    3,
                ),
                "sweep_type": "continuous axial extrusion of cartridge end profiles",
            }
        )
    return paths


def audit_v27_assembly(result: V27AssemblyResult) -> dict[str, Any]:
    contract = result.contract
    alignment = audit_tendon_alignment(
        contract, result.root, result.fixed.axes, result.fixed.components
    )
    engineering = generate_v27_engineering_audit(contract)
    sources = build_source_manifest(contract)
    collisions, checked_pair_count, checked_same_group = _all_component_collisions(result)
    arm_names = set(result.arm_component_names)
    arm_forbidden = [
        item
        for item in collisions
        if any(name in arm_names for name in item["components"])
    ]
    arm_sweep = _arm_removal_sweep(result)
    lower_cover_removal = _lower_cover_removal_paths(result)
    top_plate_cover_attachment = _top_plate_cover_attachment_audit(result)
    drive_sweep = _drive_removal_sweep(result)
    support_cartridge_removal = _output_support_cartridge_removal_sweeps(
        result, top_plate_cover_attachment
    )
    spool_removal = _spool_removal_sweeps(result)
    tendon_route = _tendon_root_route_audit(result)
    motor_ports = _motor_port_harness_audit(result)
    wiring_accessibility = _wiring_accessibility_audit(result, motor_ports)
    cover_cfg = contract.integration["root_cover"]
    cover_profile = [
        [float(z_mm), float(radius_mm)]
        for z_mm, radius_mm in cover_cfg["panel_profile_stations_mm"]
    ]
    cover_frame_height = float(cover_cfg["frame_height_mm"])
    cover_frame_thickness = float(cover_cfg["frame_radial_thickness_mm"])

    def cover_radius_at(z_mm: float) -> float:
        for (za, ra), (zb, rb) in zip(cover_profile, cover_profile[1:]):
            if za - 1e-8 <= z_mm <= zb + 1e-8:
                return ra + (rb - ra) * (z_mm - za) / (zb - za)
        raise ValueError(f"cover profile does not define z={z_mm:g} mm")

    cover_rib_centers = [
        float(value) for value in cover_cfg["raised_rib_z_centers_mm"]
    ]
    cover_support_hole_centers = [
        float(value) for value in cover_cfg["fastener_row_z_centers_mm"]
    ]
    cover_rib_specs = tuple(
        (
            center_z,
            center_z - cover_frame_height / 2.0,
            center_z + cover_frame_height / 2.0,
        )
        for center_z in cover_rib_centers
    )
    cover_rib_outer_radii = [
        cover_radius_at(center_z) + cover_frame_thickness
        for center_z in cover_rib_centers
    ]
    cover_rib_outer_radius_ranges = [
        [
            cover_radius_at(band_z0) + cover_frame_thickness,
            cover_radius_at(band_z1) + cover_frame_thickness,
        ]
        for _, band_z0, band_z1 in cover_rib_specs
    ]
    cover_max_outer_radius = max(cover_rib_outer_radii)
    cover_max_radius = max(radius_mm for _, radius_mm in cover_profile)
    cover_lower_panel_names = tuple(
        f"fixed_cover_lower_panel_{index:02d}" for index in range(1, 7)
    )
    cover_upper_panel_names = tuple(
        f"fixed_cover_upper_panel_{index:02d}" for index in range(1, 7)
    )
    cover_panel_names = (*cover_lower_panel_names, *cover_upper_panel_names)
    cover_panel_shapes = [result.components[name] for name in cover_panel_names]
    cover_panel_compound = cq.Compound.makeCompound(cover_panel_shapes)
    cover_panel_bounds = cover_panel_compound.BoundingBox()
    cover_panel_max_radius = max(
        math.hypot(vertex.Center().x, vertex.Center().y)
        for shape in cover_panel_shapes
        for vertex in shape.Vertices()
    )
    cover_outer_shapes = cover_panel_shapes
    cover_outer_compound = cq.Compound.makeCompound(cover_outer_shapes)
    cover_outer_bounds = cover_outer_compound.BoundingBox()
    cover_outer_max_radius = max(
        math.hypot(vertex.Center().x, vertex.Center().y)
        for shape in cover_outer_shapes
        for vertex in shape.Vertices()
    )

    def component_bounds_mm(name: str) -> dict[str, Any]:
        bounds = result.components[name].BoundingBox()
        return {
            "name": name,
            "x_mm": round(bounds.xlen, 3),
            "y_mm": round(bounds.ylen, 3),
            "z_mm": round(bounds.zlen, 3),
            "z_min_mm": round(bounds.zmin, 3),
            "z_max_mm": round(bounds.zmax, 3),
        }
    moving_register_z = tuple(
        float(value) for value in contract.integration["drive_register_z_mm"]
    )
    fixed_register_z = tuple(
        float(value) for value in contract.integration["fixed_drive_register_seat_z_mm"]
    )
    axial_register_engagement = max(
        0.0,
        min(moving_register_z[1], fixed_register_z[1])
        - max(moving_register_z[0], fixed_register_z[0]),
    )
    connector_clearance_hits: list[dict[str, Any]] = []
    for clearance_name, clearance_shape in result.service_clearance_shapes.items():
        for component_name, component_shape in result.components.items():
            if component_name == "v25_M28_male_plug_envelope":
                continue
            if not _aabb_overlap(clearance_shape, component_shape):
                continue
            overlap = clearance_shape.intersect(component_shape).Volume()
            if overlap > 0.02:
                connector_clearance_hits.append(
                    {
                        "clearance": clearance_name,
                        "component": component_name,
                        "volume_mm3": round(overlap, 4),
                    }
                )
    service = {
        "arm_positive_z_removal_clear": not arm_forbidden and arm_sweep["passes"],
        "arm_removal_sweep": arm_sweep,
        "lower_cover_removal": lower_cover_removal,
        "top_plate_cover_attachment": top_plate_cover_attachment,
        "arm_module_removal_sequence": [
            "deenergize_all_power_sources_and_unload_tendons",
            "release_and_remove_three_tendon_terminals_adjusters_and_retentions",
            "remove_fixed_hexagonal_root_guard",
            "remove_six_root_M5_fasteners",
            "translate_entire_arm_module_along_positive_z",
        ],
        "root_guard_attachment": {
            "part_count": 1,
            "removal_direction": "positive_z",
            "fastener_thread": "M3",
            "fastener_count": len(cover_cfg["root_guard_fastener_angles_deg"]),
            "fastener_clearance_diameter_mm": float(
                cover_cfg["root_guard_fastener_clearance_diameter_mm"]
            ),
            "alignment_tab_count": len(cover_cfg["root_guard_alignment_tab_angles_deg"]),
            "alignment_slot_clearance_mm": float(
                cover_cfg["root_guard_alignment_slot_clearance_mm"]
            ),
            "base_receiver": "fixed_top_plate",
            "load_boundary": "alignment_and_cover_retention_only",
        },
        "drive_negative_z_removal_clear": drive_sweep["passes"],
        "drive_removal_sweep": drive_sweep,
        "drive_sweep_type": drive_sweep["sweep_type"],
        "drive_sweep_travel_mm": drive_sweep["travel_mm"],
        "drive_sweep_initial_release_gap_mm": drive_sweep["initial_release_gap_mm"],
        "drive_sweep_moving_component_count": drive_sweep["moving_component_count"],
        "drive_sweep_fixed_obstacle_count": drive_sweep["fixed_obstacle_count"],
        "drive_sweep_min_clearance_mm": drive_sweep["minimum_clearance_mm"],
        "drive_sweep_collisions": drive_sweep["collisions"],
        "drive_register_axial_engagement_mm": axial_register_engagement,
        "drive_register_engagement_passes": axial_register_engagement > 0.0,
        "tendon_root_route": tendon_route,
        "motor_port_harness": motor_ports,
        "wiring_accessibility": wiring_accessibility,
        "root_fastener_tool_envelopes": len(result.root.tool_envelopes),
        "all_tool_envelopes_valid": all(shape.isValid() for shape in result.root.tool_envelopes),
        "fixed_shafts_supported_without_drive": result.fixed.shafts_supported_without_drive,
        "fixed_shaft_support_pair_count": len(result.fixed.shaft_support_pairs),
        "drive_module_removal_sequence": list(result.drive.removal_sequence),
        "spool_removal_sequence": [
            "deenergize_system_and_unload_the_selected_tendon",
            "detach_and_unwind_the_tendon_from_the_spool",
            "withdraw_the_radial_spool_drive_pin",
            "remove_the_spool_retaining_ring",
            "remove_the_outboard_6900_bearing_labyrinth_and_oil_seal_from_the_cartridge",
            "remove_two_M2_5_output_support_cartridge_screws",
            "withdraw_the_output_support_cartridge_32_mm_along_the_positive_spool_axis",
            "slide_the_wet_spool_32_mm_through_the_fixed_support_land_tunnel",
        ],
        "output_support_cartridge_interface": {
            "outer_diameter_mm": float(
                contract.integration["output_support_cartridge_outer_diameter_mm"]
            ),
            "inner_diameter_mm": float(
                contract.integration["output_support_cartridge_inner_diameter_mm"]
            ),
            "bearing_outer_seat_diameter_mm": float(
                contract.integration["bearing_outer_seat_diameter_mm"]
            ),
            "bearing_nominal_radial_clearance_mm": round(
                (
                    float(
                        contract.integration[
                            "output_support_cartridge_inner_diameter_mm"
                        ]
                    )
                    - float(contract.integration["bearing_dimensions_mm"][1])
                )
                / 2.0,
                3,
            ),
            "seal_housing_bore_diameter_mm": float(
                contract.integration["pressure_seal_housing_bore_diameter_mm"]
            ),
            "outboard_seal_retainer_shoulder": {
                "outer_diameter_mm": float(
                    contract.integration["seal_retaining_shoulder_outer_diameter_mm"]
                ),
                "opening_diameter_mm": float(
                    contract.integration["seal_retaining_shoulder_opening_diameter_mm"]
                ),
                "axial_width_mm": float(
                    contract.integration["seal_retaining_shoulder_axial_width_mm"]
                ),
                "range_mm": [
                    float(contract.integration["output_shaft_seal_ranges_mm"][1][1]),
                    float(contract.integration["output_shaft_seal_ranges_mm"][1][1])
                    + float(
                        contract.integration[
                            "seal_retaining_shoulder_axial_width_mm"
                        ]
                    ),
                ],
                "integral_with_removable_cartridge": True,
            },
            "fixed_land_bore_diameter_mm": float(
                contract.integration["output_support_cartridge_bore_diameter_mm"]
            ),
            "radial_clearance_mm": round(
                (
                    float(contract.integration["output_support_cartridge_bore_diameter_mm"])
                    - float(contract.integration["output_support_cartridge_outer_diameter_mm"])
                )
                / 2.0,
                3,
            ),
            "fastener_thread_candidate": "M2.5",
            "fastener_count": int(
                contract.integration["output_support_cartridge_fastener_count"]
            ),
            "thread_engagement_mm": float(
                contract.integration["output_support_cartridge_fastener_engagement_mm"]
            ),
            "fixed_land_remains_installed_during_spool_service": True,
            "fit_and_fastener_strength_status": "nominal CAD only; machine and verify the cartridge fit and fastener access",
        },
        "output_support_cartridge_removal": support_cartridge_removal,
        "wet_spool_interface": {
            "bore_shape": "circular_clearance_bore",
            "bore_diameter_mm": float(
                contract.integration["wet_spool_bore_diameter_mm"]
            ),
            "radial_drive_pin_diameter_mm": float(
                contract.integration["wet_spool_drive_pin_diameter_mm"]
            ),
            "radial_drive_pin_hole_diameter_mm": float(
                contract.integration["wet_spool_drive_pin_hole_diameter_mm"]
            ),
            "radial_drive_pin_length_mm": float(
                contract.integration["wet_spool_drive_pin_length_mm"]
            ),
            "axial_retention": "integral inboard shoulder plus removable external retaining-ring envelope",
            "inboard_shoulder_diameter_mm": float(
                contract.integration["wet_spool_inboard_shoulder_diameter_mm"]
            ),
            "inboard_shoulder_width_mm": float(
                contract.integration["wet_spool_inboard_shoulder_width_mm"]
            ),
            "retainer_groove_diameter_mm": float(
                contract.integration["wet_spool_retainer_groove_diameter_mm"]
            ),
            "retainer_groove_width_mm": float(
                contract.integration["wet_spool_retainer_groove_width_mm"]
            ),
            "retainer_outer_diameter_mm": float(
                contract.integration["wet_spool_retainer_outer_diameter_mm"]
            ),
            "nominal_side_clearance_mm": float(
                contract.integration["wet_spool_side_clearance_mm"]
            ),
            "physical_validation": "pin shear, shaft weakening, cable-winding profile, supplier ring dimensions and corrosion remain unverified",
        },
        "spool_removal": spool_removal,
        "m2006_coupling_interface": {
            "output_projection_mm": float(contract.drive.m2006_output_projection_mm),
            "output_crosshole_center_from_tip_mm": float(
                contract.drive.m2006_crosshole_center_from_tip_mm
            ),
            "integrated_input_shaft": True,
            "collar_diameter_mm": float(
                contract.integration["m2006_input_shaft_collar_diameter_mm"]
            ),
            "collar_to_first_bearing_clearance_mm": float(
                contract.integration["m2006_input_shaft_collar_bearing_clearance_mm"]
            ),
            "motor_socket_diameter_mm": float(
                contract.integration["m2006_input_shaft_socket_diameter_mm"]
            ),
            "motor_radial_nominal_clearance_mm": round(
                0.5
                * (
                    float(contract.integration["m2006_input_shaft_socket_diameter_mm"])
                    - float(contract.drive.m2006_output_shaft_diameter_mm)
                ),
                3,
            ),
            "motor_socket_profile": "D_bore",
            "motor_socket_flat_from_axis_mm": float(
                contract.integration["m2006_input_shaft_socket_flat_from_axis_mm"]
            ),
            "motor_output_flat_from_axis_mm": float(
                contract.integration["m2006_motor_d6_flat_from_axis_mm"]
            ),
            "motor_d_flat_nominal_clearance_mm": round(
                float(contract.integration["m2006_input_shaft_socket_flat_from_axis_mm"])
                - float(contract.integration["m2006_motor_d6_flat_from_axis_mm"]),
                3,
            ),
            "motor_d_flat_alignment": "flat normal aligned to radial cross-pin axis",
            "motor_cross_pin_retention_status": str(
                contract.integration["m2006_input_shaft_cross_pin_retainer_status"]
            ),
            "motor_socket_engagement_mm": float(
                contract.integration["m2006_input_shaft_socket_depth_mm"]
            ),
            "socket_wall_mm": round(
                0.5
                * (
                    float(contract.integration["m2006_input_shaft_collar_diameter_mm"])
                    - float(contract.integration["m2006_input_shaft_socket_diameter_mm"])
                ),
                3,
            ),
            "loose_coupling_sleeve_count": sum(
                name.startswith("fixed_coupling_sleeve_")
                for name in result.fixed_component_names
            ),
            "coupling_set_screw_count": sum(
                name.startswith("fixed_coupling_lock_screw_")
                for name in result.fixed_component_names
            ),
            "removable_cross_pin_count": 3,
        },
        "electronics_connector_clearance_hits": connector_clearance_hits,
        "electronics_connector_clearance_passes": not connector_clearance_hits,
    }
    source_payload = {
        key: {
            "role": record.role,
            "path": record.path.as_posix(),
            "sha256": record.sha256,
            "size_bytes": record.size_bytes,
        }
        for key, record in sources.items()
    }
    return {
        "candidate_id": contract.candidate_id,
        "status": "static integrated CAD candidate; not print or underwater release",
        "spiral_geometry": derive_from_contract(contract).to_dict(),
        "alignment": [asdict(item) for item in alignment],
        "engineering": engineering,
        "electronics": result.electronics_audit,
        "sources": source_payload,
        "collisions": {
            "forbidden": collisions,
            "intentional_contacts": [list(pair) for pair in result.intentional_contacts],
            "checked_pair_count": checked_pair_count,
            "checked_same_group_pairs": checked_same_group,
        },
        "service": service,
        "cover_layout": {
            "nominal_profile_circumdiameter_mm": round(
                2.0 * cover_max_radius, 3
            ),
            "nominal_outer_armor_circumdiameter_mm": round(
                2.0 * cover_max_outer_radius, 3
            ),
            "actual_panel_max_radial_diameter_mm": round(
                2.0 * cover_panel_max_radius, 3
            ),
            "actual_panel_assembly_bounds_mm": {
                "x": round(cover_panel_bounds.xlen, 3),
                "y": round(cover_panel_bounds.ylen, 3),
                "z": round(cover_panel_bounds.zlen, 3),
            },
            "actual_outer_cover_max_radial_diameter_mm": round(
                2.0 * cover_outer_max_radius, 3
            ),
            "actual_outer_cover_assembly_bounds_mm": {
                "x": round(cover_outer_bounds.xlen, 3),
                "y": round(cover_outer_bounds.ylen, 3),
                "z": round(cover_outer_bounds.zlen, 3),
            },
            "panel_height_mm": round(
                float(cover_cfg["panel_z_bounds_mm"][1])
                - float(cover_cfg["panel_z_bounds_mm"][0]),
                3,
            ),
            "panel_z_bounds_mm": [
                float(value) for value in cover_cfg["panel_z_bounds_mm"]
            ],
            "panel_profile_stations_mm": cover_profile,
            "panel_count": len(cover_panel_names),
            "upper_panel_count": len(cover_upper_panel_names),
            "lower_service_panel_count": len(cover_lower_panel_names),
            "service_split_z_mm": float(cover_cfg["panel_split_z_mm"]),
            "panel_component_bounds_mm": [
                component_bounds_mm(name) for name in cover_panel_names
            ],
            "visible_band_count": len(cover_rib_centers),
            "band_construction": "two raised levels of six flat face ribs fused into each matching service panel; no closed frame parts",
            "band_outer_circumradii_mm": cover_rib_outer_radii,
            "band_outer_circumradius_ranges_mm": cover_rib_outer_radius_ranges,
            "band_z_centers_mm": cover_rib_centers,
            "support_hole_z_centers_mm": cover_support_hole_centers,
            "raised_rib_z_centers_mm": cover_rib_centers,
            "fastener_row_z_centers_mm": cover_support_hole_centers,
            "inner_support_pad_count": (
                6
                * (len(cover_support_hole_centers) - len(cover_rib_centers))
                * len(cover_cfg["panel_fastener_tangent_offsets_mm"])
            ),
            "inner_support_pad_nominal_dimensions_mm": {
                "tangential_width": float(
                    cover_cfg["panel_fastener_pad_tangent_width_mm"]
                ),
                "vertical_height": float(cover_cfg["frame_height_mm"]),
                "inward_thickness": cover_frame_thickness,
            },
            "inner_support_pad_backing_below_head_recess_mm": round(
                float(cover_cfg["panel_thickness_mm"])
                + cover_frame_thickness
                - float(cover_cfg["panel_fastener_recess_depth_mm"]),
                3,
            ),
            "frame_radial_thickness_mm": cover_frame_thickness,
            "panel_fastener_interface": {
                "thread": "M3",
                "clearance_diameter_mm": float(
                    cover_cfg["panel_fastener_diameter_mm"]
                ),
                "tangent_offsets_mm": [
                    float(value)
                    for value in cover_cfg["panel_fastener_tangent_offsets_mm"]
                ],
                "hole_count": 6
                * len(cover_support_hole_centers)
                * len(cover_cfg["panel_fastener_tangent_offsets_mm"]),
                "tool_envelope_diameter_mm": 8.0,
                "relieved_tool_access_count": 2,
                "tool_access_relief_diameter_mm": float(
                    cover_cfg["panel_tool_access_relief_diameter_mm"]
                ),
                "tool_access_relief_depth_mm": float(
                    cover_cfg["window_surround_proud_mm"]
                ),
                "tool_access_relief_location": "lower_panel_05_bottom_support_row",
                "counterbore_access_diameter_mm": 8.0,
                "counterbore_recess_depth_mm": float(
                    cover_cfg["panel_fastener_recess_depth_mm"]
                ),
                "counterbore_access_count": 6
                * len(cover_support_hole_centers)
                * len(cover_cfg["panel_fastener_tangent_offsets_mm"]),
                "tool_driver_shaft_diameter_mm": 2.5,
                "receiver_hardware": "not modeled; M3 nut or insert method remains to be selected",
            },
            "window_surround_reveal_mm": float(
                cover_cfg["window_surround_reveal_mm"]
            ),
            "window_surround_width_mm": float(
                cover_cfg["window_surround_width_mm"]
            ),
            "window_surround_proud_mm": float(
                cover_cfg["window_surround_proud_mm"]
            ),
            "observation_window_count": len(
                cover_cfg["observation_window_normals_deg"]
            ),
            "observation_window_normals_deg": [
                float(value)
                for value in cover_cfg["observation_window_normals_deg"]
            ],
            "observation_window_mm": [
                float(value) for value in cover_cfg["observation_window_mm"]
            ],
            "observation_window_center_z_mm": float(
                cover_cfg["observation_window_center_z_mm"]
            ),
            "motor_window_mm": [
                float(value) for value in cover_cfg["motor_window_mm"]
            ],
            "motor_window_center_z_mm": float(
                cover_cfg["motor_window_center_z_mm"]
            ),
            "floodable_openings": True,
            "pressure_boundary": False,
        },
    }


def preflight_v27(result: V27AssemblyResult) -> dict[str, Any]:
    audit = audit_v27_assembly(result)
    failures: list[str] = []
    if audit["collisions"]["forbidden"]:
        failures.append("forbidden component collision")
    if not all(item["passes"] for item in audit["alignment"]):
        failures.append("tendon alignment")
    if not audit["service"]["arm_positive_z_removal_clear"]:
        failures.append("arm removal")
    if not audit["service"]["drive_negative_z_removal_clear"]:
        failures.append("drive removal sweep")
    if not audit["service"]["lower_cover_removal"]["passes"]:
        failures.append("lower cover removal path")
    if not audit["service"].get("top_plate_cover_attachment", {}).get("passes", True):
        failures.append("top-plate cover attachment and panel removal")
    if not audit["service"]["drive_register_engagement_passes"]:
        failures.append("drive register engagement")
    if not all(path["passes"] for path in audit["service"]["spool_removal"]):
        failures.append("spool removal sweep")
    if not all(
        path["passes"]
        for path in audit["service"]["output_support_cartridge_removal"]
    ):
        failures.append("output support cartridge removal sweep")
    if not audit["service"]["tendon_root_route"]["clearance_to_non_spool_components"]:
        failures.append("tendon root route clearance")
    if not audit["service"]["motor_port_harness"]["clearance_passes"]:
        failures.append("motor-port harness clearance")
    if not audit["service"]["electronics_connector_clearance_passes"]:
        failures.append("electronics connector service clearance")
    if failures:
        raise ValueError("V27 preflight failed: " + ", ".join(failures))
    return audit


def _export_assembly(names: Iterable[str], result: V27AssemblyResult, path: Path) -> None:
    assembly = cq.Assembly(name=path.stem)
    for name in names:
        assembly.add(result.components[name], name=name)
    assembly.export(str(path), exportType="STEP", unit="MM")
    step_text = path.read_text(encoding="utf-8")
    step_text, replacement_count = re.subn(
        r"(FILE_NAME\('[^']*',)'[^']+'",
        r"\1'2000-01-01T00:00:00'",
        step_text,
        count=1,
    )
    if replacement_count != 1:
        raise ValueError(f"STEP header timestamp was not found: {path}")
    path.write_text(step_text, encoding="utf-8", newline="\n")
    readback = cq.importers.importStep(str(path)).val()
    if not readback.isValid() or not readback.Solids():
        raise ValueError(f"STEP readback failed: {path}")


def _export_single_shape(shape: cq.Shape, path: Path) -> None:
    assembly = cq.Assembly(name=path.stem)
    assembly.add(shape, name=f"{path.stem}_solid")
    assembly.export(str(path), exportType="STEP", unit="MM")
    step_text = path.read_text(encoding="utf-8")
    step_text, replacement_count = re.subn(
        r"(FILE_NAME\('[^']*',)'[^']+'",
        r"\1'2000-01-01T00:00:00'",
        step_text,
        count=1,
    )
    if replacement_count != 1:
        raise ValueError(f"STEP header timestamp was not found: {path}")
    path.write_text(step_text, encoding="utf-8", newline="\n")
    readback = cq.importers.importStep(str(path)).val()
    if not readback.isValid() or len(readback.Solids()) != 1:
        raise ValueError(
            f"single-part STEP readback must contain one valid solid: {path}; "
            f"found {len(readback.Solids())}"
        )


def _remove_degenerate_binary_stl_facets(path: Path) -> int:
    """Drop zero-area OCC tessellation facets while preserving the closed shell."""
    raw = path.read_bytes()
    if len(raw) < 84:
        raise ValueError(f"binary STL is truncated: {path}")
    facet_count = struct.unpack_from("<I", raw, 80)[0]
    if len(raw) != 84 + 50 * facet_count:
        raise ValueError(f"binary STL length does not match its facet count: {path}")
    kept: list[bytes] = []
    removed = 0
    for index in range(facet_count):
        offset = 84 + 50 * index
        record = raw[offset : offset + 50]
        values = struct.unpack("<12fH", record)
        p0, p1, p2 = values[3:6], values[6:9], values[9:12]
        ab = tuple(p1[axis] - p0[axis] for axis in range(3))
        ac = tuple(p2[axis] - p0[axis] for axis in range(3))
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        if len({tuple(p0), tuple(p1), tuple(p2)}) < 3 or sum(
            value * value for value in cross
        ) <= 1.0e-24:
            removed += 1
            continue
        kept.append(record)
    if removed:
        output = bytearray(raw[:80])
        output.extend(struct.pack("<I", len(kept)))
        output.extend(b"".join(kept))
        path.write_bytes(output)
    return removed


def _write_delivery_manifest(contract: V27Contract) -> Path:
    directory = contract.output_directory.resolve()
    repo_root = directory.parents[3]
    manifest_path = directory / "来源与SHA256.csv"
    included_suffixes = {".py", ".json", ".step", ".stl", ".png", ".md", ".docx", ".pdf"}
    paths = {
        path.resolve()
        for path in directory.rglob("*")
        if path.is_file()
        and path != manifest_path
        and path.suffix.lower() in included_suffixes
    }
    paths.add(repo_root / "README.md")
    for spec in contract.source_specs.values():
        paths.add((directory / spec["path"]).resolve())

    snapshot_path = repo_root / "v27_electronics_snapshot" / "V27电子件快照.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    for collection in ("components", "service_clearances"):
        for component in snapshot[collection]:
            paths.add((snapshot_path.parent / component["file"]).resolve())
    for source in snapshot["source_files"].values():
        paths.add((repo_root / source["path"]).resolve())
    paths.add(
        directory.parent
        / "integrated_assembly_v26_arm_and_v25_electronics"
        / "parameters.json"
    )

    rows = []
    for path in sorted(paths, key=lambda value: value.relative_to(repo_root).as_posix()):
        if not path.is_file():
            raise FileNotFoundError(f"delivery manifest source is missing: {path}")
        rows.append(
            {
                "relative_path": path.relative_to(repo_root).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    with manifest_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("relative_path", "sha256", "size_bytes"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return manifest_path


def export_v27(result: V27AssemblyResult) -> dict[str, Path]:
    directory = result.contract.output_directory
    audit = preflight_v27(result)
    spiral_path = directory / "V27螺旋参数.json"
    spiral_path.write_text(
        json.dumps(
            derive_from_contract(result.contract).to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (directory / "V27装配审查.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    outputs = {
        "arm_module": directory / "SpiRobs_v27_1m_四段臂体模块.step",
        "drive_module": directory / "SpiRobs_v27_M2006三电机驱动模块.step",
        "fixed_base": directory / "SpiRobs_v27_固定传动密封基座.step",
        "root_cover": directory / "SpiRobs_v27_开放式六边形包覆附件.step",
        "full_assembly": directory / "SpiRobs_v27_1m模块化总装.step",
    }
    _export_assembly(result.arm_component_names, result, outputs["arm_module"])
    _export_assembly(result.drive_component_names, result, outputs["drive_module"])
    _export_assembly(result.fixed_component_names, result, outputs["fixed_base"])
    cover_names = tuple(
        name
        for name in result.fixed_component_names
        if name.startswith("fixed_cover_") or name == "fixed_root_guard_hex"
    )
    _export_assembly(cover_names, result, outputs["root_cover"])
    _export_assembly(result.components, result, outputs["full_assembly"])
    segment_export_records = []
    segment_step_paths: list[Path] = []
    for index, ((first_unit, last_unit), z_range, component_name) in enumerate(
        zip(
            result.arm.segment_ranges,
            result.arm.segment_z_ranges_mm,
            result.arm.print_segments,
        ),
        start=1,
    ):
        stl_path = directory / f"SpiRobs_v27_打印段{index:02d}_单元{first_unit:02d}-{last_unit:02d}.stl"
        original_shape = result.arm.print_segments[component_name]
        if len(original_shape.Solids()) != 1:
            raise ValueError(
                f"print segment {index} has {len(original_shape.Solids())} disconnected solids"
            )
        original_box = original_shape.BoundingBox()
        local_shape = original_shape.translate(cq.Vector(0.0, 0.0, -original_box.zmin))
        local_box = local_shape.BoundingBox()
        if local_box.zlen >= result.contract.arm.max_segment_height_mm:
            raise ValueError(f"print segment {index} exceeds the local Z print-height limit")
        step_path = directory / f"SpiRobs_v27_打印段{index:02d}_单元{first_unit:02d}-{last_unit:02d}.step"
        _export_single_shape(local_shape, step_path)
        segment_step_paths.append(step_path)
        cq.exporters.export(
            local_shape,
            str(stl_path),
            exportType="STL",
            tolerance=0.08,
            angularTolerance=0.10,
        )
        removed_degenerate_facets = _remove_degenerate_binary_stl_facets(stl_path)
        segment_export_records.append(
            {
                "file": stl_path.name,
                "step_file": step_path.name,
                "degenerate_stl_facets_removed": removed_degenerate_facets,
                "unit_range_in_arm": [first_unit, last_unit],
                "global_body_z_range_mm": [z_range[0], z_range[1]],
                "finished_print_height_mm": local_box.zlen,
                "split_joint_units": [
                    unit.unit_index
                    for unit in result.arm.dovetails
                    if abs(unit.boundary_z_mm - z_range[0]) < 1.0e-4
                    or abs(unit.boundary_z_mm - z_range[1]) < 1.0e-4
                ],
                "local_bounds_mm": {
                    "x": [local_box.xmin, local_box.xmax],
                    "y": [local_box.ymin, local_box.ymax],
                    "z": [local_box.zmin, local_box.zmax],
                },
                "triangulation_tolerance_mm": 0.08,
                "angular_tolerance_rad": 0.10,
            }
        )
    (directory / "V27打印段导出.json").write_text(
        json.dumps(
            {
                "candidate_id": result.contract.candidate_id,
                "coordinate_frame": "each part translated so local zmin equals 0; XY remains arm-centered",
                "segmentation_policy": "cut through the actual CAD profiles at the midpoints of units 5, 10, and 18; neighboring print segments share the split unit; ideal spiral arc intervals remain mathematical reference data",
                "global_segment_boundary_planes_mm": list(result.arm.segment_boundary_z_mm),
                "max_segment_height_mm": result.contract.arm.max_segment_height_mm,
                "dovetail_interfaces": [
                    {
                        "name": joint.name,
                        "split_joint_unit": joint.unit_index,
                        "boundary_z_mm": joint.boundary_z_mm,
                        "engagement_mm": joint.engagement_mm,
                        "clearance_per_side_mm": joint.clearance_per_side_mm,
                        "profile_rotation_deg": joint.rotation_deg,
                        "minimum_tendon_clearance_mm": joint.minimum_tendon_clearance_mm,
                        "lock_pin_azimuth_deg": joint.lock_pin_azimuth_deg,
                        "lock_pin_length_mm": joint.lock_pin_length_mm,
                    }
                    for joint in result.arm.dovetails
                ],
                "lock_pins": [
                    {
                        "name": lock.name,
                        "split_joint_unit": lock.unit_index,
                        "center_z_mm": lock.center_z_mm,
                        "diameter_mm": lock.diameter_mm,
                        "hole_diameter_mm": lock.hole_diameter_mm,
                        "axis_azimuth_deg": lock.axis_azimuth_deg,
                        "length_mm": lock.length_mm,
                        "minimum_tendon_clearance_mm": lock.tendon_clearance_mm,
                    }
                    for lock in result.arm.lock_features
                ],
                "segments": segment_export_records,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs.update(
        {f"print_segment_{index:02d}": path for index, path in enumerate(segment_step_paths, start=1)}
    )
    return outputs


if __name__ == "__main__":
    from model_contract import load_contract
    from engineering_audit import write_engineering_report
    from render_v27 import render_v27

    active_contract = load_contract()
    assembly_result = build_v27_assembly(active_contract)
    exported = export_v27(assembly_result)
    write_engineering_report(
        generate_v27_engineering_audit(active_contract),
        active_contract.output_directory / "V27工程审计.json",
    )
    renders = render_v27(assembly_result)
    for key, path in {**exported, **renders}.items():
        print(f"{key}: {path}")
    print(f"delivery_manifest: {_write_delivery_manifest(active_contract)}")
