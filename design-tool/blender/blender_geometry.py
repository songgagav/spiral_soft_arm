"""Blender-native mesh generation for the local three-cable spiral profile."""
from __future__ import annotations

import math
import pathlib
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from geometry import (  # noqa: E402
    build_body_profile_polygons,
    local_profile_metrics,
    paper_metrics,
    percent_to_fraction,
)

REVOLUTION_STEPS = 48
PROFILE_STEP_MM = 1.2
PROFILE_STATION_MERGE_TOL_MM = 1e-4


def _recalc_normals(mesh: bpy.types.Mesh) -> None:
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _profile_y_at_z(polygons, z: float) -> float:
    values = []
    eps = 1e-7
    for poly in polygons:
        for index, (x0, y0) in enumerate(poly):
            x1, y1 = poly[(index + 1) % len(poly)]
            lo, hi = min(x0, x1), max(x0, x1)
            if z < lo - eps or z > hi + eps:
                continue
            if abs(x1 - x0) <= eps:
                if abs(z - x0) <= eps:
                    values.extend((y0, y1))
            else:
                t = (z - x0) / (x1 - x0)
                if -eps <= t <= 1.0 + eps:
                    values.append(y0 + t * (y1 - y0))
    return max(values, default=0.0)


def _profile_stations(polygons, length: float) -> list[float]:
    count = max(2, int(math.ceil(length / PROFILE_STEP_MM)))
    raw = {length * i / count for i in range(count + 1)}
    raw.add(max(0.0, length - 4.0))
    for poly in polygons:
        raw.update(max(0.0, min(length, point[0])) for point in poly)
    ordered = sorted(raw)
    stations = []
    for value in ordered:
        if not stations or value - stations[-1] > PROFILE_STATION_MERGE_TOL_MM:
            stations.append(value)
    return stations


def _axis_radius(params: dict, z: float, length: float, tip_width: float) -> float:
    ratio = max(0.0, min(1.0, z / max(length, 1e-9)))
    theta = ratio * params["num_units"] * math.radians(params["delta_theta_deg"])
    width = tip_width * math.exp(params["b"] * theta)
    return max(0.08, 0.5 * percent_to_fraction(params["elastic_percent"]) * width)


def _minimum_outer_for_tendon(params: dict, local: dict, z: float, length: float) -> float:
    """Keep the straight tendon centerline enclosed by a declared radial wall."""
    fraction = max(0.0, min(1.0, z / max(length, 1e-9)))
    tip_center = 0.5 * local["local_tip_diameter_mm"] * percent_to_fraction(params["tip_hole_pos_pct"])
    base_center = 0.5 * local["local_base_diameter_mm"] * percent_to_fraction(params["base_hole_pos_pct"])
    center = tip_center + fraction * (base_center - tip_center)
    hole_radius = 0.5 * (params["tip_hole_diameter_mm"]
                         + fraction * (params["base_hole_diameter_mm"] - params["tip_hole_diameter_mm"]))
    return center + hole_radius + float(params["minimum_tendon_wall_mm"])


def _cut_outer_radius(radius: float, theta: float, params: dict, enabled: bool) -> float:
    if not enabled:
        return radius
    # The local 3-cable manufacturing cut starts at (1 - position%) of the
    # radius. The size parameter deepens that trim; flat directions sit between
    # cable paths so the cutters do not consume the tendon-hole walls.
    offset = max(0.48, 1.0 - percent_to_fraction(params["cable3_cut_pos_pct"])
                 - 0.5 * percent_to_fraction(params["cable3_cut_size_pct"]))
    plane_limit = radius
    for normal_deg in (60.0, 180.0, 300.0):
        cosine = math.cos(theta - math.radians(normal_deg))
        if cosine > 1e-9:
            plane_limit = min(plane_limit, radius * offset / cosine)
    return plane_limit


def _make_rotational_shell(params: dict, cut_enabled: bool, collection) -> tuple[bpy.types.Object, dict]:
    theory = paper_metrics(params["a_mm"], params["b"], params["num_units"], params["delta_theta_deg"])
    source_metrics = local_profile_metrics(params["a_mm"], params["b"], params["num_units"], params["delta_theta_deg"])
    polygons = build_body_profile_polygons(
        params["a_mm"], params["b"], params["delta_theta_deg"], params["p"], params["num_units"]
    )
    length = max(x for poly in polygons for x, _y in poly)
    stations = _profile_stations(polygons, length)
    angles = [2.0 * math.pi * i / REVOLUTION_STEPS for i in range(REVOLUTION_STEPS)]
    rings_outer = []
    flange_thickness = float(params.get("base_flange_thickness_mm", 4.0))
    flange_radius = 0.5 * source_metrics["local_base_diameter_mm"]
    for z in stations:
        core_r = _axis_radius(params, z, length, source_metrics["local_tip_diameter_mm"])
        outer_base = max(
            _profile_y_at_z(polygons, z),
            core_r * 1.18,
            _minimum_outer_for_tendon(params, source_metrics, z, length),
        )
        if z >= length - flange_thickness - PROFILE_STATION_MERGE_TOL_MM:
            outer_base = max(outer_base, flange_radius)
        outer_ring = []
        for theta in angles:
            radius = max(core_r * 1.02, _cut_outer_radius(outer_base, theta, params, cut_enabled))
            outer_ring.append(radius)
        rings_outer.append(outer_ring)

    vertices = []
    outer_ids = []
    for ring_index, z in enumerate(stations):
        outer_row = []
        for angle_index, theta in enumerate(angles):
            outer_r = rings_outer[ring_index][angle_index]
            outer_row.append(len(vertices))
            vertices.append((outer_r * math.cos(theta), outer_r * math.sin(theta), z))
        outer_ids.append(outer_row)

    faces = []
    for row in range(len(stations) - 1):
        for col in range(REVOLUTION_STEPS):
            nxt = (col + 1) % REVOLUTION_STEPS
            faces.append((outer_ids[row][col], outer_ids[row][nxt], outer_ids[row + 1][nxt], outer_ids[row + 1][col]))
    bottom_center = len(vertices)
    vertices.append((0.0, 0.0, stations[0]))
    top_center = len(vertices)
    vertices.append((0.0, 0.0, stations[-1]))
    for col in range(REVOLUTION_STEPS):
        nxt = (col + 1) % REVOLUTION_STEPS
        last = len(stations) - 1
        faces.append((bottom_center, outer_ids[0][nxt], outer_ids[0][col]))
        faces.append((top_center, outer_ids[last][col], outer_ids[last][nxt]))

    mesh = bpy.data.meshes.new(f"{params['candidate_id']}_body_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    _recalc_normals(mesh)
    variant = "cut_on" if cut_enabled else "cut_off"
    body = bpy.data.objects.new(f"{params['candidate_id']}_{variant}_Body", mesh)
    collection.objects.link(body)
    body["candidate_id"] = params["candidate_id"]
    body["geometry_source"] = "local unfolded primary spiral profile envelope"
    body["cut_enabled"] = bool(cut_enabled)
    body["p"] = params["p"]
    body["delta_theta_deg"] = params["delta_theta_deg"]
    body["num_units"] = params["num_units"]
    body["cable_count"] = 3
    body["length_unit"] = "mm"
    body["body_axis"] = "+Z"
    body["base_interface_flange_thickness_mm"] = flange_thickness
    body["minimum_tendon_wall_mm"] = float(params["minimum_tendon_wall_mm"])
    body["theory_centerline_length_mm"] = theory["centerline_length_mm"]
    body["discrete_chord_span_mm"] = length
    body["profile_step_mm"] = PROFILE_STEP_MM
    body["profile_station_merge_tolerance_mm"] = PROFILE_STATION_MERGE_TOL_MM
    body["revolution_steps"] = REVOLUTION_STEPS
    body["cut_proxy"] = "3-fold radial clipping; planes between tendon paths"
    body["cut_plane_offset_fraction"] = max(
        0.48,
        1.0 - percent_to_fraction(params["cable3_cut_pos_pct"])
        - 0.5 * percent_to_fraction(params["cable3_cut_size_pct"]),
    ) if cut_enabled else 1.0
    return body, {
        "theory": theory,
        "source_profile": source_metrics,
        "length_mm": length,
        "stations_mm": stations,
        "polygons": polygons,
    }


def _make_tapered_cylinder_mesh(name: str, start: Vector, end: Vector, r0: float, r1: float, sides: int = 32):
    direction = (end - start).normalized()
    helper = Vector((0.0, 0.0, 1.0)) if abs(direction.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    u = direction.cross(helper).normalized()
    v = direction.cross(u).normalized()
    vertices = []
    for center, radius in ((start, r0), (end, r1)):
        for index in range(sides):
            angle = 2.0 * math.pi * index / sides
            point = center + radius * (math.cos(angle) * u + math.sin(angle) * v)
            vertices.append(tuple(point))
    faces = []
    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple(range(sides, 2 * sides)))
    for index in range(sides):
        nxt = (index + 1) % sides
        faces.append((index, nxt, sides + nxt, sides + index))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    _recalc_normals(mesh)
    return mesh


def _new_cable_path(name: str, points: list[Vector], collection, bevel_depth: float = 0.12):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, vector in zip(spline.points, points):
        point.co = (vector.x, vector.y, vector.z, 1.0)
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    obj.hide_render = True
    obj["visualization_only"] = True
    return obj


def _apply_boolean(target, cutter, operation: str) -> None:
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    mod = target.modifiers.new(name=f"stage_a_{operation.lower()}", type="BOOLEAN")
    mod.operation = operation
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    cutter_mesh = cutter.data if cutter.type == "MESH" else None
    bpy.data.objects.remove(cutter, do_unlink=True)
    if cutter_mesh and cutter_mesh.users == 0:
        bpy.data.meshes.remove(cutter_mesh)
    _recalc_normals(target.data)


def build_candidate(params: dict, cable3_cut_enabled: bool) -> list[bpy.types.Object]:
    """Build the soft body, central elastic axis path, and three tendon paths."""
    cid = params["candidate_id"]
    variant = "cut_on" if cable3_cut_enabled else "cut_off"
    collection = bpy.data.collections.new(f"{cid}_{variant}")
    bpy.context.scene.collection.children.link(collection)
    body, details = _make_rotational_shell(params, cable3_cut_enabled, collection)
    length = details["length_mm"]
    theory = details["theory"]
    local = details["source_profile"]

    # Remove the three tapered tendon channels with Blender's exact boolean solver.
    tip_center_r = 0.5 * local["local_tip_diameter_mm"] * percent_to_fraction(params["tip_hole_pos_pct"])
    base_center_r = 0.5 * local["local_base_diameter_mm"] * percent_to_fraction(params["base_hole_pos_pct"])
    start_extension, end_extension = 5.0, 5.0
    paths = []
    cutter_vertices = []
    cutter_faces = []
    hole_r0 = 0.5 * params["tip_hole_diameter_mm"]
    hole_r1 = 0.5 * params["base_hole_diameter_mm"]
    for index, degrees in enumerate((0.0, 120.0, 240.0)):
        angle = math.radians(degrees)
        direction = Vector((math.cos(angle), math.sin(angle), 0.0))
        start = direction * tip_center_r + Vector((0.0, 0.0, -start_extension))
        end = direction * base_center_r + Vector((0.0, 0.0, length + end_extension))
        path_start = direction * tip_center_r
        path_end = direction * base_center_r + Vector((0.0, 0.0, length))
        cutter_mesh = _make_tapered_cylinder_mesh(f"{cid}_hole_{index}", start, end, hole_r0, hole_r1)
        offset = len(cutter_vertices)
        cutter_vertices.extend(tuple(vertex.co) for vertex in cutter_mesh.vertices)
        cutter_faces.extend(tuple(offset + index for index in polygon.vertices) for polygon in cutter_mesh.polygons)
        bpy.data.meshes.remove(cutter_mesh)
        points = [path_start.lerp(path_end, step / 24.0) for step in range(25)]
        path_obj = _new_cable_path(f"{cid}_{variant}_CablePath_{index}", points, collection)
        path_obj["angle_deg"] = degrees
        path_obj["tip_position_pct"] = params["tip_hole_pos_pct"]
        path_obj["base_position_pct"] = params["base_hole_pos_pct"]
        paths.append(path_obj)

    # The final 4 mm of the TPU body is reinforced into a flat 68 mm interface
    # flange. Three base bores use captive M3 hex-nut pockets so bolts from the
    # rigid support plate clamp the flange without relying on TPU threads.
    mount_radius = float(params["base_mount_hole_radius_mm"])
    mount_hole_r = 0.5 * float(params["base_mount_hole_diameter_mm"])
    nut_af = float(params["base_mount_nut_pocket_af_mm"])
    nut_depth = float(params["base_mount_nut_pocket_depth_mm"])
    for degrees in params["base_mount_hole_angles_deg"]:
        angle = math.radians(float(degrees))
        center = Vector((mount_radius * math.cos(angle), mount_radius * math.sin(angle), 0.0))
        through = _make_tapered_cylinder_mesh(
            f"{cid}_base_mount_hole", center + Vector((0.0, 0.0, length - 5.0)),
            center + Vector((0.0, 0.0, length + 5.0)), mount_hole_r, mount_hole_r, sides=32,
        )
        offset = len(cutter_vertices)
        cutter_vertices.extend(tuple(vertex.co) for vertex in through.vertices)
        cutter_faces.extend(tuple(offset + index for index in polygon.vertices) for polygon in through.polygons)
        bpy.data.meshes.remove(through)
        nut_pocket = _make_tapered_cylinder_mesh(
            f"{cid}_base_mount_nut_pocket", center + Vector((0.0, 0.0, length - nut_depth)),
            center + Vector((0.0, 0.0, length + 5.0)), nut_af / math.sqrt(3.0),
            nut_af / math.sqrt(3.0), sides=6,
        )
        offset = len(cutter_vertices)
        cutter_vertices.extend(tuple(vertex.co) for vertex in nut_pocket.vertices)
        cutter_faces.extend(tuple(offset + index for index in polygon.vertices) for polygon in nut_pocket.polygons)
        bpy.data.meshes.remove(nut_pocket)
    all_cutters_mesh = bpy.data.meshes.new(f"{cid}_{variant}_cable_cutters_mesh")
    all_cutters_mesh.from_pydata(cutter_vertices, [], cutter_faces)
    all_cutters_mesh.validate(clean_customdata=True)
    _recalc_normals(all_cutters_mesh)
    all_cutters = bpy.data.objects.new(f"{cid}_{variant}_cable_cutters", all_cutters_mesh)
    collection.objects.link(all_cutters)
    _apply_boolean(body, all_cutters, "DIFFERENCE")

    axis_curve = _new_cable_path(
        f"{cid}_{variant}_ElasticAxisCenterline",
        [Vector((0.0, 0.0, length * i / 32.0)) for i in range(33)],
        collection,
        bevel_depth=0.10,
    )
    axis_curve["physical_axis_in_body"] = True
    body["cable_hole_count"] = 3
    body["body_end_plane_rule"] = "tip peak plateau end / base maximum-width plateau start"
    body["elastic_axis_representation"] = "continuous solid core merged into single-body cross-section; no internal union seam"
    body["hole_positions_pct"] = [params["tip_hole_pos_pct"], params["base_hole_pos_pct"]]
    body["elastic_axis_diameter_ratio"] = params["elastic_percent"] / 100.0
    body["theory_base_diameter_mm"] = theory["base_diameter_mm"]
    body["local_profile_tip_diameter_mm"] = local["local_tip_diameter_mm"]
    body["local_profile_base_diameter_mm"] = local["local_base_diameter_mm"]
    body["material_density_kg_m3"] = params["density_kg_m3"]
    return [body, axis_curve, *paths]


def _set_stl_selection(objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    meshes = [obj for obj in objects if obj.type == "MESH"]
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0] if meshes else None


def export_stl(objects: list[bpy.types.Object], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _set_stl_selection(objects)
    bpy.ops.wm.stl_export(
        filepath=str(path),
        export_selected_objects=True,
        global_scale=1.0,
        apply_modifiers=True,
        ascii_format=False,
    )
    bpy.ops.object.select_all(action="DESELECT")
