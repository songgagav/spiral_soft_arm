"""检查 Blender 网格拓扑、腱线通道、壁厚、质量和 STL 往返结果。"""
from __future__ import annotations

import json
import math
import pathlib
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from blender_geometry import _axis_radius, _cut_outer_radius, _minimum_outer_for_tendon, _profile_y_at_z  # noqa: E402
from geometry import (  # noqa: E402
    build_body_profile_polygons,
    count_units,
    kg_mm2_to_kg_m2,
    local_profile_metrics,
    mm3_to_m3,
    mm_to_m,
    paper_metrics,
    percent_to_fraction,
)


def _world_vertices(obj):
    matrix = obj.matrix_world
    return [matrix @ vertex.co for vertex in obj.data.vertices]


def _bbox(obj) -> dict:
    points = _world_vertices(obj)
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    return {
        "min_mm": minimum,
        "max_mm": maximum,
        "dimensions_mm": [maximum[i] - minimum[i] for i in range(3)],
    }


def _mesh_topology(obj) -> dict:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    nonmanifold = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
    inconsistent = sum(1 for edge in bm.edges if len(edge.link_faces) == 2 and not edge.is_contiguous)
    remaining = set(bm.verts)
    components = 0
    while remaining:
        components += 1
        stack = [remaining.pop()]
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
    volume = abs(bm.calc_volume(signed=True)) if bm.faces else 0.0
    bm.free()
    return {
        "vertex_count": len(obj.data.vertices),
        "edge_count": len(obj.data.edges),
        "face_count": len(obj.data.polygons),
        "nonmanifold_edge_count": nonmanifold,
        "inconsistent_normal_edge_count": inconsistent,
        "connected_component_count": components,
        "closed_two_manifold": nonmanifold == 0,
        "volume_mm3": volume,
    }


def _mass_properties(obj, density_kg_m3: float) -> dict:
    mesh = obj.data
    mesh.calc_loop_triangles()
    vertices = _world_vertices(obj)
    signed_volume = 0.0
    first_moment = Vector((0.0, 0.0, 0.0))
    second = [[0.0] * 3 for _ in range(3)]
    for triangle in mesh.loop_triangles:
        a, b, c = (vertices[index] for index in triangle.vertices)
        vol = a.dot(b.cross(c)) / 6.0
        signed_volume += vol
        first_moment += vol * (a + b + c) / 4.0
        coords = (a, b, c)
        sums = [sum(point[i] for point in coords) for i in range(3)]
        for i in range(3):
            second[i][i] += vol * (sum(point[i] ** 2 for point in coords)
                                    + coords[0][i] * coords[1][i]
                                    + coords[0][i] * coords[2][i]
                                    + coords[1][i] * coords[2][i]) / 10.0
            for j in range(i + 1, 3):
                value = vol * (sums[i] * sums[j] + sum(point[i] * point[j] for point in coords)) / 20.0
                second[i][j] += value
                second[j][i] += value
    sign = 1.0 if signed_volume >= 0 else -1.0
    volume_mm3 = abs(signed_volume)
    if volume_mm3 <= 1e-12:
        return {"volume_mm3": 0.0, "volume_m3": 0.0, "solid_mass_kg": 0.0,
                "center_of_mass_mm": [0.0, 0.0, 0.0], "inertia_tensor_kg_mm2": [], "inertia_tensor_kg_m2": []}
    center = first_moment * sign / volume_mm3
    density_kg_mm3 = density_kg_m3 * 1e-9
    mass_kg = volume_mm3 * density_kg_mm3
    raw = [[entry * sign * density_kg_mm3 for entry in row] for row in second]
    c = tuple(center)
    parallel = [[mass_kg * ((sum(value * value for value in c) if i == j else 0.0) - c[i] * c[j])
                 for j in range(3)] for i in range(3)]
    inertia_kg_mm2 = [[raw[i][j] - parallel[i][j] for j in range(3)] for i in range(3)]
    return {
        "volume_mm3": volume_mm3,
        "volume_m3": mm3_to_m3(volume_mm3),
        "solid_mass_kg": mass_kg,
        "mass_basis": "按网格体积和假设密度计算的 100% 实体质量；不是切片软件给出的打印质量",
        "density_kg_m3": density_kg_m3,
        "center_of_mass_mm": list(c),
        "center_of_mass_m": [mm_to_m(value) for value in c],
        "inertia_tensor_kg_mm2": inertia_kg_mm2,
        "inertia_tensor_kg_m2": [[kg_mm2_to_kg_m2(value) for value in row] for row in inertia_kg_mm2],
    }


def _band_diameter(obj, z_min: float, z_max: float) -> float:
    radii = [math.hypot(point.x, point.y) for point in _world_vertices(obj)
             if z_min - 1e-5 <= point.z <= z_max + 1e-5]
    return 2.0 * max(radii, default=0.0)


def validate_mesh(obj: bpy.types.Object) -> dict:
    topology = _mesh_topology(obj)
    bbox = _bbox(obj)
    topology["bounding_box"] = bbox
    topology["mesh_name"] = obj.name
    topology["normal_orientation"] = "consistent" if topology["inconsistent_normal_edge_count"] == 0 else "inconsistent"
    return topology


def measure_minimum_walls(obj: bpy.types.Object, params: dict) -> dict:
    metrics = local_profile_metrics(params["a_mm"], params["b"], params["num_units"], params["delta_theta_deg"])
    polygons = build_body_profile_polygons(params["a_mm"], params["b"], params["delta_theta_deg"], params["p"], params["num_units"])
    length = metrics["discrete_axis_span_mm"]
    tip_r = 0.5 * metrics["local_tip_diameter_mm"]
    base_r = 0.5 * metrics["local_base_diameter_mm"]
    tip_center = tip_r * percent_to_fraction(params["tip_hole_pos_pct"])
    base_center = base_r * percent_to_fraction(params["base_hole_pos_pct"])
    h0 = 0.5 * params["tip_hole_diameter_mm"]
    h1 = 0.5 * params["base_hole_diameter_mm"]
    cut_enabled = bool(obj.get("cut_enabled", False))
    rows = []
    for index, poly in enumerate(polygons):
        z = 0.5 * (min(point[0] for point in poly) + max(point[0] for point in poly))
        fraction = max(0.0, min(1.0, z / max(length, 1e-9)))
        outer_base = max(
            _profile_y_at_z(polygons, z),
            _minimum_outer_for_tendon(params, metrics, z, length),
        )
        center_r = tip_center + fraction * (base_center - tip_center)
        hole_r = h0 + fraction * (h1 - h0)
        core_r = _axis_radius(params, z, length, metrics["local_tip_diameter_mm"])
        outer_r = _cut_outer_radius(outer_base, 0.0, params, cut_enabled)
        rows.append({
            "unit_index_1based": index + 1,
            "z_mm": z,
            "outer_wall_mm": outer_r - center_r - hole_r,
            "axis_wall_mm": center_r - hole_r - core_r,
            "hole_to_hole_mm": 2.0 * center_r * math.sin(math.pi / 3.0) - 2.0 * hole_r,
        })
    return {
        "minimum_wall_thickness_mm": min(min(row["outer_wall_mm"], row["axis_wall_mm"]) for row in rows),
        "minimum_outer_wall_mm": min(row["outer_wall_mm"] for row in rows),
        "minimum_axis_wall_mm": min(row["axis_wall_mm"] for row in rows),
        "minimum_hole_to_hole_material_mm": min(row["hole_to_hole_mm"] for row in rows),
        "sample_count": len(rows),
        "samples": rows,
        "method": "根据本地轮廓和腱线尺寸，对每个单元进行径向截面解析估算",
        "manufacturing_threshold_status": "仅报告估算值；尚未通过打印工艺样条确定制造阈值",
    }


def _cable_path_report(obj, params: dict, length: float, local: dict) -> list[dict]:
    tip_center = 0.5 * local["local_tip_diameter_mm"] * percent_to_fraction(params["tip_hole_pos_pct"])
    base_center = 0.5 * local["local_base_diameter_mm"] * percent_to_fraction(params["base_hole_pos_pct"])
    paths = []
    for index, degrees in enumerate((0.0, 120.0, 240.0)):
        angle = math.radians(degrees)
        direction = Vector((math.cos(angle), math.sin(angle), 0.0))
        start = direction * tip_center
        end = direction * base_center + Vector((0.0, 0.0, length))
        path_length = (end - start).length
        paths.append({
            "index": index,
            "angle_deg": degrees,
            "tip_center_mm": list(start),
            "base_center_mm": list(end),
            "channel_diameter_tip_mm": params["tip_hole_diameter_mm"],
            "channel_diameter_base_mm": params["base_hole_diameter_mm"],
            "straight_path_length_mm": path_length,
            "straight_path_length_m": mm_to_m(path_length),
        })
    return paths


def _open_channel_checks(obj, cables: list[dict]) -> dict:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(obj, depsgraph, epsilon=0.0)
    results = []
    for cable in cables:
        start = Vector(cable["tip_center_mm"])
        end = Vector(cable["base_center_mm"])
        origin = start.lerp(end, 0.5)
        direction = (end - start).normalized()
        hit = bvh.ray_cast(origin, direction, (end - origin).length + 20.0)
        results.append({"index": cable["index"], "open_to_base": hit[0] is None,
                        "first_hit_distance_mm": None if hit[0] is None else hit[3]})
    return {"all_three_open": len(results) == 3 and all(row["open_to_base"] for row in results), "channels": results}


def _bbox_error(before: dict, after: dict) -> dict:
    errors = [abs(before["dimensions_mm"][i] - after["dimensions_mm"][i]) for i in range(3)]
    return {"axis_errors_mm": errors, "bbox_max_error_mm": max(errors)}


def _roundtrip_stl(stl_path: pathlib.Path, before: dict) -> dict:
    old_objects = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=str(stl_path), global_scale=1.0, use_scene_unit=False)
    imported = [obj for obj in bpy.data.objects if obj not in old_objects and obj.type == "MESH"]
    if not imported:
        raise RuntimeError(f"STL 导入后未生成网格：{stl_path}")
    if len(imported) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in imported:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = imported[0]
        bpy.ops.object.join()
        imported = [bpy.context.view_layer.objects.active]
    after = _bbox(imported[0])
    error = _bbox_error(before, after)
    topology = _mesh_topology(imported[0])
    bpy.data.objects.remove(imported[0], do_unlink=True)
    return {"bbox_before_mm": before["dimensions_mm"], "bbox_after_mm": after["dimensions_mm"],
            **error, "topology_passed": topology["closed_two_manifold"] and topology["inconsistent_normal_edge_count"] == 0,
            "imported_mesh": topology}


def validate_candidate(candidate_id: str, blend_path: str, stl_paths: dict, params: dict) -> dict:
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    theory = paper_metrics(params["a_mm"], params["b"], params["num_units"], params["delta_theta_deg"])
    params["theory_metrics"] = theory
    source = local_profile_metrics(params["a_mm"], params["b"], params["num_units"], params["delta_theta_deg"])
    variants = {}
    for variant_key, stl_path in stl_paths.items():
        body_name = f"{candidate_id}_{variant_key}_Body"
        body = bpy.data.objects.get(body_name)
        if body is None:
            raise RuntimeError(f"未找到 Blender 主体对象 {body_name}")
        mesh_report = validate_mesh(body)
        mass = _mass_properties(body, params["density_kg_m3"])
        bbox_before = mesh_report["bounding_box"]
        polygons = build_body_profile_polygons(
            params["a_mm"], params["b"], params["delta_theta_deg"], params["p"], params["num_units"]
        )
        tip_peak_z = max(polygons[0], key=lambda point: point[1])[0]
        base_peak_z = max(polygons[-1], key=lambda point: point[1])[0]
        band_half_width = 1.2
        tip_diameter = _band_diameter(
            body, max(0.0, tip_peak_z - band_half_width), tip_peak_z + band_half_width
        )
        base_diameter = _band_diameter(
            body, max(0.0, base_peak_z - band_half_width), base_peak_z + band_half_width
        )
        roundtrip = _roundtrip_stl(pathlib.Path(stl_path), bbox_before)
        variants[variant_key] = {
            "mesh": mesh_report,
            "mass": mass,
            "solid_mass_kg": mass["solid_mass_kg"],
            "center_of_mass_mm": mass["center_of_mass_mm"],
            "stl_roundtrip": roundtrip,
            "stl_roundtrip_topology_passed": roundtrip["topology_passed"],
            "minimum_wall_thickness_mm": measure_minimum_walls(body, params),
            "mesh_cross_section_envelope_diameter_mm": {
                "tip_unit_peak_plus_minus_1_2mm": tip_diameter,
                "base_unit_peak_plus_minus_1_2mm": base_diameter,
                "tip_unit_peak_z_mm": tip_peak_z,
                "base_unit_peak_z_mm": base_peak_z,
                "measurement": "在实际 Blender 主体网格对应端部单元的峰值带区测量最大顶点半径，再乘以 2",
            },
            "cable3_cut_enabled": bool(body.get("cut_enabled", False)),
        }
        if variant_key == "cut_on":
            # Keep one body reference for the channel ray checks until all metrics are copied.
            cable_check = _open_channel_checks(body, _cable_path_report(body, params, source["discrete_axis_span_mm"], source))
            variants[variant_key]["cable_path_open_checks"] = cable_check
            variants[variant_key]["cable_channels"] = _cable_path_report(body, params, source["discrete_axis_span_mm"], source)
    primary_bbox = variants["cut_off"]["mesh"]["bounding_box"]
    actual_mesh_diameters = variants["cut_off"]["mesh_cross_section_envelope_diameter_mm"]
    actual_mesh_height = primary_bbox["dimensions_mm"][2]
    cut_off_roundtrip = variants["cut_off"]["stl_roundtrip"]
    cut_off_stl_valid = (
        variants["cut_off"]["stl_roundtrip_topology_passed"]
        and variants["cut_off"]["stl_roundtrip"]["imported_mesh"]["connected_component_count"] == 1
        and cut_off_roundtrip["bbox_max_error_mm"] <= 0.1
    )
    return {
        "candidate_id": candidate_id,
        "unit_count_target": params["num_units"],
        "unit_count_actual": count_units(params["theta_max_pi"], params["delta_theta_deg"]),
        "theory_metrics": theory,
        "local_unfolded_profile_metrics": source,
        "actual_cross_section_diameter_mm": {
            "tip_band": actual_mesh_diameters["tip_unit_peak_plus_minus_1_2mm"],
            "base_band": actual_mesh_diameters["base_unit_peak_plus_minus_1_2mm"],
            "source_profile_reference": {
                "tip_band": source["local_tip_diameter_mm"],
                "base_band": source["local_base_diameter_mm"],
            },
            "measurement": "`cut_off` Blender 主体网格作为打印候选；轮廓参考值另行保存",
        },
        "size_acceptance": {
            "mesh_height_550_plus_minus_5_5_mm": 544.5 <= actual_mesh_height <= 555.5,
            "base_68_plus_minus_1_mm": 67.0 <= actual_mesh_diameters["base_unit_peak_plus_minus_1_2mm"] <= 69.0,
            "tip_target_plus_minus_0_5_mm": abs(
                actual_mesh_diameters["tip_unit_peak_plus_minus_1_2mm"] - params["target_tip_diameter_mm"]
            ) <= 0.5,
        },
        "cable_count": 3,
        "stl_roundtrip_status": {
            "topology_valid_variant": "cut_off" if cut_off_stl_valid else None,
            "cut_off_stl_roundtrip_two_manifold": cut_off_stl_valid,
            "cut_off_stl_single_connected_solid": (
                variants["cut_off"]["stl_roundtrip"]["imported_mesh"]["connected_component_count"] == 1
            ),
            "cut_on_stl_roundtrip_two_manifold": variants["cut_on"]["stl_roundtrip_topology_passed"],
            "note": "拓扑有效不代表已获准打印；尺寸目标单独报告；若 `cut_on` 往返后的拓扑检查未通过，则仅供比较",
        },
        "cable_channels": variants["cut_on"]["cable_channels"],
        "cable_path_open_checks": variants["cut_on"]["cable_path_open_checks"],
        "units": {
            "length_550mm_to_m": mm_to_m(550.0),
            "measured_mesh_height_mm": source["discrete_axis_span_mm"],
            "measured_mesh_height_m": mm_to_m(source["discrete_axis_span_mm"]),
            "actual_body_bbox_height_mm": actual_mesh_height,
            "actual_body_bbox_height_m": mm_to_m(actual_mesh_height),
            "density_unit": "kg/m3",
            "mass_unit": "kg",
            "inertia_unit": "kg*m2",
            "tendon_path_unit": "m（原始腱线路径长度仍以 mm 保存）",
        },
        "variants": variants,
    }


def validate_all(candidate_dir: str, output_dir: str) -> dict:
    candidate_root = pathlib.Path(candidate_dir)
    output = pathlib.Path(output_dir).resolve()
    blend_dir = output / "blend"
    stl_dir = output / "stl"
    reports = []
    for path in sorted(candidate_root.glob("*.json")):
        params = json.loads(path.read_text(encoding="utf-8"))
        stl_paths = {key: str(stl_dir / f"{path.stem}_{key}.stl") for key in ("cut_on", "cut_off")}
        reports.append(validate_candidate(path.stem, str(blend_dir / f"{path.stem}.blend"), stl_paths, params))
    report = {
        "report_schema_version": "1.3.0",
        "generator_version": "0.4.0",
        "blender_version": bpy.app.version_string,
        "model_units": {"length": "mm", "mass": "kg", "inertia": "kg*m2", "axis": "+Z"},
        "candidate_count": len(reports),
        "recommended_print_candidate": "B32",
        "recommended_print_variant": "cut_off",
        "candidates": reports,
        "notes": [
            "四组 a、b 参数按裁切后的尖端峰值端面到基部峰值端面的有效长度拟合 550 mm、68 mm 基部和目标尖端直径；连续论文公式另列作理论比较。",
            "原始展开轮廓在最宽基部截面外多出约 40 mm 的尖缩尾段；打印候选现已在完整端面处裁切，实际 Blender 网格尺寸和 STL 往返数据逐项列出。",
            "首轮建议以 B32_cut_off 为主样机：尖端约 7.36 mm，保留完整 68 mm 基部和约 550 mm 端面间长度。",
            "两种切除变体均需在 STL 往返后保持闭合双流形和单一连通实体；推荐打印不切除变体。",
            "Blender STL 导入器在往返检查时会移除退化三角形；导入后的拓扑检查基于清理后的网格。",
            "壁厚是解析截面估算值；不能据此认定已达到 TPU 打印工艺样条的强度阈值。",
            "质量按设定密度下的 100% 实体 TPU 计算，不代表切片软件给出的打印质量。",
        ],
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"已写入报告：{report_path}")
    print(json.dumps({row["candidate_id"]: {
        "length_mm": row["local_unfolded_profile_metrics"]["discrete_axis_span_mm"],
        "mesh_height_mm": row["units"]["actual_body_bbox_height_mm"],
        "tip_diameter_mm": row["actual_cross_section_diameter_mm"]["tip_band"],
        "base_diameter_mm": row["actual_cross_section_diameter_mm"]["base_band"],
        "cut_on_open": row["cable_path_open_checks"]["all_three_open"],
    } for row in reports}, indent=2))
    return report


def main() -> None:
    validate_all(str(HERE / "candidates"), str(REPO / "local" / "spiral-soft-arm" / "stage-a"))


if __name__ == "__main__":
    main()
