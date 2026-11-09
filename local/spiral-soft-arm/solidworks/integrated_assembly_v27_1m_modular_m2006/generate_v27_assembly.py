from __future__ import annotations

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
    arm_components = _arm_components(arm, root)
    drive_components = dict(drive.components)
    fixed_components = dict(fixed.components)
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
    for index in range(1, 4):
        intentional.append(
            (f"removable_coupling_sleeve_{index:02d}", f"fixed_shaft_{index:02d}")
        )
        intentional.append(
            (f"removable_M2006_{index:02d}", f"removable_coupling_sleeve_{index:02d}")
        )
        intentional.append(
            ("removable_motor_plate", f"removable_motor_cradle_{index:02d}")
        )
        intentional.append(
            (f"fixed_wet_spool_{index:02d}", f"fixed_shaft_{index:02d}")
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
    moving_names = tuple(
        name for name in result.drive_component_names if "coupling_sleeve" not in name
    )
    obstacles = (*result.fixed_component_names, *result.electronics_component_names)
    travel_mm = 280.0
    minimum_clearance = float("inf")
    collisions: list[dict[str, Any]] = []
    for moving_name in moving_names:
        moving = result.components[moving_name]
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
                    cq.Vector(0.0, 0.0, -travel_mm),
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
            if lower_bound >= minimum_clearance:
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
        "sweep_type": "exact horizontal-face extrusion for Z-prismatic parts",
        "travel_mm": travel_mm,
        "moving_component_count": len(moving_names),
        "fixed_obstacle_count": len(obstacles),
        "minimum_clearance_mm": minimum_clearance,
        "collisions": collisions,
        "passes": not collisions,
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
    integration = result.contract.integration
    z_mm = float(integration["canister_motor_port_relief_z_mm"])
    start_radius, end_radius = (
        float(value)
        for value in integration["canister_motor_port_relief_radial_range_mm"]
    )
    angles = tuple(
        float(value) for value in integration["canister_motor_port_relief_angles_deg"]
    )
    electronic_names = set(result.electronics_component_names)
    backings = tuple(
        name
        for name in electronic_names
        if name.startswith("v27_C610_controller_") and name.endswith("_backing")
    )
    hits: list[dict[str, Any]] = []
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
        for backing_name in backings:
            backing = result.components[backing_name]
            if not _aabb_overlap(harness, backing):
                continue
            overlap = harness.intersect(backing).Volume()
            if overlap > 0.01:
                hits.append(
                    {
                        "route_index": route_index,
                        "backing": backing_name,
                        "overlap_mm3": round(overlap, 5),
                    }
                )
    return {
        "route_count": len(angles),
        "checked_backing_count": len(backings),
        "probe_diameter_mm": 2.0,
        "clearance_passes": not hits,
        "hits": hits,
    }


def audit_v27_assembly(result: V27AssemblyResult) -> dict[str, Any]:
    contract = result.contract
    alignment = audit_tendon_alignment(contract, result.root, result.fixed.axes)
    engineering = generate_v27_engineering_audit(contract)
    sources = build_source_manifest(contract)
    collisions, checked_pair_count, checked_same_group = _all_component_collisions(result)
    arm_names = set(result.arm_component_names)
    arm_forbidden = [
        item
        for item in collisions
        if any(name in arm_names for name in item["components"])
    ]
    drive_sweep = _drive_removal_sweep(result)
    tendon_route = _tendon_root_route_audit(result)
    motor_ports = _motor_port_harness_audit(result)
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
        "arm_positive_z_removal_clear": not arm_forbidden
        and result.root.register_height_mm > 0.0,
        "drive_negative_z_removal_clear": drive_sweep["passes"],
        "drive_sweep_type": drive_sweep["sweep_type"],
        "drive_sweep_travel_mm": drive_sweep["travel_mm"],
        "drive_sweep_moving_component_count": drive_sweep["moving_component_count"],
        "drive_sweep_fixed_obstacle_count": drive_sweep["fixed_obstacle_count"],
        "drive_sweep_min_clearance_mm": drive_sweep["minimum_clearance_mm"],
        "drive_sweep_collisions": drive_sweep["collisions"],
        "drive_register_axial_engagement_mm": axial_register_engagement,
        "drive_register_engagement_passes": axial_register_engagement > 0.0,
        "tendon_root_route": tendon_route,
        "motor_port_harness": motor_ports,
        "root_fastener_tool_envelopes": len(result.root.tool_envelopes),
        "all_tool_envelopes_valid": all(shape.isValid() for shape in result.root.tool_envelopes),
        "fixed_shafts_supported_without_drive": result.fixed.shafts_supported_without_drive,
        "fixed_shaft_support_pair_count": len(result.fixed.shaft_support_pairs),
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
    if not audit["service"]["drive_register_engagement_passes"]:
        failures.append("drive register engagement")
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
        "full_assembly": directory / "SpiRobs_v27_1m模块化总装.step",
    }
    _export_assembly(result.arm_component_names, result, outputs["arm_module"])
    _export_assembly(result.drive_component_names, result, outputs["drive_module"])
    _export_assembly(result.fixed_component_names, result, outputs["fixed_base"])
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
