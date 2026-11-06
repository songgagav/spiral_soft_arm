"""B32 v25 confirmed power-input and M28 bottom-lid interface geometry."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cadquery as cq


HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
H = P["hardware"]
SOURCE = (HERE / P["source_assembly"]).resolve()
spec = importlib.util.spec_from_file_location("b32_v24_frozen_source", SOURCE)
v24 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v24
spec.loader.exec_module(v24)


def box(bounds: list[float] | tuple[float, ...]) -> cq.Shape:
    x0, x1, y0, y1, z0, z1 = bounds
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0, y0, z0))


def cyl(radius: float, z0: float, z1: float,
        x: float = 0.0, y: float = 0.0) -> cq.Shape:
    return cq.Solid.makeCylinder(radius, z1-z0, cq.Vector(x, y, z0))


def annulus(outer_radius: float, inner_radius: float,
            z0: float, z1: float) -> cq.Shape:
    return cyl(outer_radius, z0, z1).cut(cyl(inner_radius, z0-0.1, z1+0.1))


def build_m28_opening_cutter(z0: float, z1: float) -> cq.Shape:
    """Return the drawing-derived 26.2 mm flat × 28 mm high opening."""
    m28 = H["m28_power"]
    circular = cyl(float(m28["panel_opening_height"])/2, z0, z1)
    half_flat = float(m28["panel_opening_flat_width"])/2
    limiter = box((-half_flat, half_flat, -20.0, 20.0, z0, z1))
    return circular.intersect(limiter).clean()


def build_m28_load_ring() -> cq.Shape:
    """Integral outside ring around the flange, clear of the Ø36 face."""
    return annulus(28.0, 20.0, -243.0, -240.0).clean()


def _original_v23_lid() -> cq.Shape:
    original = v24.v23.build_v23_assembly_components()
    return original["v10_central_electronics_canister_lid"]


def build_recessed_m28_lid() -> cq.Shape:
    """Leave a 5 mm central land in the original 10 mm bottom lid."""
    lid = _original_v23_lid()
    recess = cyl(20.0, -235.0, -226.0)
    opening = build_m28_opening_cutter(-244.0, -225.0)
    return lid.cut(recess).cut(opening).fuse(build_m28_load_ring()).clean()


def build_v25_components() -> tuple[dict[str, cq.Shape], list[str]]:
    """Replace the v24 M28 proxy and add the confirmed controller buck."""
    components, body_names = v24.assemble()
    for obsolete in (
        "v24_central_bottom_lid_M28_bore",
        "v24_M28_inside_stem_proxy",
        "v24_M28_outside_flange_proxy",
    ):
        components.pop(obsolete, None)

    components["v25_bottom_lid_with_M28_recess"] = build_recessed_m28_lid()
    m28 = H["m28_power"]
    socket = build_m28_opening_cutter(-245.0, -206.5)
    components["v25_M28_socket_body"] = socket
    components["v25_M28_outside_flange"] = annulus(
        float(m28["outside_flange_diameter"])/2, 5.5, -245.0, -240.0
    ).clean()
    plug_diameter, plug_length = map(float, m28["plug_envelope"])
    components["v25_M28_male_plug_envelope"] = cyl(
        plug_diameter/2, -245.0-plug_length, -245.0
    )
    components["v25_M28_service_clearance"] = cyl(
        20.0, -321.0, -245.0
    )

    buck = H["buck_5v"]
    components["v25_buck_5v_envelope"] = box(buck["aabb"])
    x0, x1, y0, y1, z0, z1 = buck["aabb"]
    components["v25_buck_5v_shelf"] = box(
        (x1+1.0, x1+3.0, y0-1.0, y1+1.0, z0-2.0, z1+2.0)
    )
    body_names = [name for name in body_names if "M28" not in name]
    body_names.append("v25_buck_5v_envelope")

    for name, shape in components.items():
        if not shape.isValid() or not shape.Solids():
            raise ValueError(f"Invalid v25 component: {name}")
    return components, body_names


def dry_run_audit() -> dict[str, object]:
    components, bodies = build_v25_components()
    buck = components["v25_buck_5v_envelope"]
    overlaps = []
    for name in bodies:
        if name == "v25_buck_5v_envelope":
            continue
        other = components[name]
        a, b = buck.BoundingBox(), other.BoundingBox()
        if (a.xmax <= b.xmin or b.xmax <= a.xmin
                or a.ymax <= b.ymin or b.ymax <= a.ymin
                or a.zmax <= b.zmin or b.zmax <= a.zmin):
            continue
        volume = buck.intersect(other).Volume()
        if volume > 0.02:
            overlaps.append({"part": name, "volume_mm3": round(volume, 4)})
    if overlaps:
        raise ValueError(f"Buck module overlaps selected hardware: {overlaps}")
    return {
        "component_count": len(components),
        "hardware_body_count": len(bodies),
        "buck_hardware_overlaps": overlaps,
        "m28_opening_bounds_mm": [
            round(build_m28_opening_cutter(-241.0, -226.0).BoundingBox().xlen, 3),
            round(build_m28_opening_cutter(-241.0, -226.0).BoundingBox().ylen, 3),
        ],
        "effective_panel_land_mm": 5.0,
    }


if __name__ == "__main__":
    print(json.dumps(dry_run_audit(), ensure_ascii=False, indent=2))
