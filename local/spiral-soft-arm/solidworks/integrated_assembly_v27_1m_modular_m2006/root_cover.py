from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import cadquery as cq


@dataclass(frozen=True)
class RootCoverResult:
    components: dict[str, cq.Shape]
    panel_names: tuple[str, ...]
    upper_panel_names: tuple[str, ...]
    lower_panel_names: tuple[str, ...]
    motor_window_panels: tuple[str, ...]
    observation_window_panels: tuple[str, ...]
    type_c_service_panel: str
    frame_names: tuple[str, ...]
    root_guard_name: str
    outer_circumdiameter_mm: float
    panel_height_mm: float
    print_envelope_mm: tuple[float, float, float]
    profile_stations_mm: tuple[tuple[float, float], ...]


def _unit(angle_deg: float) -> tuple[float, float, float]:
    angle = math.radians(angle_deg)
    return math.cos(angle), math.sin(angle), 0.0


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


def _hex_wire(circumradius_mm: float, z_mm: float) -> cq.Wire:
    points = [
        cq.Vector(
            circumradius_mm * math.cos(math.radians(index * 60.0)),
            circumradius_mm * math.sin(math.radians(index * 60.0)),
            z_mm,
        )
        for index in range(6)
    ]
    return cq.Wire.makePolygon(points + [points[0]])


def _hex_radial_boundary(circumradius_mm: float, angle_deg: float) -> float:
    face_normals = tuple(30.0 + 60.0 * index for index in range(6))
    delta_deg = min(
        abs((float(angle_deg) - normal_deg + 180.0) % 360.0 - 180.0)
        for normal_deg in face_normals
    )
    return circumradius_mm * math.cos(math.radians(30.0)) / math.cos(
        math.radians(delta_deg)
    )


def _face_box(
    normal_deg: float,
    normal_mm: float,
    tangent_mm: float,
    z_mm: float,
    width_mm: float,
    depth_mm: float,
    height_mm: float,
) -> cq.Shape:
    angle = normal_deg - 90.0
    return (
        cq.Workplane("XY")
        .box(width_mm, depth_mm, height_mm)
        .val()
        .rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), angle)
        .translate(
            (
                normal_mm * math.cos(math.radians(normal_deg))
                + tangent_mm * math.cos(math.radians(normal_deg + 90.0)),
                normal_mm * math.sin(math.radians(normal_deg))
                + tangent_mm * math.sin(math.radians(normal_deg + 90.0)),
                z_mm,
            )
        )
    )


def _face_hole(
    normal_deg: float,
    normal_mm: float,
    tangent_mm: float,
    z_mm: float,
    radius_mm: float,
    length_mm: float,
    inward: bool = True,
) -> cq.Shape:
    normal = _unit(normal_deg)
    tangent = _unit(normal_deg + 90.0)
    sign = -1.0 if inward else 1.0
    start_normal = normal_mm if inward else normal_mm - length_mm
    start = cq.Vector(
        start_normal * normal[0] + tangent_mm * tangent[0],
        start_normal * normal[1] + tangent_mm * tangent[1],
        z_mm,
    )
    direction = cq.Vector(sign * normal[0], sign * normal[1], 0.0)
    return cq.Solid.makeCylinder(radius_mm, length_mm, start, direction)


def _profile_frame(
    inner_radii_mm: tuple[float, float],
    outer_radii_mm: tuple[float, float],
    z_bounds_mm: tuple[float, float],
    bolt_radius_mm: float,
    bolt_offsets_mm: tuple[float, ...],
) -> cq.Shape:
    z0, z1 = z_bounds_mm
    outer = cq.Solid.makeLoft(
        [
            _hex_wire(outer_radii_mm[0], z0),
            _hex_wire(outer_radii_mm[1], z1),
        ],
        ruled=True,
    )
    inner = cq.Solid.makeLoft(
        [
            _hex_wire(inner_radii_mm[0], z0),
            _hex_wire(inner_radii_mm[1], z1),
        ],
        ruled=True,
    )
    frame = outer.cut(inner)
    center_z = (z0 + z1) / 2.0
    center_outer_radius = (outer_radii_mm[0] + outer_radii_mm[1]) / 2.0
    outer_apothem = center_outer_radius * math.cos(math.radians(30.0))
    for normal_deg in (30.0, 90.0, 150.0, 210.0, 270.0, 330.0):
        for offset in bolt_offsets_mm:
            frame = frame.cut(
                _face_hole(
                    normal_deg,
                    outer_apothem + 0.1,
                    offset,
                    center_z,
                    bolt_radius_mm,
                    18.0,
                )
            )
    return frame.clean()


def build_root_cover(contract: Any) -> RootCoverResult:
    cfg = contract.integration["root_cover"]
    outer_radius = float(cfg["outer_circumradius_mm"])
    panel_thickness = float(cfg["panel_thickness_mm"])
    z0, z1 = (float(value) for value in cfg["panel_z_bounds_mm"])
    height = z1 - z0
    split_z = float(cfg["panel_split_z_mm"])
    edge_gap = float(cfg["panel_edge_gap_mm"])
    frame_height = float(cfg["frame_height_mm"])
    frame_radial_thickness = float(cfg["frame_radial_thickness_mm"])
    if not math.isfinite(frame_radial_thickness) or frame_radial_thickness <= 0.0:
        raise ValueError("cover frame radial thickness must be finite and positive")
    surround_width = float(cfg["window_surround_width_mm"])
    surround_proud = float(cfg["window_surround_proud_mm"])
    surround_corner_clip = float(cfg["window_surround_corner_clip_mm"])
    surround_reveal = float(cfg["window_surround_reveal_mm"])
    if not all(
        math.isfinite(value) and value > 0.0
        for value in (
            surround_width,
            surround_proud,
            surround_corner_clip,
            surround_reveal,
        )
    ):
        raise ValueError("cover window surrounds require finite positive dimensions")
    frame_centers = tuple(float(value) for value in cfg["frame_z_centers_mm"])
    profile_stations = tuple(
        (float(z_mm), float(radius_mm))
        for z_mm, radius_mm in cfg["panel_profile_stations_mm"]
    )
    if len(profile_stations) < 2:
        raise ValueError("cover panel profile requires at least two stations")
    if any(
        not math.isfinite(z_mm) or not math.isfinite(radius_mm)
        for z_mm, radius_mm in profile_stations
    ):
        raise ValueError("cover panel profile stations and radii must be finite")
    if any(
        first[0] >= second[0]
        for first, second in zip(profile_stations, profile_stations[1:])
    ):
        raise ValueError("cover panel profile stations must increase in Z")
    if any(radius <= 0.0 for _, radius in profile_stations):
        raise ValueError("cover panel profile radii must be positive")
    if (
        abs(profile_stations[0][0] - z0) > 1e-6
        or abs(profile_stations[-1][0] - z1) > 1e-6
        or not any(abs(z_mm - split_z) <= 1e-6 for z_mm, _ in profile_stations)
    ):
        raise ValueError("cover profile must include panel bounds and the split plane")
    if abs(
        next(radius for z_mm, radius in profile_stations if abs(z_mm - split_z) <= 1e-6)
        - outer_radius
    ) > 1e-6:
        raise ValueError("cover split radius must match outer_circumradius_mm")
    if len(frame_centers) != 4:
        raise ValueError("cover requires four armor band center heights")
    bolt_radius = float(cfg["panel_fastener_diameter_mm"]) / 2.0
    bolt_offsets = tuple(float(value) for value in cfg["panel_fastener_tangent_offsets_mm"])
    normals = (30.0, 90.0, 150.0, 210.0, 270.0, 330.0)

    def radius_at(z_mm: float) -> float:
        for (za, ra), (zb, rb) in zip(profile_stations, profile_stations[1:]):
            if za - 1e-8 <= z_mm <= zb + 1e-8:
                fraction = (z_mm - za) / (zb - za)
                return ra + fraction * (rb - ra)
        raise ValueError(f"cover profile does not define z={z_mm:g} mm")

    def panel_solid(normal_deg: float, za: float, zb: float) -> cq.Shape:
        normal = _unit(normal_deg)
        tangent = _unit(normal_deg + 90.0)

        def section(z_mm: float) -> cq.Wire:
            apothem = radius_at(z_mm) * math.cos(math.radians(30.0))
            half_width = radius_at(z_mm) / 2.0 - edge_gap / 2.0
            corners = []
            for normal_offset, tangent_offset in (
                (apothem, -half_width),
                (apothem, half_width),
                (apothem - panel_thickness, half_width),
                (apothem - panel_thickness, -half_width),
            ):
                corners.append(
                    cq.Vector(
                        normal_offset * normal[0] + tangent_offset * tangent[0],
                        normal_offset * normal[1] + tangent_offset * tangent[1],
                        z_mm,
                    )
                )
            return cq.Wire.makePolygon(corners + [corners[0]])

        z_stations = [za]
        z_stations.extend(
            z_mm for z_mm, _ in profile_stations if za + 1e-8 < z_mm < zb - 1e-8
        )
        z_stations.append(zb)
        return cq.Solid.makeLoft([section(z_mm) for z_mm in z_stations], ruled=True)

    def cut_window(
        panel: cq.Shape,
        normal_deg: float,
        z_mm: float,
        window: tuple[float, float],
        panel_z_bounds: tuple[float, float],
    ) -> cq.Shape:
        width_mm, height_mm = (float(value) for value in window)
        window_z0 = z_mm - height_mm / 2.0
        window_z1 = z_mm + height_mm / 2.0
        panel_z0, panel_z1 = panel_z_bounds
        if window_z0 < panel_z0 - 1e-6 or window_z1 > panel_z1 + 1e-6:
            raise ValueError("cover service window must fit within its assigned panel Z bounds")
        face_center = radius_at(z_mm) * math.cos(math.radians(30.0)) - panel_thickness / 2.0
        window_stations = [window_z0, window_z1]
        window_stations.extend(
            station_z
            for station_z, _ in profile_stations
            if window_z0 < station_z < window_z1
        )
        maximum_profile_offset = max(
            abs(
                radius_at(station_z) * math.cos(math.radians(30.0))
                - panel_thickness / 2.0
                - face_center
            )
            for station_z in window_stations
        )
        cutter_depth = panel_thickness + 2.0 + 2.0 * maximum_profile_offset
        return panel.cut(
            _face_box(
                normal_deg,
                face_center,
                0.0,
                z_mm,
                width_mm,
                cutter_depth,
                height_mm,
            )
        )

    def add_window_surround(
        panel: cq.Shape,
        normal_deg: float,
        z_mm: float,
        window: tuple[float, float],
    ) -> cq.Shape:
        width_mm, height_mm = (float(value) for value in window)
        segment = next(
            (first, second)
            for first, second in zip(profile_stations, profile_stations[1:])
            if first[0] - 1e-8 <= z_mm <= second[0] + 1e-8
        )
        (za, ra), (zb, rb) = segment
        face_slope = math.cos(math.radians(30.0)) * (rb - ra) / (zb - za)
        normal_angle = math.radians(normal_deg)
        normal_scale = math.sqrt(1.0 + face_slope * face_slope)
        face_normal = cq.Vector(
            math.cos(normal_angle) / normal_scale,
            math.sin(normal_angle) / normal_scale,
            -face_slope / normal_scale,
        )
        tangent = cq.Vector(
            math.cos(math.radians(normal_deg + 90.0)),
            math.sin(math.radians(normal_deg + 90.0)),
            0.0,
        )
        face_apothem = radius_at(z_mm) * math.cos(math.radians(30.0))
        face_center = cq.Vector(
            face_apothem * math.cos(normal_angle),
            face_apothem * math.sin(normal_angle),
            z_mm,
        )
        projected_height = height_mm * normal_scale
        outer_width = width_mm + 2.0 * (surround_width + surround_reveal)
        outer_height = projected_height + 2.0 * (surround_width + surround_reveal)
        clip = min(surround_corner_clip, outer_width / 2.0, outer_height / 2.0)
        outline = [
            (-outer_width / 2.0 + clip, -outer_height / 2.0),
            (outer_width / 2.0 - clip, -outer_height / 2.0),
            (outer_width / 2.0, -outer_height / 2.0 + clip),
            (outer_width / 2.0, outer_height / 2.0 - clip),
            (outer_width / 2.0 - clip, outer_height / 2.0),
            (-outer_width / 2.0 + clip, outer_height / 2.0),
            (-outer_width / 2.0, outer_height / 2.0 - clip),
            (-outer_width / 2.0, -outer_height / 2.0 + clip),
        ]
        surround_plane = cq.Plane(
            origin=face_center - face_normal * 0.2,
            xDir=tangent,
            normal=face_normal,
        )
        surround = (
            cq.Workplane(surround_plane)
            .polyline(outline)
            .close()
            .extrude(surround_proud + 0.2)
            .val()
        )
        opening_plane = cq.Plane(
            origin=face_center - face_normal * 0.3,
            xDir=tangent,
            normal=face_normal,
        )
        opening = (
            cq.Workplane(opening_plane)
            .rect(
                width_mm + 2.0 * surround_reveal,
                projected_height + 2.0 * surround_reveal,
            )
            .extrude(surround_proud + 0.6)
            .val()
        )
        return panel.fuse(surround.cut(opening)).clean()

    components: dict[str, cq.Shape] = {}
    panel_names: list[str] = []
    upper_panel_names: list[str] = []
    lower_panel_names: list[str] = []
    motor_window_panels: list[str] = []
    observation_window_panels: list[str] = []
    normal_to_index = {normal: index for index, normal in enumerate(normals, start=1)}
    motor_normals = {90.0, 210.0, 330.0}
    observation_normals = {30.0, 150.0, 270.0}
    motor_z = float(cfg["motor_window_center_z_mm"])
    observation_z = float(cfg["observation_window_center_z_mm"])
    service_z = float(cfg["m12_service_window_center_z_mm"])
    type_c_service_panel = ""

    for normal_deg in normals:
        index = normal_to_index[normal_deg]
        upper_name = f"fixed_cover_upper_panel_{index:02d}"
        upper = panel_solid(normal_deg, split_z, z1)
        if normal_deg in motor_normals:
            upper = cut_window(
                upper,
                normal_deg,
                motor_z,
                tuple(cfg["motor_window_mm"]),
                (split_z, z1),
            )
            upper = add_window_surround(
                upper,
                normal_deg,
                motor_z,
                tuple(cfg["motor_window_mm"]),
            )
            motor_window_panels.append(upper_name)
        for frame_z in frame_centers:
            if split_z <= frame_z <= z1:
                for offset in bolt_offsets:
                    upper = upper.cut(
                        _face_hole(
                            normal_deg,
                            radius_at(frame_z) * math.cos(math.radians(30.0)) + 0.1,
                            offset,
                            frame_z,
                            bolt_radius,
                            panel_thickness + 0.2,
                        )
                    )
        upper = upper.clean()
        components[upper_name] = upper
        panel_names.append(upper_name)
        upper_panel_names.append(upper_name)

        lower_name = f"fixed_cover_lower_panel_{index:02d}"
        lower = panel_solid(normal_deg, z0, split_z)
        if normal_deg in observation_normals:
            lower = cut_window(
                lower,
                normal_deg,
                observation_z,
                tuple(cfg["observation_window_mm"]),
                (z0, split_z),
            )
            lower = add_window_surround(
                lower,
                normal_deg,
                observation_z,
                tuple(cfg["observation_window_mm"]),
            )
            observation_window_panels.append(lower_name)
        if normal_deg == 270.0:
            lower = cut_window(
                lower,
                normal_deg,
                service_z,
                tuple(cfg["m12_service_window_mm"]),
                (z0, split_z),
            )
            lower = add_window_surround(
                lower,
                normal_deg,
                service_z,
                tuple(cfg["m12_service_window_mm"]),
            )
            type_c_service_panel = lower_name
        for frame_z in frame_centers:
            if z0 <= frame_z <= split_z:
                for offset in bolt_offsets:
                    lower = lower.cut(
                        _face_hole(
                            normal_deg,
                            radius_at(frame_z) * math.cos(math.radians(30.0)) + 0.1,
                            offset,
                            frame_z,
                            bolt_radius,
                            panel_thickness + 0.2,
                        )
                    )
        lower = lower.clean()
        components[lower_name] = lower
        panel_names.append(lower_name)
        lower_panel_names.append(lower_name)

    frame_names: list[str] = []
    for index, frame_z in enumerate(frame_centers, start=1):
        band_z0 = frame_z - frame_height / 2.0
        band_z1 = frame_z + frame_height / 2.0
        inner_radii = (radius_at(band_z0), radius_at(band_z1))
        outer_radii = tuple(radius + frame_radial_thickness for radius in inner_radii)
        frame = _profile_frame(
            inner_radii,
            (outer_radii[0], outer_radii[1]),
            (band_z0, band_z1),
            bolt_radius,
            bolt_offsets,
        )
        if index == 1:
            # The low Type-C bezel runs through this band in Z. Relieve its
            # full projected footprint while keeping the two side flanks and
            # their original radial screw axes.
            service_window_height = float(cfg["m12_service_window_mm"][1])
            service_z = float(cfg["m12_service_window_center_z_mm"])
            segment = next(
                (first, second)
                for first, second in zip(profile_stations, profile_stations[1:])
                if first[0] - 1e-8 <= service_z <= second[0] + 1e-8
            )
            (za, ra), (zb, rb) = segment
            face_slope = math.cos(math.radians(30.0)) * (rb - ra) / (zb - za)
            normal_scale = math.sqrt(1.0 + face_slope * face_slope)
            surround_total = surround_width + surround_reveal
            service_outer_width = float(cfg["m12_service_window_mm"][0]) + 2.0 * surround_total
            service_outer_projected_height = service_window_height * normal_scale + 2.0 * surround_total
            service_bezel_height = service_outer_projected_height / normal_scale
            service_bezel_center_z = service_z - (
                face_slope / normal_scale
            ) * (surround_proud / 2.0)
            band_outer_center_radius = (outer_radii[0] + outer_radii[1]) / 2.0
            frame = frame.cut(
                _face_box(
                    270.0,
                    band_outer_center_radius * math.cos(math.radians(30.0))
                    - frame_radial_thickness * math.cos(math.radians(30.0)) / 2.0,
                    0.0,
                    service_bezel_center_z,
                    service_outer_width + 1.0,
                    20.0,
                    service_bezel_height + 2.0,
                )
            )
        if abs(frame_z) < 1.0e-8:
            outer_face_apothem = outer_radii[0] * math.cos(math.radians(30.0))
            anchor_z0 = frame_z - frame_height / 2.0
            anchor_height = frame_height / 2.0
            anchor_width = 10.0
            anchor_inner_radius = 100.0
            anchor_length = outer_face_apothem - anchor_inner_radius
            anchor_center_radius = 0.5 * (anchor_inner_radius + outer_face_apothem)
            for normal_deg in (30.0, 90.0, 150.0, 210.0, 270.0, 330.0):
                anchor = (
                    cq.Workplane("XY")
                    .box(anchor_length, anchor_width, anchor_height)
                    .val()
                    .rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), normal_deg)
                    .translate(
                        (
                            anchor_center_radius * math.cos(math.radians(normal_deg)),
                            anchor_center_radius * math.sin(math.radians(normal_deg)),
                            anchor_z0 + anchor_height / 2.0,
                        )
                    )
                )
                frame = frame.fuse(anchor)
                mount = cq.Solid.makeCylinder(
                    1.6,
                    frame_height / 2.0 + 0.2,
                    cq.Vector(
                        anchor_inner_radius * math.cos(math.radians(normal_deg)),
                        anchor_inner_radius * math.sin(math.radians(normal_deg)),
                        anchor_z0 - 0.1,
                    ),
                    cq.Vector(0.0, 0.0, 1.0),
                )
                frame = frame.cut(mount)
        frame = frame.clean()
        name = f"fixed_cover_frame_{index:02d}"
        components[name] = frame
        frame_names.append(name)

    guard_outer = float(cfg["root_guard_outer_circumradius_mm"])
    guard_inner = float(cfg["root_guard_inner_circumradius_mm"])
    guard_z0, guard_z1 = (float(value) for value in cfg["root_guard_z_bounds_mm"])
    guard = _hex_prism(guard_outer, guard_z0, guard_z1 - guard_z0).cut(
        _hex_prism(guard_inner, guard_z0 - 0.1, guard_z1 - guard_z0 + 0.2)
    )
    guard_window_width, guard_window_height = (
        float(value) for value in cfg["root_guard_window_mm"]
    )
    guard_apothem = 0.5 * (guard_outer + guard_inner) * math.cos(math.radians(30.0))
    for normal_deg in (90.0, 210.0, 330.0):
        guard = guard.cut(
            _face_box(
                normal_deg,
                guard_apothem,
                0.0,
                0.5 * (guard_z0 + guard_z1),
                guard_window_width,
                6.0,
                guard_window_height,
            )
        )
    fastener_radius = float(cfg["root_guard_fastener_center_radius_mm"])
    fastener_clearance_radius = 0.5 * float(
        cfg["root_guard_fastener_clearance_diameter_mm"]
    )
    arm_radial_width = float(cfg["root_guard_fastener_arm_radial_width_mm"])
    arm_tangent_width = float(cfg["root_guard_fastener_arm_tangent_width_mm"])
    leg_radial_width = float(cfg["root_guard_fastener_leg_radial_width_mm"])
    for angle_deg in cfg["root_guard_fastener_angles_deg"]:
        arm_start_radius = _hex_radial_boundary(guard_outer, float(angle_deg)) - 1.0
        arm_center_radius = arm_start_radius + 0.5 * arm_radial_width
        guard = guard.fuse(
            _face_box(
                float(angle_deg),
                arm_center_radius,
                0.0,
                0.5 * (guard_z0 + guard_z1),
                arm_tangent_width,
                arm_radial_width,
                guard_z1 - guard_z0,
            )
        ).fuse(
            _face_box(
                float(angle_deg),
                fastener_radius,
                0.0,
                0.5 * guard_z1,
                arm_tangent_width,
                leg_radial_width,
                guard_z1,
            )
        )
        radial = _unit(float(angle_deg))
        guard = guard.cut(
            cq.Solid.makeCylinder(
                fastener_clearance_radius,
                guard_z1 + 0.2,
                cq.Vector(
                    fastener_radius * radial[0],
                    fastener_radius * radial[1],
                    -0.1,
                ),
                cq.Vector(0.0, 0.0, 1.0),
            )
        )

    tab_radius = float(cfg["root_guard_alignment_tab_center_radius_mm"])
    tab_radial_width = float(cfg["root_guard_alignment_tab_radial_width_mm"])
    tab_tangent_width = float(cfg["root_guard_alignment_tab_tangent_width_mm"])
    tab_z0, tab_z1 = (
        float(value) for value in cfg["root_guard_alignment_tab_z_bounds_mm"]
    )
    for angle_deg in cfg["root_guard_alignment_tab_angles_deg"]:
        tab_arm_start_radius = _hex_radial_boundary(guard_outer, float(angle_deg)) - 1.0
        tab_arm_radial_width = (
            tab_radius - 0.5 * tab_radial_width - tab_arm_start_radius + 1.0
        )
        tab_arm_center_radius = tab_arm_start_radius + 0.5 * tab_arm_radial_width
        guard = guard.fuse(
            _face_box(
                float(angle_deg),
                tab_arm_center_radius,
                0.0,
                0.5 * (guard_z0 + guard_z1),
                tab_tangent_width,
                tab_arm_radial_width,
                guard_z1 - guard_z0,
            )
        ).fuse(
            _face_box(
                float(angle_deg),
                tab_radius,
                0.0,
                0.5 * (tab_z0 + tab_z1),
                tab_tangent_width,
                tab_radial_width,
                tab_z1 - tab_z0,
            )
        )
    root_guard_name = "fixed_root_guard_hex"
    components[root_guard_name] = guard.clean()

    max_outer_radius = max(radius for _, radius in profile_stations) + frame_radial_thickness
    print_envelope = (
        2.0 * max_outer_radius,
        math.sqrt(3.0) * max_outer_radius,
        height,
    )
    return RootCoverResult(
        components=components,
        panel_names=tuple(panel_names),
        upper_panel_names=tuple(upper_panel_names),
        lower_panel_names=tuple(lower_panel_names),
        motor_window_panels=tuple(motor_window_panels),
        observation_window_panels=tuple(observation_window_panels),
        type_c_service_panel=type_c_service_panel,
        frame_names=tuple(frame_names),
        root_guard_name=root_guard_name,
        outer_circumdiameter_mm=2.0 * max_outer_radius,
        panel_height_mm=height,
        print_envelope_mm=print_envelope,
        profile_stations_mm=profile_stations,
    )
