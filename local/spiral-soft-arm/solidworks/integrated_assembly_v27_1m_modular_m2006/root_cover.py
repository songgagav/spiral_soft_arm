from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import cadquery as cq


@dataclass(frozen=True)
class RootCoverResult:
    components: dict[str, cq.Shape]
    panel_names: tuple[str, ...]
    lower_panel_names: tuple[str, ...]
    upper_panel_names: tuple[str, ...]
    top_plate_attachment_panel_names: tuple[str, ...]
    motor_window_panels: tuple[str, ...]
    observation_window_panels: tuple[str, ...]
    type_c_service_panel: str
    raised_rib_centers_mm: tuple[float, ...]
    fastener_row_centers_mm: tuple[float, ...]
    inner_support_pad_count: int
    root_guard_name: str
    nominal_profile_circumdiameter_mm: float
    actual_panel_max_radial_diameter_mm: float
    actual_panel_assembly_bounds_mm: tuple[float, float, float]
    panel_height_mm: float
    nominal_profile_envelope_mm: tuple[float, float, float]
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


def _profile_face_slope(
    profile_stations_mm: tuple[tuple[float, float], ...], z_mm: float
) -> float:
    for (za, ra), (zb, rb) in zip(
        profile_stations_mm, profile_stations_mm[1:]
    ):
        if za - 1e-8 <= z_mm <= zb + 1e-8:
            return math.cos(math.radians(30.0)) * (rb - ra) / (zb - za)
    raise ValueError(f"cover profile does not define z={z_mm:g} mm")


def _surface_outward_normal(normal_deg: float, face_slope: float) -> cq.Vector:
    radial = _unit(normal_deg)
    return cq.Vector(radial[0], radial[1], -face_slope).normalized()


def _oriented_face_hole(
    normal_deg: float,
    normal_mm: float,
    tangent_mm: float,
    z_mm: float,
    radius_mm: float,
    length_mm: float,
    outward_normal: cq.Vector,
    start_outside_mm: float = 0.1,
) -> cq.Shape:
    radial = _unit(normal_deg)
    tangent = _unit(normal_deg + 90.0)
    face_point = cq.Vector(
        normal_mm * radial[0] + tangent_mm * tangent[0],
        normal_mm * radial[1] + tangent_mm * tangent[1],
        z_mm,
    )
    start = face_point + outward_normal * start_outside_mm
    return cq.Solid.makeCylinder(radius_mm, length_mm, start, -outward_normal)


def _profile_frame(
    inner_radii_mm: tuple[float, float],
    outer_radii_mm: tuple[float, float],
    z_bounds_mm: tuple[float, float],
    bolt_radius_mm: float,
    bolt_offsets_mm: tuple[float, ...],
    bolt_z_values_mm: tuple[float, ...],
    tool_access_diameter_mm: float,
    tool_access_recess_depth_mm: float,
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
    face_slope = math.cos(math.radians(30.0)) * (
        inner_radii_mm[1] - inner_radii_mm[0]
    ) / (z1 - z0)
    for bolt_z in bolt_z_values_mm:
        fraction = (bolt_z - z0) / (z1 - z0)
        panel_radius = inner_radii_mm[0] + fraction * (
            inner_radii_mm[1] - inner_radii_mm[0]
        )
        outer_frame_radius = outer_radii_mm[0] + fraction * (
            outer_radii_mm[1] - outer_radii_mm[0]
        )
        panel_apothem = panel_radius * math.cos(math.radians(30.0))
        normal_offset = (
            (outer_frame_radius - panel_radius) * math.cos(math.radians(30.0))
            / math.sqrt(1.0 + face_slope * face_slope)
        )
        for normal_deg in (30.0, 90.0, 150.0, 210.0, 270.0, 330.0):
            outward_normal = _surface_outward_normal(normal_deg, face_slope)
            for offset in bolt_offsets_mm:
                frame = frame.cut(
                    _oriented_face_hole(
                        normal_deg,
                        panel_apothem,
                        offset,
                        bolt_z,
                        bolt_radius_mm,
                        18.0,
                        outward_normal,
                        normal_offset + 0.1,
                    )
                )
                frame = frame.cut(
                    _oriented_face_hole(
                        normal_deg,
                        panel_apothem,
                        offset,
                        bolt_z,
                        tool_access_diameter_mm / 2.0,
                        tool_access_recess_depth_mm + 0.1,
                        outward_normal,
                        normal_offset + 0.1,
                    )
                )
    return frame.clean()


def _face_band_segment(
    normal_deg: float,
    inner_radii_mm: tuple[float, float],
    z_bounds_mm: tuple[float, float],
    radial_thickness_mm: float,
    panel_overlap_mm: float,
    edge_gap_mm: float,
    corner_gap_mm: float = 0.0,
) -> cq.Shape:
    """Create one flat-face rib that overlaps and fuses into its service panel."""
    normal = _unit(normal_deg)
    tangent = _unit(normal_deg + 90.0)
    z0, z1 = z_bounds_mm
    wires = []
    for radius, z_mm in zip(inner_radii_mm, (z0, z1)):
        panel_apothem = radius * math.cos(math.radians(30.0))
        outer_radius = radius + radial_thickness_mm
        outer_apothem = outer_radius * math.cos(math.radians(30.0))
        inner_half_width = radius / 2.0 - edge_gap_mm / 2.0
        outer_half_width = outer_radius / 2.0 - corner_gap_mm
        if inner_half_width <= 0.0 or outer_half_width <= 0.0:
            raise ValueError("armor rib width must remain positive")
        corners = (
            (panel_apothem - panel_overlap_mm, -inner_half_width),
            (outer_apothem, -outer_half_width),
            (outer_apothem, outer_half_width),
            (panel_apothem - panel_overlap_mm, inner_half_width),
        )
        points = [
            cq.Vector(
                normal_mm * normal[0] + tangent_mm * tangent[0],
                normal_mm * normal[1] + tangent_mm * tangent[1],
                z_mm,
            )
            for normal_mm, tangent_mm in corners
        ]
        wires.append(cq.Wire.makePolygon(points + [points[0]]))
    rib = cq.Solid.makeLoft(wires, ruled=True)
    if not rib.isValid() or len(rib.Solids()) != 1:
        raise ValueError("armor face rib must be one valid solid")
    return rib


def _face_inner_support_pad(
    normal_deg: float,
    outer_face_apothem_mm: float,
    panel_thickness_mm: float,
    z_mm: float,
    tangent_offset_mm: float,
    face_slope: float,
    tangent_width_mm: float,
    vertical_height_mm: float,
    inward_thickness_mm: float,
    panel_overlap_mm: float = 0.6,
) -> cq.Shape:
    """Make one local inner fastener pad, leaving the outside panel face flush."""
    dimensions = (
        panel_thickness_mm,
        tangent_width_mm,
        vertical_height_mm,
        inward_thickness_mm,
        panel_overlap_mm,
    )
    if any(not math.isfinite(value) or value <= 0.0 for value in dimensions):
        raise ValueError("inner support-pad dimensions must be finite and positive")

    radial = _unit(normal_deg)
    tangent_tuple = _unit(normal_deg + 90.0)
    tangent = cq.Vector(*tangent_tuple)
    outward_normal = _surface_outward_normal(normal_deg, face_slope)
    inner_apothem = outer_face_apothem_mm - panel_thickness_mm
    origin = cq.Vector(
        inner_apothem * radial[0] + tangent_offset_mm * tangent_tuple[0],
        inner_apothem * radial[1] + tangent_offset_mm * tangent_tuple[1],
        z_mm,
    )
    pad_plane = cq.Plane(
        origin=origin + outward_normal * panel_overlap_mm,
        xDir=tangent,
        normal=-outward_normal,
    )
    pad_surface_height = vertical_height_mm * math.sqrt(1.0 + face_slope**2)
    pad = (
        cq.Workplane(pad_plane)
        .rect(tangent_width_mm, pad_surface_height)
        .extrude(inward_thickness_mm + panel_overlap_mm)
        .val()
    )
    if not pad.isValid() or len(pad.Solids()) != 1:
        raise ValueError("inner fastener support pad must be one valid solid")
    return pad


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
    fastener_row_centers = tuple(
        float(value) for value in cfg["fastener_row_z_centers_mm"]
    )
    raised_rib_centers = tuple(
        float(value) for value in cfg["raised_rib_z_centers_mm"]
    )
    if len(fastener_row_centers) != 4 or len(raised_rib_centers) != 2:
        raise ValueError("cover requires four fastener rows and two raised ribs")
    if any(center not in fastener_row_centers for center in raised_rib_centers):
        raise ValueError("each raised armor rib must align with a fastener row")
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
    bolt_radius = float(cfg["panel_fastener_diameter_mm"]) / 2.0
    bolt_offsets = tuple(float(value) for value in cfg["panel_fastener_tangent_offsets_mm"])
    fastener_pad_width = float(cfg["panel_fastener_pad_tangent_width_mm"])
    counterbore_recess_depth = float(cfg["panel_fastener_recess_depth_mm"])
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
    lower_panel_names: list[str] = []
    upper_panel_names: list[str] = []
    motor_window_panels: list[str] = []
    observation_window_panels: list[str] = []
    clip_radius = max(radius for _, radius in profile_stations) + surround_proud + 10.0
    region_specs = (
        ("lower", z0, split_z, fastener_row_centers[:2]),
        ("upper", split_z, z1, fastener_row_centers[2:]),
    )
    normal_to_index = {normal: index for index, normal in enumerate(normals, start=1)}
    motor_normals = {90.0, 210.0, 330.0}
    observation_normals = {
        float(value) for value in cfg["observation_window_normals_deg"]
    }
    motor_z = float(cfg["motor_window_center_z_mm"])
    observation_z = float(cfg["observation_window_center_z_mm"])
    service_z = float(cfg["m12_service_window_center_z_mm"])
    type_c_service_panel = ""

    for normal_deg in normals:
        index = normal_to_index[normal_deg]
        for region, panel_z0, panel_z1, _region_row_centers in region_specs:
            panel_name = f"fixed_cover_{region}_panel_{index:02d}"
            panel = panel_solid(normal_deg, panel_z0, panel_z1)
            if region == "upper" and normal_deg in motor_normals:
                panel = cut_window(
                    panel,
                    normal_deg,
                    motor_z,
                    tuple(cfg["motor_window_mm"]),
                    (panel_z0, panel_z1),
                )
                panel = add_window_surround(
                    panel,
                    normal_deg,
                    motor_z,
                    tuple(cfg["motor_window_mm"]),
                )
                motor_window_panels.append(panel_name)
            if region == "lower" and normal_deg in observation_normals:
                panel = cut_window(
                    panel,
                    normal_deg,
                    observation_z,
                    tuple(cfg["observation_window_mm"]),
                    (panel_z0, panel_z1),
                )
                panel = add_window_surround(
                    panel,
                    normal_deg,
                    observation_z,
                    tuple(cfg["observation_window_mm"]),
                )
                observation_window_panels.append(panel_name)
            if region == "lower" and normal_deg == 270.0:
                panel = cut_window(
                    panel,
                    normal_deg,
                    service_z,
                    tuple(cfg["m12_service_window_mm"]),
                    (panel_z0, panel_z1),
                )
                panel = add_window_surround(
                    panel,
                    normal_deg,
                    service_z,
                    tuple(cfg["m12_service_window_mm"]),
                )
                type_c_service_panel = panel_name
                # The M12 bezel reaches the bottom armor band. Trim only its
                # proud outer lip across that 8 mm band height, leaving the
                # panel wall and the complete ring fastener seats intact.
                access_z = fastener_row_centers[0]
                access_slope = _profile_face_slope(tuple(profile_stations), access_z)
                access_normal = _surface_outward_normal(normal_deg, access_slope)
                access_apothem = radius_at(access_z) * math.cos(
                    math.radians(30.0)
                )
                angle = math.radians(normal_deg)
                tangent = _unit(normal_deg + 90.0)
                face_point = cq.Vector(
                    access_apothem * math.cos(angle),
                    access_apothem * math.sin(angle),
                    access_z,
                )
                service_outer_width = (
                    float(cfg["m12_service_window_mm"][0])
                    + 2.0 * (surround_width + surround_reveal)
                    + 1.0
                )
                bezel_band_trim = (
                    cq.Workplane(
                        cq.Plane(
                            origin=face_point,
                            xDir=tangent,
                            normal=access_normal,
                        )
                    )
                    .rect(service_outer_width, frame_height + 0.2)
                    .extrude(surround_proud + 0.1)
                    .val()
                )
                panel = panel.cut(bezel_band_trim).clean()
                # The lower screw row overlaps the proud M12 service-window
                # surround at the two M3 axes. Retain the screw-seat annuli in
                # both the panel and the bottom ring.
                access_radius = float(
                    cfg["panel_tool_access_relief_diameter_mm"]
                ) / 2.0
                for offset in bolt_offsets:
                    access_relief = _oriented_face_hole(
                        normal_deg,
                        access_apothem,
                        offset,
                        access_z,
                        access_radius,
                        surround_proud + 0.1,
                        access_normal,
                        start_outside_mm=surround_proud + 0.1,
                    )
                    panel = panel.cut(access_relief)
            panel_height_clip = cq.Solid.makeBox(
                2.0 * clip_radius,
                2.0 * clip_radius,
                panel_z1 - panel_z0,
                cq.Vector(-clip_radius, -clip_radius, panel_z0),
            )
            # Sloped-face bezels can extend slightly beyond the segment end
            # planes; keep each printable piece within its nominal Z bounds.
            panel = panel.intersect(panel_height_clip).clean()
            components[panel_name] = panel
            panel_names.append(panel_name)
            (lower_panel_names if region == "lower" else upper_panel_names).append(
                panel_name
            )

    fastener_specs = tuple(
        (
            row_z,
            row_z - frame_height / 2.0,
            row_z + frame_height / 2.0,
        )
        for row_z in fastener_row_centers
    )
    central_seam_z = float(cfg["central_band_seam_z_mm"])
    central_seam_height = float(cfg["central_band_seam_height_mm"])
    central_seam_recess = float(cfg["central_band_seam_radial_recess_mm"])
    if central_seam_height <= 0.0 or central_seam_recess <= 0.0:
        raise ValueError("central armor seam dimensions must be positive")
    seam_apothem = radius_at(central_seam_z) * math.cos(math.radians(30.0))
    inner_support_pad_count = 0
    for index, (row_z, band_z0, band_z1) in enumerate(fastener_specs, start=1):
        frame_inner_radii = (radius_at(band_z0), radius_at(band_z1))
        region = "lower" if index <= 2 else "upper"
        for normal_deg in normals:
            panel_name = f"fixed_cover_{region}_panel_{normal_to_index[normal_deg]:02d}"
            panel = components[panel_name]
            has_raised_rib = row_z in raised_rib_centers
            if has_raised_rib:
                rib = _face_band_segment(
                    normal_deg,
                    frame_inner_radii,
                    (band_z0, band_z1),
                    frame_radial_thickness,
                    panel_overlap_mm=0.6,
                    edge_gap_mm=edge_gap,
                )
                panel = panel.fuse(rib).clean()
            else:
                face_slope = _profile_face_slope(tuple(profile_stations), row_z)
                center_radius = radius_at(row_z)
                base_face_apothem = center_radius * math.cos(math.radians(30.0))
                for offset in bolt_offsets:
                    pad = _face_inner_support_pad(
                        normal_deg,
                        base_face_apothem,
                        panel_thickness,
                        row_z,
                        offset,
                        face_slope,
                        fastener_pad_width,
                        frame_height,
                        frame_radial_thickness,
                    )
                    panel = panel.fuse(pad).clean()
                    inner_support_pad_count += 1

            if not panel.isValid() or len(panel.Solids()) != 1:
                raise ValueError(f"integrated armor support is not one solid: {panel_name}")

            if index in (2, 3):
                # Recess the outer 1.2 mm at the split seam. The middle
                # fastener support pads remain on the inside of the panel.
                seam_groove = _face_box(
                    normal_deg,
                    seam_apothem - central_seam_recess / 2.0 + 0.1,
                    0.0,
                    central_seam_z,
                    2.0 * clip_radius,
                    central_seam_recess + 0.2,
                    central_seam_height,
                )
                panel = panel.cut(seam_groove).clean()

            center_radius = radius_at(row_z)
            base_face_apothem = center_radius * math.cos(math.radians(30.0))
            face_slope = _profile_face_slope(tuple(profile_stations), row_z)
            outward_normal = _surface_outward_normal(normal_deg, face_slope)
            rib_surface_offset = 0.0
            if has_raised_rib:
                outer_face_apothem = (
                    center_radius + frame_radial_thickness
                ) * math.cos(math.radians(30.0))
                rib_surface_offset = (
                    outer_face_apothem - base_face_apothem
                ) / math.sqrt(1.0 + face_slope * face_slope)
            for offset in bolt_offsets:
                panel = panel.cut(
                    _oriented_face_hole(
                        normal_deg,
                        base_face_apothem,
                        offset,
                        row_z,
                        bolt_radius,
                        20.0,
                        outward_normal,
                        start_outside_mm=rib_surface_offset + 0.1,
                    )
                )
                panel = panel.cut(
                    _oriented_face_hole(
                        normal_deg,
                        base_face_apothem,
                        offset,
                        row_z,
                        4.0,
                        counterbore_recess_depth,
                        outward_normal,
                        start_outside_mm=rib_surface_offset + 0.1,
                    )
                )
            panel_z0, panel_z1 = (z0, split_z) if region == "lower" else (split_z, z1)
            final_height_clip = cq.Solid.makeBox(
                2.0 * clip_radius,
                2.0 * clip_radius,
                panel_z1 - panel_z0,
                cq.Vector(-clip_radius, -clip_radius, panel_z0),
            )
            panel = panel.intersect(final_height_clip).clean()
            if not panel.isValid() or len(panel.Solids()) != 1:
                raise ValueError(f"final cover panel is not one valid solid: {panel_name}")
            components[panel_name] = panel

    attachment_normals = tuple(
        float(value) for value in cfg["top_plate_attachment_normals_deg"]
    )
    attachment_inner_radius = float(cfg["top_plate_attachment_inner_radius_mm"])
    attachment_tangent_width = float(cfg["top_plate_attachment_tangent_width_mm"])
    attachment_z0, attachment_z1 = (
        float(value) for value in cfg["top_plate_attachment_z_bounds_mm"]
    )
    attachment_hole_diameter = float(cfg["top_plate_attachment_hole_diameter_mm"])
    attachment_hole_radius = float(cfg["top_plate_attachment_hole_radius_mm"])
    attachment_overlap = float(cfg["top_plate_attachment_panel_overlap_mm"])
    if (
        len(attachment_normals) != 3
        or len(set(attachment_normals)) != 3
        or any(normal not in normals or normal in motor_normals for normal in attachment_normals)
    ):
        raise ValueError("top-plate cover ears must use three distinct non-motor face normals")
    if any(
        not math.isfinite(value) or value <= 0.0
        for value in (
            attachment_inner_radius,
            attachment_tangent_width,
            attachment_hole_diameter,
            attachment_hole_radius,
            attachment_overlap,
        )
    ):
        raise ValueError("top-plate cover-ear dimensions must be finite and positive")
    if not math.isfinite(attachment_z0) or not math.isfinite(attachment_z1) or attachment_z1 <= attachment_z0:
        raise ValueError("top-plate cover-ear Z bounds must be finite and increasing")
    attachment_wall_inner_apothem = (
        radius_at(attachment_z0) * math.cos(math.radians(30.0)) - panel_thickness
    )
    if not (
        attachment_inner_radius < attachment_hole_radius
        and attachment_hole_radius + attachment_hole_diameter / 2.0
        < attachment_wall_inner_apothem
    ):
        raise ValueError("top-plate attachment hole must lie within the radial ear shelf")
    attachment_panel_names: list[str] = []
    attachment_center_z = 0.5 * (attachment_z0 + attachment_z1)
    attachment_normal_width = (
        attachment_wall_inner_apothem + attachment_overlap - attachment_inner_radius
    )
    attachment_center_normal = (
        attachment_wall_inner_apothem + attachment_overlap + attachment_inner_radius
    ) / 2.0
    for normal_deg in attachment_normals:
        panel_name = f"fixed_cover_upper_panel_{normal_to_index[normal_deg]:02d}"
        panel = components[panel_name]
        ear = _face_box(
            normal_deg,
            attachment_center_normal,
            0.0,
            attachment_center_z,
            attachment_tangent_width,
            attachment_normal_width,
            attachment_z1 - attachment_z0,
        )
        panel = panel.fuse(ear).clean()
        radial = _unit(normal_deg)
        attachment_hole = cq.Solid.makeCylinder(
            attachment_hole_diameter / 2.0,
            attachment_z1 - attachment_z0 + 0.2,
            cq.Vector(
                attachment_hole_radius * radial[0],
                attachment_hole_radius * radial[1],
                attachment_z0 - 0.1,
            ),
            cq.Vector(0.0, 0.0, 1.0),
        )
        panel = panel.cut(attachment_hole).clean()
        if not panel.isValid() or len(panel.Solids()) != 1:
            raise ValueError(f"top-plate attachment ear is not fused to one panel: {panel_name}")
        components[panel_name] = panel
        attachment_panel_names.append(panel_name)

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

    max_outer_radius = max(radius for _, radius in profile_stations)
    nominal_profile_envelope = (
        2.0 * max_outer_radius,
        math.sqrt(3.0) * max_outer_radius,
        height,
    )
    panel_compound = cq.Compound.makeCompound(
        [components[name] for name in panel_names]
    )
    panel_bounds = panel_compound.BoundingBox()
    actual_panel_max_radius = max(
        math.hypot(vertex.Center().x, vertex.Center().y)
        for name in panel_names
        for vertex in components[name].Vertices()
    )
    return RootCoverResult(
        components=components,
        panel_names=tuple(panel_names),
        lower_panel_names=tuple(lower_panel_names),
        upper_panel_names=tuple(upper_panel_names),
        top_plate_attachment_panel_names=tuple(attachment_panel_names),
        motor_window_panels=tuple(motor_window_panels),
        observation_window_panels=tuple(observation_window_panels),
        type_c_service_panel=type_c_service_panel,
        raised_rib_centers_mm=tuple(raised_rib_centers),
        fastener_row_centers_mm=tuple(fastener_row_centers),
        inner_support_pad_count=inner_support_pad_count,
        root_guard_name=root_guard_name,
        nominal_profile_circumdiameter_mm=2.0 * max_outer_radius,
        actual_panel_max_radial_diameter_mm=2.0 * actual_panel_max_radius,
        actual_panel_assembly_bounds_mm=(
            panel_bounds.xlen,
            panel_bounds.ylen,
            panel_bounds.zlen,
        ),
        panel_height_mm=height,
        nominal_profile_envelope_mm=nominal_profile_envelope,
        profile_stations_mm=profile_stations,
    )
