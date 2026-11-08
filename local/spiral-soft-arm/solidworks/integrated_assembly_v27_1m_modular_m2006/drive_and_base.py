from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Sequence

import cadquery as cq


@dataclass(frozen=True)
class DriveAxis:
    axis_index: int
    channel_index: int
    angle_deg: float
    root_inlet: tuple[float, float, float]
    tangent_point: tuple[float, float, float]
    spool_center: tuple[float, float, float]
    tendon_direction: tuple[float, float, float]
    shaft_axis: tuple[float, float, float]
    spool_effective_radius_mm: float
    delta_from_v26_local_mm: tuple[float, float, float]


@dataclass(frozen=True)
class TendonAlignment:
    axis_index: int
    channel_index: int
    plan_error_mm: float
    side_error_mm: float
    lateral_error_mm: float
    perpendicular_error_deg: float
    passes: bool


@dataclass(frozen=True)
class DriveModuleResult:
    components: dict[str, cq.Shape]
    motor_names: tuple[str, ...]
    plate_name: str
    positioning_source: str
    official_step_path: Path
    official_step_solid_count: int
    installed_geometry_mode: str
    removal_sequence: tuple[str, ...]


@dataclass(frozen=True)
class FixedBaseResult:
    components: dict[str, cq.Shape]
    top_plate: cq.Shape
    top_plate_circumdiameter_mm: float
    axes: tuple[DriveAxis, ...]
    shafts_supported_without_drive: bool
    shaft_support_pairs: tuple[tuple[str, str], ...]


def _unit_radial(angle_deg: float) -> tuple[float, float, float]:
    angle = math.radians(angle_deg)
    return math.cos(angle), math.sin(angle), 0.0


def _unit_tangent(angle_deg: float) -> tuple[float, float, float]:
    radial = _unit_radial(angle_deg)
    return -radial[1], radial[0], 0.0


def _combine(
    radial: tuple[float, float, float],
    tangent: tuple[float, float, float],
    radial_mm: float,
    tangent_mm: float,
    z_mm: float,
) -> tuple[float, float, float]:
    return (
        radial_mm * radial[0] + tangent_mm * tangent[0],
        radial_mm * radial[1] + tangent_mm * tangent[1],
        z_mm,
    )


def _vertical_cylinder(
    center: tuple[float, float, float], radius_mm: float, z0_mm: float, z1_mm: float
) -> cq.Shape:
    return cq.Solid.makeCylinder(
        radius_mm,
        z1_mm - z0_mm,
        cq.Vector(center[0], center[1], z0_mm),
        cq.Vector(0.0, 0.0, 1.0),
    )


def _vertical_ring(
    center: tuple[float, float, float],
    outer_radius_mm: float,
    inner_radius_mm: float,
    z0_mm: float,
    z1_mm: float,
) -> cq.Shape:
    outer = _vertical_cylinder(center, outer_radius_mm, z0_mm, z1_mm)
    inner = _vertical_cylinder(center, inner_radius_mm, z0_mm - 0.1, z1_mm + 0.1)
    return outer.cut(inner)


def _hex_prism(circumradius_mm: float, z0_mm: float, height_mm: float) -> cq.Shape:
    points = [
        (
            circumradius_mm * math.cos(math.radians(index * 60.0)),
            circumradius_mm * math.sin(math.radians(index * 60.0)),
        )
        for index in range(6)
    ]
    return (
        cq.Workplane("XY")
        .workplane(offset=z0_mm)
        .polyline(points)
        .close()
        .extrude(height_mm)
        .val()
    )


def optimize_drive_axes(contract: Any, root: Any) -> tuple[DriveAxis, DriveAxis, DriveAxis]:
    tangent_radius_mm = 102.0
    effective_radius_mm = 10.0
    axes: list[DriveAxis] = []
    for index, terminal in enumerate(root.tendon_terminals, start=1):
        angle_deg = float(terminal.angle_deg)
        radial = _unit_radial(angle_deg)
        tangent = _unit_tangent(angle_deg)
        tangent_point = _combine(radial, tangent, tangent_radius_mm, 0.0, 0.0)
        spool_center = _combine(
            radial, tangent, tangent_radius_mm, effective_radius_mm, 0.0
        )
        axes.append(
            DriveAxis(
                axis_index=index,
                channel_index=index,
                angle_deg=angle_deg,
                root_inlet=tuple(float(value) for value in terminal.inlet_point),
                tangent_point=tangent_point,
                spool_center=spool_center,
                tendon_direction=radial,
                shaft_axis=(0.0, 0.0, 1.0),
                spool_effective_radius_mm=effective_radius_mm,
                delta_from_v26_local_mm=(
                    tangent_radius_mm - 81.8,
                    effective_radius_mm,
                    23.0,
                ),
            )
        )
    return tuple(axes)  # type: ignore[return-value]


def audit_tendon_alignment(
    contract: Any, root: Any, axes: Sequence[DriveAxis]
) -> tuple[TendonAlignment, ...]:
    lateral_tolerance = float(contract.drive.tendon_alignment_lateral_tolerance_mm)
    angular_tolerance = float(contract.drive.tendon_alignment_angular_tolerance_deg)
    alignments: list[TendonAlignment] = []
    for axis, terminal in zip(axes, root.tendon_terminals):
        delta = (
            axis.tangent_point[0] - terminal.inlet_point[0],
            axis.tangent_point[1] - terminal.inlet_point[1],
            axis.tangent_point[2] - terminal.inlet_point[2],
        )
        expected = terminal.axis_direction
        plan_error = abs(delta[0] * expected[1] - delta[1] * expected[0])
        side_error = abs(delta[2])
        lateral_error = math.hypot(plan_error, side_error)
        shaft_norm = math.sqrt(sum(value * value for value in axis.shaft_axis))
        tendon_norm = math.sqrt(sum(value * value for value in axis.tendon_direction))
        dot = sum(a * b for a, b in zip(axis.shaft_axis, axis.tendon_direction))
        angle = math.degrees(
            math.acos(max(-1.0, min(1.0, dot / (shaft_norm * tendon_norm))))
        )
        perpendicular_error = abs(90.0 - angle)
        alignments.append(
            TendonAlignment(
                axis_index=axis.axis_index,
                channel_index=axis.channel_index,
                plan_error_mm=plan_error,
                side_error_mm=side_error,
                lateral_error_mm=lateral_error,
                perpendicular_error_deg=perpendicular_error,
                passes=lateral_error <= lateral_tolerance
                and perpendicular_error <= angular_tolerance,
            )
        )
    return tuple(alignments)


def _source_path(contract: Any, role: str) -> Path:
    return (contract.output_directory / contract.source_specs[role]["path"]).resolve()


def build_drive_module(
    contract: Any, root: Any, axes: Sequence[DriveAxis] | None = None
) -> DriveModuleResult:
    axes = tuple(axes or optimize_drive_axes(contract, root))
    official_path = _source_path(contract, "m2006_step")
    official_shape = cq.importers.importStep(str(official_path)).val()
    official_solid_count = len(official_shape.Solids())

    plate = _hex_prism(118.0, -102.0, 6.0)
    center_clearance = _vertical_cylinder((0.0, 0.0, 0.0), 70.0, -103.0, -95.0)
    plate = plate.cut(center_clearance).clean()
    components: dict[str, cq.Shape] = {"removable_motor_plate": plate}
    motor_names: list[str] = []
    for axis in axes:
        name = f"removable_M2006_{axis.axis_index:02d}"
        motor = _vertical_cylinder(axis.spool_center, 12.2, -100.0, -35.2)
        coupling = _vertical_ring(axis.spool_center, 8.0, 5.05, -35.0, -27.2)
        cradle = _vertical_ring(axis.spool_center, 15.0, 12.4, -97.0, -86.0)
        components[name] = motor
        components[f"removable_coupling_sleeve_{axis.axis_index:02d}"] = coupling
        components[f"removable_motor_cradle_{axis.axis_index:02d}"] = cradle
        motor_names.append(name)
    components["removable_plate_register"] = _vertical_ring(
        (0.0, 0.0, 0.0), 60.0, 55.0, -96.0, -93.0
    )
    for index, angle_deg in enumerate((17.0, 157.0), start=1):
        radial = _unit_radial(angle_deg)
        center = (78.0 * radial[0], 78.0 * radial[1], 0.0)
        components[f"removable_plate_dowel_{index:02d}"] = _vertical_cylinder(
            center, 3.0, -98.0, -90.0
        )
    return DriveModuleResult(
        components=components,
        motor_names=tuple(motor_names),
        plate_name="removable_motor_plate",
        positioning_source="plate_register_and_dowels",
        official_step_path=official_path,
        official_step_solid_count=official_solid_count,
        installed_geometry_mode="published_envelope_proxy",
        removal_sequence=(
            "release_three_coupling_sleeves",
            "translate_plate_downward",
        ),
    )


def build_fixed_base(
    contract: Any, root: Any, axes: Sequence[DriveAxis] | None = None
) -> FixedBaseResult:
    axes = tuple(axes or optimize_drive_axes(contract, root))
    top_plate = _hex_prism(125.0, -8.0, 8.0)
    register_service_clearance = _vertical_cylinder(
        (0.0, 0.0, 0.0),
        0.5 * float(contract.root_interface.register_diameter_mm) + 0.25,
        -8.2,
        0.2,
    )
    top_plate = top_plate.cut(register_service_clearance).clean()
    components: dict[str, cq.Shape] = {
        "fixed_top_plate": top_plate,
        "fixed_root_receiver": root.base_side_receiver,
    }
    support_pairs: list[tuple[str, str]] = []
    for axis in axes:
        index = axis.axis_index
        center = axis.spool_center
        wet_tunnel = _vertical_cylinder(center, 13.2, -8.2, 0.2)
        top_plate = top_plate.cut(wet_tunnel)
        spool_core = _vertical_cylinder(center, 10.0, -3.5, 3.5)
        lower_flange = _vertical_cylinder(center, 12.0, -5.0, -3.5)
        upper_flange = _vertical_cylinder(center, 12.0, 3.5, 5.0)
        spool = spool_core.fuse(lower_flange, upper_flange).clean()
        shaft = _vertical_cylinder(center, 5.0, -35.0, 5.0)
        bearing_inner_name = f"fixed_bearing_inner_{index:02d}"
        bearing_outer_name = f"fixed_bearing_outer_{index:02d}"
        components[f"fixed_wet_spool_{index:02d}"] = spool
        components[f"fixed_shaft_{index:02d}"] = shaft
        components[bearing_inner_name] = _vertical_ring(center, 11.0, 5.05, -24.0, -18.0)
        components[bearing_outer_name] = _vertical_ring(center, 11.0, 5.05, -17.0, -11.0)
        components[f"fixed_seal_housing_{index:02d}"] = _vertical_ring(
            center, 14.0, 11.05, -11.0, 0.0
        )
        components[f"fixed_oil_seal_{index:02d}"] = _vertical_ring(
            center, 11.0, 5.05, -10.0, -3.0
        )
        components[f"fixed_labyrinth_{index:02d}"] = _vertical_ring(
            center, 12.0, 5.5, -3.0, 1.5
        )
        components[f"fixed_axial_retainer_{index:02d}"] = _vertical_ring(
            center, 7.5, 5.05, -27.0, -25.0
        )
        support_pairs.append((bearing_inner_name, bearing_outer_name))
    components["fixed_top_plate"] = top_plate.clean()
    return FixedBaseResult(
        components=components,
        top_plate=components["fixed_top_plate"],
        top_plate_circumdiameter_mm=float(
            contract.root_interface.top_plate_circumdiameter_mm
        ),
        axes=tuple(axes),
        shafts_supported_without_drive=True,
        shaft_support_pairs=tuple(support_pairs),
    )
