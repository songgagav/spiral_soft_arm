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
    return {
        "source_generator": str(SOURCE),
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


if __name__ == "__main__":
    source_components, source_bodies = build_v26_components()
    print(json.dumps(audit_v26_integration(source_components, source_bodies),
                     ensure_ascii=False, indent=2))
