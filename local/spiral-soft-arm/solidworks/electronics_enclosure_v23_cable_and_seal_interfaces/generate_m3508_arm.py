"""B32 three-channel M3508 drive and common dry-chamber assembly candidate."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from collections.abc import Sequence
from types import ModuleType

import cadquery as cq


HERE = Path(__file__).resolve().parent
PARAMETERS_PATH = HERE / "parameters.json"
P = json.loads(PARAMETERS_PATH.read_text(encoding="utf-8"))
DRIVE_LAYOUT_AUDIT: list[dict[str, object]] = []
DRIVE_POSES: dict[int, dict[str, object]] = {}
CHAMBER_INTEGRATION_AUDIT: list[dict[str, object]] = []
OUTPUT_STEP = HERE / "B32_v23_M3508三路拉索与轴封接口总装.step"
OUTPUT_EXTERIOR_PREVIEW = HERE / "B32_v23_M3508三路总装预览.png"
OUTPUT_SECTION_PREVIEW = HERE / "B32_v23_轴封与拉索接口剖视.png"


def source_path(key: str) -> Path:
    """Resolve one source path relative to this versioned candidate."""
    return (HERE / P["sources"][key]).resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def source_manifest() -> dict[str, dict[str, str]]:
    """Capture the exact geometry/script sources consumed by v23."""
    keys = (
        "arm_generator", "arm_parameters", "canister_generator",
        "canister_parameters", "drive_generator",
        "drive_parameters", "sleeve_step", "official_motor_step",
    )
    manifest = {}
    for key in keys:
        path = source_path(key)
        if not path.is_file():
            raise FileNotFoundError(f"Missing v23 source {key}: {path}")
        manifest[key] = {"path": str(path), "sha256": sha256(path)}
    return manifest


def load_module(name: str, path: Path) -> ModuleType:
    """Load a versioned generator by absolute path without editing it."""
    if not path.is_file():
        raise FileNotFoundError(f"Cannot load {name}; source does not exist: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create an import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def ensure_legacy_mesh_import() -> None:
    """Allow BREP-only reuse when the optional v10 STL-audit package is absent."""
    try:
        __import__("trimesh")
        return
    except ModuleNotFoundError as exc:
        if exc.name != "trimesh":
            raise
    shim = ModuleType("trimesh")

    def unavailable_mesh_load(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(
            "The v23 BREP assembly does not run v10's optional STL mesh audit; "
            "install trimesh before invoking that legacy audit."
        )

    shim.load_mesh = unavailable_mesh_load  # type: ignore[attr-defined]
    sys.modules["trimesh"] = shim


def load_reference_generators() -> tuple[ModuleType, ModuleType]:
    """Return the unchanged v10 arm builder and v20 drive builder."""
    ensure_legacy_mesh_import()
    arm = load_module("b32_v10_arm_reference", source_path("arm_generator"))
    drive = load_module("b32_v20_drive_reference", source_path("drive_generator"))
    return arm, drive


def load_cnc_sleeve() -> cq.Shape:
    """Load the one-solid, millimetre CNC Rev A D-bore sleeve."""
    shape = cq.importers.importStep(str(source_path("sleeve_step"))).val()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("The CNC Rev A sleeve must import as one valid solid")
    bounds = shape.BoundingBox()
    expected = (16.0, 16.0, 20.0)
    actual = (bounds.xlen, bounds.ylen, bounds.zlen)
    if any(abs(got - want) > 0.02 for got, want in zip(actual, expected)):
        raise ValueError(f"Unexpected CNC sleeve envelope: {actual}; expected {expected}")
    return shape


def validate_layout_parameters() -> dict[str, float]:
    """Check the prescribed initial motor/reel station relationship."""
    d = P["drive_layout"]
    offset = float(d["motor_to_reel_axis_offset_mm"])
    motor_radius = float(d["motor_center_radius_mm"])
    recorded = float(d["reel_center_radius_mm"])
    calculated_motor_radius = math.hypot(recorded, offset)
    if abs(calculated_motor_radius - motor_radius) > 0.002:
        raise ValueError(
            f"Motor-center radius {motor_radius:.3f} does not match "
            f"reel station and axis offset {calculated_motor_radius:.3f}"
        )
    channels = d["module_channel_angles_deg"]
    holes = d["tendon_hole_angles_deg"]
    if len(channels) != 3 or len(holes) != 3:
        raise ValueError("v23 requires three motor modules and three tendon holes")
    return {
        "motor_center_radius_mm": calculated_motor_radius,
        "reel_center_radius_mm": recorded,
        "motor_to_reel_axis_offset_mm": offset,
    }


def rotate_xy(x: float, y: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    return (c*x - s*y, s*x + c*y)


def bounds_xyz_mm(shape: cq.Shape) -> list[float]:
    bb = shape.BoundingBox()
    return [round(bb.xmin, 4), round(bb.ymin, 4), round(bb.zmin, 4),
            round(bb.xmax, 4), round(bb.ymax, 4), round(bb.zmax, 4)]


def line_tangent_to_hole(
    reel_radius_mm: float,
    hole_radius_mm: float,
    reel_center_z_mm: float,
    hole_z_mm: float,
    cable_surface_radius_mm: float,
    side: str = "upper",
) -> tuple[tuple[float, float], float]:
    """Return a selected reel tangent point and its straight length."""
    vx = hole_radius_mm - reel_radius_mm
    vz = hole_z_mm - reel_center_z_mm
    d2 = vx*vx + vz*vz
    cable_r = cable_surface_radius_mm
    if d2 <= cable_r*cable_r:
        raise ValueError("The tendon hole lies inside the cable-winding envelope")
    perp_x, perp_z = -vz, vx
    base_x, base_z = (cable_r*cable_r/d2*vx, cable_r*cable_r/d2*vz)
    scale = cable_r * math.sqrt(d2-cable_r*cable_r) / d2
    points = (
        (reel_radius_mm + base_x + scale*perp_x,
         reel_center_z_mm + base_z + scale*perp_z),
        (reel_radius_mm + base_x - scale*perp_x,
         reel_center_z_mm + base_z - scale*perp_z),
    )
    if side not in {"upper", "lower"}:
        raise ValueError(f"Unknown reel tangent side: {side}")
    tangent = (max if side == "upper" else min)(points, key=lambda point: point[1])
    length = math.hypot(hole_radius_mm-tangent[0], hole_z_mm-tangent[1])
    return tangent, length


def make_root_transition(angle_deg: float, radius_mm: float,
                         incoming_unit: cq.Vector) -> cq.Shape:
    """Sweep a smooth inlet that joins the frozen tapered tendon passage."""
    cfg = P["root_tendon_transition"]
    theta = math.radians(angle_deg)
    radial = cq.Vector(math.cos(theta), math.sin(theta), 0)
    root_r = float(P["drive_layout"]["tendon_hole_radius_mm"])
    slope = (float(cfg["native_channel_tip_radius_mm"])
             -float(cfg["native_channel_base_radius_mm"])) / float(cfg["native_channel_length_mm"])
    join_z = float(cfg["join_z_mm"])
    p0 = radial*root_r
    p3 = radial*(float(cfg["native_channel_base_radius_mm"])+slope*join_z) + cq.Vector(0, 0, join_z)
    channel_unit = (radial*slope + cq.Vector(0, 0, 1)).normalized()
    p1 = p0 + incoming_unit.normalized()*float(cfg["start_handle_mm"])
    p2 = p3 - channel_unit*float(cfg["end_handle_mm"])
    path = cq.Edge.makeBezier([p0, p1, p2, p3])
    circle = cq.Wire.makeCircle(radius_mm, p0, incoming_unit)
    swept = cq.Solid.sweep(circle, [], path, makeSolid=True, isFrenet=True)
    if not swept.isValid() or len(swept.Solids()) != 1:
        raise ValueError(f"Invalid root tendon passage sweep at {angle_deg} degrees")
    return swept


def rework_plate_and_root_inlets(plate: cq.Shape, arm_step: cq.Shape) -> tuple[cq.Shape, cq.Shape]:
    """Replace vertical plate bores with coaxial sloping bores and root fairleads."""
    if not DRIVE_LAYOUT_AUDIT:
        build_three_drives()
    cfg = P["root_tendon_transition"]
    bore_r = float(cfg["plate_bore_diameter_mm"])/2
    mouth_r = float(cfg["plate_mouth_diameter_mm"])/2
    chamfer = float(cfg["plate_mouth_axial_depth_mm"])
    original_vertical_r = float(P["drive_layout"]["tendon_hole_radius_mm"])
    solids = list(arm_step.Solids())
    root_indices = [i for i, shape in enumerate(solids)
                    if abs(shape.BoundingBox().zmin) < 0.01 and shape.BoundingBox().zmax > 60]
    if len(root_indices) != 1:
        raise ValueError("Cannot identify the one frozen B32 root segment")
    root_index = root_indices[0]
    root = solids[root_index]
    for row in DRIVE_LAYOUT_AUDIT:
        theta = math.radians(float(row["hole_angle_deg"]))
        radial = cq.Vector(math.cos(theta), math.sin(theta), 0)
        top = radial*original_vertical_r
        # Close the old vertical hole and cut the new inclined bore through the
        # full 8 mm plate. The original 30.6 mm arm channel is kept above z=0.
        plug = cq.Solid.makeCylinder(mouth_r+0.3, 8.1,
                                    top+cq.Vector(0, 0, -8.1), cq.Vector(0, 0, 1))
        plate = plate.fuse(plug).clean()
        start = cq.Vector(*[float(v) for v in row["cable_tangent_point_xyz_mm"]])
        direction = (top-start).normalized()
        bottom = top + direction*(-8.0/direction.z)
        length = (top-bottom).Length
        # A shallow axis makes an elongated opening on each horizontal face.
        # Extend the cutter past both faces so its tilted circular section is
        # fully open rather than leaving a thin internal lip.
        overrun = max(2.0, (mouth_r+0.3)/direction.z)
        bore = cq.Solid.makeCylinder(bore_r, length+2*overrun,
                                     bottom-direction*overrun, direction)
        lower_mouth = cq.Solid.makeCone(mouth_r, bore_r, chamfer, bottom, direction)
        upper_mouth = cq.Solid.makeCone(bore_r, mouth_r, chamfer,
                                       top-direction*chamfer, direction)
        plate = plate.cut(bore).cut(lower_mouth).cut(upper_mouth).clean()
        passage_r = float(cfg["passage_diameter_mm"])/2
        curved_cut = make_root_transition(float(row["hole_angle_deg"]),
                                          passage_r, direction)
        inlet_lead = cq.Solid.makeCylinder(passage_r, 16.0,
                                           top-direction*10.0, direction)
        root = root.cut(curved_cut.fuse(inlet_lead)).clean()
    if not plate.isValid() or len(plate.Solids()) != 1 or not root.isValid() or len(root.Solids()) != 1:
        raise ValueError("Reworked plate or B32 root is not a single valid solid")
    solids[root_index] = root
    return plate, cq.Compound.makeCompound(solids)


def build_three_drives() -> dict[str, cq.Shape]:
    """Place three v20 channels; return named BREP parts in robot coordinates."""
    arm_builder, drive_builder = load_reference_generators()
    config = P["drive_layout"]
    v20 = drive_builder.P
    reel_layout = drive_builder.reel_winding_layout()
    reel_cfg = v20["reel"]
    gear_cfg = v20["drive"]["stock_miter_gear"]
    cable_surface_radius = (
        reel_layout["centerline_radii_mm"][-1] + reel_cfg["cable_diameter_proxy_mm"]/2
    )
    reel_radius = float(config["reel_center_radius_mm"])
    hole_radius = float(config["tendon_hole_radius_mm"])
    reel_z = float(config["reel_center_local_xyz_mm"][2])
    hole_z = float(config["tendon_hole_exit_z_mm"])
    motor_offset = float(config["motor_to_reel_axis_offset_mm"])
    motor_sleeve = load_cnc_sleeve().translate((0, 0, -81.0))
    base_parts = drive_builder.build_parts()

    # Rebuild the output shaft so its seal counterface is a complete Ø10 mm
    # cylinder.  Keep flats only where the wet reel and the output-gear screws
    # need torque transfer; the v20 blanket D-flat crossed the seal lip track.
    reel_x0 = float(reel_layout["center_x_mm"]) - float(reel_cfg["axial_width_mm"])/2
    reel_x1 = float(reel_layout["center_x_mm"]) + float(reel_cfg["axial_width_mm"])/2
    flat_offset = float(gear_cfg["shaft_flat_across_mm"])-float(gear_cfg["shaft_diameter_mm"])/2
    output_shaft = drive_builder.cyl_x(
        float(gear_cfg["shaft_diameter_mm"])/2,
        reel_x0,
        float(gear_cfg["output_bore_end_x_mm"]),
        0.0,
        -23.0,
    )
    output_shaft = output_shaft.cut(drive_builder.box(
        reel_x0-.1, reel_x1+.1, flat_offset, 7.0, -30.0, -16.0
    ))
    output_shaft = output_shaft.cut(drive_builder.box(
        -28.1, -17.4, -7.0, 7.0, -23.0+flat_offset, -16.0
    ))
    output_shaft = output_shaft.cut(drive_builder.cyl_x(
        float(reel_cfg["retainer_screw_shank_diameter_proxy_mm"])/2,
        reel_x0-.1,
        reel_x0+float(reel_cfg["retainer_tap_depth_mm"]),
        0.0,
        -23.0,
    ))
    base_parts["tangential_output_shaft_D_flat_and_M4_tap_proxy"] = output_shaft.clean()

    # Replace the interfaces changed after the measured fit audit.
    base_parts["D_bore_20mm_shaft_coupling"] = motor_sleeve
    base_parts.pop("motor_output_rotary_seal_16x22x7_envelope", None)
    # The M3508 and this sleeve coupling are both inside the common dry chamber.
    # The legacy 16x35 seal had no seat in v22 and is not part of the water boundary.
    base_parts.pop("motor_output_rotary_seal_16x35x7_envelope", None)
    # The v20/v22 floating seal carrier is superseded by the direct Ø22 seat
    # integrated into the shared chamber wall in this version.
    base_parts.pop("dry_side_radial_seal_support_sleeve_envelope", None)
    seal_x0, seal_x1 = (float(x) for x in config["output_seal_local_x_range_mm"])
    base_parts["SKF_10x22x7_rotary_seal_envelope"] = drive_builder.ring_x(
        11.0, 5.02, seal_x0, seal_x1, 0.0, -23.0
    )
    base_parts.pop("SKF_3200_ATN9_output_bearing_envelope", None)
    base_parts["SKF_61900_2RS1_output_bearing_A"] = drive_builder.ring_x(
        11.0, 5.02, -42.0, -36.0, 0, -23.0
    )
    base_parts["SKF_61900_2RS1_output_bearing_B"] = drive_builder.ring_x(
        11.0, 5.02, -34.0, -28.0, 0, -23.0
    )
    base_parts["dry_side_output_bearing_support_sleeve_envelope"] = drive_builder.ring_x(
        12.0, 11.0, -42.0, -28.0, 0, -23.0
    )
    base_parts["fixed_labyrinth_envelope"] = drive_builder.ring_x(
        10.0, 5.4, -51.15, -50.7, 0, -23.0
    )
    base_parts.pop("transparent_right_angle_drive_pod_envelope", None)
    # The output bulkhead is built as part of the shared wet-side reel tunnel.
    # Do not retain the old short v20 plate here; it stopped before the chamber.
    base_parts.pop("dry_wet_bulkhead_local_proxy", None)

    # The original one-channel guide plate and its short cable proxy are replaced
    # by the v10 top plate holes and the recalculated long radial tendon routes.
    base_parts.pop("chamfered_cable_guide_plate_proxy", None)
    base_parts.pop("straight_tangent_tendon_proxy", None)

    module_parts: dict[str, cq.Shape] = {}
    DRIVE_LAYOUT_AUDIT.clear()
    DRIVE_POSES.clear()
    for channel_angle, hole_angle in zip(
        config["module_channel_angles_deg"], config["tendon_hole_angles_deg"], strict=True
    ):
        if abs(((float(hole_angle)-float(channel_angle)) % 360.0) - 60.0) > 1e-8:
            raise ValueError("Each v10 tendon hole must remain 60 degrees from its module index")
        rotation = float(hole_angle) + float(config["module_rotation_offset_from_hole_deg"])
        radial, tangent = arm_builder.frame(float(hole_angle))
        reel_target = cq.Vector(
            reel_radius*radial.x,
            reel_radius*radial.y,
            reel_z,
        )
        reel_local = v20["drive"]["motor_to_reel_tangent_offset_mm"]
        local_reel_x = -float(reel_local)
        rotated_reel_xy = rotate_xy(local_reel_x, 0.0, rotation)
        translation = cq.Vector(
            reel_target.x - rotated_reel_xy[0],
            reel_target.y - rotated_reel_xy[1],
            0.0,
        )
        DRIVE_POSES[int(hole_angle)] = {
            "rotation_deg": rotation,
            "translation_xyz_mm": [translation.x, translation.y, translation.z],
        }

        def transformed(shape: cq.Shape) -> cq.Shape:
            return shape.rotate((0, 0, 0), (0, 0, 1), rotation).translate(translation)

        placed_parts: dict[str, cq.Shape] = {}
        for name, shape in base_parts.items():
            if not shape.isValid():
                raise ValueError(f"Invalid v20 component before placement: {name}")
            placed = transformed(shape)
            if not placed.isValid() or not placed.Solids():
                raise ValueError(f"Invalid transformed v23 component: {name}")
            placed_parts[name] = placed
            module_parts[f"drive_{int(hole_angle):03d}_{name}"] = placed

        tangent_point, cable_length = line_tangent_to_hole(
            reel_radius,
            hole_radius,
            reel_z,
            hole_z,
            float(cable_surface_radius),
            str(config["tendon_tangent_side"]),
        )
        cable_start = cq.Vector(
            tangent_point[0]*radial.x,
            tangent_point[0]*radial.y,
            tangent_point[1],
        )
        cable_end = cq.Vector(hole_radius*radial.x, hole_radius*radial.y, hole_z)
        cable_direction = cable_end - cable_start
        if abs(cable_direction.dot(tangent)) > 1e-7:
            raise ValueError(f"Cable path is not radial at hole {hole_angle} degrees")
        cable_radius = float(reel_cfg["cable_diameter_proxy_mm"]) / 2
        cable = cq.Solid.makeCylinder(
            cable_radius, cable_direction.Length, cable_start, cable_direction.normalized()
        )
        module_parts[f"drive_{int(hole_angle):03d}_straight_tendon_proxy"] = cable
        transition = make_root_transition(float(hole_angle), cable_radius,
                                          cable_direction.normalized())
        module_parts[f"drive_{int(hole_angle):03d}_root_transition_tendon_proxy"] = transition

        def compound_bounds(names: Sequence[str]) -> list[float]:
            return bounds_xyz_mm(cq.Compound.makeCompound([placed_parts[name] for name in names]))

        motor_center = translation
        reel_center_actual = translation + cq.Vector(*(
            (*rotate_xy(local_reel_x, 0.0, rotation), reel_z)
        ))
        actual_reel_r = math.hypot(reel_center_actual.x, reel_center_actual.y)
        motor_center_r = math.hypot(motor_center.x, motor_center.y)
        reel_axis_local = rotate_xy(1.0, 0.0, rotation)
        reel_axis = cq.Vector(reel_axis_local[0], reel_axis_local[1], 0.0)
        cable_unit = cable_direction.normalized()
        DRIVE_LAYOUT_AUDIT.append({
            "channel_angle_deg": float(channel_angle),
            "hole_angle_deg": float(hole_angle),
            "module_rotation_deg": rotation,
            "module_translation_xyz_mm": [round(translation.x, 6), round(translation.y, 6), 0.0],
            "motor_axis_center_xyz_mm": [round(motor_center.x, 4), round(motor_center.y, 4), -68.7],
            "motor_center_radius_mm": round(motor_center_r, 4),
            "reel_center_xyz_mm": [round(reel_center_actual.x, 4), round(reel_center_actual.y, 4), reel_z],
            "reel_center_radius_mm": round(actual_reel_r, 4),
            "reel_axis_unit": [round(reel_axis.x, 8), round(reel_axis.y, 8), 0.0],
            "cable_tangent_point_xyz_mm": [round(cable_start.x, 4), round(cable_start.y, 4), round(cable_start.z, 4)],
            "tendon_hole_center_xyz_mm": [round(cable_end.x, 4), round(cable_end.y, 4), round(cable_end.z, 4)],
            "plate_underside_entry_radius_mm": round(
                tangent_point[0] + (-8.0-tangent_point[1])
                * (hole_radius-tangent_point[0])/(hole_z-tangent_point[1]), 4
            ),
            "cable_tangent_local_xyz_mm": [round(v, 5) for v in rotate_xy(
                cable_start.x-translation.x, cable_start.y-translation.y, -rotation
            )] + [round(cable_start.z, 5)],
            "tendon_hole_local_xyz_mm": [round(v, 5) for v in rotate_xy(
                cable_end.x-translation.x, cable_end.y-translation.y, -rotation
            )] + [round(cable_end.z, 5)],
            "cable_to_hole_length_mm": round(cable_length, 4),
            "reel_axis_cable_dot": round(abs(reel_axis.dot(cable_unit)), 8),
            "cable_plan_radial_cross": round(abs(
                radial.x*(cable_unit.y) - radial.y*(cable_unit.x)
            ), 8),
            "component_bounds_xyz_minmax_mm": {
                "motor": bounds_xyz_mm(placed_parts["DJI_M3508_P19_official_STEP"]),
                "sleeve": bounds_xyz_mm(placed_parts["D_bore_20mm_shaft_coupling"]),
                "reel": compound_bounds((
                    "wet_reel_inner_flange_D_bore", "wet_reel_core_D_bore",
                    "wet_reel_outer_flange_D_bore", "wet_reel_axial_retainer_plate",
                    "M4x10_wet_reel_retainer_screw_proxy",
                )),
                "shafts": compound_bounds((
                    "extended_vertical_drive_shaft_two_M4_flats",
                    "tangential_output_shaft_D_flat_and_M4_tap_proxy",
                )),
                "output_seal": bounds_xyz_mm(placed_parts["SKF_10x22x7_rotary_seal_envelope"]),
                "input_gear": bounds_xyz_mm(placed_parts["KHK_MMSA1_5_20R_input_gear_catalog_envelope"]),
                "output_gear": bounds_xyz_mm(placed_parts["KHK_MMSA1_5_20L_output_gear_catalog_envelope"]),
                "tendon": bounds_xyz_mm(cable),
            },
            "component_count_including_tendon": len(base_parts) + 1,
        })
    return module_parts


def build_v10_reference_components() -> dict[str, cq.Shape]:
    """Rebuild the unchanged B32 arm/top/electronics references without old drives."""
    arm, _drive = load_reference_generators()
    motor_config = arm.v5.motor_module.load_config()
    drive = arm.CFG["drive_layout"]
    motor_config["layout"]["motor_center_radius_mm"] = 98.5
    motor_config["layout"]["spool_center_offset_from_motor_center_mm"] = 52.0
    motor_config["motor_saddles"]["foot_radial_offset_mm"] = 25.1
    motor_config["plate"]["diameter_mm"] = 2*arm.CFG["hex_plate"]["circumradius_mm"]
    motor_config["plate"]["fixture_hole_radius_mm"] = arm.v5.CFG[
        "base_plate_fixture_radius_mm"
    ]
    arm.v5.CFG = {
        **arm.v5.CFG,
        "motor_center_radius_mm": drive["motor_center_radius_mm"],
        "base_plate_diameter_mm": motor_config["plate"]["diameter_mm"],
    }
    arm.v5.tendon_points = arm.straight_tendon_points
    arm.v5.minimum_bend_radius = lambda _points: 1e9
    source_mount = arm.v5.motor_module.build_motor_mount(motor_config)
    mount = arm.make_horizontal_mount(motor_config, source_mount)
    plate, _tabs = arm.make_plate(mount)
    arm_step = cq.importers.importStep(str(arm.OUT_ARM)).val()
    if not arm_step.isValid() or len(arm_step.Solids()) != 5:
        raise ValueError("The frozen v10 arm STEP must contain three arm segments and two pins")
    plate, arm_step = rework_plate_and_root_inlets(plate, arm_step)
    plate, guard = arm.make_root_guard(plate)
    canister, canister_lid, tether_gland = arm.make_shell_with_clear_tendon_radials()
    fairing = arm.make_fairing()
    electrical_parts = {**arm.v5.make_battery(), **arm.v5.make_electronics()}
    wire_parts = arm.v5.make_wire_proxies()
    rerouted_battery_leads = {}
    wire_parts.pop("battery_to_BMS_1")
    wire_parts.pop("battery_to_BMS_2")
    rerouted_battery_leads["v23_battery_to_BMS_two_core_harness"] = arm.v5.wire(
        [
            (0.0, -31.0, -101.0), (0.0, -43.0, -108.0),
            (-43.0, -43.0, -114.0), (-43.0, -43.0, -178.0),
            (-43.0, -43.0, -214.0), (-34.0, -26.0, -214.0),
            (-27.5, -18.0, -217.0),
        ],
        1.2,
    )

    components: dict[str, cq.Shape] = {
        "B32_v10_arm_sections_and_dovetails": arm_step,
        "v10_hexagonal_top_plate_with_tabs": plate,
        "v10_central_electronics_canister": canister,
        "v10_central_electronics_canister_lid": canister_lid,
        "v10_shore_tether_gland_proxy": tether_gland,
    }
    components.update({f"v10_{name}": shape for name, shape in guard.items()})
    components.update({
        f"v10_{name}": shape for name, shape in fairing.items()
        if name.startswith("upper_panel_")
    })
    components.update({f"v10_{name}": shape for name, shape in electrical_parts.items()})
    components.update({
        f"v10_{name}": shape for name, shape in wire_parts.items()
        if not name.startswith("motor_")
    })
    components.update(rerouted_battery_leads)
    for name, shape in components.items():
        if not shape.isValid() or not shape.Solids():
            raise ValueError(f"Invalid frozen v10 reference component: {name}")
    return components


def _hex_wire(radius: float, z: float, rotation_deg: float = 0.0) -> cq.Wire:
    vertices = [
        cq.Vector(
            radius*math.cos(math.radians(-30.0 + 60.0*i + rotation_deg)),
            radius*math.sin(math.radians(-30.0 + 60.0*i + rotation_deg)),
            z,
        )
        for i in range(6)
    ]
    return cq.Wire.makePolygon(vertices + [vertices[0]])


def _hex_solid(radius: float, z0: float, z1: float,
               rotation_deg: float = 0.0) -> cq.Shape:
    return cq.Solid.makeLoft(
        [_hex_wire(radius, z0, rotation_deg), _hex_wire(radius, z1, rotation_deg)],
        ruled=True,
    )


def _hex_loft(profiles: Sequence[Sequence[float]],
              radial_offset_mm: float = 0.0) -> cq.Shape:
    wires = [
        _hex_wire(float(radius)-radial_offset_mm, float(z), 0.0)
        for z, radius in sorted(profiles, key=lambda row: float(row[0]))
    ]
    return cq.Solid.makeLoft(wires, ruled=True)


def build_shared_drive_chamber(
    drives: dict[str, cq.Shape], parameters: dict[str, object] | None = None,
) -> dict[str, cq.Shape]:
    """Build the faceted shared dry shell and isolated wet reel/tendon paths.

    The cable/reel lanes are hollow box tunnels aligned with the v10 plate holes.
    Each lane opens to the water-facing outer fairing window and terminates at a
    cable-guide proxy. Each output shaft crosses a thickened integrated boss
    with a nominal finish-machined radial-seal seat; this is not a pressure
    rating or proof that the seal is suitable for water service.
    """
    cfg = parameters or P["shared_dry_chamber"]
    outer_profiles = cfg["outer_profile_z_radius_mm"]
    wall_t = float(cfg["wall_thickness_mm"])
    inner_delta = wall_t / math.cos(math.radians(30.0))
    outer = _hex_loft(outer_profiles)
    inner = _hex_loft(outer_profiles, inner_delta)
    chamber_shell = outer.cut(inner)
    dry_volume = inner

    arm_builder, drive_builder = load_reference_generators()
    tunnel_cfg = cfg["wet_reel_tunnel_local_mm"]
    x0, x1 = (float(v) for v in tunnel_cfg["outer_x_range"])
    y0, y1 = (float(v) for v in tunnel_cfg["outer_y_range"])
    z0, z1 = (float(v) for v in tunnel_cfg["outer_z_range"])
    ix0, ix1 = (float(v) for v in tunnel_cfg["inner_x_range"])
    iy0, iy1 = (float(v) for v in tunnel_cfg["inner_y_range"])
    iz0, iz1 = (float(v) for v in tunnel_cfg["inner_z_range"])
    tunnel_outer_local = drive_builder.box(x0, x1, y0, y1, z0, z1)
    tunnel_inner_local = drive_builder.box(ix0, ix1, iy0, iy1, iz0, iz1)
    shaft_center_y = float(tunnel_cfg["output_shaft_center_y_mm"])
    shaft_center_z = float(tunnel_cfg["output_shaft_center_z_mm"])
    gland_cfg = cfg["output_seal_gland"]
    gland_start = float(gland_cfg["seat_start_x_mm"])
    gland_depth = float(gland_cfg["seat_depth_mm"])
    gland_end = gland_start+gland_depth
    shoulder_x = float(gland_cfg["seat_shoulder_x_mm"])
    boss_x0, boss_x1 = (float(v) for v in gland_cfg["boss_axial_range_mm"])
    boss_r = float(gland_cfg["boss_outer_diameter_mm"])/2
    seal_r = float(gland_cfg["housing_bore_diameter_mm"])/2
    shaft_clearance_r = float(gland_cfg["shaft_clearance_bore_diameter_mm"])/2
    chamfer_r = float(gland_cfg["entry_chamfer_radial_mm"])
    chamfer_x = float(gland_cfg["entry_chamfer_axial_mm"])
    if abs(gland_end-shoulder_x) > 1e-6 or abs(boss_x1-shoulder_x) > 1e-6:
        raise ValueError("The radial-seal seat depth, shoulder, and boss end must agree")
    if gland_depth < float(gland_cfg["seal_width_mm"])+0.3-1e-8:
        raise ValueError("The metal-inserted seal seat must be at least width + 0.3 mm")
    seal_boss_local = drive_builder.cyl_x(
        boss_r, boss_x0, boss_x1, shaft_center_y, shaft_center_z
    )
    shaft_cut_local = drive_builder.cyl_x(
        shaft_clearance_r, boss_x0-0.2, boss_x1+0.2, shaft_center_y, shaft_center_z
    )
    gland_cut_local = drive_builder.cyl_x(
        seal_r, gland_start, gland_end, shaft_center_y, shaft_center_z
    )
    chamfer_cut_local = cq.Solid.makeCone(
        seal_r+chamfer_r,
        seal_r,
        chamfer_x,
        cq.Vector(gland_start-chamfer_x, shaft_center_y, shaft_center_z),
        cq.Vector(1, 0, 0),
    )
    cable_tube_cfg = cfg["tendon_pass_through"]
    cable_outer_r = float(cable_tube_cfg["outer_diameter_mm"]) / 2
    cable_inner_r = float(cable_tube_cfg["inner_diameter_mm"]) / 2
    cable_cap_hole_r = float(cable_tube_cfg["bulkhead_hole_diameter_mm"]) / 2

    chamber_parts: dict[str, cq.Shape] = {}
    wet_clearances: list[cq.Shape] = []
    pose_by_angle = DRIVE_POSES
    if len(pose_by_angle) != 3 or len(DRIVE_LAYOUT_AUDIT) != 3:
        raise RuntimeError("Build the three drive placements before the shared chamber")

    for row in DRIVE_LAYOUT_AUDIT:
        angle = int(round(float(row["hole_angle_deg"])))
        pose = pose_by_angle[angle]
        rotation = float(pose["rotation_deg"])
        tx, ty, tz = (float(v) for v in pose["translation_xyz_mm"])

        def placed(shape: cq.Shape) -> cq.Shape:
            return shape.rotate((0, 0, 0), (0, 0, 1), rotation).translate((tx, ty, tz))

        tunnel_outer = placed(tunnel_outer_local)
        tunnel_inner = placed(tunnel_inner_local)
        seal_boss = placed(seal_boss_local)
        shaft_cut = placed(shaft_cut_local)
        gland_cut = placed(gland_cut_local)
        chamfer_cut = placed(chamfer_cut_local)
        cable_start = cq.Vector(*[float(v) for v in row["cable_tangent_point_xyz_mm"]])
        cable_end = cq.Vector(*[float(v) for v in row["tendon_hole_center_xyz_mm"]])
        cable_direction = cable_end-cable_start
        cable_unit = cable_direction.normalized()
        liner_start = cable_start + cable_unit*float(cable_tube_cfg[
            "liner_start_offset_after_tangent_mm"
        ])
        liner_length = (cable_end-liner_start).Length - float(cable_tube_cfg[
            "liner_end_clearance_before_root_mm"
        ])
        if (liner_length <= 0.0
                or (liner_start-cable_start).Length+liner_length >= cable_direction.Length):
            raise ValueError(f"Invalid liner stop position at channel {angle}")
        cable_outer = cq.Solid.makeCylinder(cable_outer_r, liner_length,
                                             liner_start, cable_unit)
        cable_inner = cq.Solid.makeCylinder(cable_inner_r, liner_length+0.2,
                                             liner_start-cable_unit*0.1, cable_unit)
        cable_tube = cable_outer.cut(cable_inner).clean()

        local_start = [float(v) for v in row["cable_tangent_local_xyz_mm"]]
        local_end = [float(v) for v in row["tendon_hole_local_xyz_mm"]]
        inner_end_y = float(tunnel_cfg["inner_end_y_mm"])
        dy = local_end[1]-local_start[1]
        if abs(dy) < 1e-8:
            raise ValueError(f"Cable path {angle} does not cross the tunnel end plane")
        t_cap = (inner_end_y-local_start[1])/dy
        cap_z = local_start[2] + t_cap*(local_end[2]-local_start[2])
        cap_center_local = cq.Vector(float(tunnel_cfg["cable_tunnel_local_x_mm"]),
                                     inner_end_y, cap_z)
        cap_axis_local = cq.Vector(local_end[0]-local_start[0], dy,
                                   local_end[2]-local_start[2]).normalized()
        cap_hole_local = cq.Solid.makeCylinder(
            cable_cap_hole_r, 24.0, cap_center_local-cap_axis_local*12.0,
            cap_axis_local,
        )
        cap_hole = placed(cap_hole_local)
        chamber_shell = chamber_shell.fuse(tunnel_outer).fuse(seal_boss).clean()
        chamber_shell = (chamber_shell.cut(tunnel_inner).cut(shaft_cut)
                         .cut(gland_cut).cut(chamfer_cut).cut(cap_hole).clean())

        pocket = cq.Compound.makeCompound([tunnel_inner, cable_outer])
        dry_volume = dry_volume.cut(tunnel_inner).cut(cable_outer).clean()
        wet_clearances.append(pocket)
        chamber_parts[f"wet_reel_clearance_volume_{angle:03d}"] = pocket
        chamber_parts[f"tendon_pass_through_{angle:03d}"] = cable_tube

    # The lower annular cover closes the shared drive volume around the existing
    # 136 mm electronics canister; the thin annular gasket is a dimensional proxy.
    cover_cfg = cfg["service_cover"]
    cover_r = float(cover_cfg["outer_hex_circumradius_mm"])
    cover_z0, cover_z1 = (float(v) for v in cover_cfg["z_range_mm"])
    cover_hole_r = float(cover_cfg["central_clearance_diameter_mm"])/2
    cover = _hex_solid(cover_r, cover_z0, cover_z1)
    cover = cover.cut(drive_builder.cyl_z(cover_hole_r, cover_z0-0.1, cover_z1+0.1))
    bolt_r = float(cover_cfg["fastener_pattern_radius_mm"])
    bolt_hole_r = float(cover_cfg["fastener_clearance_diameter_mm"])/2
    bolt_angles = [float(v) for v in cover_cfg["fastener_angles_deg"]]
    for bolt_angle in bolt_angles:
        bx, by = rotate_xy(bolt_r, 0.0, bolt_angle)
        bore = drive_builder.cyl_z(bolt_hole_r, cover_z0-0.1, cover_z1+0.1, bx, by)
        cover = cover.cut(bore)
        chamber_shell = chamber_shell.cut(
            drive_builder.cyl_z(bolt_hole_r, cover_z1-0.2, cover_z1+0.2, bx, by)
        )
    cover = cover.clean()
    gasket = drive_builder.ring_z(
        float(cover_cfg["canister_gasket_outer_diameter_mm"])/2,
        float(cover_cfg["canister_gasket_inner_diameter_mm"])/2,
        cover_z1-1.0,
        cover_z1,
    )
    wire_port_cfg = cfg["electronics_motor_wire_pass_through"]
    wire_outer_r = float(wire_port_cfg["outer_diameter_mm"])/2
    wire_inner_r = float(wire_port_cfg["inner_diameter_mm"])/2
    wire_length = float(wire_port_cfg["length_mm"])
    wire_start_r = float(wire_port_cfg["radial_start_mm"])
    wire_z = float(wire_port_cfg["center_z_mm"])
    for port_angle in wire_port_cfg["angles_deg"]:
        angle = int(round(float(port_angle)))
        radial, _tangent = arm_builder.frame(float(port_angle))
        direction = radial.normalized()
        start = radial*wire_start_r + cq.Vector(0, 0, wire_z)
        outer_tube = cq.Solid.makeCylinder(wire_outer_r, wire_length, start, direction)
        inner_tube = cq.Solid.makeCylinder(wire_inner_r, wire_length+0.2,
                                           start-direction*0.1, direction)
        chamber_parts[f"electronics_motor_wire_pass_through_{angle:03d}"] = (
            outer_tube.cut(inner_tube).clean()
        )

    chamber_parts.update({
        "common_dry_chamber_shell": chamber_shell,
        "removable_bottom_service_cover": cover,
        "bottom_cover_gasket_proxy": gasket,
        "dry_cavity_reference": dry_volume,
    })
    for shape_name, shape in chamber_parts.items():
        if not shape.isValid() or not shape.Solids():
            raise ValueError(f"Invalid shared-chamber geometry: {shape_name}")
    return chamber_parts


def build_v23_assembly_components() -> dict[str, cq.Shape]:
    """Combine the frozen v10 structure with physical v23 drives and shell parts."""
    drives = build_three_drives()
    references = build_v10_reference_components()
    chamber = build_shared_drive_chamber(drives, P["shared_dry_chamber"])
    top_plate = references.pop("v10_hexagonal_top_plate_with_tabs")
    chamber_shell = chamber["common_dry_chamber_shell"]
    integral_top_and_chamber = top_plate.fuse(chamber_shell).clean()
    if not integral_top_and_chamber.isValid() or not integral_top_and_chamber.Solids():
        raise ValueError("The integral v10 top plate and v23 chamber fusion is invalid")
    CHAMBER_INTEGRATION_AUDIT.clear()
    interface_z = float(P["shared_dry_chamber"]["top_interface"]["interface_z_mm"])
    gear_clearance = float(P["shared_dry_chamber"].get(
        "gear_to_top_plate_clearance_mm", 0.35
    ))
    for angle in (60, 180, 300):
        gear = drives[f"drive_{angle:03d}_KHK_MMSA1_5_20L_output_gear_catalog_envelope"]
        interference = gear.intersect(top_plate)
        intersection_volume = float(interference.Volume())
        if intersection_volume > 0.02:
            box = interference.BoundingBox()
            pocket_top = gear.BoundingBox().zmax + gear_clearance
            pocket = cq.Solid.makeBox(
                box.xlen+2*gear_clearance,
                box.ylen+2*gear_clearance,
                pocket_top-interface_z+0.1,
                cq.Vector(box.xmin-gear_clearance,
                          box.ymin-gear_clearance,
                          interface_z-0.1),
            )
            integral_top_and_chamber = integral_top_and_chamber.cut(pocket).clean()
        residual = float(gear.intersect(integral_top_and_chamber).Volume())
        CHAMBER_INTEGRATION_AUDIT.append({
            "channel_hole_angle_deg": angle,
            "gear_plate_intersection_before_relief_mm3": round(intersection_volume, 5),
            "clearance_pocket_xy_mm": (
                [round(box.xmin-gear_clearance, 4), round(box.ymin-gear_clearance, 4),
                 round(box.xmax+gear_clearance, 4), round(box.ymax+gear_clearance, 4)]
                if intersection_volume > 0.02 else None
            ),
            "clearance_pocket_top_z_mm": round(pocket_top, 4)
            if intersection_volume > 0.02 else None,
            "gear_remaining_intersection_with_integrated_plate_mm3": round(residual, 5),
        })
    if not integral_top_and_chamber.isValid() or not integral_top_and_chamber.Solids():
        raise ValueError("The integrated drive chamber failed after gear relief cuts")
    physical_chamber = {
        name: shape for name, shape in chamber.items()
        if not name.startswith("wet_reel_clearance_volume_")
        and name not in {"dry_cavity_reference", "common_dry_chamber_shell"}
    }
    physical_chamber["v23_integral_top_plate_and_drive_chamber"] = integral_top_and_chamber
    overlap_names = set(references) & (set(drives) | set(physical_chamber))
    if overlap_names:
        raise ValueError(f"Duplicate v23 assembly component names: {sorted(overlap_names)}")
    components = {**references, **drives, **physical_chamber}
    for name, shape in components.items():
        if not shape.isValid() or not shape.Solids():
            raise ValueError(f"Invalid v23 assembly component: {name}")
    return components


def _assembly_color(name: str) -> cq.Color:
    if "B32_v10_arm" in name:
        return cq.Color(0.78, 0.40, 0.24, 1.0)
    if "hexagonal_top_plate" in name:
        return cq.Color(0.22, 0.42, 0.58, 0.95)
    if "root_guard" in name:
        return cq.Color(0.48, 0.55, 0.61, 0.8)
    if "upper_panel" in name:
        return cq.Color(0.68, 0.74, 0.79, 0.28)
    if "common_dry_chamber_shell" in name or "integral_top_plate_and_drive_chamber" in name:
        return cq.Color(0.43, 0.63, 0.68, 0.30)
    if "service_cover" in name:
        return cq.Color(0.30, 0.48, 0.55, 0.75)
    if "gasket" in name or "pass_through" in name:
        return cq.Color(0.12, 0.63, 0.57, 0.9)
    if "DJI_M3508" in name:
        return cq.Color(0.12, 0.20, 0.29, 1.0)
    if "wet_reel" in name or "wound_tendon" in name or "retainer_screw" in name:
        return cq.Color(0.88, 0.61, 0.18, 1.0)
    if "gear" in name or "shaft" in name or "bearing" in name:
        return cq.Color(0.72, 0.73, 0.75, 0.95)
    if "seal" in name or "labyrinth" in name:
        return cq.Color(0.78, 0.20, 0.18, 0.95)
    if "tendon" in name:
        return cq.Color(0.87, 0.31, 0.14, 1.0)
    if "canister" in name or "battery" in name or "electronics" in name:
        return cq.Color(0.27, 0.55, 0.59, 0.35)
    if name.startswith("v10_"):
        return cq.Color(0.56, 0.62, 0.67, 0.95)
    return cq.Color(0.58, 0.63, 0.67, 0.85)


def render_v23_preview(components: dict[str, cq.Shape], path: Path,
                       section: bool = False) -> None:
    """Render a review image from the exact v23 BREP components."""
    import vtk
    from PIL import Image, ImageDraw, ImageFont

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(1600, 1120)
    window.SetMultiSamples(0)
    scene = vtk.vtkRenderer()
    scene.SetBackground(0.94, 0.965, 0.98)
    scene.SetUseDepthPeeling(1)
    window.AddRenderer(scene)

    for name, source_shape in components.items():
        shape = source_shape
        if section:
            bb = shape.BoundingBox()
            if name == "B32_v10_arm_sections_and_dovetails":
                selected_arm_parts = [
                    part for part in shape.Solids()
                    if part.BoundingBox().zmin < 60.0
                    and part.BoundingBox().zmax < 110.0
                ]
                if not selected_arm_parts:
                    continue
                shape = cq.Compound.makeCompound(selected_arm_parts)
            elif bb.zmin > 80.0 or bb.zmax < -245.0:
                continue
        vertices, faces = shape.tessellate(0.8 if section else 1.2, 0.18)
        if len(vertices) < 3 or not faces:
            continue
        points = vtk.vtkPoints()
        points.SetNumberOfPoints(len(vertices))
        for index, point in enumerate(vertices):
            points.SetPoint(index, point.x, point.y, point.z)
        polys = vtk.vtkCellArray()
        for face in faces:
            polys.InsertNextCell(3)
            for node in face:
                polys.InsertCellPoint(int(node))
        poly = vtk.vtkPolyData()
        poly.SetPoints(points)
        poly.SetPolys(polys)
        if section:
            plane = vtk.vtkPlane()
            plane.SetOrigin(0.0, 0.0, 0.0)
            plane.SetNormal(0.0, 1.0, 0.0)
            clip = vtk.vtkClipPolyData()
            clip.SetInputData(poly)
            clip.SetClipFunction(plane)
            clip.SetValue(0.0)
            clip.InsideOutOff()
            clip.Update()
            poly = clip.GetOutput()
            if poly.GetNumberOfPoints() < 3:
                continue
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        color = _assembly_color(name)
        red, green, blue, alpha = color.toTuple()
        prop = actor.GetProperty()
        prop.SetColor(red, green, blue)
        prop.SetOpacity(alpha)
        prop.SetSpecular(0.24)
        prop.SetSpecularPower(24)
        prop.SetInterpolationToPhong()
        scene.AddActor(actor)

    camera = scene.GetActiveCamera()
    camera.ParallelProjectionOn()
    if section:
        camera.SetFocalPoint(0.0, 0.0, -100.0)
        camera.SetPosition(430.0, -680.0, 35.0)
        camera.SetViewUp(0.0, 0.0, 1.0)
        camera.SetParallelScale(265.0)
    else:
        camera.SetFocalPoint(0.0, 0.0, 155.0)
        camera.SetPosition(480.0, -760.0, 440.0)
        camera.SetViewUp(0.0, 0.0, 1.0)
        camera.SetParallelScale(455.0)
    scene.ResetCameraClippingRange()
    window.Render()
    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.SetInputBufferTypeToRGB()
    capture.ReadFrontBufferOff()
    capture.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(path))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()
    window.Finalize()

    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    font = ImageFont.truetype(str(font_path), 28) if font_path.is_file() else ImageFont.load_default()
    title = "B32 v23 驱动与干仓剖视（Y=0）" if section else "B32 v23 三路 M3508 共用干仓总装"
    subtitle = "几何审查图 · 不代表打印、密封或 5 m 水压验证"
    draw.rounded_rectangle((28, 24, 760, 102), radius=14, fill=(255, 255, 255))
    draw.text((48, 30), title, font=font, fill=(28, 44, 58))
    draw.text((50, 68), subtitle, font=ImageFont.truetype(str(font_path), 17)
              if font_path.is_file() else ImageFont.load_default(),
              fill=(74, 91, 104))
    image.save(path)


def export_v23_assembly() -> dict[str, object]:
    """Export the named v23 assembly and its exterior/section review images."""
    components = build_v23_assembly_components()
    assembly = cq.Assembly(name="B32_v23_M3508_three_channel_shared_dry_chamber")
    for name, shape in components.items():
        assembly.add(shape, name=name, color=_assembly_color(name))
    assembly.export(str(OUTPUT_STEP), exportType="STEP", unit="MM")
    render_v23_preview(components, OUTPUT_EXTERIOR_PREVIEW, section=False)
    render_v23_preview(components, OUTPUT_SECTION_PREVIEW, section=True)
    readback = cq.importers.importStep(str(OUTPUT_STEP)).val()
    if not readback.isValid():
        raise ValueError("The exported v23 assembly failed STEP re-import validity")
    return {
        "component_count": len(components),
        "source_solid_count": sum(len(shape.Solids()) for shape in components.values()),
        "step_path": str(OUTPUT_STEP),
        "step_valid": readback.isValid(),
        "step_solid_count": len(readback.Solids()),
        "assembly_bounds_xyz_minmax_mm": bounds_xyz_mm(readback),
        "exterior_preview_path": str(OUTPUT_EXTERIOR_PREVIEW),
        "section_preview_path": str(OUTPUT_SECTION_PREVIEW),
        "exterior_preview_size_px": list(__import__("PIL.Image", fromlist=["Image"]).open(
            OUTPUT_EXTERIOR_PREVIEW
        ).size),
        "section_preview_size_px": list(__import__("PIL.Image", fromlist=["Image"]).open(
            OUTPUT_SECTION_PREVIEW
        ).size),
    }


if __name__ == "__main__":
    print(json.dumps(export_v23_assembly(), ensure_ascii=False, indent=2))
