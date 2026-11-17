from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
import cadquery as cq
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def _triangles(shape: Any, offset: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> list[list[tuple[float, float, float]]]:
    vertices, facets = shape.tessellate(1.6, 0.35)
    xyz = [
        (vertex.x + offset[0], vertex.y + offset[1], vertex.z + offset[2])
        for vertex in vertices
    ]
    return [[xyz[index] for index in facet] for facet in facets]


def _add(
    ax: Any,
    shape: Any,
    color: str,
    alpha: float,
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    mesh = Poly3DCollection(
        _triangles(shape, offset),
        facecolor=color,
        edgecolor="none",
        linewidth=0.0,
        alpha=alpha,
    )
    ax.add_collection3d(mesh)


def _figure(title: str) -> tuple[Any, Any]:
    figure = plt.figure(figsize=(14, 9), dpi=110, facecolor="#eef3f6")
    ax = figure.add_subplot(111, projection="3d")
    ax.set_facecolor("#eef3f6")
    ax.set_title(title, fontsize=15, pad=18)
    ax.set_xlabel("X / mm")
    ax.set_ylabel("Y / mm")
    ax.set_zlabel("Z / mm")
    ax.grid(True, alpha=0.20)
    return figure, ax


def _save(figure: Any, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


def _group_style(result: Any, name: str) -> tuple[str, float]:
    if name in result.arm_component_names:
        return "#e6c97a", 0.92
    if name in result.drive_component_names:
        return "#315d78", 0.92
    if "cover_panel" in name or "root_guard" in name:
        return "#69aebe", 0.20
    if "cover_frame" in name:
        return "#3b7381", 0.46
    if name in result.fixed_component_names:
        return "#7a8790", 0.34
    if "canister" in name or "bottom_lid" in name:
        return "#66a6b8", 0.22
    if "21700" in name:
        return "#2caa74", 0.90
    if "C610" in name or "controller" in name:
        return "#20262d", 0.90
    if "UPS" in name:
        return "#c24c55", 0.90
    if "regulator" in name:
        return "#d18b32", 0.90
    if "PD1002" in name:
        return "#7758ad", 0.90
    if "ideal_diode" in name:
        return "#37a6a1", 0.90
    if "BMS" in name:
        return "#c5a735", 0.90
    if "M28" in name or "M12" in name:
        return "#168b87", 0.92
    if "carrier" in name or "shelf" in name or "backing" in name or "rail" in name:
        return "#526875", 0.70
    return "#80a86b", 0.72


def _full_review(result: Any, path: Path) -> None:
    figure = plt.figure(figsize=(15.5, 9.0), dpi=150, facecolor="#f4f6f8")
    figure.suptitle("V27 完整总装｜1 m 四段臂体 · 三路 M2006 · 根部电子仓", fontsize=18, y=0.97)
    ax_full = figure.add_subplot(1, 2, 1, projection="3d")
    ax_root = figure.add_subplot(1, 2, 2, projection="3d")
    for ax in (ax_full, ax_root):
        ax.set_facecolor("#f4f6f8")
        ax.set_axis_off()
        ax.set_proj_type("ortho")

    selected = [
        *result.arm_component_names,
        *result.drive_component_names,
        *result.fixed_component_names,
        *result.electronics_component_names,
    ]
    for name in selected:
        color, alpha = _group_style(result, name)
        if name == "fixed_top_plate":
            alpha = 0.34
        elif name.startswith("fixed_"):
            alpha = 0.82
        if "cover_panel" in name or "root_guard" in name:
            alpha = 0.16
        elif "cover_frame" in name:
            alpha = 0.34
        elif "canister" in name or "bottom_lid" in name:
            alpha = 0.10
        _add(ax_full, result.components[name], color, alpha)

    ax_full.set_xlim(-155, 155)
    ax_full.set_ylim(-155, 155)
    ax_full.set_zlim(-270, 1050)
    ax_full.set_box_aspect((310, 310, 1320))
    ax_full.view_init(elev=8, azim=35)
    ax_full.set_title("整机全貌（等比例）", fontsize=13, pad=8)
    ax_full.text2D(0.04, 0.08, "臂体名义长度 1,000 mm", transform=ax_full.transAxes, fontsize=11)

    root_names = [
        "arm_root_flange",
        "arm_root_backing",
        "arm_register",
        "arm_tendon_terminals",
        *result.drive_component_names,
        "fixed_top_plate",
        "fixed_root_receiver",
        *(f"fixed_wet_spool_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_shaft_{index:02d}" for index in range(1, 4)),
        *(f"fixed_bevel_pod_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_support_land_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_support_cartridge_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_support_cartridge_screw_{index:02d}_{screw:02d}" for index in range(1, 4) for screw in range(1, 3)),
        *(f"fixed_bevel_input_envelope_{index:02d}" for index in range(1, 4)),
        *(f"fixed_bevel_output_envelope_{index:02d}" for index in range(1, 4)),
        *(f"fixed_oil_seal_{side}_{index:02d}" for index in range(1, 4) for side in ("drive_side", "outboard")),
        *(f"fixed_labyrinth_{side}_{index:02d}" for index in range(1, 4) for side in ("drive_side", "outboard")),
        *(f"fixed_spool_retainer_{index:02d}" for index in range(1, 4)),
        *(f"fixed_spool_drive_pin_{index:02d}" for index in range(1, 4)),
        *result.electronics_component_names,
    ]
    for name in root_names:
        color, alpha = _group_style(result, name)
        if name == "fixed_top_plate":
            alpha = 0.28
        elif name.startswith("fixed_"):
            alpha = 0.78
        if "cover_panel" in name or "root_guard" in name:
            alpha = 0.16
        elif "cover_frame" in name:
            alpha = 0.34
        elif "canister" in name or "bottom_lid" in name:
            alpha = 0.10
        _add(ax_root, result.components[name], color, alpha)
    ax_root.set_xlim(-88, 88)
    ax_root.set_ylim(-88, 88)
    ax_root.set_zlim(-260, 34)
    ax_root.set_box_aspect((176, 176, 294))
    ax_root.view_init(elev=13, azim=36)
    ax_root.set_title("根部放大：机械传动与电子仓", fontsize=13, pad=8)
    ax_root.text2D(
        0.02,
        0.10,
        "电机轴 Z 向竖装；线盘轴为水平切向，两轴垂直。\n线缆从卷筒下侧切线沿径向直达根部线孔。\n直角齿轮仅为无齿形包络，尚未完成齿形/强度核定。",
        transform=ax_root.transAxes,
        fontsize=9,
        color="#263746",
        bbox={"facecolor": "white", "alpha": 0.78, "edgecolor": "#cbd4db"},
    )
    ax_root.text2D(
        0.02,
        0.03,
        "仓内：4×21700｜UPS/PD1002｜STM32｜C610",
        transform=ax_root.transAxes,
        fontsize=10,
    )
    figure.subplots_adjust(left=0.01, right=0.99, top=0.91, bottom=0.04, wspace=0.02)
    _save(figure, path)


def _exploded_review(result: Any, path: Path) -> None:
    figure = plt.figure(figsize=(16.0, 9.0), dpi=150, facecolor="#f4f6f8")
    figure.suptitle("V27 模块化拆卸示意｜臂体与三电机模块独立更换", fontsize=18, y=0.97)
    ax_full = figure.add_subplot(1, 2, 1, projection="3d")
    ax_root = figure.add_subplot(1, 2, 2, projection="3d")
    for ax in (ax_full, ax_root):
        ax.set_facecolor("#f4f6f8")
        ax.set_axis_off()
        ax.set_proj_type("ortho")

    selected = [
        *result.arm_component_names,
        *result.drive_component_names,
        *result.fixed_component_names,
        *result.electronics_component_names,
    ]
    for name in selected:
        color, alpha = _group_style(result, name)
        if name in result.arm_component_names:
            offset = (0.0, 0.0, 90.0)
            alpha = 0.98
        elif name in result.drive_component_names:
            offset = (0.0, 0.0, -110.0)
            alpha = 0.98
        else:
            offset = (0.0, 0.0, 0.0)
            if name == "fixed_top_plate":
                alpha = 0.34
            elif name.startswith("fixed_"):
                alpha = 0.82
            elif "canister" in name or "bottom_lid" in name:
                alpha = 0.10
        _add(ax_full, result.components[name], color, alpha, offset)
    ax_full.set_xlim(-160, 160)
    ax_full.set_ylim(-160, 160)
    ax_full.set_zlim(-360, 1160)
    ax_full.set_box_aspect((320, 320, 1520))
    ax_full.view_init(elev=9, azim=35)
    ax_full.set_title("整体拆分位置（全长视图）", fontsize=13, pad=8)

    root_names = [
        "arm_root_flange",
        "arm_root_backing",
        "arm_register",
        "arm_tendon_terminals",
        *result.drive_component_names,
        "fixed_top_plate",
        "fixed_root_receiver",
        *(f"fixed_wet_spool_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_shaft_{index:02d}" for index in range(1, 4)),
        *(f"fixed_bevel_pod_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_support_land_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_support_cartridge_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_support_cartridge_screw_{index:02d}_{screw:02d}" for index in range(1, 4) for screw in range(1, 3)),
        *(f"fixed_bevel_input_envelope_{index:02d}" for index in range(1, 4)),
        *(f"fixed_bevel_output_envelope_{index:02d}" for index in range(1, 4)),
        *(f"fixed_oil_seal_{side}_{index:02d}" for index in range(1, 4) for side in ("drive_side", "outboard")),
        *(f"fixed_labyrinth_{side}_{index:02d}" for index in range(1, 4) for side in ("drive_side", "outboard")),
        *(f"fixed_spool_retainer_{index:02d}" for index in range(1, 4)),
        *(f"fixed_spool_drive_pin_{index:02d}" for index in range(1, 4)),
        *result.electronics_component_names,
    ]
    for name in root_names:
        color, alpha = _group_style(result, name)
        if name in result.arm_component_names or name in {
            "arm_root_flange",
            "arm_root_backing",
            "arm_register",
            "arm_tendon_terminals",
        }:
            offset = (0.0, 0.0, 90.0)
            alpha = 0.98
        elif name in result.drive_component_names:
            offset = (0.0, 0.0, -110.0)
            alpha = 0.98
        else:
            offset = (0.0, 0.0, 0.0)
            if name == "fixed_top_plate":
                alpha = 0.30
            elif name.startswith("fixed_"):
                alpha = 0.80
            elif "canister" in name or "bottom_lid" in name:
                alpha = 0.10
        _add(ax_root, result.components[name], color, alpha, offset)
    ax_root.set_xlim(-92, 92)
    ax_root.set_ylim(-92, 92)
    ax_root.set_zlim(-310, 390)
    ax_root.set_box_aspect((184, 184, 700))
    ax_root.view_init(elev=12, azim=36)
    ax_root.set_title("根部拆卸动作放大（远端臂体截略）", fontsize=13, pad=8)
    ax_root.text2D(0.02, 0.92, "↑ +Z：四段臂体模块从根部拔出", transform=ax_root.transAxes, color="#8a6415", fontsize=10)
    ax_root.text2D(0.02, 0.86, "↓ −Z：三台 M2006 与安装板整体抽出", transform=ax_root.transAxes, color="#244d68", fontsize=10)

    figure.text(
        0.5,
        0.025,
        "金色：整根四段臂体模块　｜　灰色：固定轴系、轴封、线轮及电子仓　｜　蓝色：三电机公共安装板模块",
        ha="center",
        fontsize=10,
    )
    figure.subplots_adjust(left=0.01, right=0.99, top=0.91, bottom=0.07, wspace=0.02)
    _save(figure, path)


def _root_review(result: Any, path: Path) -> None:
    figure, ax = _figure("V27 root quick-change — register, asymmetric dowels and six M5 services")
    for name in (
        "arm_root_flange",
        "arm_root_backing",
        "arm_register",
        "arm_tendon_terminals",
        "fixed_root_receiver",
        "fixed_top_plate",
    ):
        color, alpha = _group_style(result, name)
        _add(ax, result.components[name], color, 0.78 if name != "fixed_top_plate" else 0.22)
    for shape in result.root.dowel_proxies:
        _add(ax, shape, "#c74232", 0.95)
    for shape in result.root.tool_envelopes:
        _add(ax, shape, "#4f8fc4", 0.12)
    ax.set_xlim(-130, 130)
    ax.set_ylim(-130, 130)
    ax.set_zlim(-16, 32)
    ax.set_box_aspect((260, 260, 48))
    ax.view_init(elev=35, azim=38)
    _save(figure, path)


def _drive_section_review(result: Any, path: Path) -> None:
    figure, ax = _figure("V27 单路传动方向审查｜竖直电机轴 × 水平切向线盘轴")
    names = [
        "removable_M2006_01",
        "removable_M2006_cross_pin_01",
        "fixed_shaft_01",
        "fixed_output_shaft_01",
        "fixed_bevel_pod_01",
        "fixed_output_support_land_01",
        "fixed_output_support_cartridge_01",
        "fixed_output_support_cartridge_screw_01_01",
        "fixed_output_support_cartridge_screw_01_02",
        "fixed_bevel_input_envelope_01",
        "fixed_bevel_output_envelope_01",
        "fixed_bearing_inner_01",
        "fixed_bearing_outer_01",
        "fixed_oil_seal_drive_side_01",
        "fixed_oil_seal_outboard_01",
        "fixed_labyrinth_drive_side_01",
        "fixed_labyrinth_outboard_01",
        "fixed_spool_retainer_01",
        "fixed_spool_drive_pin_01",
        "fixed_wet_spool_01",
        "fixed_top_plate",
    ]
    palette = {
        "M2006": "#2d5873",
        "coupling": "#8954a1",
        "shaft": "#d6a936",
        "bearing": "#353b40",
        "seal": "#c7493a",
        "labyrinth": "#d5792c",
        "gear": "#c54c34",
        "spool": "#d6a936",
        "plate": "#7a8790",
    }
    for name in names:
        if "bevel_input_envelope" in name:
            key, alpha = "gear", 0.92
        elif "bevel_output_envelope" in name:
            key, alpha = "gear", 0.82
        elif "bevel_pod" in name or "output_support_pod" in name:
            key, alpha = "plate", 0.10
        else:
            key = next((item for item in palette if item.lower() in name.lower()), "plate")
            alpha = 0.08 if name == "fixed_top_plate" else 0.92
        _add(ax, result.components[name], palette[key], alpha)
    axis = result.fixed.axes[0]
    center = axis.spool_center
    tendon_end = axis.root_inlet
    tendon_start = axis.tangent_point
    ax.plot(
        [tendon_start[0], tendon_end[0]],
        [tendon_start[1], tendon_end[1]],
        [tendon_start[2], tendon_end[2]],
        color="#c73535",
        linewidth=3.0,
        marker="o",
        markersize=4,
        label="拉索直线段",
    )
    motor_origin = axis.motor_center
    motor_direction = tuple(value * 20.0 for value in axis.motor_axis)
    spool_direction = tuple(value * 20.0 for value in axis.spool_axis)
    ax.quiver(*motor_origin, *motor_direction, color="#1f6da8", linewidth=2.5, arrow_length_ratio=0.18)
    ax.quiver(*center, *spool_direction, color="#dd7c23", linewidth=2.5, arrow_length_ratio=0.18)
    ax.text(
        motor_origin[0],
        motor_origin[1],
        motor_origin[2] + 22.0,
        "电机轴 Z",
        color="#1f6da8",
        fontsize=9,
    )
    ax.text(
        center[0] + spool_direction[0] * 1.1,
        center[1] + spool_direction[1] * 1.1,
        center[2] + spool_direction[2] * 1.1,
        "线盘轴 T",
        color="#b45a0d",
        fontsize=9,
    )
    route_points = (center, axis.tangent_point, axis.root_inlet)
    x_margin = 14.0
    y_margin = 26.0
    x_limits = (
        min(point[0] for point in route_points) - x_margin,
        max(point[0] for point in route_points) + x_margin,
    )
    y_limits = (
        min(point[1] for point in route_points) - y_margin,
        max(point[1] for point in route_points) + y_margin,
    )
    ax.set_xlim(*x_limits)
    ax.set_ylim(*y_limits)
    ax.set_zlim(-112, 34)
    ax.set_box_aspect((x_limits[1] - x_limits[0], y_limits[1] - y_limits[0], 146))
    ax.view_init(elev=24, azim=36)
    ax.text2D(
        0.02,
        0.96,
        "蓝：竖直电机轴　橙：水平线盘轴（相互垂直）　红：线盘下侧切点至根部线孔的直线路段",
        transform=ax.transAxes,
        fontsize=10,
        color="#263746",
        bbox={"facecolor": "white", "alpha": 0.88, "edgecolor": "#cbd4db"},
    )
    _save(figure, path)


def _drive_details_sheet(result: Any, path: Path) -> None:
    figure = plt.figure(figsize=(20, 9), dpi=190, facecolor="#f1f4f6")
    figure.suptitle(
        "V27 M2006—轴套—直角齿轮—轴封—湿侧线盘｜CAD 细节审查",
        fontsize=18,
        y=0.97,
        color="#263746",
    )
    axes = [
        figure.add_subplot(1, 3, index, projection="3d")
        for index in (1, 2, 3)
    ]
    view_parts = [
        (
            "01  M2006 电机与一体输入轴",
            [
                ("removable_M2006_01", "#315d78", 0.66),
                ("removable_M2006_cross_pin_01", "#cf5548", 1.0),
                ("fixed_shaft_01", "#d3a53a", 0.82),
            ],
            "发布外形代理：电机壳 Ø24.4 × 47.8；D6 轴伸 17 mm\n"
            "一体输入轴：Ø15 座肩，D6 Ø6.2 × 13 深；平面 2.6 mm，轴平面 2.5 mm\n"
            "Ø2.8 可拆横销沿 D 平面法向；名义平面间隙 0.1 mm\n"
            "原独立套筒及 M3 紧定螺钉已取消；电机拆下后固定轴留在基座。",
        ),
        (
            "02  90° 伞齿轮与阶梯轴",
            [
                ("fixed_bevel_pod_01", "#9aa4aa", 0.12),
                ("fixed_output_support_land_01", "#9aa4aa", 0.10),
                ("fixed_output_support_cartridge_01", "#687d88", 0.92),
                ("fixed_output_support_cartridge_screw_01_01", "#42484c", 1.0),
                ("fixed_output_support_cartridge_screw_01_02", "#42484c", 1.0),
                ("fixed_shaft_01", "#d3a53a", 0.74),
                ("fixed_output_shaft_01", "#c79a34", 0.54),
                ("fixed_bevel_input_envelope_01", "#c24f38", 0.88),
                ("fixed_bevel_output_envelope_01", "#dc8242", 0.78),
                ("fixed_input_bearing_1_01", "#39434b", 0.86),
                ("fixed_input_bearing_2_01", "#5a6770", 0.82),
            ],
            "KHK SM1.25-25H × 2：25 齿、1:1、90°；图中仅为无齿形目录包络\n"
            "输入 Ø10 轴；输出 Ø10 轴，齿轮位为 Ø8 h6 D 平面 + M4 紧定。\n"
            "输入轴竖直，输出/线盘轴水平且相互垂直。",
        ),
        (
            "03  支承、双道轴封与湿侧线盘",
            [
                ("fixed_output_support_land_01", "#9aa4aa", 0.10),
                ("fixed_output_support_cartridge_01", "#687d88", 0.90),
                ("fixed_output_support_cartridge_screw_01_01", "#42484c", 1.0),
                ("fixed_output_support_cartridge_screw_01_02", "#42484c", 1.0),
                ("fixed_output_shaft_01", "#c79a34", 0.42),
                ("fixed_bearing_inner_01", "#39434b", 0.94),
                ("fixed_bearing_outer_01", "#5a6770", 0.94),
                ("fixed_oil_seal_drive_side_01", "#bf4b43", 0.88),
                ("fixed_oil_seal_outboard_01", "#cf6b5b", 0.88),
                ("fixed_labyrinth_drive_side_01", "#dc8b36", 0.92),
                ("fixed_labyrinth_outboard_01", "#e6a44f", 0.92),
                ("fixed_spool_retainer_01", "#54595c", 0.96),
                ("fixed_spool_drive_pin_01", "#2b8b8b", 0.98),
                ("fixed_wet_spool_01", "#d4aa48", 0.66),
            ],
            "固定土地留在基座；Ø26.8 通孔装 Ø26.4/Ø22.02 轴承筒，2 × M2.5 锁止\n"
            "Ø23/Ø20.5 × 1.5 油封止肩与轴承筒一体\n"
            "2 × 6900：10 × 22 × 6 mm；2 × NBR 油封：10 × 22 × 7 mm\n"
            "迷宫在油封外侧；线盘由 10.8×0.8 mm 轴肩与卡簧轴向保持，径向销传扭，端隙 0.2 mm。\n"
            "拆卸需先拔销；卡簧/槽尺寸仍须按供货件复核。\n"
            "拉索按切线直线进入根部线孔。\n"
            "轴封阻力、耐海水性和 5 m 水压性能尚未实测。",
        ),
    ]
    route_axis = result.fixed.axes[0]
    route_start = route_axis.tangent_point
    route_end = route_axis.root_inlet
    for index, (ax, (title, parts, note)) in enumerate(zip(axes, view_parts)):
        ax.set_facecolor("#f1f4f6")
        ax.set_axis_off()
        ax.set_proj_type("ortho")
        shapes = []
        for name, color, alpha in parts:
            shape = result.components[name]
            shapes.append(shape)
            _add(ax, shape, color, alpha)
        boxes = [shape.BoundingBox() for shape in shapes]
        xmin = min(box.xmin for box in boxes)
        xmax = max(box.xmax for box in boxes)
        ymin = min(box.ymin for box in boxes)
        ymax = max(box.ymax for box in boxes)
        zmin = min(box.zmin for box in boxes)
        zmax = max(box.zmax for box in boxes)
        if index == 2:
            xmin = min(xmin, route_start[0], route_end[0])
            xmax = max(xmax, route_start[0], route_end[0])
            ymin = min(ymin, route_start[1], route_end[1])
            ymax = max(ymax, route_start[1], route_end[1])
            zmin = min(zmin, route_start[2], route_end[2])
            zmax = max(zmax, route_start[2], route_end[2])
        span = max(xmax - xmin, ymax - ymin, zmax - zmin, 1.0)
        margin = max(4.0, span * 0.10)
        dx, dy, dz = (xmax - xmin + 2.0 * margin, ymax - ymin + 2.0 * margin, zmax - zmin + 2.0 * margin)
        ax.set_xlim(xmin - margin, xmax + margin)
        ax.set_ylim(ymin - margin, ymax + margin)
        ax.set_zlim(zmin - margin, zmax + margin)
        ax.set_box_aspect((dx, dy, dz))
        ax.view_init(elev=24, azim=38)
        ax.set_title(title, fontsize=12, color="#263746", pad=8)
        ax.text2D(
            0.02,
            0.025,
            note,
            transform=ax.transAxes,
            fontsize=9,
            color="#263746",
            bbox={"facecolor": "white", "alpha": 0.92, "edgecolor": "#cad3d9"},
        )

    start = route_start
    end = route_end
    axes[2].plot(
        [start[0], end[0]],
        [start[1], end[1]],
        [start[2], end[2]],
        color="#c73535",
        linewidth=3.0,
    )
    axes[2].text(
        start[0],
        start[1],
        start[2] + 2.0,
        "切线拉索 → 根部孔",
        color="#a42b2b",
        fontsize=8,
    )
    figure.text(
        0.5,
        0.015,
        "尺寸按当前 V27 CAD 合同值｜M2006 为发布尺寸包络代理｜伞齿轮未建齿形｜油封/迷宫未完成水下资格验证",
        ha="center",
        fontsize=10,
        color="#52616a",
    )
    figure.subplots_adjust(left=0.015, right=0.985, top=0.88, bottom=0.12, wspace=0.04)
    _save(figure, path)


def _electronics_review(result: Any, path: Path) -> None:
    figure, ax = _figure("V27 electronics bay — selected hardware and service interfaces")
    for name in result.electronics_component_names:
        color, alpha = _group_style(result, name)
        if "canister" in name or "bottom_lid" in name:
            alpha = 0.12
        _add(ax, result.components[name], color, alpha)
    for shape in result.service_clearance_shapes.values():
        _add(ax, shape, "#d23d38", 0.10)
    ax.text(-72, -72, -310, "Red: M28 plug service envelope", color="#a12623")
    ax.set_xlim(-78, 78)
    ax.set_ylim(-78, 78)
    ax.set_zlim(-330, -10)
    ax.set_box_aspect((156, 156, 320))
    ax.view_init(elev=13, azim=36)
    _save(figure, path)


def _cover_review(
    result: Any, path: Path, exploded_path: Path, opaque_path: Path
) -> None:
    figure = plt.figure(figsize=(16, 8.5), dpi=145, facecolor="#f4f6f8")
    figure.suptitle("V27 阶梯护甲根部包覆｜两道外凸环带、大面积观察口与服务分界", fontsize=17, y=0.97)
    axes = [
        figure.add_subplot(1, 2, index, projection="3d")
        for index in (1, 2)
    ]
    cover_names = [
        name
        for name in result.fixed_component_names
        if name.startswith("fixed_cover_") or name == "fixed_root_guard_hex"
    ]
    stable_names = [
        "fixed_top_plate",
        "fixed_common_motor_chamber",
        "fixed_root_receiver",
        *(f"fixed_wet_spool_{index:02d}" for index in range(1, 4)),
        *(f"fixed_bevel_pod_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_support_land_{index:02d}" for index in range(1, 4)),
        *(f"fixed_output_support_cartridge_{index:02d}" for index in range(1, 4)),
        *(f"fixed_oil_seal_{side}_{index:02d}" for index in range(1, 4) for side in ("drive_side", "outboard")),
        *(f"fixed_labyrinth_{side}_{index:02d}" for index in range(1, 4) for side in ("drive_side", "outboard")),
        *(f"fixed_spool_retainer_{index:02d}" for index in range(1, 4)),
        *(f"fixed_spool_drive_pin_{index:02d}" for index in range(1, 4)),
        *result.drive_component_names,
        *result.electronics_component_names,
    ]
    for ax in axes:
        ax.set_facecolor("#f4f6f8")
        ax.set_axis_off()
        ax.set_proj_type("ortho")
        for name in stable_names:
            if name not in result.components:
                continue
            color, alpha = _group_style(result, name)
            if "canister" in name or "bottom_lid" in name:
                alpha = 0.08
            elif name.startswith("fixed_"):
                alpha = 0.55
            _add(ax, result.components[name], color, alpha)
        for name in cover_names:
            color, alpha = _group_style(result, name)
            _add(ax, result.components[name], color, alpha)
        ax.set_xlim(-180, 180)
        ax.set_ylim(-180, 180)
        ax.set_zlim(-250, 80)
        ax.set_box_aspect((360, 360, 330))
        ax.view_init(elev=18, azim=35)
    axes[0].set_title("装配状态：肩部、环带与六面护甲", fontsize=12)
    axes[0].text2D(
        0.04,
        0.04,
        "两道外凸六边形环带｜两处大观察口｜下部可拆服务板｜外水连通｜非耐压壳",
        transform=axes[0].transAxes,
        fontsize=10,
        color="#263746",
        bbox={"facecolor": "white", "alpha": 0.82, "edgecolor": "#cbd4db"},
    )
    axes[1].set_title("拆卸示意：下部服务板连同环带肋条沿面法线取出", fontsize=12)
    detached = result.components["fixed_cover_lower_panel_05"].translate(cq.Vector(0.0, -55.0, 0.0))
    color, alpha = _group_style(result, "fixed_cover_panel_detached")
    _add(axes[1], detached, color, 0.40)
    figure.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.03, wspace=0.01)
    _save(figure, path)

    figure2 = plt.figure(figsize=(9, 7), dpi=140, facecolor="#f4f6f8")
    ax = figure2.add_subplot(111, projection="3d")
    ax.set_facecolor("#f4f6f8")
    ax.set_axis_off()
    for name in cover_names:
        color, alpha = _group_style(result, name)
        _add(ax, result.components[name], color, alpha)
    ax.set_xlim(-180, 180)
    ax.set_ylim(-180, 180)
    ax.set_zlim(-250, 80)
    ax.set_box_aspect((360, 360, 330))
    ax.view_init(elev=20, azim=35)
    ax.set_title("V27 阶梯护甲包覆附件｜半透明检查视图", fontsize=13, pad=10)
    _save(figure2, exploded_path)

    _cover_opaque_view(
        [(name, result.components[name]) for name in cover_names], opaque_path
    )


def _top_plate_cover_joint_review(result: Any, path: Path) -> None:
    """Render a magnified view of the three hidden ear-to-plate interfaces."""
    cfg = result.contract.integration["root_cover"]
    normals = tuple(float(value) for value in cfg["top_plate_attachment_normals_deg"])
    hole_radius = float(cfg["top_plate_attachment_hole_radius_mm"])
    ear_z0, ear_z1 = (
        float(value) for value in cfg["top_plate_attachment_z_bounds_mm"]
    )
    plate = result.components["fixed_top_plate"]
    plate_z0 = plate.BoundingBox().zmin
    figure = plt.figure(figsize=(15.5, 7.5), dpi=145, facecolor="#f4f6f8")
    figure.suptitle(
        "V27 顶板与包覆件隐藏固定耳｜三处连接局部放大",
        fontsize=17,
        y=0.96,
    )
    for slot, normal_deg in enumerate(normals, start=1):
        panel_index = int((normal_deg - 30.0) / 60.0) + 1
        panel_name = f"fixed_cover_upper_panel_{panel_index:02d}"
        angle = math.radians(normal_deg)
        x_mm, y_mm = hole_radius * math.cos(angle), hole_radius * math.sin(angle)
        ax = figure.add_subplot(1, 3, slot, projection="3d")
        ax.set_facecolor("#f4f6f8")
        ax.set_axis_off()
        ax.set_proj_type("ortho")
        local_clip = cq.Solid.makeBox(
            68.0,
            68.0,
            ear_z1 - plate_z0 + 28.0,
            cq.Vector(x_mm - 34.0, y_mm - 34.0, plate_z0 - 12.0),
        )
        plate_detail = plate.intersect(local_clip)
        panel_detail = result.components[panel_name].intersect(local_clip)
        _add(ax, plate_detail, "#687983", 0.55)
        _add(ax, panel_detail, "#5c9eaa", 0.42)

        bolt_shaft = cq.Solid.makeCylinder(
            1.5,
            ear_z1 - plate_z0,
            cq.Vector(x_mm, y_mm, plate_z0),
            cq.Vector(0.0, 0.0, 1.0),
        )
        receiver = cq.Solid.makeCylinder(
            3.25,
            2.4,
            cq.Vector(x_mm, y_mm, plate_z0 - 2.4),
            cq.Vector(0.0, 0.0, 1.0),
        )
        _add(ax, bolt_shaft, "#d6a444", 0.96)
        _add(ax, receiver, "#d6a444", 0.55)
        ax.plot(
            [x_mm, x_mm],
            [y_mm, y_mm],
            [ear_z1 - 1.0, ear_z1 + 10.0],
            color="#d6a444",
            linewidth=3.5,
            marker="o",
            markersize=3.5,
            zorder=100,
        )
        ax.text2D(
            0.04,
            0.06,
            "M3 nominal axis Ø3.0",
            transform=ax.transAxes,
            fontsize=8,
            color="#9b6c18",
            bbox={"facecolor": "white", "alpha": 0.88, "edgecolor": "#d6a444"},
        )
        ax.set_xlim(x_mm - 34.0, x_mm + 34.0)
        ax.set_ylim(y_mm - 34.0, y_mm + 34.0)
        ax.set_zlim(plate_z0 - 12.0, ear_z1 + 16.0)
        ax.set_box_aspect((68.0, 68.0, 36.0))
        ax.view_init(elev=27, azim=normal_deg + 38.0)
        ax.set_title(f"面板 {panel_index:02d}｜法向 {normal_deg:.0f}°", fontsize=11, pad=3)
    figure.text(
        0.5,
        0.06,
        "蓝灰：上板一体固定耳与顶盘　｜　金色：Ø3.0 螺杆与 Ø6.5×2.4 mm 接收件名义包络　｜　实际紧固件尚未选定",
        ha="center",
        fontsize=10,
        color="#263746",
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "#cbd4db"},
    )
    figure.subplots_adjust(left=0.01, right=0.99, top=0.87, bottom=0.12, wspace=0.01)
    _save(figure, path)


def _cover_opaque_view(parts: Iterable[tuple[str, cq.Shape]], path: Path) -> None:
    figure = plt.figure(figsize=(9, 7), dpi=140, facecolor="#f4f6f8")
    ax = figure.add_subplot(111, projection="3d")
    ax.set_facecolor("#f4f6f8")
    ax.set_axis_off()
    ax.set_proj_type("ortho")
    for name, shape in parts:
        if "root_guard" in name:
            color = "#365866"
        else:
            color = "#aab8c0"
        _add(ax, shape, color, 0.98)
        for edge in shape.Edges():
            if edge.geomType() != "LINE":
                continue
            vertices = edge.Vertices()
            if len(vertices) != 2:
                continue
            ax.plot(
                [vertex.X for vertex in vertices],
                [vertex.Y for vertex in vertices],
                [vertex.Z for vertex in vertices],
                color="#304a56",
                linewidth=1.0,
                alpha=0.98,
                solid_capstyle="round",
            )
    ax.set_xlim(-180, 180)
    ax.set_ylim(-180, 180)
    ax.set_zlim(-250, 80)
    ax.set_box_aspect((360, 360, 330))
    ax.view_init(elev=20, azim=35)
    ax.set_title("V27 阶梯护甲｜不透明外观预览", fontsize=14, pad=12)
    ax.text2D(
        0.02,
        0.03,
        "两道阶梯环带 · 大观察口 · 肋条与面板一体打印 · 8 mm 倒角窗框",
        transform=ax.transAxes,
        fontsize=9,
        color="#263746",
        bbox={"facecolor": "white", "alpha": 0.84, "edgecolor": "#cbd4db"},
    )
    _save(figure, path)


def _cover_comparison(before_path: Path, after_path: Path, output_path: Path) -> None:
    if not before_path.is_file():
        raise FileNotFoundError(f"simplified-cover baseline is missing: {before_path}")
    if not after_path.is_file():
        raise FileNotFoundError(f"restored-cover preview is missing: {after_path}")
    before = plt.imread(before_path)
    after = plt.imread(after_path)
    if before.shape[:2] != after.shape[:2]:
        raise ValueError(
            "cover comparison images must share the same pixel dimensions and camera scale"
        )

    figure, axes = plt.subplots(1, 2, figsize=(18, 8.5), dpi=120, facecolor="#f4f6f8")
    figure.suptitle(
        "V27 包覆外观改版前后对比｜同一相机与坐标范围",
        fontsize=18,
        y=0.98,
    )
    for ax, image, title in (
        (axes[0], before, "改版前｜V27 简化六棱包覆"),
        (axes[1], after, "改版后｜V27 阶梯护甲"),
    ):
        ax.imshow(image)
        ax.set_axis_off()
        ax.set_title(title, fontsize=14, pad=12)
    figure.text(
        0.5,
        0.025,
        "固定显示范围：X/Y ±180 mm，Z −250…80 mm；相机方位 elev 20° / azim 35°",
        ha="center",
        fontsize=10,
        color="#3c4e59",
    )
    figure.subplots_adjust(left=0.01, right=0.99, top=0.88, bottom=0.07, wspace=0.02)
    _save(figure, output_path)


def _dovetail_review(result: Any, path: Path) -> None:
    figure = plt.figure(figsize=(15, 6.5), dpi=130, facecolor="#eef3f6")
    segment_shapes = tuple(result.arm.print_segments.values())
    for index, (joint, lock) in enumerate(
        zip(result.arm.dovetails, result.arm.lock_features), start=1
    ):
        ax = figure.add_subplot(1, 3, index, projection="3d")
        boundary = joint.boundary_z_mm
        crop = cq.Solid.makeBox(
            180.0,
            180.0,
            joint.engagement_mm + 18.0,
            cq.Vector(-90.0, -90.0, boundary - 8.0),
        )
        lower = segment_shapes[index - 1].intersect(crop).translate((0.0, 0.0, -boundary))
        upper = segment_shapes[index].intersect(crop).translate((0.0, 0.0, -boundary))
        pin = lock.proxy.translate((0.0, 0.0, -boundary))
        _add(ax, lower, "#d3a849", 0.94)
        _add(ax, upper, "#5d9db1", 0.34)
        _add(ax, pin, "#50565a", 0.98)
        radius = 0.5 * lock.length_mm - 1.0
        view_radius = min(52.0, radius + 7.0)
        ax.set_xlim(-view_radius, view_radius)
        ax.set_ylim(-view_radius, view_radius)
        ax.set_zlim(-8.0, joint.engagement_mm + 6.0)
        ax.set_box_aspect((2.0 * view_radius, 2.0 * view_radius, 34.0))
        ax.set_title(
            f"Unit {joint.unit_index} split | {joint.engagement_mm:.0f} mm | "
            f"pin Ø{lock.diameter_mm:.0f}",
            fontsize=10,
        )
        ax.set_axis_off()
        ax.view_init(elev=23, azim=36)
    figure.suptitle("V27 internal joint dovetails — gold lower tongue, transparent blue socket, gray lock pin", y=0.98)
    figure.tight_layout()
    _save(figure, path)


def render_v27(result: Any) -> dict[str, Path]:
    directory = result.contract.output_directory
    paths = {
        "full_transparent": directory / "V27_总装半透明审查.png",
        "exploded_modules": directory / "V27_三模块分解审查.png",
        "root_quick_change": directory / "V27_根部快换近景.png",
        "drive_section": directory / "V27_M2006传动密封剖视.png",
        "drive_details": directory / "V27_传动系统细节图.png",
        "electronics_bay": directory / "V27_电子仓半透明布局.png",
        "dovetail_joints": directory / "V27_燕尾榫装配近景.png",
        "root_cover_review": directory / "V27_半透明包覆件总装与拆卸.png",
        "root_cover_only": directory / "V27_六边形包覆附件.png",
        "root_cover_opaque": directory / "V27_阶梯护甲外观.png",
        "top_plate_cover_joint": directory / "V27_顶板包覆固定耳连接细节.png",
        "cover_comparison": directory / "V27_包覆件改版前后对比.png",
    }
    _full_review(result, paths["full_transparent"])
    _exploded_review(result, paths["exploded_modules"])
    _root_review(result, paths["root_quick_change"])
    _drive_section_review(result, paths["drive_section"])
    _drive_details_sheet(result, paths["drive_details"])
    _electronics_review(result, paths["electronics_bay"])
    _dovetail_review(result, paths["dovetail_joints"])
    _cover_review(
        result,
        paths["root_cover_review"],
        paths["root_cover_only"],
        paths["root_cover_opaque"],
    )
    _top_plate_cover_joint_review(result, paths["top_plate_cover_joint"])
    _cover_comparison(
        directory / "V27_简化版包覆基线.png",
        paths["root_cover_only"],
        paths["cover_comparison"],
    )
    return paths
