from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
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
        edgecolor=(0.08, 0.10, 0.12, min(0.30, alpha)),
        linewidth=0.12,
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
    figure, ax = _figure("V27 1 m modular M2006 assembly — transparent review")
    selected = [
        *result.arm_component_names,
        "removable_motor_plate",
        *result.drive.motor_names,
        "fixed_top_plate",
        "fixed_root_receiver",
        *(f"fixed_wet_spool_{index:02d}" for index in range(1, 4)),
        "v24_central_electronics_canister",
        "v25_bottom_lid_with_M28_recess",
        *(f"v27_C610_controller_{index:02d}_envelope" for index in range(1, 4)),
    ]
    for name in selected:
        color, alpha = _group_style(result, name)
        _add(ax, result.components[name], color, alpha)
    ax.set_xlim(-150, 150)
    ax.set_ylim(-150, 150)
    ax.set_zlim(-330, 1080)
    ax.set_box_aspect((300, 300, 1410))
    ax.view_init(elev=13, azim=38)
    _save(figure, path)


def _exploded_review(result: Any, path: Path) -> None:
    figure, ax = _figure("V27 three-module replacement concept — exploded")
    selected = [
        *result.arm_component_names,
        "removable_motor_plate",
        *result.drive.motor_names,
        "fixed_top_plate",
        "fixed_root_receiver",
        *(f"fixed_wet_spool_{index:02d}" for index in range(1, 4)),
        "v24_central_electronics_canister",
    ]
    for name in selected:
        color, alpha = _group_style(result, name)
        if name in result.arm_component_names:
            offset = (0.0, 0.0, 90.0)
            alpha = 0.96
        elif name in result.drive_component_names:
            offset = (0.0, 0.0, -110.0)
            alpha = 0.96
        else:
            offset = (0.0, 0.0, 0.0)
        _add(ax, result.components[name], color, alpha, offset)
    ax.text(0, 0, 1090, "A  whole four-section arm module", color="#70520d")
    ax.text(0, 0, -205, "B  three-M2006 common drive plate", color="#183b52")
    ax.text(0, 0, -5, "C  fixed shaft / seal / wet-spool base", color="#48535a")
    ax.set_xlim(-160, 160)
    ax.set_ylim(-160, 160)
    ax.set_zlim(-360, 1160)
    ax.set_box_aspect((320, 320, 1520))
    ax.view_init(elev=14, azim=32)
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
    figure, ax = _figure("V27 drive chain section — M2006 / coupling / fixed bearing and seal support / wet spool")
    names = [
        "removable_M2006_01",
        "removable_coupling_sleeve_01",
        "fixed_shaft_01",
        "fixed_bearing_inner_01",
        "fixed_bearing_outer_01",
        "fixed_oil_seal_01",
        "fixed_labyrinth_01",
        "fixed_axial_retainer_01",
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
        "spool": "#d6a936",
        "plate": "#7a8790",
    }
    for name in names:
        key = next((item for item in palette if item.lower() in name.lower()), "plate")
        alpha = 0.22 if name == "fixed_top_plate" else 0.92
        _add(ax, result.components[name], palette[key], alpha)
    center = result.fixed.axes[0].spool_center
    ax.set_xlim(center[0] - 28, center[0] + 28)
    ax.set_ylim(center[1] - 28, center[1] + 28)
    ax.set_zlim(-112, 16)
    ax.set_box_aspect((56, 56, 128))
    ax.view_init(elev=7, azim=-86)
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
        "electronics_bay": directory / "V27_电子仓半透明布局.png",
        "dovetail_joints": directory / "V27_燕尾榫装配近景.png",
    }
    _full_review(result, paths["full_transparent"])
    _exploded_review(result, paths["exploded_modules"])
    _root_review(result, paths["root_quick_change"])
    _drive_section_review(result, paths["drive_section"])
    _electronics_review(result, paths["electronics_bay"])
    _dovetail_review(result, paths["dovetail_joints"])
    return paths
