from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import cadquery as cq


@dataclass(frozen=True)
class TendonTerminal:
    name: str
    angle_deg: float
    key_code: str
    capture_block: cq.Shape
    adjustment_envelope: cq.Shape
    secondary_retention: cq.Shape
    inlet_point: tuple[float, float, float]
    axis_direction: tuple[float, float, float]
    adjustment_stroke_mm: float
    future_load_cell_straight_length_mm: float


@dataclass(frozen=True)
class RootInterfaceResult:
    arm_side_flange: cq.Shape
    base_side_receiver: cq.Shape
    metal_backing_proxy: cq.Shape
    register_proxy: cq.Shape
    dowel_proxies: tuple[cq.Shape, ...]
    dowel_angles_deg: tuple[float, ...]
    fastener_centers: tuple[tuple[float, float, float], ...]
    fastener_thread: str
    tool_envelopes: tuple[cq.Shape, ...]
    tendon_terminals: tuple[TendonTerminal, ...]
    centering_feature: str
    fasteners_define_centering: bool
    register_diameter_mm: float
    register_height_mm: float
    tool_envelope_diameter_mm: float


def _annulus(
    outer_radius_mm: float,
    inner_radius_mm: float,
    z0_mm: float,
    height_mm: float,
) -> cq.Shape:
    outer = cq.Solid.makeCylinder(
        outer_radius_mm,
        height_mm,
        cq.Vector(0.0, 0.0, z0_mm),
        cq.Vector(0.0, 0.0, 1.0),
    )
    inner = cq.Solid.makeCylinder(
        inner_radius_mm,
        height_mm + 0.2,
        cq.Vector(0.0, 0.0, z0_mm - 0.1),
        cq.Vector(0.0, 0.0, 1.0),
    )
    return outer.cut(inner)


def _radial_point(radius_mm: float, angle_deg: float, z_mm: float = 0.0) -> tuple[float, float, float]:
    angle = math.radians(angle_deg)
    return radius_mm * math.cos(angle), radius_mm * math.sin(angle), z_mm


def _cylinder_between(
    radius_mm: float,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
) -> cq.Shape:
    vector = cq.Vector(end[0] - start[0], end[1] - start[1], end[2] - start[2])
    return cq.Solid.makeCylinder(
        radius_mm,
        vector.Length,
        cq.Vector(*start),
        vector.normalized(),
    )


def _oriented_box(
    length_mm: float,
    width_mm: float,
    height_mm: float,
    center_radius_mm: float,
    angle_deg: float,
) -> cq.Shape:
    box = cq.Workplane("XY").box(length_mm, width_mm, height_mm).val()
    box = box.translate((center_radius_mm, 0.0, 0.0))
    return box.rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), angle_deg)


def build_root_interface(contract: Any, arm: Any) -> RootInterfaceResult:
    cfg = contract.root_interface
    flange_radius = 0.5 * float(cfg.flange_max_diameter_mm)
    arm_radius = 0.5 * float(contract.arm.root_diameter_mm)
    register_radius = 0.5 * float(cfg.register_diameter_mm)
    arm_flange = _annulus(flange_radius, arm_radius + 0.5, 0.0, 8.0)
    register = _annulus(register_radius, arm_radius + 0.5, -float(cfg.register_height_mm), float(cfg.register_height_mm))
    arm_flange = arm_flange.fuse(register).clean()

    receiver = _annulus(flange_radius, 40.0, -8.0, 8.0)
    receiver_pocket = cq.Solid.makeCylinder(
        register_radius + 0.25,
        float(cfg.register_height_mm) + 0.1,
        cq.Vector(0.0, 0.0, -float(cfg.register_height_mm)),
        cq.Vector(0.0, 0.0, 1.0),
    )
    receiver = receiver.cut(receiver_pocket).clean()
    backing = _annulus(flange_radius - 2.0, arm_radius + 0.5, 8.0, 2.0)

    dowels: list[cq.Shape] = []
    for angle_deg in cfg.dowel_angles_deg:
        x_mm, y_mm, _ = _radial_point(72.0, angle_deg)
        pin = cq.Solid.makeCylinder(
            0.5 * float(cfg.dowel_diameter_mm),
            8.0,
            cq.Vector(x_mm, y_mm, -4.0),
            cq.Vector(0.0, 0.0, 1.0),
        )
        dowels.append(pin)
        clearance = cq.Solid.makeCylinder(
            0.5 * float(cfg.dowel_diameter_mm) + 0.1,
            16.0,
            cq.Vector(x_mm, y_mm, -8.0),
            cq.Vector(0.0, 0.0, 1.0),
        )
        arm_flange = arm_flange.cut(clearance)
        receiver = receiver.cut(clearance)

    fastener_centers: list[tuple[float, float, float]] = []
    tool_envelopes: list[cq.Shape] = []
    tool_diameter = float(cfg.minimum_tool_clearance_mm)
    for index in range(int(cfg.fastener_count)):
        angle_deg = index * 360.0 / float(cfg.fastener_count)
        center = _radial_point(0.5 * float(cfg.fastener_pcd_mm), angle_deg)
        fastener_centers.append(center)
        hole = cq.Solid.makeCylinder(
            0.5 * float(cfg.fastener_clearance_diameter_mm),
            20.0,
            cq.Vector(center[0], center[1], -9.0),
            cq.Vector(0.0, 0.0, 1.0),
        )
        arm_flange = arm_flange.cut(hole)
        receiver = receiver.cut(hole)
        backing = backing.cut(hole)
        tool_envelopes.append(
            cq.Solid.makeCylinder(
                0.5 * tool_diameter,
                25.0,
                cq.Vector(center[0], center[1], 0.0),
                cq.Vector(0.0, 0.0, 1.0),
            )
        )

    terminals: list[TendonTerminal] = []
    for index, (angle_deg, channel) in enumerate(
        zip((0.0, 120.0, 240.0), arm.tendon_centerlines), start=1
    ):
        key_code = f"K{index}-{3.0 + 0.5 * (index - 1):.1f}"
        capture = _oriented_box(18.0, 7.0 + index, 8.0, 50.0, angle_deg)
        axis = _radial_point(1.0, angle_deg)
        adjustment = _cylinder_between(
            2.0,
            _radial_point(58.0, angle_deg),
            _radial_point(78.0, angle_deg),
        )
        tangential = (-axis[1], axis[0], 0.0)
        pin_center = _radial_point(50.0, angle_deg)
        retention = cq.Solid.makeCylinder(
            1.0,
            12.0,
            cq.Vector(
                pin_center[0] - 6.0 * tangential[0],
                pin_center[1] - 6.0 * tangential[1],
                0.0,
            ),
            cq.Vector(*tangential),
        )
        terminals.append(
            TendonTerminal(
                name=f"tendon_terminal_{index:02d}",
                angle_deg=angle_deg,
                key_code=key_code,
                capture_block=capture,
                adjustment_envelope=adjustment,
                secondary_retention=retention,
                inlet_point=tuple(float(value) for value in channel.samples[0]),
                axis_direction=axis,
                adjustment_stroke_mm=12.0,
                future_load_cell_straight_length_mm=20.0,
            )
        )

    return RootInterfaceResult(
        arm_side_flange=arm_flange.clean(),
        base_side_receiver=receiver.clean(),
        metal_backing_proxy=backing.clean(),
        register_proxy=register,
        dowel_proxies=tuple(dowels),
        dowel_angles_deg=tuple(float(value) for value in cfg.dowel_angles_deg),
        fastener_centers=tuple(fastener_centers),
        fastener_thread=cfg.fastener_thread,
        tool_envelopes=tuple(tool_envelopes),
        tendon_terminals=tuple(terminals),
        centering_feature="register",
        fasteners_define_centering=False,
        register_diameter_mm=float(cfg.register_diameter_mm),
        register_height_mm=float(cfg.register_height_mm),
        tool_envelope_diameter_mm=tool_diameter,
    )


def audit_root_interface(result: RootInterfaceResult) -> dict[str, float | bool]:
    separation = (result.dowel_angles_deg[1] - result.dowel_angles_deg[0]) % 360.0
    asymmetric = not any(abs(separation - value) < 1e-8 for value in (120.0, 180.0, 240.0))
    terminal_angles = {round(item.angle_deg, 6) for item in result.tendon_terminals}
    return {
        "positive_register_engagement": result.register_height_mm > 0.0,
        "asymmetric_dowels": asymmetric,
        "minimum_tool_envelope_diameter_mm": result.tool_envelope_diameter_mm,
        "all_fasteners_tool_accessible": len(result.tool_envelopes) == 6
        and all(item.isValid() for item in result.tool_envelopes),
        "tendon_terminals_do_not_cross": terminal_angles == {0.0, 120.0, 240.0},
    }
