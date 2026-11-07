"""B32 V26 integration layer for the original arm and V25 electronics."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cadquery as cq


HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
SOURCE = (HERE / P["source_generator"]).resolve()
spec = importlib.util.spec_from_file_location("b32_v25_frozen_for_v26", SOURCE)
v25 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v25
spec.loader.exec_module(v25)


def build_v26_components() -> tuple[dict[str, cq.Shape], list[str]]:
    """Return the unchanged V25 assembly as the V26 integration source."""
    components, body_names = v25.build_v25_components()
    missing = [
        name for name in P["required_components"] if name not in components
    ]
    if missing:
        raise ValueError(f"V26 source is missing required components: {missing}")
    for prefix in P["required_drive_prefixes"]:
        if not any(name.startswith(prefix) for name in components):
            raise ValueError(f"V26 source is missing drive prefix: {prefix}")
    return components, body_names


def physical_v26_components(
        components: dict[str, cq.Shape]) -> dict[str, cq.Shape]:
    """Remove declared observation-only envelopes from the physical export."""
    excluded = set(P["observation_only_components"])
    return {name: shape for name, shape in components.items()
            if name not in excluded}


def _rounded_bounds(shape: cq.Shape) -> list[float]:
    bounds = shape.BoundingBox()
    return [round(value, 3) for value in (
        bounds.xmin, bounds.xmax, bounds.ymin,
        bounds.ymax, bounds.zmin, bounds.zmax,
    )]


def audit_v26_integration(components: dict[str, cq.Shape],
                          body_names: list[str]) -> dict[str, object]:
    """Check inherited identities and the arm/electronics coordinate boundary."""
    missing_required = [
        name for name in P["required_components"] if name not in components
    ]
    missing_drives = [
        prefix for prefix in P["required_drive_prefixes"]
        if not any(name.startswith(prefix) for name in components)
    ]
    arm_name = P["original_arm"]["component_name"]
    arm = components[arm_name]
    arm_bounds = arm.BoundingBox()
    canister = components["v24_central_electronics_canister"]
    canister_bounds = canister.BoundingBox()
    gap = arm_bounds.zmin - canister_bounds.zmax
    expected_bounds = P["original_arm"]["bounds"]
    actual_bounds = _rounded_bounds(arm)
    bound_error = [round(actual - expected, 4)
                   for actual, expected in zip(actual_bounds, expected_bounds)]
    physical = physical_v26_components(components)
    inherited_fit = v25.audit_v25_components(components, body_names)
    inherited_overlap_count = (
        len(inherited_fit["hardware_to_hardware_volume_overlaps"])
        + len(inherited_fit["internal_to_shell_volume_overlaps"])
        + len(inherited_fit["buck_to_v24_hardware_volume_overlaps"])
        + len(inherited_fit["m28_to_hardware_volume_overlaps"])
    )
    return {
        "source_generator": P["source_generator"],
        "component_count": len(components),
        "physical_component_count": len(physical),
        "hardware_body_count": len(body_names),
        "missing_required_components": missing_required,
        "missing_drive_prefixes": missing_drives,
        "original_arm_solids": len(arm.Solids()),
        "original_arm_bounds_mm": actual_bounds,
        "original_arm_bound_error_mm": bound_error,
        "arm_root_z_mm": round(arm_bounds.zmin, 3),
        "electronics_canister_top_z_mm": round(canister_bounds.zmax, 3),
        "arm_to_electronics_gap_mm": round(gap, 3),
        "inherited_v25_overlap_count": inherited_overlap_count,
        "inherited_v25_fit_audit": inherited_fit,
        "observation_only_exported": sorted(
            set(P["observation_only_components"]).intersection(physical)
        ),
        "unverified": [
            "dynamic tendon motion, friction, slack and bending clearance",
            "dovetail strength and printed-part fit",
            "M28 terminals, PCB holes, complete wiring and strain relief",
            "thermal performance, O-ring compression and 5 m pressure sealing",
        ],
    }


def _load_renderer():
    path = HERE / "render_integrated_assembly.py"
    renderer_spec = importlib.util.spec_from_file_location(
        "b32_v26_renderer", path
    )
    renderer = importlib.util.module_from_spec(renderer_spec)
    sys.modules[renderer_spec.name] = renderer
    renderer_spec.loader.exec_module(renderer)
    return renderer


def export_v26() -> dict[str, object]:
    """Export, reimport, audit, and render the independent V26 assembly."""
    components, body_names = build_v26_components()
    physical = physical_v26_components(components)
    audit = audit_v26_integration(components, body_names)
    if (audit["missing_required_components"]
            or audit["missing_drive_prefixes"]
            or audit["original_arm_solids"] != P["original_arm"]["solid_count"]
            or any(abs(value) > 0.02
                   for value in audit["original_arm_bound_error_mm"])
            or audit["inherited_v25_overlap_count"]
            or audit["observation_only_exported"]):
        raise ValueError(f"V26 integration audit failed: {audit}")

    renderer = _load_renderer()
    step_path = HERE / P["outputs"]["step"]
    assembly = cq.Assembly(name="B32_v26_original_arm_and_v25_electronics")
    for name, shape in physical.items():
        assembly.add(shape, name=name, color=cq.Color(*renderer.colour(name)))
    assembly.export(str(step_path), exportType="STEP", unit="MM")

    readback = cq.importers.importStep(str(step_path)).val()
    if not readback.isValid() or not readback.Solids():
        raise ValueError("V26 STEP failed BREP reimport")
    images = renderer.render_v26_images(physical)
    audit.update({
        "step_valid": True,
        "step_solids": len(readback.Solids()),
        "step_bounds_mm": _rounded_bounds(readback),
        "whole_preview": images["whole_preview"],
        "root_preview": images["root_preview"],
    })
    audit_path = HERE / P["outputs"]["audit"]
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "step": step_path.name,
        "step_valid": True,
        "step_solids": len(readback.Solids()),
        "whole_preview": images["whole_preview"],
        "root_preview": images["root_preview"],
        "audit": audit_path.name,
    }


if __name__ == "__main__":
    print(json.dumps(export_v26(), ensure_ascii=False, indent=2))
