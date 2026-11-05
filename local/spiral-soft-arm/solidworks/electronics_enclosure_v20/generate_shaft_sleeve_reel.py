"""B32 v20 one-channel M3508 shaft-coupling and cable-reel review model.

This is an editable packaging/effect model derived from the v17 drive layout.
The miter gears are dimensional envelopes, not manufacturable tooth geometry.
"""
from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path

import cadquery as cq

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
OFFICIAL_STEP = HERE / P["motor"]["official_step"]["file"]


def box(x0: float, x1: float, y0: float, y1: float,
        z0: float, z1: float) -> cq.Shape:
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0, y0, z0))


def cyl_z(r: float, z0: float, z1: float,
          x: float = 0, y: float = 0) -> cq.Shape:
    return cq.Solid.makeCylinder(r, z1-z0, cq.Vector(x, y, z0), cq.Vector(0, 0, 1))


def cyl_x(r: float, x0: float, x1: float,
          y: float = 0, z: float = 0) -> cq.Shape:
    return cq.Solid.makeCylinder(r, x1-x0, cq.Vector(x0, y, z), cq.Vector(1, 0, 0))


def cyl_y(r: float, y0: float, y1: float,
          x: float = 0, z: float = 0) -> cq.Shape:
    return cq.Solid.makeCylinder(r, y1-y0, cq.Vector(x, y0, z), cq.Vector(0, 1, 0))


def ring_z(ro: float, ri: float, z0: float, z1: float,
           x: float = 0, y: float = 0) -> cq.Shape:
    return cyl_z(ro, z0, z1, x, y).cut(cyl_z(ri, z0-.1, z1+.1, x, y)).clean()


def ring_x(ro: float, ri: float, x0: float, x1: float,
           y: float = 0, z: float = 0) -> cq.Shape:
    return cyl_x(ro, x0, x1, y, z).cut(cyl_x(ri, x0-.1, x1+.1, y, z)).clean()


def d_ring_x(ro: float, bore_radius: float, bore_across_flat: float,
             x0: float, x1: float, y: float = 0, z: float = 0) -> cq.Shape:
    """Return an X-axis ring with a +Y D-bore; across-flat is the overall D size."""
    flat_offset = bore_across_flat - bore_radius
    if not 0 < flat_offset < bore_radius:
        raise ValueError("D-bore across-flat dimension is incompatible with its radius")
    bore = cyl_x(bore_radius, x0-.1, x1+.1, y, z)
    flat_cut = box(x0-.2, x1+.2, y+flat_offset, y+bore_radius+2,
                   z-bore_radius-2, z+bore_radius+2)
    return cyl_x(ro, x0, x1, y, z).cut(bore.cut(flat_cut)).clean()


def miter_blank_z(back_z: float, hub_radius: float, hub_width: float,
                  total_length: float, base_radius: float, tip_radius: float,
                  bore_radius: float, bore_length: float,
                  relief_tip_radius: float | None = None) -> cq.Shape:
    """Catalog-dimension, tooth-free axial blank; caller cuts the M4 screw holes."""
    shoulder_z = back_z + hub_width
    tip_z = back_z + total_length
    outer = cyl_z(hub_radius, back_z, shoulder_z).fuse(
        cq.Solid.makeCone(base_radius, tip_radius, total_length-hub_width,
                          cq.Vector(0, 0, shoulder_z), cq.Vector(0, 0, 1)))
    bore_end = back_z + bore_length
    body = outer.cut(cyl_z(bore_radius, back_z-.1, bore_end))
    if relief_tip_radius is not None and tip_z > bore_end:
        body = body.cut(cq.Solid.makeCone(bore_radius, relief_tip_radius, tip_z-bore_end,
                    cq.Vector(0, 0, bore_end), cq.Vector(0, 0, 1)))
    return body.clean()


def miter_blank_x(back_x: float, y: float, z: float, hub_radius: float,
                  hub_width: float, total_length: float, base_radius: float,
                  tip_radius: float, bore_radius: float,
                  bore_length: float) -> cq.Shape:
    """Catalog-dimension, tooth-free X-axis blank with a 16.5 mm finished bore."""
    shoulder_x = back_x + hub_width
    tip_x = back_x + total_length
    outer = cyl_x(hub_radius, back_x, shoulder_x, y, z).fuse(
        cq.Solid.makeCone(base_radius, tip_radius, total_length-hub_width,
                          cq.Vector(shoulder_x, y, z), cq.Vector(1, 0, 0)))
    return outer.cut(cyl_x(bore_radius, back_x-.1, back_x+bore_length, y, z)).clean()


def frustum_z(r0: float, r1: float, z0: float, z1: float,
              bore: float) -> cq.Shape:
    outer = cq.Solid.makeCone(r0, r1, z1-z0, cq.Vector(0, 0, z0), cq.Vector(0, 0, 1))
    return outer.cut(cyl_z(bore, z0-.1, z1+.1)).clean()


def frustum_x(r0: float, r1: float, x0: float, x1: float,
              z: float, bore: float) -> cq.Shape:
    outer = cq.Solid.makeCone(r0, r1, x1-x0, cq.Vector(x0, 0, z), cq.Vector(1, 0, 0))
    return outer.cut(cyl_x(bore, x0-.1, x1+.1, 0, z)).clean()


def d_bore(radius: float, flat: float, z0: float, z1: float,
           flat_angle_deg: float = 0.0) -> cq.Shape:
    """Build a D cavity; flat is the across-flat dimension, oriented to the motor."""
    flat_offset = flat - radius
    if flat_offset <= 0 or flat_offset >= radius:
        raise ValueError("D-bore across-flat dimension is incompatible with its radius")
    cavity = cyl_z(radius, z0, z1)
    flat_cut = box(flat_offset, radius+2, -radius-2, radius+2, z0-.1, z1+.1)
    flat_cut = flat_cut.rotate((0, 0, z0), (0, 0, z1), flat_angle_deg)
    return cavity.cut(flat_cut).clean()


def reel_winding_layout() -> dict[str, object]:
    """Return a non-overlapping, evenly spaced cable-wrap envelope layout."""
    cfg = P["reel"]
    cable_d = cfg["cable_diameter_proxy_mm"]
    turns = int(cfg["turns_per_layer"])
    layers = int(cfg["radial_layers"])
    pitch = cfg["axial_winding_pitch_mm"]
    radial_pitch = cfg["radial_winding_pitch_mm"]
    width = cfg["axial_width_mm"]
    flange = cfg["flange_thickness_mm"]
    core_width = width - 2 * flange
    center_x = -P["drive"]["motor_to_reel_tangent_offset_mm"]
    if turns < 1 or layers < 1 or pitch < cable_d or radial_pitch < cable_d:
        raise ValueError("Cable winding pitch/layer count is physically invalid")
    if core_width < (turns-1)*pitch + cable_d:
        raise ValueError("Reel core is too narrow for the specified cable turns")
    axial_centers = [center_x + (i-(turns-1)/2)*pitch for i in range(turns)]
    centerline_radii = [cfg["core_radius_mm"] + cable_d/2 + i*radial_pitch
                        for i in range(layers)]
    return {
        "center_x_mm": center_x,
        "core_width_mm": core_width,
        "core_x0_mm": center_x-core_width/2,
        "core_x1_mm": center_x+core_width/2,
        "axial_centers_mm": axial_centers,
        "centerline_radii_mm": centerline_radii,
    }


def tangent_point() -> tuple[float, float]:
    """Exact upper tangent from outer winding layer to the guide-port center."""
    c = (37.0, -23.0)
    h = (30.6, -8.8)
    radius = reel_winding_layout()["centerline_radii_mm"][-1]
    vx, vz = h[0]-c[0], h[1]-c[1]
    d2 = vx*vx + vz*vz
    if d2 <= radius*radius:
        raise ValueError("Guide port lies inside the reel cable envelope")
    d = math.sqrt(d2)
    perp = (-vz, vx)
    base = (radius*radius/d2*vx, radius*radius/d2*vz)
    off_scale = radius*math.sqrt(d2-radius*radius)/d2
    offsets = ((base[0]+off_scale*perp[0], base[1]+off_scale*perp[1]),
               (base[0]-off_scale*perp[0], base[1]-off_scale*perp[1]))
    choices = [(c[0]+q[0], c[1]+q[1]) for q in offsets]
    return max(choices, key=lambda q: q[1])


def load_official_motor() -> cq.Shape:
    """Import the downloaded DJI STEP and align its actual output axis to v20."""
    if not OFFICIAL_STEP.is_file():
        raise FileNotFoundError(f"Official M3508 STEP is missing: {OFFICIAL_STEP}")
    cfg = P["motor"]["official_step"]
    motor = cq.importers.importStep(str(OFFICIAL_STEP)).val()
    if not motor.isValid() or not motor.Solids():
        raise ValueError("Official M3508 STEP did not import as valid solids")

    source_x, source_y = cfg["output_axis_xy_mm"]
    source_tip_z = cfg["output_tip_z_mm"]
    target_tip_z = P["motor"]["assembly_output_tip_z_mm"]
    return motor.translate(cq.Vector(-source_x, -source_y, target_tip_z-source_tip_z))


def build_parts() -> dict[str, cq.Shape]:
    # Local coordinates reproduce one v17 channel: motor axis at (0,0),
    # cable-reel center 54 mm away along the tangent axis X.
    parts: dict[str, cq.Shape] = {}

    # Imported manufacturer geometry replaces the earlier dimensional envelope.
    parts["DJI_M3508_P19_official_STEP"] = load_official_motor()

    # 20 mm coupling: 12.3 mm D engagement (stops before the user-document
    # groove estimate) + 7.7 mm round shaft socket. The Ø5.5 axial clearance
    # hole carries a long M5 retaining screw through the secondary shaft.
    sleeve = cyl_z(8.0, -81.0, -61.0)
    motor_shaft_radius = P["motor"]["output_shaft_diameter_mm"] / 2
    motor_bore_radius = motor_shaft_radius + P["coupling"]["female_D_radial_clearance_mm"]
    sleeve = sleeve.cut(d_bore(
        motor_bore_radius, P["coupling"]["female_D_across_flat_mm"], -81.1, -68.7,
        P["motor"]["official_step"]["d_flat_normal_angle_deg"]))
    sleeve = sleeve.cut(cyl_z(5.1, -68.7, -60.9))
    sleeve = sleeve.cut(cyl_z(2.75, -81.1, -60.9))
    # Two opposing M3 set-screw bores and fastener envelopes, 6.2 mm above tip.
    for side, y0, y1 in (("plus", 4.9, 8.1), ("minus", -8.1, -4.9)):
        sleeve = sleeve.cut(cyl_y(1.35, y0, y1, 0, -64.8))
        parts[f"M3_set_screw_{side}"] = cyl_y(1.2, 5.0, 7.4, 0, -64.8) if side == "plus" else cyl_y(1.2, -7.4, -5.0, 0, -64.8)
    parts["D_bore_20mm_shaft_coupling"] = sleeve.clean()

    # The input shaft stops at the KHK 16.5 mm bore end. Two 9.5 mm
    # across-flat lands meet the included M4 set-screw proxies in the Ø25 hub.
    gear_cfg = P["drive"]["stock_miter_gear"]
    gear = miter_blank_z(
        back_z=-51.0,
        hub_radius=gear_cfg["hub_diameter_mm"]/2,
        hub_width=gear_cfg["hub_width_mm"],
        total_length=gear_cfg["total_axis_length_mm"],
        base_radius=gear_cfg["outside_diameter_mm"]/2,
        tip_radius=8.0,
        bore_radius=gear_cfg["bore_diameter_mm"]/2,
        bore_length=gear_cfg["bore_length_mm"],
        relief_tip_radius=7.0,
    )
    screw_z = -51.0 + gear_cfg["screw_center_from_back_mm"]
    flat = gear_cfg["screw_contact_radial_offset_mm"]
    hub_r = gear_cfg["hub_diameter_mm"]/2
    gear = gear.cut(cyl_x(2.1, flat-.05, hub_r+.1, 0, screw_z))
    gear = gear.cut(cyl_y(2.1, flat-.05, hub_r+.1, 0, screw_z))
    parts["KHK_MMSA1_5_20R_input_gear_catalog_envelope"] = gear.clean()
    parts["KHK_input_M4_set_screw_X_proxy"] = cyl_x(2.0, flat, hub_r, 0, screw_z)
    parts["KHK_input_M4_set_screw_Y_proxy"] = cyl_y(2.0, flat, hub_r, 0, screw_z)

    # Input spindle has a Ø5.5 through-bolt clearance. Its top washer/head
    # sit in the inferred central relief of the tooth-free gear envelope.
    shaft = cyl_z(5.0, -68.7, gear_cfg["input_bore_end_z_mm"])
    shaft = shaft.cut(cyl_z(2.75, -68.8, gear_cfg["input_bore_end_z_mm"]+.1))
    flat_offset = gear_cfg["shaft_flat_across_mm"] - gear_cfg["shaft_diameter_mm"]/2
    shaft = shaft.cut(box(flat_offset, 7.0, -7.0, 7.0, -51.0, -40.5))
    shaft = shaft.cut(box(-7.0, 7.0, flat_offset, 7.0, -51.0, -40.5))
    parts["extended_vertical_drive_shaft_two_M4_flats"] = shaft.clean()

    # M5 x 45 proxy: 0.8 mm washer places the screw underside at z=-33.7,
    # giving 10 mm engagement into the motor's stated 10 mm blind thread.
    screw = cyl_z(2.5, -78.7, -33.7).fuse(cyl_z(4.25, -33.7, -28.7))
    parts["M5x45_axial_retaining_screw_proxy"] = screw.clean()
    washer = ring_z(4.8, 2.6, -34.5, -33.7)
    parts["M5_spacer_washer_0_8mm"] = washer

    # The catalog table supplies mounting distances, hub geometry and bore
    # length; tooth geometry remains a non-meshing envelope proxy.
    parts["SKF_6000_2RS1_input_bearing_envelope"] = ring_z(13.0, 5.02, -60.0, -52.0)
    output_gear = miter_blank_x(
        back_x=-28.0, y=0.0, z=-23.0,
        hub_radius=gear_cfg["hub_diameter_mm"]/2,
        hub_width=gear_cfg["hub_width_mm"],
        total_length=gear_cfg["total_axis_length_mm"],
        base_radius=gear_cfg["outside_diameter_mm"]/2,
        tip_radius=8.0,
        bore_radius=gear_cfg["bore_diameter_mm"]/2,
        bore_length=gear_cfg["bore_length_mm"],
    )
    screw_x = -28.0 + gear_cfg["screw_center_from_back_mm"]
    output_gear = output_gear.cut(cyl_y(2.1, flat-.05, hub_r+.1, screw_x, -23.0))
    output_gear = output_gear.cut(cyl_z(2.1, -23.0+flat-.05, -23.0+hub_r+.1,
                                      screw_x, 0.0))
    parts["KHK_MMSA1_5_20L_output_gear_catalog_envelope"] = output_gear.clean()
    parts["KHK_output_M4_set_screw_Y_proxy"] = cyl_y(2.0, flat, hub_r, screw_x, -23.0)
    parts["KHK_output_M4_set_screw_Z_proxy"] = cyl_z(2.0, -23.0+flat, -23.0+hub_r,
                                                    screw_x, 0.0)

    # Move the wet reel 1.5 mm away from the labyrinth face while keeping the
    # tangent and guide-port line on the same radial plane.
    reel_cfg = P["reel"]
    layout = reel_winding_layout()
    center_x = layout["center_x_mm"]
    half_width = reel_cfg["axial_width_mm"] / 2
    reel_x0, reel_x1 = center_x-half_width, center_x+half_width

    # Output shaft and dry-side support/seal stack; the wet reel remains outside.
    output_shaft = cyl_x(5.0, reel_x0, gear_cfg["output_bore_end_x_mm"], 0, -23.0)
    output_shaft = output_shaft.cut(box(reel_x0-.1, -11.4, flat_offset, 7.0,
                                        -30.0, -16.0))
    output_shaft = output_shaft.cut(box(-28.1, -17.4, -7.0, 7.0,
                                        -23.0+flat_offset, -16.0))
    reel_cfg = P["reel"]
    output_shaft = output_shaft.cut(cyl_x(
        reel_cfg["retainer_screw_shank_diameter_proxy_mm"]/2,
        reel_x0-.1, reel_x0+reel_cfg["retainer_tap_depth_mm"], 0, -23.0))
    parts["tangential_output_shaft_D_flat_and_M4_tap_proxy"] = output_shaft.clean()
    parts["SKF_3200_ATN9_output_bearing_envelope"] = ring_x(15.0, 5.02, -42.0, -28.0, 0, -23.0)
    parts["SKF_10x22x7_rotary_seal_envelope"] = ring_x(11.0, 5.02, -49.5, -42.5, 0, -23.0)
    # Seat the thin labyrinth ring against the wet-side bulkhead face; the
    # previous inherited position intersected both the bulkhead and cartridge.
    parts["fixed_labyrinth_envelope"] = ring_x(13.8, 5.4, -51.15, -50.7, 0, -23.0)

    # Keep the seal seat and bearing seat as separate serviceable envelopes;
    # the 0.5 mm axial gap between them is intentional and remains a housing
    # detail to resolve, not a fused one-piece cartridge.
    parts["dry_side_radial_seal_support_sleeve_envelope"] = ring_x(
        12.0, 11.0, -50.5, -42.5, 0, -23.0)
    parts["dry_side_output_bearing_support_sleeve_envelope"] = ring_x(
        16.0, 15.0, -42.0, -28.0, 0, -23.0)
    wall = box(-50.7, -49.0, -23.0, 23.0, -58.0, 4.0)
    # Ø24.1 opening clears the Ø24 cartridge envelope by 0.05 mm radially.
    wall = wall.cut(cyl_x(12.05, -50.8, -48.9, 0, -23.0))
    parts["dry_wet_bulkhead_local_proxy"] = wall.clean()

    # Wet-side cable drum. Keep the 8 mm overall width while allocating enough
    # core width for three Ø1.6 wraps per layer; two radial layers fit inside
    # the Ø21 flanges without overlapping the cable envelopes.
    x0, x1 = reel_x0, reel_x1
    bore_r = reel_cfg["d_bore_diameter_mm"] / 2
    bore_af = reel_cfg["d_bore_across_flat_mm"]
    parts["wet_reel_inner_flange_D_bore"] = d_ring_x(reel_cfg["flange_radius_mm"], bore_r, bore_af,
        x0, layout["core_x0_mm"], 0, -23.0)
    parts["wet_reel_core_D_bore"] = d_ring_x(reel_cfg["core_radius_mm"], bore_r, bore_af,
        layout["core_x0_mm"], layout["core_x1_mm"], 0, -23.0)
    parts["wet_reel_outer_flange_D_bore"] = d_ring_x(reel_cfg["flange_radius_mm"], bore_r, bore_af,
        layout["core_x1_mm"], x1, 0, -23.0)
    plate = ring_x(reel_cfg["retainer_plate_outer_diameter_mm"]/2,
                   reel_cfg["retainer_plate_bore_diameter_mm"]/2,
                   reel_cfg["retainer_plate_x0_mm"], reel_cfg["retainer_plate_x1_mm"],
                   0, -23.0)
    parts["wet_reel_axial_retainer_plate"] = plate
    screw_head_x1 = reel_cfg["retainer_plate_x0_mm"]
    screw_head_x0 = screw_head_x1 - reel_cfg["retainer_screw_head_height_mm"]
    screw_shank_x1 = reel_cfg["retainer_plate_x1_mm"] + reel_cfg["retainer_screw_engagement_mm"]
    screw_head = cyl_x(reel_cfg["retainer_screw_head_diameter_mm"]/2,
                       screw_head_x0, screw_head_x1, 0, -23.0)
    screw_shank = cyl_x(reel_cfg["retainer_screw_shank_diameter_proxy_mm"]/2,
                        screw_head_x1, screw_shank_x1, 0, -23.0)
    parts["M4x10_wet_reel_retainer_screw_proxy"] = screw_head.fuse(screw_shank).clean()
    cable_radius = reel_cfg["cable_diameter_proxy_mm"] / 2
    turn_index = 1
    for radius in layout["centerline_radii_mm"]:
        for x in layout["axial_centers_mm"]:
            parts[f"wound_tendon_turn_{turn_index}_proxy"] = cq.Solid.makeTorus(
                radius, cable_radius, cq.Vector(x, 0, -23.0), cq.Vector(1, 0, 0))
            turn_index += 1

    # Exact straight cable segment from the reel tangent to the chamfered port.
    tangent_r, tangent_z = tangent_point()
    start = cq.Vector(center_x, tangent_r-37.0, tangent_z)
    hole_center = cq.Vector(center_x, 30.6-37.0, -8.8)
    unit = (hole_center-start).normalized()
    finish_z = -7.3 + 2.0  # continue through the full plate and 2 mm beyond it
    finish = hole_center + unit*((finish_z-hole_center.z)/unit.z)
    direction = finish-start
    parts["straight_tangent_tendon_proxy"] = cq.Solid.makeCylinder(
        0.8, direction.Length, start, direction.normalized())

    # Guide plate and enlarged 1.5 mm conical leads for the oblique tendon.
    # A conventional Ø7.2 x 1.5 mm 45-degree chamfer clipped the Ø1.6 cable
    # envelope at the current 59-degree approach angle; Ø10 mm mouths clear it.
    port = box(-66.0, -42.0, -20.0, 8.0, -10.3, -7.3)
    port = port.cut(cyl_z(2.1, -10.4, -7.2, center_x, -6.4))
    mouth_r = P["reel"]["guide_port_mouth_diameter_mm"] / 2
    port = port.cut(cq.Solid.makeCone(mouth_r, 2.1, 1.5,
        cq.Vector(center_x, -6.4, -10.3), cq.Vector(0, 0, 1)))
    port = port.cut(cq.Solid.makeCone(2.1, mouth_r, 1.5,
        cq.Vector(center_x, -6.4, -8.8), cq.Vector(0, 0, 1)))
    parts["chamfered_cable_guide_plate_proxy"] = port.clean()

    # D-shaft seal sits on the cylindrical OD of the sleeve at the motor-side
    # bulkhead. The annular carrier is fused into the removable pod envelope.
    motor_seal_cfg = P["motor_output_shaft_seal"]
    parts["motor_output_rotary_seal_16x22x7_envelope"] = ring_z(
        motor_seal_cfg["outer_diameter_mm"]/2,
        motor_seal_cfg["sleeve_contact_diameter_mm"]/2,
        *motor_seal_cfg["z_range_mm"])

    # Existing removable right-angle cartridge envelope, made translucent in render.
    # The bottom disk closes the annular pod around the motor sleeve seal.
    pod = ring_z(27.0, 17.0, -80.5, -11.0)
    pod = pod.fuse(ring_z(27.0, 11.0, -80.5, -73.5))
    pod = pod.cut(cyl_x(16.2, -28.0, 1.0, 0, -23.0)).clean()
    parts["transparent_right_angle_drive_pod_envelope"] = pod
    return parts


COLORS = {
    "DJI_M3508_P19_official_STEP": ((0.10, 0.20, 0.30), 1.0),
    "D_bore_20mm_shaft_coupling": ((0.82, 0.58, 0.19), 1.0),
    "extended_vertical_drive_shaft_two_M4_flats": ((0.72, 0.75, 0.78), 1.0),
    "M5x45_axial_retaining_screw_proxy": ((0.34, 0.39, 0.43), 1.0),
    "M5_spacer_washer_0_8mm": ((0.54, 0.58, 0.62), 1.0),
    "SKF_6000_2RS1_input_bearing_envelope": ((0.58, 0.62, 0.67), 0.94),
    "KHK_MMSA1_5_20R_input_gear_catalog_envelope": ((0.87, 0.49, 0.13), 0.72),
    "KHK_MMSA1_5_20L_output_gear_catalog_envelope": ((0.91, 0.61, 0.18), 0.72),
    "KHK_input_M4_set_screw_X_proxy": ((0.30, 0.34, 0.39), 1.0),
    "KHK_input_M4_set_screw_Y_proxy": ((0.30, 0.34, 0.39), 1.0),
    "KHK_output_M4_set_screw_Y_proxy": ((0.30, 0.34, 0.39), 1.0),
    "KHK_output_M4_set_screw_Z_proxy": ((0.30, 0.34, 0.39), 1.0),
    "tangential_output_shaft_D_flat_and_M4_tap_proxy": ((0.72, 0.75, 0.78), 1.0),
    "SKF_3200_ATN9_output_bearing_envelope": ((0.58, 0.62, 0.67), 0.94),
    "SKF_10x22x7_rotary_seal_envelope": ((0.77, 0.23, 0.20), 0.92),
    "motor_output_rotary_seal_16x22x7_envelope": ((0.82, 0.19, 0.16), 0.95),
    "fixed_labyrinth_envelope": ((0.37, 0.69, 0.72), 0.9),
    "dry_side_radial_seal_support_sleeve_envelope": ((0.28, 0.56, 0.66), 0.2),
    "dry_side_output_bearing_support_sleeve_envelope": ((0.28, 0.56, 0.66), 0.2),
    "dry_wet_bulkhead_local_proxy": ((0.18, 0.52, 0.64), 0.18),
    "wet_reel_inner_flange_D_bore": ((0.88, 0.64, 0.16), 1.0),
    "wet_reel_core_D_bore": ((0.93, 0.72, 0.26), 1.0),
    "wet_reel_outer_flange_D_bore": ((0.88, 0.64, 0.16), 1.0),
    "wet_reel_axial_retainer_plate": ((0.58, 0.64, 0.70), 1.0),
    "M4x10_wet_reel_retainer_screw_proxy": ((0.30, 0.34, 0.39), 1.0),
    "straight_tangent_tendon_proxy": ((0.84, 0.31, 0.15), 1.0),
    "chamfered_cable_guide_plate_proxy": ((0.35, 0.63, 0.71), 0.23),
    "transparent_right_angle_drive_pod_envelope": ((0.18, 0.49, 0.62), 0.12),
}
COLORS.update({f"wound_tendon_turn_{i}_proxy": ((0.84, 0.31, 0.15), 1.0)
               for i in range(1, int(P["reel"]["turns_per_layer"]*P["reel"]["radial_layers"])+1)})


def render_vtk(parts: dict[str, cq.Shape], path: Path, section: bool = False,
               reel_closeup: bool = False) -> None:
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(1500, 1050)
    window.SetMultiSamples(0)
    scene = vtk.vtkRenderer()
    scene.SetBackground(0.94, 0.965, 0.98)
    scene.SetUseDepthPeeling(1)
    window.AddRenderer(scene)

    cut_box = box(-100.0, 100.0, 0.0, 100.0, -180.0, 20.0) if section else None
    if section:
        cut_box = cut_box.rotate((0, 0, 0), (0, 0, 1),
                                 P["motor"]["official_step"]["d_flat_normal_angle_deg"])
    selected = ("DJI_M3508_P19_official_STEP",
                "D_bore_20mm_shaft_coupling", "extended_vertical_drive_shaft_two_M4_flats",
                "motor_output_rotary_seal_16x22x7_envelope",
                "M5x45_axial_retaining_screw_proxy", "M5_spacer_washer_0_8mm",
                "M3_set_screw_plus", "M3_set_screw_minus", "SKF_6000_2RS1_input_bearing_envelope")
    reel_parts = {"wet_reel_inner_flange_D_bore", "wet_reel_core_D_bore",
                  "wet_reel_outer_flange_D_bore", "wet_reel_axial_retainer_plate",
                  "M4x10_wet_reel_retainer_screw_proxy",
                  "tangential_output_shaft_D_flat_and_M4_tap_proxy",
                  "straight_tangent_tendon_proxy", "chamfered_cable_guide_plate_proxy"}
    total_turns = int(P["reel"]["turns_per_layer"]*P["reel"]["radial_layers"])
    reel_parts.update(f"wound_tendon_turn_{i}_proxy" for i in range(1, total_turns+1))
    for name, shape in parts.items():
        color, opacity = COLORS.get(name, ((0.7, 0.7, 0.7), 1.0))
        if reel_closeup and name not in reel_parts:
            continue
        if reel_closeup and name == "wet_reel_inner_flange_D_bore":
            # Show the winding behind the near flange in this detail view only.
            opacity = 0.14
        if section:
            if name not in selected:
                continue
            # Cut through the reel-axis plane to expose the D-bore and screw stack.
            shape = shape.intersect(cut_box)
            if shape.isNull() or shape.Volume() < 1e-5:
                continue
            opacity = 1.0
        vertices, faces = shape.tessellate(0.45 if section else 0.9, 0.12)
        points = vtk.vtkPoints()
        points.SetNumberOfPoints(len(vertices))
        for j, p in enumerate(vertices):
            points.SetPoint(j, p.x, p.y, p.z)
        polys = vtk.vtkCellArray()
        for face in faces:
            polys.InsertNextCell(3)
            for node in face:
                polys.InsertCellPoint(int(node))
        data = vtk.vtkPolyData()
        data.SetPoints(points)
        data.SetPolys(polys)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(data)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*color)
        prop.SetOpacity(opacity)
        prop.SetSpecular(0.22)
        prop.SetSpecularPower(24)
        prop.SetInterpolationToPhong()
        scene.AddActor(actor)

    camera = scene.GetActiveCamera()
    reel_center_x = reel_winding_layout()["center_x_mm"]
    camera.ParallelProjectionOn()
    if section:
        camera.SetFocalPoint(0, 0, -65)
        camera.SetPosition(115, -165, -28)
        camera.SetViewUp(0, 0, 1)
        camera.SetParallelScale(25)
    elif reel_closeup:
        camera.SetFocalPoint(reel_center_x, -1, -19)
        camera.SetPosition(reel_center_x-156, 50, 65)
        camera.SetViewUp(0, 0, 1)
        camera.SetParallelScale(21)
    else:
        camera.SetFocalPoint(-26, 0, -84)
        # Look from the wet reel/cable side so the drum and straight tangent
        # segment remain in front of, rather than hidden behind, the gears.
        camera.SetPosition(-80, 185, 0)
        camera.SetViewUp(0, 0, 1)
        camera.SetParallelScale(103)
    scene.ResetCameraClippingRange()
    window.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(window)
    grab.SetInputBufferTypeToRGB()
    grab.Update()
    output = grab.GetOutput()
    width, height, _ = output.GetDimensions()
    pixels = vtk_to_numpy(output.GetPointData().GetScalars()).reshape(height, width, 3)[::-1]
    canvas = Image.fromarray(np.asarray(pixels, dtype=np.uint8).copy())

    font_path = "C:/Windows/Fonts/msyh.ttc"
    font = ImageFont.truetype(font_path, 26 if not section else 28)
    body = ImageFont.truetype(font_path, 19)
    small = ImageFont.truetype(font_path, 17)
    panel_w = 560
    framed = Image.new("RGB", (canvas.width+panel_w, canvas.height), (247, 249, 251))
    framed.paste(canvas, (0, 0))
    draw = ImageDraw.Draw(framed)
    px = canvas.width + 30
    if section:
        draw.text((px, 34), "D 形线轮与端面压片剖视", font=font, fill=(31, 48, 62))
        notes = [
            "线轮轴向宽 8 mm；内孔 Ø10.3 / AF 9.8",
            "输出轴 Ø10 / AF 9.5，D 平面朝 +Y",
            "圆周与平面名义间隙均为 0.15 mm",
            "端面压片 Ø14 × 1.5 mm，限制线轮轴向滑脱",
            "M4 × 10 螺钉代理；轴内啮合长度 8.5 mm",
            "轴向盲孔深 9 mm；螺纹牙型未建模",
            "螺钉头 Ø7 × 4 mm，需确认工具可接近",
            "线轮、压片为独立件，便于拆装维护",
            "本图聚焦线轮；电机 D 轴套另有一道油封",
            "间隙为打印拟合初值，先做配合试片",
        ]
        y = 98
        for i, line in enumerate(notes):
            draw.text((px, y), line, font=body if i < 7 else small,
                      fill=(43, 61, 76) if i < 7 else (157, 74, 40))
            y += 54 if i < 7 else 42
        draw.text((28, canvas.height-42), "轴向剖面示意；螺纹牙型、配合公差和材料变形未建模。", font=small, fill=(54, 68, 81))
    elif reel_closeup:
        draw.text((px, 34), "湿侧线轮 | 切线直达线孔", font=font, fill=(31, 48, 62))
        layout = reel_winding_layout()
        tangent_r, tangent_z = tangent_point()
        line_length = math.dist((tangent_r, tangent_z), (30.6, -8.8))
        cable_d = P["reel"]["cable_diameter_proxy_mm"]
        outer_surface = layout["centerline_radii_mm"][-1] + cable_d/2
        estimated_length = sum(2*math.pi*r*P["reel"]["turns_per_layer"]
                               for r in layout["centerline_radii_mm"])
        notes = [
            "卷筒芯半径 6.5 mm，挡边半径 10.5 mm",
            "线径假设 Ø1.6 mm；绕线示意 2 层 × 3 圈",
            f"轴向/径向节距 {P['reel']['axial_winding_pitch_mm']:.1f} mm；外层半径 {outer_surface:.1f} mm",
            f"外层切点至导孔中心线长约 {line_length:.2f} mm",
            f"导孔 Ø4.2 mm，双侧 Ø{P['reel']['guide_port_mouth_diameter_mm']:.1f} × 1.5 mm 锥口",
            f"几何绕线量约 {estimated_length:.0f} mm，未计余量",
        ]
        y = 112
        for line in notes:
            draw.text((px, y), line, font=body, fill=(43,61,76))
            y += 64
        draw.text((px, y+16), "标注为候选包络", font=body, fill=(157,74,40))
        draw.text((px, y+64), "实际行程、排线方式和轴封水下性能仍需验证。", font=small, fill=(80,93,105))
    else:
        draw.text((px, 34), "B32 v20 | M3508 D轴套双轴封与线轮", font=font, fill=(31, 48, 62))
        notes = [
            ("1", "M3508 P19 官方 STEP，竖直安装"),
            ("2", "D 形轴套套在电机输出轴上"),
            ("3", "电机油封压在 Ø16 轴套外圆"),
            ("4", "90° 锥齿包络，齿形为示意"),
            ("5", "横轴：轴承 / 主油封 / 迷宫"),
            ("6", "湿侧线轮，Ø13 芯、Ø21 挡边"),
            ("7", "线绳沿卷筒切线直达倒角线孔"),
        ]
        y = 105
        palette = [(0.10,0.20,0.30),(0.82,0.58,0.19),(0.58,0.62,0.67),
                   (0.87,0.49,0.13),(0.77,0.23,0.20),(0.93,0.72,0.26),(0.84,0.31,0.15)]
        for (n, line), color in zip(notes, palette):
            draw.rounded_rectangle((px, y+2, px+34, y+36), radius=8,
                                   fill=tuple(round(v*255) for v in color))
            draw.text((px+10, y+4), n, font=small, fill=(255,255,255))
            draw.text((px+48, y+4), line, font=body, fill=(43,61,76))
            y += 72
        draw.text((px, y+18), "候选尺寸 / 待确认", font=body, fill=(157,74,40))
        for line in ("电机 D 面及卡簧槽仍需实物复测",
                     "轴封、轴承与水压等级还需样机验证",
                     "齿轮仅示目录尺寸包络，不含真实齿形",
                     "KHK 螺钉孔角度及随件螺钉需对到货件核实"):
            y += 39
            draw.text((px, y), line, font=small, fill=(80,93,105))
        draw.text((24, canvas.height-40), "单通道传动模块预览；不是完整 B32 总装或水密验证结果。",
                  font=small, fill=(54,68,81))
    framed.save(path)


def render_section_diagram(path: Path) -> None:
    """Show the reel D-fit, axial retainer plate, and M4 screw in axial section."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(13, 7.5), dpi=180)
    fig.patch.set_facecolor("#f4f7fa")
    ax.set_facecolor("#f4f7fa")

    cfg = P["reel"]
    layout = reel_winding_layout()
    center_x = layout["center_x_mm"]
    d = cfg["shaft_diameter_mm"]
    male_flat = cfg["shaft_flat_across_mm"] - d/2
    bore_r = cfg["d_bore_diameter_mm"] / 2
    bore_flat = cfg["d_bore_across_flat_mm"] - bore_r
    x_outer0 = center_x - cfg["axial_width_mm"]/2
    x_outer1 = x_outer0 + cfg["flange_thickness_mm"]
    x_core0, x_core1 = layout["core_x0_mm"], layout["core_x1_mm"]
    x_inner1 = center_x + cfg["axial_width_mm"]/2
    shaft_x0 = x_outer0
    shaft_x1 = P["drive"]["stock_miter_gear"]["output_bore_end_x_mm"]
    r_core, r_flange, r_bore = cfg["core_radius_mm"], cfg["flange_radius_mm"], bore_r
    gold, dark_gold = "#d39a2f", "#bd8124"
    steel, dark = "#9da7ae", "#3a434a"

    # Cable drum is shown as a longitudinal section; upper/lower bands are
    # the two sides of each annular part, with the D-flat at +Y above center.
    for xa, xb, outer in ((x_outer0, x_outer1, r_flange),
                          (x_core0, x_core1, r_core),
                          (x_core1, x_inner1, r_flange)):
        ax.add_patch(Rectangle((xa, bore_flat), xb-xa, outer-bore_flat,
                               facecolor=gold if outer == r_core else dark_gold,
                               edgecolor="#76521e", lw=1.2, zorder=2))
        ax.add_patch(Rectangle((xa, -outer), xb-xa, outer-r_bore,
                               facecolor=gold if outer == r_core else dark_gold,
                               edgecolor="#76521e", lw=1.2, zorder=2))

    # Ø10 shaft with 9.5 mm across-flat on +Y; the reel bore leaves the
    # declared 0.15 mm nominal round and flat clearance.
    ax.add_patch(Rectangle((shaft_x0, -d/2), shaft_x1-shaft_x0, d/2+male_flat,
                           facecolor=steel, edgecolor="#56616a", lw=1.3, zorder=4))
    ax.plot([shaft_x0, shaft_x1], [male_flat, male_flat], color="#45515a", lw=1.2, zorder=5)
    ax.plot([shaft_x0, x_inner1], [bore_flat, bore_flat], color="#3f6f91", lw=1.2,
            linestyle="--", zorder=5)

    # Retainer plate overlaps the spool flange; an M4x10 proxy screws into
    # the blind axial tap at the shaft free end.
    plate_x0, plate_x1 = cfg["retainer_plate_x0_mm"], cfg["retainer_plate_x1_mm"]
    plate_r = cfg["retainer_plate_outer_diameter_mm"] / 2
    screw_r = cfg["retainer_screw_head_diameter_mm"] / 2
    shank_r = cfg["retainer_screw_shank_diameter_proxy_mm"] / 2
    head_x0 = plate_x0 - cfg["retainer_screw_head_height_mm"]
    ax.add_patch(Rectangle((plate_x0, 2.2), plate_x1-plate_x0, plate_r-2.2,
                           facecolor="#8295a2", edgecolor="#46545e", lw=1.1, zorder=6))
    ax.add_patch(Rectangle((plate_x0, -plate_r), plate_x1-plate_x0, plate_r-2.2,
                           facecolor="#8295a2", edgecolor="#46545e", lw=1.1, zorder=6))
    ax.add_patch(Rectangle((head_x0, -screw_r), cfg["retainer_screw_head_height_mm"],
                           2*screw_r, facecolor=dark, edgecolor="#22282d", lw=1.0, zorder=7))
    ax.add_patch(Rectangle((plate_x0, -shank_r),
                           cfg["retainer_plate_thickness_mm"] + cfg["retainer_screw_engagement_mm"],
                           2*shank_r, facecolor=dark, edgecolor="#22282d", lw=0.7, zorder=7))

    ax.annotate("D 孔 AF 9.8 / Ø10.3\n对 Ø10 轴平面留 0.15 mm",
                xy=(center_x, bore_flat), xytext=(center_x-.5, 10.8), ha="center", fontsize=8.5,
                arrowprops=dict(arrowstyle="->", color="#34434d", lw=1.0), color="#34434d")
    ax.annotate("Ø14 × 1.5 压片", xy=(plate_x0+.7, 6.4), xytext=(plate_x0-2.5, 10.8),
                fontsize=8.5, arrowprops=dict(arrowstyle="->", color="#34434d", lw=1.0),
                color="#34434d")
    ax.annotate("M4 × 10 螺钉代理\n轴内啮合 8.5 mm",
                xy=(plate_x1+2.0, 1.65), xytext=(-44.0, 10.8),
                fontsize=8.5, arrowprops=dict(arrowstyle="->", color="#34434d", lw=1.0),
                color="#34434d")
    ax.text(-66, 15.3, "线轮 D 孔与端面压片 | 轴向剖视", fontsize=14,
            color="#1f3040", weight="bold")
    ax.text(-66, 13.3, "单位 mm；间隙为打印拟合初值，先做配合试片；螺纹牙型未建模。",
            fontsize=8.5, color="#8d492e")
    ax.set_xlim(-67, -36)
    ax.set_ylim(-15.5, 16.5)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("输出轴 X / mm")
    ax.set_ylabel("径向 Y / mm")
    ax.grid(True, color="#bec9d1", alpha=.45, lw=.55)
    fig.tight_layout(pad=1.5)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def render_motor_output_seal_diagram(path: Path) -> None:
    """Show the oil seal running on the round OD of the sleeve over the D shaft."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    cfg = P["motor_output_shaft_seal"]
    seal_z0, seal_z1 = cfg["z_range_mm"]
    sleeve_r = cfg["sleeve_contact_diameter_mm"] / 2
    seal_r = cfg["outer_diameter_mm"] / 2
    fig = plt.figure(figsize=(13, 7), dpi=180)
    fig.patch.set_facecolor("#f4f7fa")
    ax = fig.add_axes([.09, .19, .40, .68])
    ax.set_facecolor("#f4f7fa")

    # Axisymmetric section proxy: show the D shaft inside the sleeve, with
    # the oil seal on the sleeve's smooth round outside surface.
    shaft_r = P["motor"]["output_shaft_diameter_mm"] / 2
    ax.add_patch(Rectangle((-83, -shaft_r), 14.3, 2*shaft_r,
                           facecolor="#697782", edgecolor="#3c474f", lw=1.0, zorder=2))
    ax.add_patch(Rectangle((-83, shaft_r), 23, sleeve_r-shaft_r,
                           facecolor="#9da7ae", edgecolor="#4d5961", lw=1.1, zorder=3))
    ax.add_patch(Rectangle((-83, -sleeve_r), 23, sleeve_r-shaft_r,
                           facecolor="#9da7ae", edgecolor="#4d5961", lw=1.1, zorder=3))
    ax.add_patch(Rectangle((seal_z0, sleeve_r), seal_z1-seal_z0, seal_r-sleeve_r,
                           facecolor="#c65348", edgecolor="#873d36", lw=1.1, zorder=4))
    ax.add_patch(Rectangle((seal_z0, -seal_r), seal_z1-seal_z0, seal_r-sleeve_r,
                           facecolor="#c65348", edgecolor="#873d36", lw=1.1, zorder=4))
    ax.add_patch(Rectangle((seal_z0, seal_r), seal_z1-seal_z0, 3.0,
                           facecolor="#4b8797", edgecolor="#275765", lw=0.9, zorder=1))
    ax.add_patch(Rectangle((seal_z0, -seal_r-3.0), seal_z1-seal_z0, 3.0,
                           facecolor="#4b8797", edgecolor="#275765", lw=0.9, zorder=1))
    ax.axhline(0, color="#34434d", lw=0.7, ls="--")
    ax.set_xlim(-84, -59)
    ax.set_ylim(-15, 15)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("电机输出轴轴向 Z / mm")
    ax.set_ylabel("径向距离 / mm")
    ax.grid(True, color="#bec9d1", alpha=.45, lw=.55)

    fig.text(.55, .88, "电机 D 轴套外圆轴封", fontsize=17, weight="bold", color="#1f3040")
    fig.text(.55, .82, "轴向剖面：D 形轴在套内传扭，油封不压在 D 平面上。",
             fontsize=10, color="#34434d")
    legend = [
        ("#697782", "M3508 D 型输出轴（轴套内孔配合）"),
        ("#9da7ae", "轴套：圆柱外径 Ø16 mm"),
        ("#c65348", "骨架油封包络：16 × 22 × 7 mm"),
        ("#4b8797", "油封座孔 Ø22 mm；由支承底盖定位"),
    ]
    y = .72
    for color, label in legend:
        fig.patches.append(Rectangle((.55, y-.017), .025, .025, transform=fig.transFigure,
                                     facecolor=color, edgecolor="#34434d", lw=.5))
        fig.text(.59, y, label, fontsize=10, va="center", color="#34434d")
        y -= .075
    fig.text(.55, .39, "轴封位置：轴向 Z = -80.5 至 -73.5 mm", fontsize=10, color="#34434d")
    fig.text(.55, .34, "此处显示油封工作面和座孔包络；具体油封型号尚未选定。",
             fontsize=9.5, color="#8d492e")
    fig.text(.55, .29, "唇形、过盈量、材料、压力方向及 5 m 水压性能需按实物规格验证。",
             fontsize=9.5, color="#8d492e")
    fig.text(.55, .21, "底盖与电机外壳的完整连接、电缆引出结构不在本单通道模型范围内。",
             fontsize=9.5, color="#536474")
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def interface_metrics(a: cq.Shape, b: cq.Shape) -> dict[str, float]:
    """Measure minimum solid-surface gap and overlap volume for two parts."""
    return {
        "minimum_surface_distance_mm": round(float(a.distance(b)), 6),
        "intersection_volume_mm3": round(float(a.intersect(b).Volume()), 9),
    }


def main() -> None:
    parts = build_parts()
    assembly = cq.Assembly(name="B32_v20_M3508_D_sleeve_dual_seal_drive_reel_review")
    for name, shape in parts.items():
        color, _ = COLORS.get(name, ((0.7, 0.7, 0.7), 1.0))
        assembly.add(shape, name=name, color=cq.Color(*color))
    step_path = HERE / "B32_v20_M3508_轴套线轮双轴封传动模组.step"
    assembly.export(str(step_path), exportType="STEP", unit="MM")
    render_vtk(parts, HERE / "B32_v20_M3508_轴套线轮双轴封效果图.png", section=False)
    render_vtk(parts, HERE / "B32_v20_线轮切线近景.png", reel_closeup=True)
    render_section_diagram(HERE / "B32_v20_D形线轮与压片剖视.png")
    render_motor_output_seal_diagram(HERE / "B32_v20_电机D轴套油封剖视.png")

    boxes = {name: [round(shape.BoundingBox().xlen, 2),
                    round(shape.BoundingBox().ylen, 2),
                    round(shape.BoundingBox().zlen, 2)]
             for name, shape in parts.items()}
    assembly_shape = cq.Compound.makeCompound(list(parts.values()))
    assembly_bb = assembly_shape.BoundingBox()
    assembly_bounds = {
        "min_xyz_mm": [round(assembly_bb.xmin, 3), round(assembly_bb.ymin, 3), round(assembly_bb.zmin, 3)],
        "max_xyz_mm": [round(assembly_bb.xmax, 3), round(assembly_bb.ymax, 3), round(assembly_bb.zmax, 3)],
        "size_xyz_mm": [round(assembly_bb.xlen, 3), round(assembly_bb.ylen, 3), round(assembly_bb.zlen, 3)],
    }
    tr, tz = tangent_point()
    layout = reel_winding_layout()
    reel_cfg = P["reel"]
    reel_x0 = layout["center_x_mm"] - reel_cfg["axial_width_mm"]/2
    reel_x1 = layout["center_x_mm"] + reel_cfg["axial_width_mm"]/2
    cable_d = reel_cfg["cable_diameter_proxy_mm"]
    turn_pitch = reel_cfg["axial_winding_pitch_mm"]
    outer_centerline_radius = layout["centerline_radii_mm"][-1]
    estimated_wound_length = sum(2*math.pi*r*reel_cfg["turns_per_layer"]
                                 for r in layout["centerline_radii_mm"])
    tangent_length = math.dist((tr, tz), (30.6, -8.8))
    tangent_dy, tangent_dz = tr-30.6, tz+8.8
    tangent_approach_deg = math.degrees(math.atan2(abs(tangent_dy), abs(tangent_dz)))
    projected_cable_halfwidth = cable_d/2*tangent_length/abs(tangent_dz)
    throat_radial_clearance = reel_cfg["guide_port_bore_diameter_mm"]/2-projected_cable_halfwidth
    mouth_center_offset = abs(tangent_dy)*reel_cfg["guide_port_chamfer_depth_mm"]/abs(tangent_dz)
    mouth_radial_clearance = reel_cfg["guide_port_mouth_diameter_mm"]/2-mouth_center_offset-projected_cable_halfwidth
    motor_cfg = P["motor"]["official_step"]
    gear_cfg = P["drive"]["stock_miter_gear"]
    motor_shape = parts["DJI_M3508_P19_official_STEP"]
    motor_bb = motor_shape.BoundingBox()
    motor_coupler_overlap = motor_shape.intersect(
        parts["D_bore_20mm_shaft_coupling"]).Volume()
    turn_shapes = [parts[f"wound_tendon_turn_{i}_proxy"]
                   for i in range(1, int(reel_cfg["turns_per_layer"]*reel_cfg["radial_layers"])+1)]
    turn_overlap_max = max((turn_shapes[i].intersect(turn_shapes[j]).Volume()
                            for i in range(len(turn_shapes))
                            for j in range(i+1, len(turn_shapes))), default=0.0)
    tendon_shape = parts["straight_tangent_tendon_proxy"]
    tendon_obstructions = {
        name: round(tendon_shape.intersect(parts[name]).Volume(), 8)
        for name in ("wet_reel_inner_flange_D_bore", "wet_reel_core_D_bore",
                     "wet_reel_outer_flange_D_bore", "chamfered_cable_guide_plate_proxy",
                     "fixed_labyrinth_envelope", "dry_wet_bulkhead_local_proxy",
                     "dry_side_radial_seal_support_sleeve_envelope")
    }
    gear_pair_envelope = interface_metrics(
        parts["KHK_MMSA1_5_20R_input_gear_catalog_envelope"],
        parts["KHK_MMSA1_5_20L_output_gear_catalog_envelope"])
    gear_screw_flat_contacts = {
        "input_M4_X_to_shaft_flat": interface_metrics(
            parts["KHK_input_M4_set_screw_X_proxy"],
            parts["extended_vertical_drive_shaft_two_M4_flats"]),
        "input_M4_Y_to_shaft_flat": interface_metrics(
            parts["KHK_input_M4_set_screw_Y_proxy"],
            parts["extended_vertical_drive_shaft_two_M4_flats"]),
        "output_M4_Y_to_shaft_flat": interface_metrics(
            parts["KHK_output_M4_set_screw_Y_proxy"],
            parts["tangential_output_shaft_D_flat_and_M4_tap_proxy"]),
        "output_M4_Z_to_shaft_flat": interface_metrics(
            parts["KHK_output_M4_set_screw_Z_proxy"],
            parts["tangential_output_shaft_D_flat_and_M4_tap_proxy"]),
    }
    reel_shaft_fit = interface_metrics(
        parts["tangential_output_shaft_D_flat_and_M4_tap_proxy"],
        parts["wet_reel_core_D_bore"])
    reel_retention_interfaces = {
        "plate_to_inner_flange": interface_metrics(
            parts["wet_reel_axial_retainer_plate"], parts["wet_reel_inner_flange_D_bore"]),
        "retainer_screw_to_plate": interface_metrics(
            parts["M4x10_wet_reel_retainer_screw_proxy"],
            parts["wet_reel_axial_retainer_plate"]),
        "retainer_screw_to_output_shaft_tap": interface_metrics(
            parts["M4x10_wet_reel_retainer_screw_proxy"],
            parts["tangential_output_shaft_D_flat_and_M4_tap_proxy"]),
    }
    seal_stack_interfaces = {
        "motor_D_bore_sleeve_to_16mm_rotary_seal": interface_metrics(
            parts["D_bore_20mm_shaft_coupling"],
            parts["motor_output_rotary_seal_16x22x7_envelope"]),
        "motor_rotary_seal_to_seat_in_drive_pod_bulkhead": interface_metrics(
            parts["motor_output_rotary_seal_16x22x7_envelope"],
            parts["transparent_right_angle_drive_pod_envelope"]),
        "input_gear_to_input_bearing": interface_metrics(
            parts["KHK_MMSA1_5_20R_input_gear_catalog_envelope"],
            parts["SKF_6000_2RS1_input_bearing_envelope"]),
        "input_shaft_to_input_bearing": interface_metrics(
            parts["extended_vertical_drive_shaft_two_M4_flats"],
            parts["SKF_6000_2RS1_input_bearing_envelope"]),
        "output_gear_to_output_bearing": interface_metrics(
            parts["KHK_MMSA1_5_20L_output_gear_catalog_envelope"],
            parts["SKF_3200_ATN9_output_bearing_envelope"]),
        "output_shaft_to_output_bearing": interface_metrics(
            parts["tangential_output_shaft_D_flat_and_M4_tap_proxy"],
            parts["SKF_3200_ATN9_output_bearing_envelope"]),
        "output_shaft_to_radial_seal": interface_metrics(
            parts["tangential_output_shaft_D_flat_and_M4_tap_proxy"],
            parts["SKF_10x22x7_rotary_seal_envelope"]),
        "output_shaft_to_labyrinth": interface_metrics(
            parts["tangential_output_shaft_D_flat_and_M4_tap_proxy"],
            parts["fixed_labyrinth_envelope"]),
        "seal_support_to_labyrinth": interface_metrics(
            parts["dry_side_radial_seal_support_sleeve_envelope"],
            parts["fixed_labyrinth_envelope"]),
        "seal_support_to_bulkhead": interface_metrics(
            parts["dry_side_radial_seal_support_sleeve_envelope"],
            parts["dry_wet_bulkhead_local_proxy"]),
        "bearing_support_to_bulkhead": interface_metrics(
            parts["dry_side_output_bearing_support_sleeve_envelope"],
            parts["dry_wet_bulkhead_local_proxy"]),
        "seal_support_to_bearing_support": interface_metrics(
            parts["dry_side_radial_seal_support_sleeve_envelope"],
            parts["dry_side_output_bearing_support_sleeve_envelope"]),
        "bearing_support_to_labyrinth": interface_metrics(
            parts["dry_side_output_bearing_support_sleeve_envelope"],
            parts["fixed_labyrinth_envelope"]),
        "labyrinth_to_bulkhead": interface_metrics(
            parts["fixed_labyrinth_envelope"], parts["dry_wet_bulkhead_local_proxy"]),
        "wet_reel_outer_flange_to_labyrinth": interface_metrics(
            parts["wet_reel_outer_flange_D_bore"], parts["fixed_labyrinth_envelope"]),
        "wet_reel_core_to_labyrinth": interface_metrics(
            parts["wet_reel_core_D_bore"], parts["fixed_labyrinth_envelope"]),
    }
    pod = parts["transparent_right_angle_drive_pod_envelope"]
    drive_pod_clearances = {
        name: interface_metrics(parts[name], pod)
        for name in ("DJI_M3508_P19_official_STEP", "D_bore_20mm_shaft_coupling",
                     "KHK_MMSA1_5_20R_input_gear_catalog_envelope",
                     "SKF_6000_2RS1_input_bearing_envelope",
                     "extended_vertical_drive_shaft_two_M4_flats",
                     "KHK_MMSA1_5_20L_output_gear_catalog_envelope",
                     "SKF_3200_ATN9_output_bearing_envelope",
                     "tangential_output_shaft_D_flat_and_M4_tap_proxy",
                     "wet_reel_outer_flange_D_bore", "chamfered_cable_guide_plate_proxy")
    }
    retainer_screw_to_tendon = interface_metrics(
        parts["M4x10_wet_reel_retainer_screw_proxy"], tendon_shape)
    native_invalid_parts = [name for name, shape in parts.items() if not shape.isValid()]
    report = {
        "status": P["status"],
        "model_scope": "one drive channel; adds a 16 mm seal on the cylindrical D-bore sleeve OD at the lower drive-pod bulkhead; retains the horizontal reel-shaft wet/dry seal and v19 reel geometry",
        "seal_architecture": {
            "motor_output_D_shaft": "the D motor shaft is fitted inside the 16 mm round-OD sleeve; the seal lip runs on the sleeve cylindrical surface",
            "horizontal_reel_output_shaft": "retained 10 x 22 x 7 mm seal as the primary wet/dry boundary for the exposed reel",
            "interpretation": "two seal locations; neither the CAD seal envelopes nor modeled carrier establish pressure rating or waterproof performance"
        },
        "official_motor_step": {
            "file": motor_cfg["file"],
            "sha256": hashlib.sha256(OFFICIAL_STEP.read_bytes()).hexdigest().upper(),
            "solids": len(motor_shape.Solids()),
            "valid": motor_shape.isValid(),
            "source_output_axis_xy_mm": motor_cfg["output_axis_xy_mm"],
            "source_output_tip_z_mm": motor_cfg["output_tip_z_mm"],
            "assembly_output_tip_z_mm": P["motor"]["assembly_output_tip_z_mm"],
            "d_flat_normal_angle_deg": motor_cfg["d_flat_normal_angle_deg"],
            "assembly_bounds_xyz_mm": [round(motor_bb.xlen, 3), round(motor_bb.ylen, 3),
                                       round(motor_bb.zlen, 3)]
        },
        "D_bore_fit": {
            "official_motor_across_flat_mm": P["motor"]["output_shaft_flat_dimension_mm"],
            "female_socket_across_flat_mm": P["coupling"]["female_D_across_flat_mm"],
            "flat_surface_clearance_mm": round(
                (P["coupling"]["female_D_across_flat_mm"]
                 - P["motor"]["output_shaft_flat_dimension_mm"]) / 2, 3),
            "round_surface_clearance_mm": P["coupling"]["female_D_radial_clearance_mm"],
            "motor_to_sleeve_intersection_volume_mm3": round(motor_coupler_overlap, 6)
        },
        "coupling": P["coupling"],
        "stock_gear_catalog_basis": {
            **P["drive"]["stock_miter_gear"],
            "L_dimension_interpretation": "M4 screw-hole center location from the gear back face, not screw length",
            "catalog_tooth_geometry_available_in_model": False
        },
        "tangent_point_radius_z_mm": [round(tr, 3), round(tz, 3)],
        "reel_center_x_and_guide_plane_mm": round(layout["center_x_mm"], 3),
        "tangent_cable_centerline_length_mm": round(tangent_length, 3),
        "physical_review": {
            "native_shape_validation": {
                "valid_part_count": len(parts)-len(native_invalid_parts),
                "part_count": len(parts),
                "invalid_parts": native_invalid_parts,
                "maximum_pairwise_winding_intersection_mm3": round(turn_overlap_max, 8),
                "straight_tendon_intersection_volumes_mm3": tendon_obstructions,
                "stock_gear_screw_to_shaft_flat": gear_screw_flat_contacts,
                "reel_retainer_screw_to_tendon": retainer_screw_to_tendon,
                "shaft_flat_geometry": {
                    "shaft_diameter_mm": gear_cfg["shaft_diameter_mm"],
                    "shaft_across_flat_mm": gear_cfg["shaft_flat_across_mm"],
                    "flat_depth_from_nominal_radius_mm": round(
                        gear_cfg["shaft_diameter_mm"]/2-gear_cfg["screw_contact_radial_offset_mm"], 3),
                    "input_flat_axial_span_z_mm": [-51.0, -40.5],
                    "output_gear_flat_axial_span_x_mm": [-28.0, -17.5],
                    "M4_screw_center_input_z_mm": round(-51.0+gear_cfg["screw_center_from_back_mm"], 3),
                    "M4_screw_center_output_x_mm": round(-28.0+gear_cfg["screw_center_from_back_mm"], 3),
                    "angular_layout": gear_cfg["screw_layout_status"]
                },
                "reel_D_bore_to_shaft_fit": reel_shaft_fit,
                "reel_axial_retention_interfaces": reel_retention_interfaces,
                "dry_wet_drive_stack_interfaces": seal_stack_interfaces,
                "motor_output_D_axis_seal": {
                    "sleeve_running_diameter_mm": P["motor_output_shaft_seal"]["sleeve_contact_diameter_mm"],
                    "seal_outer_diameter_mm": P["motor_output_shaft_seal"]["outer_diameter_mm"],
                    "seal_width_mm": P["motor_output_shaft_seal"]["width_mm"],
                    "axial_z_range_mm": P["motor_output_shaft_seal"]["z_range_mm"],
                    "running_surface": "round cylindrical OD of D-bore coupling sleeve; D flat remains inside sleeve",
                    "coupling_sleeve_to_lip_interface": interface_metrics(
                        parts["D_bore_20mm_shaft_coupling"],
                        parts["motor_output_rotary_seal_16x22x7_envelope"]),
                    "housing_to_seal_interface": interface_metrics(
                        parts["motor_output_rotary_seal_16x22x7_envelope"],
                        parts["transparent_right_angle_drive_pod_envelope"]),
                    "limitation": "seal is a dimension envelope; the lower motor pressure case, cable feedthrough, lip interference, material, and 5 m pressure test are not validated"
                },
                "drive_pod_clearances": drive_pod_clearances,
                "reel_retainer_stack": {
                    "plate_x_range_mm": [reel_cfg["retainer_plate_x0_mm"], reel_cfg["retainer_plate_x1_mm"]],
                    "reel_x_range_mm": [round(reel_x0, 3), round(reel_x1, 3)],
                    "retainer_tap_depth_mm": reel_cfg["retainer_tap_depth_mm"],
                    "nominal_screw_engagement_mm": reel_cfg["retainer_screw_engagement_mm"],
                    "blind_hole_bottom_clearance_mm": round(
                        reel_cfg["retainer_tap_depth_mm"]-reel_cfg["retainer_screw_engagement_mm"], 3),
                    "thread_form_modeled": False
                },
                "tooth_free_gear_pair_envelopes": {
                    **gear_pair_envelope,
                    "interpretation": "tooth-free envelopes only; overlap or gap does not verify real tooth mesh"
                },
                "input_M5_head_and_washer_to_input_gear": {
                    "head_to_gear": interface_metrics(
                        parts["M5x45_axial_retaining_screw_proxy"],
                        parts["KHK_MMSA1_5_20R_input_gear_catalog_envelope"]),
                    "washer_to_gear": interface_metrics(
                        parts["M5_spacer_washer_0_8mm"],
                        parts["KHK_MMSA1_5_20R_input_gear_catalog_envelope"]),
                    "interpretation": "central relief is inferred from a tooth-free envelope and needs inspection on the actual gear"
                }
            },
            "reel_winding": {
                "status": "non-overlapping cable-envelope arrangement; continuous helical lay is not modeled",
                "turns_per_layer": reel_cfg["turns_per_layer"],
                "radial_layers": reel_cfg["radial_layers"],
                "axial_turn_centers_mm": [round(x, 3) for x in layout["axial_centers_mm"]],
                "cable_centerline_radii_mm": [round(r, 3) for r in layout["centerline_radii_mm"]],
                "axial_pitch_mm": turn_pitch,
                "radial_pitch_mm": reel_cfg["radial_winding_pitch_mm"],
                "cable_diameter_mm": cable_d,
                "axial_envelope_gap_mm": round(turn_pitch-cable_d, 3),
                "radial_envelope_gap_mm": round(reel_cfg["radial_winding_pitch_mm"]-cable_d, 3),
                "axial_edge_margin_mm": round((layout["core_width_mm"]-(reel_cfg["turns_per_layer"]-1)*turn_pitch-cable_d)/2, 3),
                "outer_layer_surface_radius_mm": round(outer_centerline_radius+cable_d/2, 3),
                "flange_radial_clearance_mm": round(reel_cfg["flange_radius_mm"]-(outer_centerline_radius+cable_d/2), 3),
                "estimated_wound_length_mm": round(estimated_wound_length, 1),
                "winding_capacity_note": "geometric six-wrap estimate; verify against measured arm tendon stroke and reserve"
            },
            "guide_port": {
                "status": "cable envelope clears the modeled port; actual cable bend/wear is not validated",
                "approach_angle_from_port_axis_deg": round(tangent_approach_deg, 2),
                "throat_diameter_mm": reel_cfg["guide_port_bore_diameter_mm"],
                "mouth_diameter_mm": reel_cfg["guide_port_mouth_diameter_mm"],
                "lead_depth_mm": reel_cfg["guide_port_chamfer_depth_mm"],
                "cable_clearance_at_throat_mm": round(throat_radial_clearance, 3),
                "cable_clearance_at_mouth_mm": round(mouth_radial_clearance, 3),
                "cable_continues_through_plate_and_2mm_beyond": True
            }
        },
        "part_count": len(parts),
        "assembly_bounds_xyz_mm": assembly_bounds,
        "part_bounds_xyz_mm": boxes,
        "artifact_sha256": {
            "step": hashlib.sha256(step_path.read_bytes()).hexdigest().upper(),
            "generator": hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(),
            "parameters": hashlib.sha256((HERE / "parameters.json").read_bytes()).hexdigest().upper()
        },
        "exports": ["B32_v20_M3508_轴套线轮双轴封传动模组.step",
                    "B32_v20_M3508_轴套线轮双轴封效果图.png",
                    "B32_v20_线轮切线近景.png",
                    "B32_v20_D形线轮与压片剖视.png",
                    "B32_v20_电机D轴套油封剖视.png"]
    }
    (HERE / "装配审查.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",
                                          encoding="utf-8")
    print(json.dumps({"step": report["exports"][0], "effect": report["exports"][1],
                      "reel_closeup": report["exports"][2], "section": report["exports"][3], "part_count": len(parts),
                      "tangent_length_mm": report["tangent_cable_centerline_length_mm"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
