"""生成四组 Blender 对数螺旋候选及对应的 STL 变体。"""
from __future__ import annotations

import json
import math
import pathlib
import sys

import bpy
from mathutils import Vector

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from blender_geometry import build_candidate, export_stl  # noqa: E402
from geometry import count_units, local_profile_metrics, paper_metrics, percent_to_fraction  # noqa: E402

EXPECTED = {
    "A36": (36, 3.7794787730, 0.13961, 8.0),
    "A37": (37, 3.4591883310, 0.14013, 8.25),
    "B32": (32, 5.4367772850, 0.13699, 7.4),
    "B33": (33, 4.9562457360, 0.13774, 7.5833333333),
}


def load_candidate(path: pathlib.Path) -> dict:
    params = json.loads(path.read_text(encoding="utf-8"))
    if params["candidate_id"] not in EXPECTED:
        raise ValueError(f"出现未知的阶段 A 候选参数文件：{path.name}")
    expected_n, expected_a, expected_b, expected_theta_max = EXPECTED[params["candidate_id"]]
    if params["num_units"] != expected_n or count_units(params["theta_max_pi"], params["delta_theta_deg"]) != expected_n:
        raise ValueError(f"{path.stem}：theta_max_pi 计算出的单元数与冻结的整数单元数不符")
    if (abs(params["a_mm"] - expected_a) > 1e-6 or abs(params["b"] - expected_b) > 1e-6
            or abs(params["theta_max_pi"] - expected_theta_max) > 1e-9):
        raise ValueError(f"{path.stem}：参数与已审定的 V2 候选基线不一致")
    if params["p"] != 0.5 or params["delta_theta_deg"] != 30.0:
        raise ValueError(f"{path.stem}：第一阶段固定 p=0.5、delta_theta=30°")
    if params.get("fit_basis") != "local_discrete_profile":
        raise ValueError(f"{path.stem}：候选需标记为针对本地离散轮廓拟合")
    if not params.get("clip_at_peak_planes"):
        raise ValueError(f"{path.stem}：候选必须在完整尖端/基部截面处裁切外伸尾部")
    if params["two_cable"] or params["cable_count"] != 3:
        raise ValueError(f"{path.stem}：候选必须采用三腱结构")
    if params["minimum_tendon_wall_mm"] < 0.8:
        raise ValueError(f"{path.stem}：腱道径向余量不得低于 0.8 mm 的几何设计值")
    for key in ("tip_hole_pos_pct", "base_hole_pos_pct", "cable3_cut_pos_pct", "cable3_cut_size_pct"):
        params[key + "_fraction"] = percent_to_fraction(params[key])
    params["theory_metrics"] = paper_metrics(
        params["a_mm"], params["b"], params["num_units"], params["delta_theta_deg"]
    )
    params["local_profile_metrics"] = local_profile_metrics(
        params["a_mm"], params["b"], params["num_units"], params["delta_theta_deg"]
    )
    fit = params["fitted_local_profile_mm"]
    measured_height = params["local_profile_metrics"]["discrete_axis_span_mm"]
    measured_base = params["local_profile_metrics"]["local_base_diameter_mm"]
    measured_tip = params["local_profile_metrics"]["local_tip_diameter_mm"]
    if (abs(measured_height - fit["printable_body_height"]) > 0.05
            or abs(measured_base - fit["base_diameter"]) > 0.01
            or abs(measured_tip - fit["tip_diameter"]) > 0.01):
        raise ValueError(f"{path.stem}：候选 JSON 中的本地轮廓拟合结果与当前生成器不一致")
    if (abs(measured_height - params["target_centerline_length_mm"]) > 5.5
            or abs(measured_base - params["target_base_diameter_mm"]) > 1.0
            or abs(measured_tip - params["target_tip_diameter_mm"]) > 0.5):
        raise ValueError(f"{path.stem}：本地离散轮廓不满足冻结的 CAD 目标尺寸")
    return params


def _prepare_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != bpy.context.scene.collection.name:
            bpy.data.collections.remove(collection)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1500
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene["model_length_unit"] = "mm"
    scene["model_axis"] = "+Z"
    scene["generator_version"] = "0.4.0"


def _render_comparison(results: list[dict], output_path: pathlib.Path) -> None:
    _prepare_scene()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.background_type = "WORLD"
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.cavity_ridge_factor = 1.4
    scene.display.shading.cavity_valley_factor = 1.0
    scene.display.shading.show_shadows = True
    scene.world.color = (0.87, 0.89, 0.92)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    names = ("A36", "A37", "B32", "B33")
    colors = ((0.16, 0.48, 0.78, 1.0), (0.25, 0.67, 0.56, 1.0),
              (0.92, 0.52, 0.18, 1.0), (0.69, 0.32, 0.62, 1.0))
    for index, candidate_id in enumerate(names):
        stl_path = pathlib.Path(results[index]["variants"]["cut_off"]["stl_path"])
        before = set(bpy.data.objects)
        bpy.ops.wm.stl_import(filepath=str(stl_path))
        created = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
        if not created:
            raise RuntimeError(f"无法导入用于比较的网格：{stl_path}")
        offset = (index - 1.5) * 78.0
        for obj in created:
            obj.location.x += offset
            mat = bpy.data.materials.new(f"{candidate_id}_preview_material")
            mat.diffuse_color = colors[index]
            obj.data.materials.append(mat)
        bpy.ops.object.text_add(location=(offset - 18.0, -45.0, -35.0))
        label = bpy.context.object
        label.name = f"Label_{candidate_id}"
        label.data.body = candidate_id
        label.data.align_x = "CENTER"
        label.data.size = 11.0
        label.rotation_euler[0] = math.radians(90.0)
        label.data.extrude = 0.2
    bpy.ops.object.camera_add(location=(530.0, -1150.0, 830.0))
    camera = bpy.context.object
    camera.name = "Comparison_camera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 1000.0
    camera.data.clip_end = 5000.0
    camera.rotation_euler = (Vector((0.0, 0.0, 250.0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.8, 0.8, 0.8)
    scene.render.filepath = str(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)


def generate_candidates(candidate_dir: str, output_dir: str) -> list[dict]:
    source = pathlib.Path(candidate_dir)
    output = pathlib.Path(output_dir).resolve()
    blend_dir = output / "blend"
    stl_dir = output / "stl"
    blend_dir.mkdir(parents=True, exist_ok=True)
    stl_dir.mkdir(parents=True, exist_ok=True)
    _prepare_scene()
    results = []
    candidate_files = sorted(source.glob("*.json"))
    if {path.stem for path in candidate_files} != set(EXPECTED):
        raise ValueError("候选输入目录必须且只能包含 A36、A37、B32、B33")

    for config_path in candidate_files:
        params = load_candidate(config_path)
        _prepare_scene()
        variants = {}
        objects_by_variant = {}
        for enabled, key in ((True, "cut_on"), (False, "cut_off")):
            objects = build_candidate(params, cable3_cut_enabled=enabled)
            body = next(obj for obj in objects if obj.type == "MESH" and obj.name.endswith("_Body"))
            mesh_objects = [obj for obj in objects if obj.type == "MESH"]
            stl_path = stl_dir / f"{params['candidate_id']}_{key}.stl"
            export_stl(mesh_objects, stl_path)
            variants[key] = {
                "stl_path": str(stl_path),
                "cable3_cut_enabled": enabled,
                "cable_path_angles_deg": [0.0, 120.0, 240.0],
                "object_names": [obj.name for obj in objects],
            }
            objects_by_variant[key] = objects
            collection = bpy.data.collections.get(f"{params['candidate_id']}_{key}")
            if key == "cut_off" and collection:
                collection.hide_viewport = True
                collection.hide_render = True
        blend_path = blend_dir / f"{params['candidate_id']}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        results.append({
            "candidate_id": params["candidate_id"],
            "num_units": params["num_units"],
            "cable_count": 3,
            "fit_basis": params["fit_basis"],
            "fitted_local_profile_mm": params["fitted_local_profile_mm"],
            "local_profile_metrics": params["local_profile_metrics"],
            "theory_metrics": params["theory_metrics"],
            "blend_path": str(blend_path),
            "objects": {
                "body": f"{params['candidate_id']}_cut_on_Body / {params['candidate_id']}_cut_off_Body",
                "elastic_axis": f"{params['candidate_id']}_cut_on_ElasticAxisCenterline",
                "cable_paths": ", ".join(f"{params['candidate_id']}_cut_on_CablePath_{i}" for i in range(3)),
            },
            "variants": variants,
        })
    _render_comparison(results, output / "comparison.png")
    print(f"已生成 {len(results)} 组候选，输出目录：{output}")
    return results


def main() -> None:
    result = generate_candidates(str(HERE / "candidates"), str(REPO / "local" / "spiral-soft-arm" / "stage-a"))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
