from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from itertools import combinations
from typing import Any, Iterable

import cadquery as cq

from arm_module import ArmBuildResult, build_arm_module
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


@dataclass(frozen=True)
class V27AssemblyResult:
    contract: V27Contract
    components: dict[str, cq.Shape]
    arm_component_names: tuple[str, ...]
    drive_component_names: tuple[str, ...]
    fixed_component_names: tuple[str, ...]
    electronics_component_names: tuple[str, ...]
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


def _select_v25_electronics(contract: V27Contract) -> dict[str, cq.Shape]:
    """Reconstruct the frozen V24/V25 envelopes from tracked JSON only."""
    v24_path = (contract.output_directory / contract.source_specs["v24_parameters"]["path"]).resolve()
    v25_path = (contract.output_directory / contract.source_specs["v25_parameters"]["path"]).resolve()
    v24 = json.loads(v24_path.read_text(encoding="utf-8"))
    v25 = json.loads(v25_path.read_text(encoding="utf-8"))
    selected: dict[str, cq.Shape] = {}
    canister = v24["canister"]
    outer = cq.Solid.makeCylinder(0.5 * canister["outer_diameter"], canister["top_z"] - canister["bottom_z"], cq.Vector(0, 0, canister["bottom_z"]), cq.Vector(0, 0, 1))
    inner = cq.Solid.makeCylinder(0.5 * canister["inner_diameter"], canister["top_z"] - canister["bottom_z"] + 0.2, cq.Vector(0, 0, canister["bottom_z"] - 0.1), cq.Vector(0, 0, 1))
    selected["v24_central_electronics_canister"] = outer.cut(inner)
    lid = cq.Solid.makeCylinder(68.0, 10.0, cq.Vector(0, 0, -240), cq.Vector(0, 0, 1))
    m28_bore = cq.Solid.makeCylinder(13.9, 10.2, cq.Vector(0, 0, -240.1), cq.Vector(0, 0, 1))
    selected["v25_bottom_lid_with_M28_recess"] = lid.cut(m28_bore)

    hardware = v24["hardware"]
    for index, (x_mm, y_mm) in enumerate(hardware["cells"]["centres_xy"], start=1):
        selected[f"v24_21700_cell_{index}"] = cq.Solid.makeCylinder(
            0.5 * hardware["cells"]["diameter"],
            hardware["cells"]["length"],
            cq.Vector(x_mm, y_mm, hardware["cells"]["z"][0] + 12.0),
            cq.Vector(0, 0, 1),
        )
    for key, name in (
        ("controller", "v27_STM32F407_controller_envelope"),
        ("ups", "v24_UPS_envelope"),
        ("regulator", "v24_regulator_envelope"),
        ("pd1002", "v24_PD1002_envelope"),
        ("ideal_diode", "v24_ideal_diode_envelope"),
        ("bms", "v24_BMS_envelope"),
    ):
        aabb = hardware[key]["aabb"]
        selected[name] = cq.Solid.makeBox(aabb[1] - aabb[0], aabb[3] - aabb[2], aabb[5] - aabb[4], cq.Vector(aabb[0], aabb[2], aabb[4]))
    buck_aabb = v25["hardware"]["buck_5v"]["aabb"]
    selected["v25_buck_5v_envelope"] = cq.Solid.makeBox(
        buck_aabb[1] - buck_aabb[0], buck_aabb[3] - buck_aabb[2], buck_aabb[5] - buck_aabb[4], cq.Vector(buck_aabb[0], buck_aabb[2], buck_aabb[4])
    )
    selected["v25_M28_socket_body"] = cq.Solid.makeCylinder(13.9, 38.5, cq.Vector(0, 0, -240), cq.Vector(0, 0, 1))
    selected["v24_M12_USB_C_inside_stem_proxy"] = cq.Solid.makeCylinder(7.2, 18.0, cq.Vector(0, -68, -202), cq.Vector(0, 1, 0))
    selected["v24_central_electronics_canister"] = selected[
        "v24_central_electronics_canister"
    ].cut(selected["v24_M12_USB_C_inside_stem_proxy"])
    selected["v24_regulator_envelope"] = selected[
        "v24_regulator_envelope"
    ].translate((0.0, 0.0, 15.0))
    # The official C610 STEP is an exploded service model.  The fixed electronics
    # side therefore uses the measured main-case envelope only, with three units
    # occupying the C620 bays removed above.
    for index, angle_deg in enumerate((0.0, 120.0, 240.0), start=1):
        center = _polar_center(48.0, angle_deg, -55.0)
        shape = _box_from_center(22.0, 7.25, 44.8, center).rotate(
            (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), angle_deg
        )
        selected[f"v27_C610_controller_{index:02d}_envelope"] = shape
    for name, shape in selected.items():
        if not shape.isValid() or not shape.Solids():
            raise ValueError(f"invalid selected V25 electronics component: {name}")
    return selected


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
    electronics_components = _select_v25_electronics(contract)
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
        ("removable_motor_plate", "removable_plate_register"),
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
    moving_names = tuple(
        name for name in result.drive_component_names if "coupling_sleeve" not in name
    )
    obstacles = (*result.fixed_component_names, *result.electronics_component_names)
    offsets = tuple(float(value) for value in range(10, 201, 10))
    minimum_clearance = float("inf")
    collisions: list[dict[str, Any]] = []
    for offset in offsets:
        for moving_name in moving_names:
            moving = result.components[moving_name].translate((0.0, 0.0, -offset))
            moving_box = moving.BoundingBox()
            for obstacle_name in obstacles:
                obstacle = result.components[obstacle_name]
                obstacle_box = obstacle.BoundingBox()
                dx = max(obstacle_box.xmin - moving_box.xmax, moving_box.xmin - obstacle_box.xmax, 0.0)
                dy = max(obstacle_box.ymin - moving_box.ymax, moving_box.ymin - obstacle_box.ymax, 0.0)
                dz = max(obstacle_box.zmin - moving_box.zmax, moving_box.zmin - obstacle_box.zmax, 0.0)
                bbox_distance = math.sqrt(dx * dx + dy * dy + dz * dz)
                if bbox_distance > 0.0:
                    minimum_clearance = min(minimum_clearance, bbox_distance)
                    continue
                volume = moving.intersect(obstacle).Volume()
                if volume > 0.02:
                    collisions.append({"offset_mm": offset, "components": [moving_name, obstacle_name], "volume_mm3": round(volume, 4)})
                    minimum_clearance = 0.0
                else:
                    minimum_clearance = min(minimum_clearance, moving.distance(obstacle))
    return {
        "sample_count": len(offsets),
        "minimum_clearance_mm": minimum_clearance,
        "collisions": collisions,
        "passes": not collisions,
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
    service = {
        "arm_positive_z_removal_clear": not arm_forbidden
        and result.root.register_height_mm > 0.0,
        "drive_negative_z_removal_clear": drive_sweep["passes"],
        "drive_sweep_sample_count": drive_sweep["sample_count"],
        "drive_sweep_min_clearance_mm": drive_sweep["minimum_clearance_mm"],
        "drive_sweep_collisions": drive_sweep["collisions"],
        "root_fastener_tool_envelopes": len(result.root.tool_envelopes),
        "all_tool_envelopes_valid": all(shape.isValid() for shape in result.root.tool_envelopes),
        "fixed_shafts_supported_without_drive": result.fixed.shafts_supported_without_drive,
        "fixed_shaft_support_pair_count": len(result.fixed.shaft_support_pairs),
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
        "alignment": [asdict(item) for item in alignment],
        "engineering": engineering,
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


def export_v27(result: V27AssemblyResult) -> dict[str, Path]:
    directory = result.contract.output_directory
    audit = preflight_v27(result)
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
    return outputs
