from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import cadquery as cq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arm_module import _dovetail_points, _root_transition_points, make_root_transition_passage
from model_contract import load_contract


HERE = Path(__file__).resolve().parent
OUT = HERE / "coupons"


def _box(x: float, y: float, z: float, origin: tuple[float, float, float]) -> cq.Solid:
    return cq.Solid.makeBox(x, y, z, cq.Vector(*origin))


def _profile_prism(points: list[tuple[float, float]], z0: float, height: float) -> cq.Shape:
    return (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .polyline(points)
        .close()
        .extrude(height)
        .val()
    )


def _radial_hole(z: float, diameter: float, azimuth_deg: float = 30.0) -> cq.Solid:
    angle = math.radians(azimuth_deg)
    direction = cq.Vector(math.cos(angle), math.sin(angle), 0.0)
    start = cq.Vector(0.0, 0.0, z) - direction * 40.0
    return cq.Solid.makeCylinder(diameter / 2.0, 80.0, start, direction)


def build_dovetail_ladder(contract: Any) -> cq.Compound:
    """One male gauge and three sockets using the V27 normal-offset profile."""
    joint = contract.arm.dovetail
    base = _box(48.0, 36.0, 4.0, (-24.0, -18.0, 0.0))
    tongue = _profile_prism(_dovetail_points(contract, 0.0), 4.0, 12.0)
    male = base.fuse(tongue).cut(_radial_hole(10.0, joint.lock_pin_hole_diameter_mm)).clean()

    components: list[cq.Shape] = [male]
    variants = (0.20, 0.30, 0.40)
    for index, clearance in enumerate(variants, start=1):
        body = _box(48.0, 36.0, 16.0, (-24.0, -18.0, 0.0))
        socket = _profile_prism(
            _dovetail_points(contract, clearance),
            -0.1,
            float(joint.engagement_mm) + 0.32 + 0.1,
        )
        female = body.cut(socket).cut(
            _radial_hole(6.02, joint.lock_pin_hole_diameter_mm)
        ).clean()
        female = female.translate(cq.Vector(60.0 * index, 0.0, 0.0))
        components.append(female)
    return cq.Compound.makeCompound(components)


def _sector_points(inner_r: float, outer_r: float, start_deg: float, end_deg: float) -> list[tuple[float, float]]:
    steps = max(24, int(abs(end_deg - start_deg) * 1.5))
    outer = [
        (outer_r * math.cos(math.radians(start_deg + (end_deg - start_deg) * i / steps)),
         outer_r * math.sin(math.radians(start_deg + (end_deg - start_deg) * i / steps)))
        for i in range(steps + 1)
    ]
    inner = [
        (inner_r * math.cos(math.radians(end_deg - (end_deg - start_deg) * i / steps)),
         inner_r * math.sin(math.radians(end_deg - (end_deg - start_deg) * i / steps)))
        for i in range(steps + 1)
    ]
    return outer + inner


def build_root_register_ladder(contract: Any) -> cq.Compound:
    """Local arc gauges for the 130 mm register's radial clearance only."""
    arm_radius = 0.5 * float(contract.arm.root_diameter_mm)
    register_radius = 0.5 * float(contract.root_interface.register_diameter_mm)
    male = _profile_prism(
        _sector_points(arm_radius + 0.5, register_radius, -30.0, 30.0),
        0.0,
        float(contract.root_interface.register_height_mm),
    )
    components: list[cq.Shape] = [male]
    for index, clearance in enumerate((0.15, 0.25, 0.35), start=1):
        female = _profile_prism(
            _sector_points(register_radius + clearance, register_radius + 10.0, -32.0, 32.0),
            0.0,
            float(contract.root_interface.register_height_mm) + 3.0,
        )
        female = female.translate(cq.Vector(70.0 * index, 0.0, 0.0))
        components.append(female)
    return cq.Compound.makeCompound(components)


def build_tendon_transition_ladder(contract: Any) -> cq.Compound:
    """Three same-path channels around the current 0.8 mm passage diameter."""
    controls = _root_transition_points(contract, 0.0)
    start, _, _, join = controls
    join_vector = join
    after_join = controls[2]
    end_direction = (join_vector - after_join).normalized()
    components: list[cq.Shape] = []
    for index, diameter in enumerate((0.8, 1.0, 1.2)):
        radius = diameter / 2.0
        host = _box(43.0, 16.0, 75.0, (23.0, -8.0, 0.0))
        transition = make_root_transition_passage(contract, 0.0, radius)
        radial_start = cq.Vector(67.0, 0.0, float(start.z))
        radial_end = start
        radial = cq.Solid.makeCylinder(
            radius,
            (radial_end - radial_start).Length,
            radial_start,
            (radial_end - radial_start).normalized(),
        )
        host_top_z = 75.0
        axial_exit_distance = (host_top_z + 1.0 - join_vector.z) / end_direction.z
        axial_end = join_vector + end_direction * axial_exit_distance
        axial = cq.Solid.makeCylinder(
            radius,
            (axial_end - join_vector).Length,
            join_vector,
            end_direction,
        )
        coupon = host.cut(transition).cut(radial).cut(axial).clean()
        coupon = coupon.translate(cq.Vector(55.0 * index, 0.0, 0.0))
        components.append(coupon)
    return cq.Compound.makeCompound(components)


def _export_pair(name: str, shape: cq.Compound, notes: dict[str, Any]) -> dict[str, Any]:
    solids = shape.Solids()
    if not solids or any(not solid.isValid() or len(solid.Solids()) != 1 for solid in solids):
        raise ValueError(f"{name}: coupon set contains an invalid or disconnected part")
    bounds = shape.BoundingBox()
    if bounds.xlen > 350.0 or bounds.ylen > 350.0 or bounds.zlen > 320.0:
        raise ValueError(f"{name}: coupon layout exceeds the stated 350 x 350 x 320 mm envelope")
    step_path = OUT / f"{name}.step"
    stl_path = OUT / f"{name}.stl"
    cq.exporters.export(shape, str(step_path))
    cq.exporters.export(shape, str(stl_path), tolerance=0.05, angularTolerance=0.08)
    return {
        "name": name,
        "status": "CAD coupon candidate; not sliced or physically tested",
        "solid_count": len(solids),
        "bounds_mm": {"x": bounds.xlen, "y": bounds.ylen, "z": bounds.zlen},
        "build_volume_envelope_mm": [350.0, 350.0, 320.0],
        "step": step_path.name,
        "stl": stl_path.name,
        "sha256": {
            "step": hashlib.sha256(step_path.read_bytes()).hexdigest(),
            "stl": hashlib.sha256(stl_path.read_bytes()).hexdigest(),
        },
        **notes,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    contract = load_contract()
    records = [
        _export_pair(
            "V27_coupon_dovetail_lock_pin_ladder",
            build_dovetail_ladder(contract),
            {
                "purpose": "Compare V27 trapezoid socket clearances and the 3.3 mm cross-pin bore.",
                "male_profile": {
                    "bottom_width_mm": contract.arm.dovetail.bottom_width_mm,
                    "top_width_mm": contract.arm.dovetail.top_width_mm,
                    "profile_height_mm": contract.arm.dovetail.profile_height_mm,
                    "rotation_deg": contract.arm.dovetail.rotation_deg,
                    "engagement_mm": contract.arm.dovetail.engagement_mm,
                },
                "female_clearance_per_side_mm": [0.20, 0.30, 0.40],
                "female_coupon_x_offsets_mm": [60.0, 120.0, 180.0],
                "pin_hole_diameter_mm": contract.arm.dovetail.lock_pin_hole_diameter_mm,
                "assembly_note": "The three female sockets are separate variants. Pair each with the shared male gauge; use the specified 3 mm metal pin only after the dovetail fit is checked.",
                "limitations": ["does not reproduce the surrounding spiral-cell wall", "does not establish joint strength or fatigue life"],
            },
        ),
        _export_pair(
            "V27_coupon_root_register_radial_clearance_ladder",
            build_root_register_ladder(contract),
            {
                "purpose": "Compare local arc fit around the 130 mm register.",
                "male_register_diameter_mm": contract.root_interface.register_diameter_mm,
                "nominal_model_radial_clearance_mm": 0.25,
                "female_radial_clearance_variants_mm": [0.15, 0.25, 0.35],
                "female_coupon_x_offsets_mm": [70.0, 140.0, 210.0],
                "limitations": ["arc coupons measure local radial fit only", "do not check full-circle ovality, dowel alignment, bolt-group load, or flange flatness"],
            },
        ),
        _export_pair(
            "V27_coupon_tendon_transition_diameter_ladder",
            build_tendon_transition_ladder(contract),
            {
                "purpose": "Compare tendon passage diameters along the V27 root fairlead curve.",
                "tendon_nominal_diameter_mm": contract.arm.tendon_diameter_mm,
                "passage_diameter_variants_mm": [0.8, 1.0, 1.2],
                "coupon_x_offsets_mm": [0.0, 55.0, 110.0],
                "current_model_passage_diameter_mm": 0.8,
                "limitations": ["one radial route is represented because the three routes are rotational copies", "does not reproduce a flexible spiral arm or quantify UHMWPE wear"],
            },
        ),
    ]
    payload = {
        "candidate_id": contract.candidate_id,
        "status": "CAD coupon candidates; no slicer or physical test was performed",
        "records": records,
    }
    (OUT / "V27_coupon_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
