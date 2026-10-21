"""Build the B32 pre-print assembly and export the first mechanical package."""
from __future__ import annotations

import json
import math
import pathlib
import shutil
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "local" / "spiral-soft-arm" / "preprint" / "v1"
STAGE = REPO / "local" / "spiral-soft-arm" / "stage-a"
ARM_STL = STAGE / "stl" / "B32_cut_off.stl"
MM = 1.0
PACKAGE_VERSION = "0.1.0"


def collection(name: str):
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def link_obj(obj, coll):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def deselect_all():
    bpy.ops.object.select_all(action="DESELECT")


def cube(name: str, dims, loc, coll):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return link_obj(obj, coll)


def cylinder(name: str, radius: float, depth: float, loc, coll, axis=(0.0, 0.0, 1.0), vertices=48):
    direction = Vector(axis).normalized()
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=loc,
        rotation=direction.to_track_quat("Z", "Y").to_euler(),
    )
    obj = bpy.context.object
    obj.name = name
    return link_obj(obj, coll)


def apply_boolean(target, cutter, operation="DIFFERENCE"):
    deselect_all()
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    mod = target.modifiers.new("preprint_boolean", "BOOLEAN")
    mod.operation = operation
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    cutter_mesh = cutter.data if cutter.type == "MESH" else None
    bpy.data.objects.remove(cutter, do_unlink=True)
    if cutter_mesh and cutter_mesh.users == 0:
        bpy.data.meshes.remove(cutter_mesh)
    recalc_normals(target.data)


def recalc_normals(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def join_as_one(objects, name: str, coll):
    if not objects:
        raise ValueError("join_as_one needs at least one object")
    deselect_all()
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    result = bpy.context.view_layer.objects.active
    result.name = name
    deselect_all()
    result.select_set(True)
    bpy.context.view_layer.objects.active = result
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return link_obj(result, coll)


def union_as_one(objects, name: str, coll):
    if not objects:
        raise ValueError("union_as_one needs at least one object")
    target = objects[0]
    for cutter in objects[1:]:
        apply_boolean(target, cutter, "UNION")
    target.name = name
    deselect_all()
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return link_obj(target, coll)


def basis_xy(angle_deg: float):
    angle = math.radians(angle_deg)
    radial = Vector((math.cos(angle), math.sin(angle), 0.0))
    tangent = Vector((-math.sin(angle), math.cos(angle), 0.0))
    return radial, tangent


def xy_at(angle_deg: float, radius: float, tangent_offset: float = 0.0):
    radial, tangent = basis_xy(angle_deg)
    point = radius * radial + tangent_offset * tangent
    return point.x, point.y


def set_material(obj, name, color, metallic=0.0, roughness=0.55):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (*color, 1.0)
        principled.inputs["Metallic"].default_value = metallic
        principled.inputs["Roughness"].default_value = roughness
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def add_mesh_cylinder_cutter(cutters, name, radius, depth, loc, axis=(0.0, 0.0, 1.0), vertices=32):
    obj = cylinder(name, radius, depth, loc, cutters, axis=axis, vertices=vertices)
    return obj


def make_base_frame(coll):
    part_coll = collection("PRINT_BaseFrame")
    plate = cylinder("BaseFrame_280mm", 140.0, 8.0, (0.0, 0.0, 0.0), part_coll, vertices=192)
    cutters = []
    # Tendon exits and three M3 flange fasteners.
    for angle in (0.0, 120.0, 240.0):
        x, y = xy_at(angle, 30.6)
        cutters.append(add_mesh_cylinder_cutter(part_coll, "feed_hole", 2.2, 10.0, (x, y, 0.0)))
    for angle in (60.0, 180.0, 300.0):
        x, y = xy_at(angle, 28.5)
        cutters.append(add_mesh_cylinder_cutter(part_coll, "M3_body_fastener", 1.7, 10.0, (x, y, 0.0)))
    # Two metal P-clamps per M2006 motor; round holes allow the tab spacing to be revised.
    for angle in (0.0, 120.0, 240.0):
        for station in (-88.0, -50.0):
            for radial_offset in (-15.0, 15.0):
                x, y = xy_at(angle, 75.0 + radial_offset, station)
                cutters.append(add_mesh_cylinder_cutter(part_coll, "motor_clamp_M4", 2.25, 10.0, (x, y, 0.0)))
        # Bearing yokes sit either side of each take-up spool.
        for tangent_offset in (-15.0, 15.0):
            for radial_offset in (-8.5, 8.5):
                x, y = xy_at(angle, 75.0 + radial_offset, tangent_offset)
                cutters.append(add_mesh_cylinder_cutter(part_coll, "bearing_yoke_M3", 1.7, 10.0, (x, y, 0.0)))
        # One generic four-point pattern for the C610 tray.
        for radial_offset in (-15.0, 15.0):
            for tangent_offset in (-28.0, 28.0):
                x, y = xy_at(angle, 105.0 + radial_offset, tangent_offset)
                cutters.append(add_mesh_cylinder_cutter(part_coll, "C610_tray_M3", 1.7, 10.0, (x, y, 0.0)))
        # Fairlead bracket's two mount points both sit outside the arm footprint.
        for radial_offset, tangent_offset in ((9.0, -8.0), (9.0, 8.0)):
            x, y = xy_at(angle, 35.6 + radial_offset, tangent_offset)
            cutters.append(add_mesh_cylinder_cutter(part_coll, "fairlead_mount_M3", 1.7, 10.0, (x, y, 0.0)))
    # Fixture holes around the outer edge of the test plate.
    for angle in range(0, 360, 30):
        x, y = xy_at(float(angle), 132.0)
        cutters.append(add_mesh_cylinder_cutter(part_coll, "fixture_M5", 2.7, 10.0, (x, y, 0.0)))
    cutters_mesh = bpy.data.meshes.new("BaseFrame_cutters_mesh")
    verts, faces = [], []
    for cutter in cutters:
        offset = len(verts)
        verts.extend(tuple(cutter.matrix_world @ v.co) for v in cutter.data.vertices)
        faces.extend(tuple(offset + i for i in p.vertices) for p in cutter.data.polygons)
    cutters_mesh.from_pydata(verts, [], faces)
    cutters_mesh.validate(clean_customdata=True)
    recalc_normals(cutters_mesh)
    cutter_obj = bpy.data.objects.new("BaseFrame_all_bores", cutters_mesh)
    part_coll.objects.link(cutter_obj)
    apply_boolean(plate, cutter_obj, "DIFFERENCE")
    for cutter in cutters:
        if cutter.name in bpy.data.objects:
            bpy.data.objects.remove(cutter, do_unlink=True)
    plate.name = "BaseFrame_PRINT_280x8"
    plate["material_recommendation"] = "PETG, PA12, or aluminum for the rigid frame; not TPU"
    plate["length_unit"] = "mm"
    plate["motor_layout"] = "3x tangential M2006, 2x 25 mm P-clamp per motor"
    set_material(plate, "PETG_dark", (0.12, 0.17, 0.22))
    return plate


def make_bearing_yoke(part_coll):
    yoke = cube("BearingYoke_proto", (24.0, 10.0, 29.0), (0.0, 0.0, 0.0), part_coll)
    pocket = cylinder("606_outer_seat", 8.6, 6.2, (0.0, 0.0, 0.0), part_coll, axis=(0.0, 1.0, 0.0), vertices=64)
    apply_boolean(yoke, pocket)
    bore = cylinder("shaft_bore_6_2", 3.1, 12.0, (0.0, 0.0, 0.0), part_coll, axis=(0.0, 1.0, 0.0), vertices=48)
    apply_boolean(yoke, bore)
    cutters = []
    for x in (-8.5, 8.5):
        cutters.append(cylinder("mount_M3", 1.7, 32.0, (x, 0.0, 0.0), part_coll, vertices=32))
    cutter_mesh = bpy.data.meshes.new("yoke_mount_cutters_mesh")
    verts, faces = [], []
    for cutter in cutters:
        offset = len(verts)
        verts.extend(tuple(cutter.matrix_world @ v.co) for v in cutter.data.vertices)
        faces.extend(tuple(offset + i for i in p.vertices) for p in cutter.data.polygons)
    cutter_mesh.from_pydata(verts, [], faces)
    cutter_mesh.validate(clean_customdata=True)
    recalc_normals(cutter_mesh)
    cutter_obj = bpy.data.objects.new("yoke_mount_cutters", cutter_mesh)
    part_coll.objects.link(cutter_obj)
    apply_boolean(yoke, cutter_obj)
    for cutter in cutters:
        if cutter.name in bpy.data.objects:
            bpy.data.objects.remove(cutter, do_unlink=True)
    yoke.name = "BearingYoke_606"
    yoke["bearing"] = "606-2Z, 6x17x6 mm; pocket Ø17.2 x 6.2 mm"
    yoke["shaft_bore_mm"] = 6.2
    set_material(yoke, "PETG_or_PA12", (0.24, 0.28, 0.31))
    return yoke


def make_spool(part_coll):
    sides = 64
    ys = (-7.2, -5.8, 5.8, 7.2)
    outer_rs = (9.5, 6.5, 6.5, 9.5)
    inner_r = 3.1
    vertices, faces = [], []
    outer_rows, inner_rows = [], []
    for y, outer_r in zip(ys, outer_rs):
        outer_row, inner_row = [], []
        for i in range(sides):
            angle = 2.0 * math.pi * i / sides
            outer_row.append(len(vertices))
            vertices.append((outer_r * math.cos(angle), y, outer_r * math.sin(angle)))
            inner_row.append(len(vertices))
            vertices.append((inner_r * math.cos(angle), y, inner_r * math.sin(angle)))
        outer_rows.append(outer_row)
        inner_rows.append(inner_row)
    for row in range(len(ys) - 1):
        for i in range(sides):
            nxt = (i + 1) % sides
            faces.append((outer_rows[row][i], outer_rows[row][nxt], outer_rows[row + 1][nxt], outer_rows[row + 1][i]))
            faces.append((inner_rows[row][nxt], inner_rows[row][i], inner_rows[row + 1][i], inner_rows[row + 1][nxt]))
    for i in range(sides):
        nxt = (i + 1) % sides
        faces.append((outer_rows[0][nxt], outer_rows[0][i], inner_rows[0][i], inner_rows[0][nxt]))
        last = len(ys) - 1
        faces.append((outer_rows[last][i], outer_rows[last][nxt], inner_rows[last][nxt], inner_rows[last][i]))
    mesh = bpy.data.meshes.new("LineSpool_grooved_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    recalc_normals(mesh)
    spool = bpy.data.objects.new("LineSpool_grooved", mesh)
    part_coll.objects.link(spool)
    # A one-layer helical groove, 10 turns over 10 mm of drum width.
    curve = bpy.data.curves.new("spool_groove_cutter_curve", "CURVE")
    curve.dimensions = "3D"
    curve.use_fill_caps = True
    curve.resolution_u = 2
    curve.bevel_depth = 0.43
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    turns = 10.0
    steps = 800
    spline.points.add(steps)
    for i in range(steps + 1):
        u = i / steps
        theta = 2.0 * math.pi * turns * u
        y = -5.0 + 10.0 * u
        spline.points[i].co = (6.48 * math.cos(theta), y, 6.48 * math.sin(theta), 1.0)
    cutter_obj = bpy.data.objects.new("spool_groove_cutter", curve)
    part_coll.objects.link(cutter_obj)
    deselect_all()
    cutter_obj.select_set(True)
    bpy.context.view_layer.objects.active = cutter_obj
    bpy.ops.object.convert(target="MESH")
    cutter_obj = bpy.context.view_layer.objects.active
    apply_boolean(spool, cutter_obj, "DIFFERENCE")
    anchor = cylinder("spool_tendon_anchor_hole", 0.65, 16.0, (8.0, 0.0, 0.0), part_coll,
                      axis=(0.0, 1.0, 0.0), vertices=32)
    apply_boolean(spool, anchor, "DIFFERENCE")
    spool["cable_diameter_mm"] = 0.5
    spool["effective_radius_mm"] = 6.5
    spool["groove_pitch_mm"] = 1.0
    spool["groove_turns"] = 10
    spool["ideal_single_layer_capacity_mm"] = 408.4
    spool["shaft_bore_mm"] = 6.2
    set_material(spool, "PETG_spool", (0.86, 0.52, 0.17))
    return spool


def make_c610_tray(part_coll):
    # Open-top tray captures the 50 x 22 x 7.3 mm ESC between its rails and the base frame.
    pieces = [cube("tray_base", (40.0, 66.0, 3.0), (0.0, 0.0, -8.8), part_coll)]
    for x in (-15.0, 15.0):
        for y in (-28.0, 28.0):
            pieces.append(cylinder("tray_frame_standoff", 3.5, 7.8, (x, y, -3.9), part_coll, vertices=40))
    for x in (-12.5, 12.5):
        pieces.append(cube("tray_side_rail", (2.0, 54.0, 7.8), (x, 0.0, -3.9), part_coll))
    for y in (-27.0, 27.0):
        for x in (-10.0, 10.0):
            pieces.append(cube("tray_end_stop", (6.0, 2.0, 7.8), (x, y, -3.9), part_coll))
    tray = union_as_one(pieces, "C610_Tray", part_coll)
    # Four M3 frame fasteners; the ESC is captured by the tray rails and frame, without assuming PCB hole locations.
    cutters = []
    for x in (-15.0, 15.0):
        for y in (-28.0, 28.0):
            cutters.append(cylinder("tray_mount_hole", 1.7, 14.0, (x, y, -5.0), part_coll, vertices=32))
    for cutter in cutters:
        apply_boolean(tray, cutter)
    tray["board_envelope_mm"] = [50.0, 22.0, 7.3]
    tray["note"] = "open-top capture tray for the 50 x 22 x 7.3 mm C610 envelope; fit-check the delivered controller before printing the full set"
    set_material(tray, "PETG_or_PA12", (0.24, 0.28, 0.31))
    return tray


def make_fairlead_bracket(part_coll):
    pieces = [
        cube("fairlead_cheek_left", (14.0, 3.0, 22.0), (0.0, -6.0, 5.0), part_coll),
        cube("fairlead_cheek_right", (14.0, 3.0, 22.0), (0.0, 6.0, 5.0), part_coll),
        cube("fairlead_top_bridge", (24.0, 20.0, 4.0), (0.0, 0.0, 14.0), part_coll),
    ]
    bracket = union_as_one(pieces, "FairleadBracket", part_coll)
    axle = cylinder("idler_axle_bore", 1.65, 24.0, (0.0, 0.0, 0.0), part_coll, axis=(0.0, 1.0, 0.0), vertices=32)
    apply_boolean(bracket, axle)
    for x, y in ((9.0, -8.0), (9.0, 8.0)):
        bore = cylinder("fairlead_M3_mount", 1.7, 24.0, (x, y, 5.0), part_coll, vertices=32)
        apply_boolean(bracket, bore)
    bracket["idler_axis"] = "local +Y; use a 3 mm pin"
    bracket["guide_center_mm"] = [0.0, 0.0, 0.0]
    set_material(bracket, "PETG_or_PA12", (0.22, 0.27, 0.30))
    pulley = cylinder("FairleadPulley", 5.0, 8.0, (0.0, 0.0, 0.0), part_coll, axis=(0.0, 1.0, 0.0), vertices=64)
    bore = cylinder("pulley_bore", 1.65, 10.0, (0.0, 0.0, 0.0), part_coll, axis=(0.0, 1.0, 0.0), vertices=32)
    apply_boolean(pulley, bore)
    set_material(pulley, "PETG_pulley", (0.85, 0.70, 0.24))
    return bracket, pulley


def make_tip_anchor(part_coll, tip_radius: float):
    outer = cylinder("TipAnchor_outer", 4.8, 4.2, (0.0, 0.0, 0.9), part_coll, vertices=96)
    inner = cylinder("TipAnchor_sleeve_bore", tip_radius + 0.095, 3.2, (0.0, 0.0, 1.55), part_coll, vertices=96)
    apply_boolean(outer, inner)
    # Three tether holes at the B32 tip hole radius, with underside stopper-knot seats.
    tether_center = 0.5 * 7.359161656027865 * 0.50
    for angle in (0.0, 120.0, 240.0):
        x, y = xy_at(angle, tether_center)
        through = cylinder("tip_tendon_hole", 0.55, 4.6, (x, y, 0.9), part_coll, vertices=40)
        apply_boolean(outer, through)
        knot = cylinder("tip_knot_pocket", 1.15, 0.9, (x, y, -0.75), part_coll, vertices=48)
        apply_boolean(outer, knot)
    outer.name = "TipAnchor_B32_low_profile"
    outer["outer_diameter_mm"] = 9.6
    outer["body_tip_diameter_reference_mm"] = 7.359
    outer["tether_hole_count"] = 3
    outer["retention"] = "three 0.5 mm UHMWPE/PE lines; stopper-knot seats on distal face; trial-fit before full use"
    deselect_all()
    outer.select_set(True)
    bpy.context.view_layer.objects.active = outer
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    set_material(outer, "PETG_or_PA12", (0.82, 0.28, 0.20))
    return outer


def make_curve_path(name, points, coll, bevel=0.3):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = bevel
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, value in zip(spline.points, points):
        point.co = (value.x, value.y, value.z, 1.0)
    obj = bpy.data.objects.new(name, curve)
    coll.objects.link(obj)
    return obj


def make_motor_reference(angle, coll, material):
    radial, tangent = basis_xy(angle)
    r = 75.0
    motor_face_t = -36.0
    body_length = 64.8
    body_center_t = motor_face_t - body_length * 0.5
    body_center = r * radial + body_center_t * tangent + Vector((0.0, 0.0, -22.5))
    body = cylinder("M2006_P36_reference_envelope", 12.2, body_length,
                    tuple(body_center), coll, axis=tuple(tangent), vertices=64)
    set_material(body, material.name, tuple(material.diffuse_color[:3]), metallic=0.55)
    gearbox_center = r * radial + (motor_face_t - 4.0) * tangent + Vector((0.0, 0.0, -22.5))
    gearbox = cylinder("M2006_gearbox_envelope", 12.2, 8.0,
                       tuple(gearbox_center), coll, axis=tuple(tangent), vertices=64)
    set_material(gearbox, material.name, tuple(material.diffuse_color[:3]), metallic=0.6)
    shaft_center = r * radial + (motor_face_t + 3.0) * tangent + Vector((0.0, 0.0, -22.5))
    shaft = cylinder("M2006_D6mm_shaft_reference", 3.0, 6.0,
                     tuple(shaft_center), coll, axis=tuple(tangent), vertices=32)
    set_material(shaft, "Steel", (0.55, 0.58, 0.60), metallic=0.85)
    return body, gearbox, shaft


def make_pclamp_reference(angle, station, coll):
    radial, tangent = basis_xy(angle)
    center = 75.0 * radial + station * tangent + Vector((0.0, 0.0, -22.5))
    curve = bpy.data.curves.new("P_clamp_band_reference", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = 0.65
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    points = []
    for i in range(121):
        theta = math.radians(135.0 + 270.0 * i / 120.0)
        p = center + 13.0 * math.cos(theta) * radial + Vector((0.0, 0.0, 13.0 * math.sin(theta)))
        points.append(p)
    spline.points.add(len(points) - 1)
    for point, value in zip(spline.points, points):
        point.co = (value.x, value.y, value.z, 1.0)
    obj = bpy.data.objects.new("Purchased_25mm_P_clamp_reference", curve)
    coll.objects.link(obj)
    set_material(obj, "Zinc_plated_reference", (0.62, 0.66, 0.69), metallic=0.8)
    return obj


def add_bearing_reference(angle, tangent_offset, coll):
    radial, tangent = basis_xy(angle)
    center = 75.0 * radial + tangent_offset * tangent + Vector((0.0, 0.0, -22.5))
    outer = cylinder("606_2Z_bearing_reference_OD17", 8.5, 6.0, tuple(center), coll, axis=tuple(tangent), vertices=48)
    inner = cylinder("606_bore_ID6", 3.0, 7.0, tuple(center), coll, axis=tuple(tangent), vertices=32)
    apply_boolean(outer, inner)
    set_material(outer, "Bearing_steel", (0.61, 0.64, 0.68), metallic=0.85)
    return outer


def add_c610_reference(angle, coll):
    radial, tangent = basis_xy(angle)
    center = 105.0 * radial + Vector((0.0, 0.0, -11.65))
    board = cube("C610_reference_envelope_50x22x7_3", (22.0, 50.0, 7.3), tuple(center), coll)
    board.rotation_euler.z = math.radians(angle)
    set_material(board, "C610_dark_reference", (0.14, 0.16, 0.18), metallic=0.1)
    return board


def add_body_and_reference(assembly_coll, reference_coll):
    if not ARM_STL.is_file():
        raise FileNotFoundError(ARM_STL)
    bpy.ops.wm.stl_import(filepath=str(ARM_STL), global_scale=1.0, use_scene_unit=False)
    arm = next(obj for obj in bpy.context.selected_objects if obj.type == "MESH")
    arm.name = "SoftArm_B32_cut_off_550mm"
    link_obj(arm, assembly_coll)
    arm.rotation_euler = (math.pi, 0.0, 0.0)
    arm.location = (0.0, 0.0, 550.0)
    arm["assembly_transform"] = "base at z=0; tip at z=550 mm"
    set_material(arm, "TPU95A_orange", (0.86, 0.32, 0.12), roughness=0.8)
    steel = bpy.data.materials.get("Motor_reference_gray") or bpy.data.materials.new("Motor_reference_gray")
    steel.diffuse_color = (0.55, 0.58, 0.61, 1.0)
    for angle in (0.0, 120.0, 240.0):
        make_motor_reference(angle, reference_coll, steel)
        for station in (-88.0, -50.0):
            make_pclamp_reference(angle, station, reference_coll)
        add_c610_reference(angle, reference_coll)
    return arm


def instance_at(proto, name, loc, angle_deg, coll):
    obj = proto.copy()
    obj.data = proto.data.copy()
    obj.name = name
    coll.objects.link(obj)
    obj.location = loc
    obj.rotation_euler.z = math.radians(angle_deg)
    return obj


def make_assembly_objects(arm, frame, yoke_proto, spool_proto, tray_proto,
                          bracket_proto, pulley_proto, anchor_proto, assembly_coll,
                          print_coll, reference_coll):
    frame_obj = frame.copy()
    frame_obj.data = frame.data.copy()
    frame_obj.name = "BaseFrame_assembled"
    assembly_coll.objects.link(frame_obj)
    frame_obj.location = (0.0, 0.0, -4.0)

    # Arm base and M3 fastener stack; nuts sit in the B32 TPU hex pockets.
    for angle in (60.0, 180.0, 300.0):
        x, y = xy_at(angle, 28.5)
        nut = cylinder("M3_hex_nut_reference", 3.18, 2.4, (x, y, 1.2), reference_coll, vertices=6)
        set_material(nut, "Steel", (0.60, 0.63, 0.66), metallic=0.85)
        screw = cylinder("M3x12_socket_screw_reference", 1.5, 12.0, (x, y, -2.0), reference_coll, vertices=32)
        head = cylinder("M3_socket_head_reference", 2.75, 3.0, (x, y, -9.5), reference_coll, vertices=32)
        set_material(screw, "Steel", (0.60, 0.63, 0.66), metallic=0.85)
        set_material(head, "Steel", (0.60, 0.63, 0.66), metallic=0.85)

    # The B32 cap is fit on the upper tip; origin sits at the body tip plane.
    tip_anchor = instance_at(anchor_proto, "TipAnchor_B32_assembled", (0.0, 0.0, 550.0), 0.0, assembly_coll)
    tip_anchor.rotation_euler = (math.pi, 0.0, 0.0)
    tip_anchor["visualization_only_reference_fit"] = True

    # Each module: two bearings, a single-layer take-up spool and two metal P-clamps.
    for angle in (0.0, 120.0, 240.0):
        radial, tangent = basis_xy(angle)
        for t in (-15.0, 15.0):
            loc = 75.0 * radial + t * tangent + Vector((0.0, 0.0, -22.5))
            instance_at(yoke_proto, f"BearingYoke_{int(angle)}_{int(t)}", tuple(loc), angle, assembly_coll)
            add_bearing_reference(angle, t, reference_coll)
        spool_loc = 75.0 * radial + Vector((0.0, 0.0, -22.5))
        instance_at(spool_proto, f"LineSpool_{int(angle)}", tuple(spool_loc), angle, assembly_coll)
        # 6 mm support shaft and D-shaft clamp coupler are metal reference hardware.
        shaft = cylinder("Shaft_6mm_reference", 3.0, 48.0, tuple(spool_loc), reference_coll, axis=tuple(tangent), vertices=32)
        set_material(shaft, "Steel", (0.57, 0.60, 0.63), metallic=0.85)
        coupler_loc = 75.0 * radial - 25.5 * tangent + Vector((0.0, 0.0, -22.5))
        coupler = cylinder("D6_to_6mm_coupler_reference", 4.5, 21.0, tuple(coupler_loc), reference_coll, axis=tuple(tangent), vertices=48)
        coupler["fit_reference"] = "21 mm metal D6-to-6 mm round shaft coupler; verify the delivered M2006 output shaft engagement"
        set_material(coupler, "Steel", (0.54, 0.57, 0.60), metallic=0.85)
        # Fairlead centre is at the radial 90-degree redirection point.
        guide_loc = 35.6 * radial + Vector((0.0, 0.0, -24.0))
        instance_at(bracket_proto, f"FairleadBracket_{int(angle)}", tuple(guide_loc), angle, assembly_coll)
        instance_at(pulley_proto, f"FairleadPulley_{int(angle)}", tuple(guide_loc), angle, assembly_coll)
        # C610 tray sits outside the motor envelope on the underside of the frame.
        tray_loc = 105.0 * radial + Vector((0.0, 0.0, -8.0))
        instance_at(tray_proto, f"C610Tray_{int(angle)}", tuple(tray_loc), angle, assembly_coll)
        # Approximate tendon path: vertical lead, 90-degree idler arc, radial lead to spool.
        p0 = 30.6 * radial + Vector((0.0, 0.0, 0.0))
        p1 = 30.6 * radial + Vector((0.0, 0.0, -24.0))
        path_points = [p0, p1]
        for i in range(1, 25):
            theta = math.pi + 0.5 * math.pi * i / 24.0
            pt = (35.6 + 5.0 * math.cos(theta)) * radial + Vector((0.0, 0.0, -24.0 + 5.0 * math.sin(theta)))
            path_points.append(pt)
        path_points.append(68.5 * radial + Vector((0.0, 0.0, -29.0)))
        cable = make_curve_path(f"TendonPath_{int(angle)}_visual", path_points, reference_coll, bevel=0.3)
        set_material(cable, f"Tendon_{int(angle)}", (0.93, 0.84, 0.37), roughness=0.75)


def mesh_metrics(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    nonmanifold = sum(1 for edge in bm.edges if not edge.is_manifold)
    remaining = set(bm.verts)
    components = 0
    while remaining:
        components += 1
        stack = [remaining.pop()]
        while stack:
            vert = stack.pop()
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
    bm.free()
    points = [obj.matrix_world @ Vector(v.co) for v in obj.data.vertices]
    if points:
        minp = [min(p[i] for p in points) for i in range(3)]
        maxp = [max(p[i] for p in points) for i in range(3)]
        dims = [maxp[i] - minp[i] for i in range(3)]
    else:
        dims = [0.0, 0.0, 0.0]
    return {"vertices": len(obj.data.vertices), "faces": len(obj.data.polygons),
            "nonmanifold_edges": nonmanifold, "connected_components": components,
            "dimensions_mm": [round(value, 4) for value in dims],
            "closed_single_solid": nonmanifold == 0 and components == 1}


def export_local_stl(obj, path: pathlib.Path):
    original = obj.matrix_world.copy()
    duplicate = obj.copy()
    duplicate.data = obj.data.copy()
    bpy.context.scene.collection.objects.link(duplicate)
    duplicate.name = "__export_local__"
    duplicate.hide_viewport = False
    duplicate.hide_render = False
    duplicate.hide_set(False)
    duplicate.matrix_world = original.to_3x3().to_4x4()
    deselect_all()
    duplicate.select_set(True)
    bpy.context.view_layer.objects.active = duplicate
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.stl_export(
        filepath=str(path),
        export_selected_objects=True,
        apply_modifiers=True,
        global_scale=1.0,
        use_scene_unit=False,
    )
    mesh_copy = duplicate.data
    bpy.data.objects.remove(duplicate, do_unlink=True)
    if mesh_copy.users == 0:
        bpy.data.meshes.remove(mesh_copy)
    obj.matrix_world = original


def make_coupon(src_obj, zmin: float, zmax: float, name: str, coll):
    coupon = src_obj.copy()
    coupon.data = src_obj.data.copy()
    coll.objects.link(coupon)
    coupon.name = name
    coupon.location = (0.0, 0.0, 0.0)
    coupon.rotation_euler = (0.0, 0.0, 0.0)
    bm = bmesh.new()
    bm.from_mesh(coupon.data)
    geometry = lambda: list(bm.verts) + list(bm.edges) + list(bm.faces)
    if zmin > 0.0:
        result = bmesh.ops.bisect_plane(
            bm, geom=geometry(), dist=1e-6, plane_co=(0.0, 0.0, zmin),
            plane_no=(0.0, 0.0, 1.0), clear_inner=True,
        )
        cut_edges = [item for item in result["geom_cut"] if isinstance(item, bmesh.types.BMEdge) and item.is_valid]
        if cut_edges:
            bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
    if zmax < 550.0:
        result = bmesh.ops.bisect_plane(
            bm, geom=geometry(), dist=1e-6, plane_co=(0.0, 0.0, zmax),
            plane_no=(0.0, 0.0, 1.0), clear_outer=True,
        )
        cut_edges = [item for item in result["geom_cut"] if isinstance(item, bmesh.types.BMEdge) and item.is_valid]
        if cut_edges:
            bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(coupon.data)
    bm.free()
    coupon.data.update()
    return coupon


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.background_type = "WORLD"
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_specular_highlight = True
    scene.display.shading.show_object_outline = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1600
    scene.render.resolution_percentage = 100
    scene.camera = None
    bpy.ops.object.camera_add(location=(360.0, -620.0, 440.0))
    camera = bpy.context.object
    camera.name = "PreviewCamera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 810.0
    camera.rotation_euler = (math.radians(63.0), 0.0, math.radians(30.0))
    # Aim the camera robustly at the arm midpoint.
    target = Vector((0.0, 0.0, 260.0))
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    return camera


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in list(bpy.data.collections):
        if coll.name != bpy.context.scene.collection.name:
            bpy.data.collections.remove(coll)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene["preprint_package"] = "B32 550 mm three-tendon logarithmic spiral arm"
    scene["generator_version"] = "0.4.0"
    scene["preprint_package_generator_version"] = PACKAGE_VERSION

    assembly_coll = collection("ASSEMBLY_B32")
    reference_coll = collection("REFERENCE_HARDWARE_NOT_FOR_PRINT")
    print_coll = collection("PRINT_PART_PROTOTYPES")
    coupon_coll = collection("PROCESS_COUPONS")
    metal_ref = bpy.data.materials.new("Motor_reference_gray")
    metal_ref.diffuse_color = (0.55, 0.58, 0.61, 1.0)

    # The main frame and prototype parts are built at their own local origins.
    frame = make_base_frame(print_coll)
    yoke_proto = make_bearing_yoke(print_coll)
    spool_proto = make_spool(print_coll)
    tray_proto = make_c610_tray(print_coll)
    bracket_proto, pulley_proto = make_fairlead_bracket(print_coll)
    anchor_proto = make_tip_anchor(print_coll, 0.5 * 7.359161656027865)

    arm = add_body_and_reference(assembly_coll, reference_coll)
    make_assembly_objects(arm, frame, yoke_proto, spool_proto, tray_proto,
                          bracket_proto, pulley_proto, anchor_proto,
                          assembly_coll, print_coll, reference_coll)

    # Duplicate test sections from the same B32 body; they are supplied for vendor process trials.
    source = bpy.data.objects.get("SoftArm_B32_cut_off_550mm")
    # Use the canonical untransformed STL for coupon cuts.
    bpy.ops.wm.stl_import(filepath=str(ARM_STL), global_scale=1.0, use_scene_unit=False)
    canonical = next(obj for obj in bpy.context.selected_objects if obj.type == "MESH")
    canonical.name = "B32_coupon_source_hidden"
    link_obj(canonical, coupon_coll)
    tip_coupon = make_coupon(canonical, 0.0, 80.0, "B32_tip_80mm_process_coupon", coupon_coll)
    base_coupon = make_coupon(canonical, 470.0, 550.0, "B32_base_80mm_process_coupon", coupon_coll)
    canonical.hide_viewport = True
    canonical.hide_render = True
    for obj in (tip_coupon, base_coupon):
        obj.hide_viewport = True
        obj.hide_render = True

    # Hide print prototypes from the final preview; assembly copies remain visible.
    for obj in print_coll.objects:
        obj.hide_viewport = True
        obj.hide_render = True

    # Create a small exploded view collection for a second inspection view in the .blend.
    # Keep all file exports centered at each part's local origin.
    stl_dir = OUT / "stl"
    stl_dir.mkdir(parents=True, exist_ok=True)
    soft_arm_copy = stl_dir / "01_soft_arm_B32_cut_off_550mm.stl"
    shutil.copy2(ARM_STL, soft_arm_copy)
    part_rows = [{"file": soft_arm_copy.name, **mesh_metrics(arm)}]
    print_objects = [
        ("02_rigid_base_frame_280x8.stl", frame),
        ("03_bearing_yoke_606x17.stl", yoke_proto),
        ("04_grooved_line_spool_6p5R.stl", spool_proto),
        ("05_C610_adjustable_tray.stl", tray_proto),
        ("06_fairlead_bracket.stl", bracket_proto),
        ("07_fairlead_pulley.stl", pulley_proto),
        ("08_tip_anchor_low_profile_B32.stl", anchor_proto),
    ]
    for filename, obj in print_objects:
        path = stl_dir / filename
        export_local_stl(obj, path)
        part_rows.append({"file": filename, **mesh_metrics(obj)})
    for filename, obj, zmin, zmax in (
        ("09_B32_tip_80mm_process_coupon.stl", tip_coupon, 0.0, 80.0),
        ("10_B32_base_80mm_process_coupon.stl", base_coupon, 470.0, 550.0),
    ):
        path = stl_dir / filename
        export_local_stl(obj, path)
        part_rows.append({"file": filename, "source_z_range_mm": [zmin, zmax], **mesh_metrics(obj)})
    invalid_parts = [part["file"] for part in part_rows if not part["closed_single_solid"]]
    if invalid_parts:
        raise RuntimeError("refusing to package non-closed or disconnected print meshes: " + ", ".join(invalid_parts))
    with (OUT / "printable_parts.json").open("w", encoding="utf-8") as stream:
        json.dump({
            "units": "mm",
            "recommended_first_build": "B32",
            "package_generator_version": PACKAGE_VERSION,
            "tendon_design": {
                "count": 3,
                "line_diameter_mm": 0.5,
                "straight_path_length_mm": 550.765,
                "spool_effective_radius_mm": 6.5,
                "single_layer_turns": 10,
                "theoretical_single_layer_takeup_mm": 408.4,
            },
            "assembly_envelopes": {
                "M2006_body_mm": [24.4, 64.8],
                "C610_board_mm": [22.0, 50.0, 7.3],
                "C610_tray_mm": [40.0, 66.0, 10.3],
                "tray_nominal_board_clearance_mm": {"radial": 0.5, "tangential": 1.0},
                "tray_cable_exit_gap_mm": 14.0,
                "minimum_corner_post_to_board_clearance_mm": 1.5,
                "fit_note": "C610 is captured in an open-top cage; motor, clamps, bearings and coupler are simplified envelopes; verify purchased parts before assembly",
            },
            "parts": part_rows,
        }, stream, indent=2, ensure_ascii=False)
        stream.write("\n")

    # Render and save the editable assembly.
    camera = setup_render()
    scene.render.filepath = str(OUT / "assembly_preview.png")
    bpy.ops.render.render(write_still=True)
    overview_transform = (camera.location.copy(), camera.rotation_euler.copy(), camera.data.ortho_scale)
    camera.location = (320.0, -400.0, -150.0)
    camera.data.ortho_scale = 460.0
    target = Vector((0.0, 0.0, -15.0))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1200
    scene.render.filepath = str(OUT / "base_mechanism_detail.png")
    bpy.ops.render.render(write_still=True)
    camera.location, camera.rotation_euler, camera.data.ortho_scale = overview_transform
    scene.render.filepath = str(OUT / "assembly_preview.png")
    blend_path = OUT / "B32_preprint_assembly.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f"已生成装配与打印件：{OUT}")
    print(json.dumps(part_rows, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    build()
