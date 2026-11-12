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
    motor_center: tuple[float, float, float]
    motor_axis: tuple[float, float, float]
    tangent_point: tuple[float, float, float]
    surface_contact_point: tuple[float, float, float]
    spool_center: tuple[float, float, float]
    spool_axis: tuple[float, float, float]
    tendon_direction: tuple[float, float, float]
    spool_effective_radius_mm: float
    delta_from_v26_local_mm: tuple[float, float, float]


@dataclass(frozen=True)
class TendonAlignment:
    axis_index: int
    channel_index: int
    plan_error_mm: float
    side_error_mm: float
    lateral_error_mm: float
    surface_error_mm: float
    perpendicular_error_deg: float
    motor_spool_axis_error_deg: float
    entry_direction_error_deg: float
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


def _axis_cylinder(
    center: tuple[float, float, float],
    axis: tuple[float, float, float],
    radius_mm: float,
    s0_mm: float,
    s1_mm: float,
) -> cq.Shape:
    direction = cq.Vector(*axis).normalized()
    start = cq.Vector(*center) + direction * s0_mm
    return cq.Solid.makeCylinder(radius_mm, s1_mm - s0_mm, start, direction)


def _axis_ring(
    center: tuple[float, float, float],
    axis: tuple[float, float, float],
    outer_radius_mm: float,
    inner_radius_mm: float,
    s0_mm: float,
    s1_mm: float,
) -> cq.Shape:
    outer = _axis_cylinder(center, axis, outer_radius_mm, s0_mm, s1_mm)
    inner = _axis_cylinder(center, axis, inner_radius_mm, s0_mm - 0.1, s1_mm + 0.1)
    return outer.cut(inner)


def _axis_flat_cut(
    center: tuple[float, float, float],
    angle_deg: float,
    flat_from_axis_mm: float,
    s0_mm: float,
    s1_mm: float,
) -> cq.Shape:
    radial = _unit_radial(angle_deg)
    tangent = _unit_tangent(angle_deg)
    axial_center = 0.5 * (s0_mm + s1_mm)
    cutter_center = (
        center[0] + radial[0] * (flat_from_axis_mm + 10.0) + tangent[0] * axial_center,
        center[1] + radial[1] * (flat_from_axis_mm + 10.0) + tangent[1] * axial_center,
        center[2],
    )
    return _oriented_box(
        cutter_center,
        20.0,
        s1_mm - s0_mm + 0.2,
        40.0,
        angle_deg,
    )


def _axis_d_bore(
    center: tuple[float, float, float],
    angle_deg: float,
    radius_mm: float,
    flat_from_axis_mm: float,
    s0_mm: float,
    s1_mm: float,
) -> cq.Shape:
    bore = _axis_cylinder(
        center,
        _unit_tangent(angle_deg),
        radius_mm,
        s0_mm,
        s1_mm,
    )
    return bore.cut(
        _axis_flat_cut(center, angle_deg, flat_from_axis_mm, s0_mm, s1_mm)
    )


def _bevel_envelope(
    apex: tuple[float, float, float],
    axis: tuple[float, float, float],
    base_radius_mm: float,
    height_mm: float,
) -> cq.Shape:
    direction = cq.Vector(*axis).normalized()
    base = cq.Vector(*apex) - direction * height_mm
    return cq.Solid.makeCone(base_radius_mm, 0.0, height_mm, base, direction)


def _catalog_miter_envelope(
    apex: tuple[float, float, float],
    axis: tuple[float, float, float],
    outside_radius_mm: float,
    pitch_diameter_mm: float,
    face_width_mm: float,
    hub_diameter_mm: float,
    hub_width_mm: float,
    bore_diameter_mm: float,
) -> cq.Shape:
    """Build a catalog-sized miter-gear envelope; this deliberately has no teeth."""
    direction = cq.Vector(*axis).normalized()
    pitch_radius = pitch_diameter_mm / 2.0
    outer_depth = pitch_radius
    axial_face_width = face_width_mm / math.sqrt(2.0)
    inner_depth = outer_depth - axial_face_width
    inner_radius = inner_depth
    start = cq.Vector(*apex) + direction * inner_depth
    toothed_envelope = cq.Solid.makeCone(
        inner_radius,
        outside_radius_mm,
        outer_depth - inner_depth,
        start,
        direction,
    )
    hub_start = cq.Vector(*apex) + direction * outer_depth
    hub = cq.Solid.makeCylinder(hub_diameter_mm / 2.0, hub_width_mm, hub_start, direction)
    gear = toothed_envelope.fuse(hub).clean()
    bore_start = cq.Vector(*apex) + direction * (inner_depth - 0.1)
    bore = cq.Solid.makeCylinder(
        bore_diameter_mm / 2.0,
        outer_depth + hub_width_mm - inner_depth + 0.2,
        bore_start,
        direction,
    )
    if bore_diameter_mm > 0.0:
        gear = gear.cut(bore)
    return gear.clean()


def _oriented_box(
    center: tuple[float, float, float],
    radial_width_mm: float,
    tangent_length_mm: float,
    height_mm: float,
    angle_deg: float,
) -> cq.Shape:
    return (
        cq.Workplane("XY")
        .box(radial_width_mm, tangent_length_mm, height_mm)
        .val()
        .rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), angle_deg)
        .translate(center)
    )


def _radial_cylinder_at(
    center: tuple[float, float, float],
    angle_deg: float,
    radius_mm: float,
    r0_mm: float,
    r1_mm: float,
    z_mm: float,
) -> cq.Shape:
    radial = _unit_radial(angle_deg)
    return cq.Solid.makeCylinder(
        radius_mm,
        r1_mm - r0_mm,
        cq.Vector(center[0] + r0_mm * radial[0], center[1] + r0_mm * radial[1], z_mm),
        cq.Vector(radial[0], radial[1], 0.0),
    )


def _flat_cut(
    center: tuple[float, float, float],
    angle_deg: float,
    flat_from_axis_mm: float,
    z0_mm: float,
    z1_mm: float,
) -> cq.Shape:
    cutter = cq.Solid.makeBox(
        20.0,
        40.0,
        z1_mm - z0_mm + 0.2,
        cq.Vector(flat_from_axis_mm, -20.0, z0_mm - 0.1),
    ).rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), angle_deg)
    return cutter.translate((center[0], center[1], 0.0))


def _vertical_d_bore(
    center: tuple[float, float, float],
    radius_mm: float,
    flat_from_axis_mm: float,
    angle_deg: float,
    z0_mm: float,
    z1_mm: float,
) -> cq.Shape:
    bore = _vertical_cylinder(center, radius_mm, z0_mm, z1_mm)
    return bore.cut(
        _flat_cut(center, angle_deg, flat_from_axis_mm, z0_mm, z1_mm)
    )


def _radial_cylinder(
    angle_deg: float,
    radius_mm: float,
    r0_mm: float,
    r1_mm: float,
    z_mm: float,
) -> cq.Shape:
    radial = _unit_radial(angle_deg)
    return cq.Solid.makeCylinder(
        radius_mm,
        r1_mm - r0_mm,
        cq.Vector(r0_mm * radial[0], r0_mm * radial[1], z_mm),
        cq.Vector(radial[0], radial[1], 0.0),
    )


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
    tangent_radius_mm = float(contract.drive.tendon_tangent_radius_mm)
    effective_radius_mm = float(contract.drive.spool_effective_radius_mm)
    tangent_z_mm = float(contract.drive.spool_tangent_z_mm)
    core_radius_mm = float(contract.drive.spool_core_radius_mm)
    tendon_radius_mm = 0.5 * float(contract.arm.tendon_diameter_mm)
    motor_tangent_offset_mm = float(contract.integration["motor_tangent_offset_mm"])
    axes: list[DriveAxis] = []
    for index, terminal in enumerate(root.tendon_terminals, start=1):
        angle_deg = float(terminal.angle_deg)
        radial = _unit_radial(angle_deg)
        tangent = _unit_tangent(angle_deg)
        # Cable leaves the lower surface of a horizontal, tangential-axis spool.
        # Centering the drum one effective radius above the route keeps its lower
        # tangent at the root-inlet elevation while leaving the plate un-slotted.
        spool_center = _combine(
            radial, tangent, tangent_radius_mm, 0.0, tangent_z_mm + effective_radius_mm
        )
        surface_contact = (
            spool_center[0],
            spool_center[1],
            spool_center[2] - core_radius_mm,
        )
        tangent_point = (
            surface_contact[0],
            surface_contact[1],
            surface_contact[2] - tendon_radius_mm,
        )
        motor_center = _combine(
            radial, tangent, tangent_radius_mm, -motor_tangent_offset_mm, 0.0
        )
        axes.append(
            DriveAxis(
                axis_index=index,
                channel_index=index,
                angle_deg=angle_deg,
                root_inlet=tuple(float(value) for value in terminal.inlet_point),
                motor_center=motor_center,
                motor_axis=(0.0, 0.0, 1.0),
                tangent_point=tangent_point,
                surface_contact_point=surface_contact,
                spool_center=spool_center,
                spool_axis=tangent,
                tendon_direction=tuple(float(value) for value in terminal.axis_direction),
                spool_effective_radius_mm=effective_radius_mm,
                delta_from_v26_local_mm=(
                    tangent_radius_mm - 81.8,
                    -motor_tangent_offset_mm,
                    effective_radius_mm,
                ),
            )
        )
    return tuple(axes)  # type: ignore[return-value]


def audit_tendon_alignment(
    contract: Any,
    root: Any,
    axes: Sequence[DriveAxis],
    components: dict[str, cq.Shape] | None = None,
) -> tuple[TendonAlignment, ...]:
    lateral_tolerance = float(contract.drive.tendon_alignment_lateral_tolerance_mm)
    angular_tolerance = float(contract.drive.tendon_alignment_angular_tolerance_deg)
    alignments: list[TendonAlignment] = []
    for axis, terminal in zip(axes, root.tendon_terminals):
        surface_error = 0.0
        if components is not None:
            spool = components[f"fixed_wet_spool_{axis.axis_index:02d}"]
            surface_probe = cq.Vertex.makeVertex(*axis.surface_contact_point)
            surface_error = spool.distance(surface_probe)
        delta = (
            axis.tangent_point[0] - terminal.inlet_point[0],
            axis.tangent_point[1] - terminal.inlet_point[1],
            axis.tangent_point[2] - terminal.inlet_point[2],
        )
        expected = terminal.axis_direction
        plan_error = abs(delta[0] * expected[1] - delta[1] * expected[0])
        side_error = abs(delta[2])
        lateral_error = math.hypot(plan_error, side_error)
        tendon_norm = math.sqrt(sum(value * value for value in axis.tendon_direction))
        spool_norm = math.sqrt(sum(value * value for value in axis.spool_axis))
        motor_norm = math.sqrt(sum(value * value for value in axis.motor_axis))
        cable_dot = sum(a * b for a, b in zip(axis.spool_axis, axis.tendon_direction))
        cable_angle = math.degrees(
            math.acos(max(-1.0, min(1.0, abs(cable_dot) / (spool_norm * tendon_norm))))
        )
        perpendicular_error = abs(90.0 - cable_angle)
        motor_spool_dot = sum(a * b for a, b in zip(axis.motor_axis, axis.spool_axis))
        motor_spool_angle = math.degrees(
            math.acos(
                max(-1.0, min(1.0, abs(motor_spool_dot) / (motor_norm * spool_norm)))
            )
        )
        motor_spool_error = abs(90.0 - motor_spool_angle)
        delta_norm = math.sqrt(sum(value * value for value in delta))
        expected_norm = math.sqrt(sum(value * value for value in expected))
        entry_dot = sum(a * b for a, b in zip(delta, expected))
        entry_angle = math.degrees(
            math.acos(max(-1.0, min(1.0, abs(entry_dot) / (delta_norm * expected_norm))))
        )
        alignments.append(
            TendonAlignment(
                axis_index=axis.axis_index,
                channel_index=axis.channel_index,
                plan_error_mm=plan_error,
                side_error_mm=side_error,
                lateral_error_mm=lateral_error,
                surface_error_mm=surface_error,
                perpendicular_error_deg=perpendicular_error,
                motor_spool_axis_error_deg=motor_spool_error,
                entry_direction_error_deg=entry_angle,
                passes=lateral_error <= lateral_tolerance
                and surface_error <= 0.01
                and perpendicular_error <= angular_tolerance
                and motor_spool_error <= angular_tolerance
                and entry_angle <= angular_tolerance,
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

    plate = _hex_prism(
        float(contract.integration["drive_module_plate_circumradius_mm"]), -108.0, 6.0
    )
    center_clearance = _vertical_cylinder(
        (0.0, 0.0, 0.0),
        float(contract.integration["drive_plate_clearance_radius_mm"]),
        -109.0,
        -101.0,
    )
    plate = plate.cut(center_clearance).clean()
    dowel_radius = float(contract.integration["drive_plate_dowel_radius_mm"])
    dowel_angles = tuple(
        float(value) for value in contract.integration["drive_plate_dowel_angles_deg"]
    )
    dowel_hole_radius = float(
        contract.integration["drive_plate_dowel_hole_diameter_mm"]
    ) / 2.0
    dowel_pin_radius = float(
        contract.integration["drive_plate_dowel_pin_diameter_mm"]
    ) / 2.0
    for angle_deg in dowel_angles:
        radial = _unit_radial(angle_deg)
        center = (dowel_radius * radial[0], dowel_radius * radial[1], 0.0)
        plate = plate.cut(
            _vertical_cylinder(center, dowel_hole_radius, -109.0, -101.0)
        ).clean()
    register_z0, register_z1 = (
        float(value) for value in contract.integration["drive_register_z_mm"]
    )
    register = _vertical_ring(
        (0.0, 0.0, 0.0),
        float(contract.integration["drive_register_outer_radius_mm"]),
        float(contract.integration["drive_register_inner_radius_mm"]),
        register_z0,
        register_z1,
    )
    plate = plate.fuse(register).clean()
    components: dict[str, cq.Shape] = {"removable_motor_plate": plate}
    motor_names: list[str] = []
    integration = contract.integration
    motor_tip_z = float(contract.drive.m2006_output_tip_z_mm)
    motor_projection = float(contract.drive.m2006_output_projection_mm)
    motor_face_z = motor_tip_z - motor_projection
    motor_back_z = motor_tip_z - float(contract.drive.m2006_total_length_mm)
    crosshole_z = motor_tip_z - float(
        contract.drive.m2006_crosshole_center_from_tip_mm
    )
    motor_radius = float(integration["m2006_motor_casing_diameter_mm"]) / 2.0
    motor_shaft_radius = float(contract.drive.m2006_output_shaft_diameter_mm) / 2.0
    motor_d_flat_from_axis = float(integration["m2006_motor_d6_flat_from_axis_mm"])
    motor_crosshole_radius = float(contract.drive.m2006_crosshole_diameter_mm) / 2.0
    pin_radius = float(integration["m2006_input_shaft_cross_pin_diameter_mm"]) / 2.0
    pin_length = float(integration["m2006_input_shaft_cross_pin_length_mm"])
    for axis in axes:
        name = f"removable_M2006_{axis.axis_index:02d}"
        motor = _vertical_cylinder(axis.motor_center, motor_radius, motor_back_z, motor_face_z)
        output_shaft = _vertical_cylinder(
            axis.motor_center, motor_shaft_radius, motor_face_z, motor_tip_z
        ).cut(
            _flat_cut(
                axis.motor_center,
                axis.angle_deg,
                motor_d_flat_from_axis,
                motor_face_z,
                motor_tip_z,
            )
        ).clean()
        crosshole = _radial_cylinder_at(
            axis.motor_center,
            axis.angle_deg,
            motor_crosshole_radius + 0.05,
            -4.0,
            4.0,
            crosshole_z,
        )
        motor = motor.fuse(output_shaft).cut(crosshole).clean()
        components[name] = motor
        components[f"removable_M2006_cross_pin_{axis.axis_index:02d}"] = (
            _radial_cylinder_at(
                axis.motor_center,
                axis.angle_deg,
                pin_radius,
                -pin_length / 2.0,
                pin_length / 2.0,
                crosshole_z,
            )
        )
        radial = _unit_radial(axis.angle_deg)
        tangent = _unit_tangent(axis.angle_deg)
        mount_tabs = [
            _oriented_box(
                _combine(
                    radial,
                    tangent,
                    float(contract.drive.tendon_tangent_radius_mm) - 8.0,
                    -float(integration["motor_tangent_offset_mm"]) + tangent_offset,
                    -103.0,
                ),
                8.0,
                4.0,
                4.0,
                axis.angle_deg,
            )
            for tangent_offset in (-5.0, 0.0, 5.0)
        ]
        components[f"removable_motor_cradle_{axis.axis_index:02d}"] = (
            cq.Compound.makeCompound(mount_tabs)
        )
        motor_names.append(name)
    for index, angle_deg in enumerate(dowel_angles, start=1):
        radial = _unit_radial(angle_deg)
        center = (dowel_radius * radial[0], dowel_radius * radial[1], 0.0)
        components[f"removable_plate_dowel_{index:02d}"] = _vertical_cylinder(
            center, dowel_pin_radius, -106.0, -98.0
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
            "remove_lower_cover_panels_and_bottom_frame",
            "disconnect_motor_harnesses",
            "remove_three_motor_cross_pins",
            "translate_plate_downward_to_withdraw_D6_shafts",
        ),
    )


def build_fixed_base(
    contract: Any, root: Any, axes: Sequence[DriveAxis] | None = None
) -> FixedBaseResult:
    axes = tuple(axes or optimize_drive_axes(contract, root))
    top_plate = _hex_prism(125.0, -8.0, 8.0)
    register_service_clearance = _vertical_cylinder(
        (0.0, 0.0, 0.0),
        90.25,
        -8.2,
        0.2,
    )
    top_plate = top_plate.cut(register_service_clearance).clean()
    components: dict[str, cq.Shape] = {
        "fixed_top_plate": top_plate,
        "fixed_root_receiver": root.base_side_receiver,
    }
    outer_shell = _vertical_ring((0.0, 0.0, 0.0), 132.0, 128.0, -110.0, -8.0)
    inner_shell = _vertical_ring((0.0, 0.0, 0.0), 72.0, 68.5, -110.0, -8.0)
    relief_radius = float(
        contract.integration["canister_motor_port_relief_diameter_mm"]
    ) / 2.0
    relief_z = float(contract.integration["canister_motor_port_relief_z_mm"])
    relief_start, relief_end = (
        float(value)
        for value in contract.integration["canister_motor_port_relief_radial_range_mm"]
    )
    for angle_deg in contract.integration["canister_motor_port_relief_angles_deg"]:
        inner_shell = inner_shell.cut(
            _radial_cylinder(
                float(angle_deg), relief_radius, relief_start, relief_end, relief_z
            )
        ).clean()
    components["fixed_common_motor_chamber"] = cq.Compound.makeCompound(
        [outer_shell, inner_shell]
    )
    seat_z0, seat_z1 = (
        float(value)
        for value in contract.integration["fixed_drive_register_seat_z_mm"]
    )
    components["fixed_drive_plate_register_seat"] = _vertical_ring(
        (0.0, 0.0, 0.0),
        float(contract.integration["fixed_drive_register_seat_outer_radius_mm"]),
        float(contract.integration["fixed_drive_register_seat_inner_radius_mm"]),
        seat_z0,
        seat_z1,
    )
    dowel_radius = float(contract.integration["drive_plate_dowel_radius_mm"])
    dowel_angles = tuple(
        float(value) for value in contract.integration["drive_plate_dowel_angles_deg"]
    )
    for index, angle_deg in enumerate(dowel_angles, start=1):
        radial = _unit_radial(angle_deg)
        center = (dowel_radius * radial[0], dowel_radius * radial[1], 0.0)
        components[f"fixed_drive_plate_dowel_socket_{index:02d}"] = _vertical_ring(
            center,
            float(contract.integration["fixed_drive_plate_dowel_socket_outer_radius_mm"]),
            float(contract.integration["fixed_drive_plate_dowel_socket_inner_radius_mm"]),
            -106.0,
            -98.0,
        )
    support_pairs: list[tuple[str, str]] = []
    shaft_radius = float(contract.integration["fixed_shaft_diameter_mm"]) / 2.0
    radial_clearance = float(contract.integration["bearing_radial_clearance_mm"])
    bearing_inner_radius = shaft_radius + radial_clearance
    bearing_outer_radius = float(contract.integration["bearing_dimensions_mm"][1]) / 2.0
    bearing_seat_inner_radius = float(
        contract.integration["bearing_outer_seat_diameter_mm"]
    ) / 2.0
    input_bearing_ranges = tuple(
        tuple(float(value) for value in bounds)
        for bounds in contract.integration["input_shaft_bearing_z_ranges_mm"]
    )
    output_bearing_ranges = tuple(
        tuple(float(value) for value in bounds)
        for bounds in contract.integration["output_shaft_bearing_ranges_mm"]
    )
    output_seal_ranges = tuple(
        tuple(float(value) for value in bounds)
        for bounds in contract.integration["output_shaft_seal_ranges_mm"]
    )
    output_labyrinth_ranges = tuple(
        tuple(float(value) for value in bounds)
        for bounds in contract.integration["output_shaft_labyrinth_ranges_mm"]
    )
    spool_ranges = tuple(
        tuple(float(value) for value in bounds)
        for bounds in contract.integration["spool_axial_ranges_mm"]
    )
    motor_tip_z = float(contract.drive.m2006_output_tip_z_mm)
    motor_projection = float(contract.drive.m2006_output_projection_mm)
    socket_start_z = motor_tip_z - float(
        contract.integration["m2006_input_shaft_socket_depth_mm"]
    )
    input_shaft_collar_end_z = input_bearing_ranges[0][0] - float(
        contract.integration["m2006_input_shaft_collar_bearing_clearance_mm"]
    )
    motor_crosshole_z = motor_tip_z - float(
        contract.drive.m2006_crosshole_center_from_tip_mm
    )
    input_collar_radius = float(
        contract.integration["m2006_input_shaft_collar_diameter_mm"]
    ) / 2.0
    motor_socket_radius = float(
        contract.integration["m2006_input_shaft_socket_diameter_mm"]
    ) / 2.0
    motor_socket_flat_from_axis = float(
        contract.integration["m2006_input_shaft_socket_flat_from_axis_mm"]
    )
    crosshole_clearance = float(
        contract.integration["m2006_input_shaft_cross_pin_hole_diameter_mm"]
    ) / 2.0
    input_post_outer = float(contract.integration["input_support_post_outer_radius_mm"])
    input_post_inner = float(contract.integration["input_support_post_inner_radius_mm"])
    gear_review = contract.integration["gear_hardware_review"]
    gear_radius = float(gear_review["outside_diameter_mm"]) / 2.0
    gear_pitch_diameter = float(gear_review["pitch_diameter_mm"])
    gear_face_width = float(gear_review["face_width_mm"])
    gear_hub_diameter = float(gear_review["hub_diameter_mm"])
    gear_hub_width = float(gear_review["hub_width_mm"])
    gear_bore_diameter = float(gear_review["bore_diameter_mm"])
    gear_journal_radius = float(gear_review["gear_journal_diameter_mm"]) / 2.0
    gear_journal_flat = float(gear_review["gear_journal_flat_from_axis_mm"])
    gear_outer_depth = gear_pitch_diameter / 2.0
    gear_inner_depth = gear_outer_depth - gear_face_width / math.sqrt(2.0)
    gear_total_depth = gear_outer_depth + gear_hub_width
    seal_outer_radius = float(contract.integration["pressure_seal_housing_bore_diameter_mm"]) / 2.0
    seal_housing_axial_overrun = float(
        contract.integration["pressure_seal_housing_axial_overrun_mm"]
    )
    seal_retainer_outer_radius = float(
        contract.integration["seal_retaining_shoulder_outer_diameter_mm"]
    ) / 2.0
    seal_retainer_inner_radius = float(
        contract.integration["seal_retaining_shoulder_opening_diameter_mm"]
    ) / 2.0
    seal_retainer_width = float(
        contract.integration["seal_retaining_shoulder_axial_width_mm"]
    )
    seal_inner_radius = bearing_inner_radius
    spool_core_radius = float(contract.drive.spool_core_radius_mm)
    spool_flange_radius = float(contract.integration["spool_flange_radius_mm"])
    spool_bore_radius = float(contract.integration["wet_spool_bore_diameter_mm"]) / 2.0
    spool_drive_pin_radius = float(
        contract.integration["wet_spool_drive_pin_diameter_mm"]
    ) / 2.0
    spool_drive_pin_hole_radius = float(
        contract.integration["wet_spool_drive_pin_hole_diameter_mm"]
    ) / 2.0
    spool_drive_pin_length = float(
        contract.integration["wet_spool_drive_pin_length_mm"]
    )
    pod_radial_width = float(contract.integration["bevel_pod_radial_width_mm"])
    drive_pod_bounds = tuple(
        float(value) for value in contract.integration["drive_bevel_pod_tangent_bounds_mm"]
    )
    far_pod_bounds = tuple(
        float(value) for value in contract.integration["far_support_pod_tangent_bounds_mm"]
    )
    pod_z_bounds = tuple(
        float(value) for value in contract.integration["bevel_pod_z_bounds_mm"]
    )
    drive_cavity_bounds = tuple(
        float(value)
        for value in contract.integration["drive_bevel_pod_cavity_tangent_bounds_mm"]
    )
    far_cavity_bounds = tuple(
        float(value)
        for value in contract.integration["far_support_pod_cavity_tangent_bounds_mm"]
    )
    pod_cavity_z_bounds = tuple(
        float(value) for value in contract.integration["bevel_pod_cavity_z_bounds_mm"]
    )
    output_support_cartridge_outer_radius = float(
        contract.integration["output_support_cartridge_outer_diameter_mm"]
    ) / 2.0
    output_support_cartridge_inner_radius = float(
        contract.integration["output_support_cartridge_inner_diameter_mm"]
    ) / 2.0
    output_support_cartridge_bore_radius = float(
        contract.integration["output_support_cartridge_bore_diameter_mm"]
    ) / 2.0
    output_support_cartridge_lug_length = float(
        contract.integration["output_support_cartridge_end_lug_thickness_mm"]
    )
    output_support_cartridge_lug_radial_width = float(
        contract.integration["output_support_cartridge_lug_radial_width_mm"]
    )
    output_support_cartridge_lug_height = float(
        contract.integration["output_support_cartridge_lug_height_mm"]
    )
    output_support_cartridge_lug_z_offset = float(
        contract.integration["output_support_cartridge_lug_z_offset_mm"]
    )
    output_support_cartridge_service_travel = float(
        contract.integration["output_support_cartridge_service_travel_mm"]
    )
    output_support_screw_radius = float(
        contract.integration["output_support_cartridge_fastener_shank_diameter_mm"]
    ) / 2.0
    output_support_screw_tap_radius = float(
        contract.integration["output_support_cartridge_fastener_tap_drill_diameter_mm"]
    ) / 2.0
    output_support_screw_clearance_radius = float(
        contract.integration["output_support_cartridge_fastener_clearance_diameter_mm"]
    ) / 2.0
    output_support_screw_head_radius = float(
        contract.integration["output_support_cartridge_fastener_head_diameter_mm"]
    ) / 2.0
    output_support_screw_head_depth = float(
        contract.integration["output_support_cartridge_fastener_head_depth_mm"]
    )
    output_support_screw_engagement = float(
        contract.integration["output_support_cartridge_fastener_engagement_mm"]
    )

    for axis in axes:
        index = axis.axis_index
        center = axis.motor_center
        spool_center = axis.spool_center
        tangent = axis.spool_axis
        # The motor axis is vertical and the spool axis is tangential. Their
        # centerlines intersect at the bevel pair's pitch-cone apex.
        gear_apex = (center[0], center[1], spool_center[2])
        gear_apex_s = -float(contract.integration["motor_tangent_offset_mm"])
        input_gear_axis = (0.0, 0.0, -1.0)
        output_gear_axis = tuple(-value for value in tangent)
        input_hub_z0 = spool_center[2] - gear_total_depth
        input_hub_z1 = spool_center[2] - gear_outer_depth

        # The M2006 D6 socket, cross-pin collar, vertical input shaft, and
        # stepped 8 mm gear journal are one fixed-base part.
        input_shaft = _vertical_cylinder(
            center, shaft_radius, motor_tip_z, spool_center[2] - gear_inner_depth
        )
        input_shaft = input_shaft.cut(
            _vertical_cylinder(
                center,
                shaft_radius + 0.05,
                input_hub_z0,
                spool_center[2] - gear_inner_depth,
            )
        ).fuse(
            _vertical_cylinder(
                center,
                gear_journal_radius,
                input_hub_z0,
                spool_center[2] - gear_inner_depth,
            )
        )
        input_shaft = input_shaft.cut(
            _flat_cut(center, axis.angle_deg, gear_journal_flat, input_hub_z0, input_hub_z1)
        ).clean()
        input_shaft = input_shaft.fuse(
            _vertical_cylinder(
                center,
                input_collar_radius,
                socket_start_z,
                input_shaft_collar_end_z,
            )
        ).clean()
        input_shaft = input_shaft.cut(
            _vertical_d_bore(
                center,
                motor_socket_radius,
                motor_socket_flat_from_axis,
                axis.angle_deg,
                socket_start_z,
                motor_tip_z,
            )
        ).cut(
            _radial_cylinder_at(
                center,
                axis.angle_deg,
                crosshole_clearance,
                -input_collar_radius - 0.5,
                input_collar_radius + 0.5,
                motor_crosshole_z,
            )
        ).clean()

        # The removable drive remains dry. Separate drive-side and far-side pods
        # seal the exposed wet spool without crossing its radial cable tangent.
        motor_radial = _unit_radial(axis.angle_deg)
        pod_center_z = 0.5 * (pod_z_bounds[0] + pod_z_bounds[1])
        pod_height = pod_z_bounds[1] - pod_z_bounds[0]
        def make_dry_pod(
            tangent_bounds: tuple[float, float],
            cavity_bounds: tuple[float, float],
            seal_range: tuple[float, float],
            with_input_support: bool,
        ) -> cq.Shape:
            pod_center_t = 0.5 * (tangent_bounds[0] + tangent_bounds[1])
            pod_center = _combine(
                motor_radial,
                tangent,
                float(contract.drive.tendon_tangent_radius_mm),
                pod_center_t,
                pod_center_z,
            )
            pod_outer = _oriented_box(
                pod_center,
                pod_radial_width,
                tangent_bounds[1] - tangent_bounds[0],
                pod_height,
                axis.angle_deg,
            )
            cavity_center = _combine(
                motor_radial,
                tangent,
                float(contract.drive.tendon_tangent_radius_mm),
                0.5 * (cavity_bounds[0] + cavity_bounds[1]),
                0.5 * (pod_cavity_z_bounds[0] + pod_cavity_z_bounds[1]),
            )
            pod_cavity = _oriented_box(
                cavity_center,
                pod_radial_width - 3.0,
                cavity_bounds[1] - cavity_bounds[0],
                pod_cavity_z_bounds[1] - pod_cavity_z_bounds[0],
                axis.angle_deg,
            )
            shell = pod_outer.cut(pod_cavity)
            shell = shell.cut(
                _axis_cylinder(
                    spool_center,
                    tangent,
                    seal_outer_radius,
                    seal_range[0] - seal_housing_axial_overrun,
                    seal_range[1] + seal_housing_axial_overrun,
                )
            )
            dry_face = seal_range[0] if seal_range[0] < 0.0 else seal_range[1]
            if dry_face < 0.0:
                retainer_range = (dry_face - seal_retainer_width, dry_face)
            else:
                retainer_range = (dry_face, dry_face + seal_retainer_width)
            integral_retainer = _axis_ring(
                spool_center,
                tangent,
                seal_retainer_outer_radius,
                seal_retainer_inner_radius,
                retainer_range[0],
                retainer_range[1],
            )
            shell = shell.fuse(integral_retainer).clean()
            if with_input_support:
                shell = shell.cut(
            _vertical_cylinder(
                    center,
                    input_collar_radius + 0.25,
                    pod_z_bounds[0] - 0.1,
                    pod_z_bounds[0] + 3.1,
                )
                )
            return shell

        drive_pod = make_dry_pod(
            drive_pod_bounds, drive_cavity_bounds, output_seal_ranges[0], True
        )
        far_pod = make_dry_pod(
            far_pod_bounds, far_cavity_bounds, output_seal_ranges[1], False
        )
        # Support the long output shaft close to its gear hub and on the far
        # side of the spool. Each bulkhead bridges the 6900 seat to the pod wall.
        output_bearing_support_outer = pod_radial_width / 2.0 - 0.5
        for station, (s0, s1) in enumerate(output_bearing_ranges):
            support = _axis_ring(
                spool_center,
                tangent,
                output_bearing_support_outer,
                bearing_seat_inner_radius,
                s0,
                s1,
            )
            if station == 0:
                drive_pod = drive_pod.fuse(support).clean()
            else:
                far_pod = far_pod.fuse(support).clean()

        far_pod = far_pod.cut(
            _axis_cylinder(
                spool_center,
                tangent,
                output_support_cartridge_bore_radius,
                far_pod_bounds[0] - 0.2,
                far_pod_bounds[1] + 0.2,
            )
        ).clean()
        output_support_cartridge = _axis_ring(
            spool_center,
            tangent,
            output_support_cartridge_outer_radius,
            output_support_cartridge_inner_radius,
            far_pod_bounds[0],
            far_pod_bounds[1],
        )
        outboard_seal_retainer_start = output_seal_ranges[1][1]
        output_support_cartridge = output_support_cartridge.fuse(
            _axis_ring(
                spool_center,
                tangent,
                seal_retainer_outer_radius,
                seal_retainer_inner_radius,
                outboard_seal_retainer_start,
                outboard_seal_retainer_start + seal_retainer_width,
            )
        ).clean()
        cartridge_end = far_pod_bounds[1]
        bolt_centers = (
            (spool_center[0], spool_center[1], spool_center[2] - output_support_cartridge_lug_z_offset),
            (spool_center[0], spool_center[1], spool_center[2] + output_support_cartridge_lug_z_offset),
        )
        support_screws: list[cq.Shape] = []
        for screw_index, bolt_center in enumerate(bolt_centers, start=1):
            lug_center = (
                bolt_center[0] + tangent[0] * (cartridge_end + output_support_cartridge_lug_length / 2.0),
                bolt_center[1] + tangent[1] * (cartridge_end + output_support_cartridge_lug_length / 2.0),
                bolt_center[2],
            )
            lug = _oriented_box(
                lug_center,
                output_support_cartridge_lug_radial_width,
                output_support_cartridge_lug_length,
                output_support_cartridge_lug_height,
                axis.angle_deg,
            )
            output_support_cartridge = output_support_cartridge.fuse(lug).clean()
            output_support_cartridge = output_support_cartridge.cut(
                _axis_cylinder(
                    bolt_center,
                    tangent,
                    output_support_screw_clearance_radius,
                    cartridge_end - 0.1,
                    cartridge_end + output_support_cartridge_lug_length + 0.1,
                )
            ).cut(
                _axis_cylinder(
                    bolt_center,
                    tangent,
                    output_support_screw_head_radius + 0.1,
                    cartridge_end + output_support_cartridge_lug_length - output_support_screw_head_depth,
                    cartridge_end + output_support_cartridge_lug_length + 0.1,
                )
            ).clean()
            far_pod = far_pod.cut(
                _axis_cylinder(
                    bolt_center,
                    tangent,
                    output_support_screw_tap_radius,
                    cartridge_end - output_support_screw_engagement,
                    cartridge_end + 0.1,
                )
            ).clean()
            screw_shank_end = cartridge_end + output_support_cartridge_lug_length - output_support_screw_head_depth
            screw = _axis_cylinder(
                bolt_center,
                tangent,
                output_support_screw_radius,
                cartridge_end - output_support_screw_engagement,
                screw_shank_end,
            ).fuse(
                _axis_cylinder(
                    bolt_center,
                    tangent,
                    output_support_screw_head_radius,
                    screw_shank_end,
                    cartridge_end + output_support_cartridge_lug_length,
                )
            ).clean()
            support_screws.append(screw)

        vertical_gear = _catalog_miter_envelope(
            gear_apex,
            input_gear_axis,
            gear_radius,
            gear_pitch_diameter,
            gear_face_width,
            gear_hub_diameter,
            gear_hub_width,
            gear_bore_diameter,
        )
        horizontal_gear = _catalog_miter_envelope(
            gear_apex,
            output_gear_axis,
            gear_radius,
            gear_pitch_diameter,
            gear_face_width,
            gear_hub_diameter,
            gear_hub_width,
            gear_bore_diameter,
        )

        # M4 radial set screws bear on D-flats. The tapped holes are secondary
        # operations on stock plain-bore hubs and need hardness/manufacturer review.
        set_screw_radius = float(gear_review.get("set_screw_diameter_mm", 4.0)) / 2.0
        input_hub_center_z = 0.5 * (input_hub_z0 + input_hub_z1)
        vertical_gear = vertical_gear.cut(
            _radial_cylinder_at(
                center,
                axis.angle_deg,
                set_screw_radius + 0.1,
                gear_journal_flat - 0.2,
                gear_hub_diameter / 2.0 + 0.2,
                input_hub_center_z,
            )
        ).clean()
        output_hub_center_s = gear_apex_s - gear_outer_depth - gear_hub_width / 2.0
        output_hub_center = _combine(
            motor_radial,
            tangent,
            float(contract.drive.tendon_tangent_radius_mm),
            output_hub_center_s,
            spool_center[2],
        )
        horizontal_gear = horizontal_gear.cut(
            _radial_cylinder_at(
                output_hub_center,
                axis.angle_deg,
                set_screw_radius + 0.1,
                gear_journal_flat - 0.2,
                gear_hub_diameter / 2.0 + 0.2,
                spool_center[2],
            )
        ).clean()

        # Local top-plate reliefs clear the catalog-sized, toothless envelopes.
        # The outside across vertices remains 250 mm; these are local cut-outs.
        clearance = 0.8
        for gear_axis in (input_gear_axis, output_gear_axis):
            gear_relief = _catalog_miter_envelope(
                gear_apex,
                gear_axis,
                gear_radius + clearance,
                gear_pitch_diameter,
                gear_face_width,
                gear_hub_diameter + 2.0 * clearance,
                gear_hub_width + 2.0 * clearance,
                0.0,
            )
            top_plate = top_plate.cut(gear_relief).clean()

        # Clear the fixed plate through the full cartridge path. The bore
        # relieves the sleeve; the narrow lower slot relieves its mounting lug.
        support_path_start = far_pod_bounds[0] - 0.2
        support_path_end = (
            far_pod_bounds[1]
            + output_support_cartridge_lug_length
            + output_support_cartridge_service_travel
            + 0.2
        )
        top_plate = top_plate.cut(
            _axis_cylinder(
                spool_center,
                tangent,
                output_support_cartridge_bore_radius,
                support_path_start,
                support_path_end,
            )
        ).clean()
        lower_lug_clearance = _oriented_box(
            _combine(
                motor_radial,
                tangent,
                float(contract.drive.tendon_tangent_radius_mm),
                0.5 * (support_path_start + support_path_end),
                spool_center[2] - output_support_cartridge_lug_z_offset,
            ),
            output_support_cartridge_lug_radial_width + 0.4,
            support_path_end - support_path_start,
            output_support_cartridge_lug_height + 0.4,
            axis.angle_deg,
        )
        top_plate = top_plate.cut(lower_lug_clearance).clean()

        output_shaft = _axis_cylinder(
            spool_center,
            tangent,
            shaft_radius,
            drive_cavity_bounds[0],
            far_cavity_bounds[1],
        )
        gear_journal_s0 = gear_apex_s - gear_total_depth
        gear_journal_s1 = gear_apex_s - gear_inner_depth
        output_shaft = output_shaft.cut(
            _axis_cylinder(
                spool_center,
                tangent,
                shaft_radius + 0.05,
                gear_journal_s0,
                gear_journal_s1,
            )
        ).fuse(
            _axis_cylinder(
                spool_center,
                tangent,
                gear_journal_radius,
                gear_journal_s0,
                gear_journal_s1,
            )
        )
        output_shaft = output_shaft.cut(
            _axis_flat_cut(
                spool_center,
                axis.angle_deg,
                gear_journal_flat,
                gear_apex_s - gear_total_depth,
                gear_apex_s - gear_outer_depth,
            )
        )
        output_shaft = output_shaft.cut(
            _radial_cylinder_at(
                spool_center,
                axis.angle_deg,
                spool_drive_pin_hole_radius,
                -shaft_radius - 0.1,
                shaft_radius + 0.1,
                spool_center[2],
            )
        ).clean()
        shoulder_width = float(
            contract.integration["wet_spool_inboard_shoulder_width_mm"]
        )
        shoulder_diameter = float(
            contract.integration["wet_spool_inboard_shoulder_diameter_mm"]
        )
        spool_retainer_groove_diameter = float(
            contract.integration["wet_spool_retainer_groove_diameter_mm"]
        )
        spool_retainer_groove_width = float(
            contract.integration["wet_spool_retainer_groove_width_mm"]
        )
        spool_retainer_outer_diameter = float(
            contract.integration["wet_spool_retainer_outer_diameter_mm"]
        )
        spool_side_clearance = float(
            contract.integration["wet_spool_side_clearance_mm"]
        )
        spool_inner_face = spool_ranges[0][0]
        spool_outer_face = spool_ranges[2][1]
        shoulder_s1 = spool_inner_face - spool_side_clearance
        shoulder_s0 = shoulder_s1 - shoulder_width
        groove_s0 = spool_outer_face + spool_side_clearance
        groove_s1 = groove_s0 + spool_retainer_groove_width
        output_shaft = output_shaft.fuse(
            _axis_cylinder(
                spool_center,
                tangent,
                shoulder_diameter / 2.0,
                shoulder_s0,
                shoulder_s1,
            )
        ).clean()
        output_shaft = output_shaft.cut(
            _axis_ring(
                spool_center,
                tangent,
                shaft_radius + 0.05,
                spool_retainer_groove_diameter / 2.0,
                groove_s0,
                groove_s1,
            )
        ).clean()
        spool_core = _axis_cylinder(
            spool_center, tangent, spool_core_radius, spool_ranges[1][0], spool_ranges[1][1]
        )
        spool_flange_a = _axis_cylinder(
            spool_center, tangent, spool_flange_radius, spool_ranges[0][0], spool_ranges[0][1]
        )
        spool_flange_b = _axis_cylinder(
            spool_center, tangent, spool_flange_radius, spool_ranges[2][0], spool_ranges[2][1]
        )
        spool = spool_core.fuse(spool_flange_a, spool_flange_b).clean()
        spool = spool.cut(
            _axis_cylinder(
                spool_center,
                tangent,
                spool_bore_radius,
                spool_ranges[0][0] - 0.1,
                spool_ranges[2][1] + 0.1,
            )
        ).cut(
            _radial_cylinder_at(
                spool_center,
                axis.angle_deg,
                spool_drive_pin_hole_radius,
                -spool_core_radius - 0.2,
                spool_core_radius + 0.2,
                spool_center[2],
            )
        ).clean()

        bearing_names: list[str] = []
        for station, (s0, s1) in enumerate(output_bearing_ranges, start=1):
            bearing_name = (
                f"fixed_bearing_inner_{index:02d}"
                if station == 1
                else f"fixed_bearing_outer_{index:02d}"
            )
            bearing_names.append(bearing_name)
            components[bearing_name] = _axis_ring(
                spool_center,
                tangent,
                bearing_outer_radius,
                bearing_inner_radius,
                s0,
                s1,
            )
        for side, seal_range, labyrinth_range in zip(
            ("drive_side", "outboard"), output_seal_ranges, output_labyrinth_ranges
        ):
            components[f"fixed_oil_seal_{side}_{index:02d}"] = _axis_ring(
                spool_center,
                tangent,
                seal_outer_radius,
                seal_inner_radius,
                *seal_range,
            )
            components[f"fixed_labyrinth_{side}_{index:02d}"] = _axis_ring(
                spool_center,
                tangent,
                float(contract.integration["labyrinth_outer_radius_mm"]),
                shaft_radius + float(contract.integration["labyrinth_radial_clearance_mm"]),
                *labyrinth_range,
            )
        components[f"fixed_spool_retainer_{index:02d}"] = _axis_ring(
            spool_center,
            tangent,
            spool_retainer_outer_diameter / 2.0,
            spool_retainer_groove_diameter / 2.0,
            groove_s0,
            groove_s1,
        )
        components[f"fixed_spool_drive_pin_{index:02d}"] = _radial_cylinder_at(
            spool_center,
            axis.angle_deg,
            spool_drive_pin_radius,
            -spool_drive_pin_length / 2.0,
            spool_drive_pin_length / 2.0,
            spool_center[2],
        )
        for station, (s0, s1) in enumerate(input_bearing_ranges, start=1):
            components[f"fixed_input_bearing_{station}_{index:02d}"] = _vertical_ring(
                center, bearing_outer_radius, bearing_inner_radius, s0, s1
            )
        input_post_z0, input_post_z1 = (
            float(value)
            for value in contract.integration["input_support_post_z_bounds_mm"]
        )
        input_post = _vertical_ring(
            center, input_post_outer, input_post_inner, input_post_z0, input_post_z1
        ).clean()
        components[f"fixed_input_support_post_{index:02d}"] = input_post
        components[f"fixed_bevel_pod_{index:02d}"] = drive_pod
        components[f"fixed_output_support_land_{index:02d}"] = far_pod
        components[f"fixed_output_support_cartridge_{index:02d}"] = output_support_cartridge
        for screw_index, screw in enumerate(support_screws, start=1):
            components[
                f"fixed_output_support_cartridge_screw_{index:02d}_{screw_index:02d}"
            ] = screw
        components[f"fixed_bevel_input_envelope_{index:02d}"] = vertical_gear
        components[f"fixed_bevel_output_envelope_{index:02d}"] = horizontal_gear
        components[f"fixed_wet_spool_{index:02d}"] = spool
        components[f"fixed_shaft_{index:02d}"] = input_shaft
        components[f"fixed_output_shaft_{index:02d}"] = output_shaft
        support_pairs.append((bearing_names[0], bearing_names[1]))

    components["fixed_top_plate"] = top_plate.clean()
    for x_mm, y_mm, _ in root.fastener_centers:
        probe = _vertical_cylinder((x_mm, y_mm, 0.0), 2.75, -9.0, 11.0)
        components["fixed_top_plate"] = components["fixed_top_plate"].cut(probe).clean()
    cover_mount_radius = 100.0
    for angle_deg in (30.0, 90.0, 150.0, 210.0, 270.0, 330.0):
        radial = _unit_radial(angle_deg)
        center = (
            cover_mount_radius * radial[0],
            cover_mount_radius * radial[1],
            0.0,
        )
        components["fixed_top_plate"] = components["fixed_top_plate"].cut(
            _vertical_cylinder(center, 1.6, -8.1, 0.1)
        ).clean()
    guard_cfg = contract.integration["root_cover"]
    fastener_radius = float(guard_cfg["root_guard_fastener_center_radius_mm"])
    pocket_radius = 0.5 * float(guard_cfg["root_guard_insert_pocket_diameter_mm"])
    pocket_depth = float(guard_cfg["root_guard_insert_pocket_depth_mm"])
    for angle_deg in guard_cfg["root_guard_fastener_angles_deg"]:
        radial = _unit_radial(float(angle_deg))
        center = (fastener_radius * radial[0], fastener_radius * radial[1], 0.0)
        components["fixed_top_plate"] = components["fixed_top_plate"].cut(
            _vertical_cylinder(center, pocket_radius, -pocket_depth, 0.1)
        ).clean()
    tab_radius = float(guard_cfg["root_guard_alignment_tab_center_radius_mm"])
    tab_clearance = float(guard_cfg["root_guard_alignment_slot_clearance_mm"])
    tab_radial_width = float(guard_cfg["root_guard_alignment_tab_radial_width_mm"])
    tab_tangent_width = float(guard_cfg["root_guard_alignment_tab_tangent_width_mm"])
    tab_z0, _ = (float(value) for value in guard_cfg["root_guard_alignment_tab_z_bounds_mm"])
    for angle_deg in guard_cfg["root_guard_alignment_tab_angles_deg"]:
        radial = _unit_radial(float(angle_deg))
        center = (tab_radius * radial[0], tab_radius * radial[1], 0.5 * tab_z0)
        components["fixed_top_plate"] = components["fixed_top_plate"].cut(
            _oriented_box(
                center,
                tab_radial_width + 2.0 * tab_clearance,
                tab_tangent_width + 2.0 * tab_clearance,
                -tab_z0 + 0.2,
                float(angle_deg),
            )
        ).clean()
    return FixedBaseResult(
        components=components,
        top_plate=components["fixed_top_plate"],
        top_plate_circumdiameter_mm=float(
            contract.root_interface.top_plate_circumdiameter_mm
        ),
        axes=tuple(axes),
        shafts_supported_without_drive=(len(support_pairs) == 3),
        shaft_support_pairs=tuple(support_pairs),
    )
