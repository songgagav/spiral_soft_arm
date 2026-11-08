from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import math
from pathlib import Path
import re
import sys
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


def _load_v25(contract: V27Contract) -> Any:
    path = (contract.output_directory / contract.source_specs["v25_generator"]["path"]).resolve()
    spec = importlib.util.spec_from_file_location("v27_v25_electronics_source", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    module = _load_v25(contract)
    source, _ = module.build_v25_components()
    excluded = {
        "v24_central_bottom_lid_M28_bore",
        "v25_M28_service_clearance",
    }
    selected = {
        name: shape
        for name, shape in source.items()
        if (name.startswith("v24_") or name.startswith("v25_"))
        and name not in excluded
        and "C620" not in name
    }
    selected["v27_STM32F407_controller_envelope"] = selected.pop(
        "v24_controller_envelope"
    )
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
            "arm_tendon_terminals": terminal_compound,
        }
    )
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
    intentional = [("arm_root_flange", "fixed_root_receiver")]
    for index in range(1, 4):
        intentional.append(
            (f"removable_coupling_sleeve_{index:02d}", f"fixed_shaft_{index:02d}")
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


def _cross_group_collisions(result: V27AssemblyResult) -> list[dict[str, Any]]:
    groups = (
        result.arm_component_names,
        result.drive_component_names,
        result.fixed_component_names,
        result.electronics_component_names,
    )
    intentional = {frozenset(pair) for pair in result.intentional_contacts}
    collisions: list[dict[str, Any]] = []
    for first_group_index, first_group in enumerate(groups):
        for second_group in groups[first_group_index + 1 :]:
            for first_name in first_group:
                first = result.components[first_name]
                for second_name in second_group:
                    if frozenset((first_name, second_name)) in intentional:
                        continue
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
    return collisions


def audit_v27_assembly(result: V27AssemblyResult) -> dict[str, Any]:
    contract = result.contract
    alignment = audit_tendon_alignment(contract, result.root, result.fixed.axes)
    engineering = generate_v27_engineering_audit(contract)
    sources = build_source_manifest(contract)
    collisions = _cross_group_collisions(result)
    arm_names = set(result.arm_component_names)
    arm_forbidden = [
        item
        for item in collisions
        if any(name in arm_names for name in item["components"])
    ]
    electronics_shell = result.components["v24_central_electronics_canister"].BoundingBox()
    motor_min_radius = min(
        math.hypot(axis.spool_center[0], axis.spool_center[1]) - 12.2
        for axis in result.fixed.axes
    )
    service = {
        "arm_positive_z_removal_clear": not arm_forbidden
        and result.root.register_height_mm > 0.0,
        "drive_negative_z_removal_clear": motor_min_radius > max(abs(electronics_shell.xmax), abs(electronics_shell.ymax)),
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
        },
        "service": service,
    }


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
