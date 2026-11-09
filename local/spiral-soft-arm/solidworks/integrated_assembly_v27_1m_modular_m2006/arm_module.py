from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Any, Sequence

import cadquery as cq
from spiral_parameters import derive_from_contract


@dataclass(frozen=True)
class TendonChannel:
    name: str
    angle_deg: float
    samples: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class DovetailInterface:
    name: str
    unit_index: int
    boundary_z_mm: float
    male: cq.Shape
    female_cutter: cq.Shape
    engagement_mm: float
    clearance_per_side_mm: float
    rotation_deg: float
    minimum_tendon_clearance_mm: float
    lock_pin_azimuth_deg: float
    lock_pin_length_mm: float


@dataclass(frozen=True)
class LockFeature:
    name: str
    kind: str
    proxy: cq.Shape
    insertion_clearance_mm: float
    unit_index: int
    center_z_mm: float
    diameter_mm: float
    hole_diameter_mm: float
    axis_azimuth_deg: float
    length_mm: float
    tendon_clearance_mm: float


@dataclass(frozen=True)
class TipAnchor:
    name: str
    proxy: cq.Shape


@dataclass(frozen=True)
class ArmBuildResult:
    print_segments: dict[str, cq.Shape]
    segment_ranges: tuple[tuple[int, int], ...]
    segment_z_ranges_mm: tuple[tuple[float, float], ...]
    segment_spans_mm: tuple[float, ...]
    segment_boundary_z_mm: tuple[float, ...]
    tendon_centerlines: tuple[TendonChannel, ...]
    dovetails: tuple[DovetailInterface, ...]
    lock_features: tuple[LockFeature, ...]
    tip_anchors: tuple[TipAnchor, ...]
    assembled_proxy: cq.Shape
    root_diameter_mm: float
    tip_diameter_mm: float
    geometry_source: str
    unit_profile_count: int


def compute_unit_planes(contract: Any) -> tuple[float, ...]:
    """Return root-to-tip planes using exact paper centerline arc intervals."""
    arm = contract.arm
    count = int(arm.unit_count)
    if count < 2:
        raise ValueError("the logarithmic arm requires at least two units")
    spiral = derive_from_contract(contract)
    root_to_tip_lengths = reversed(spiral.unit_interval_lengths_mm)
    planes = [0.0]
    for interval_length in root_to_tip_lengths:
        planes.append(planes[-1] + interval_length)
    planes[-1] = float(arm.nominal_length_mm)
    return tuple(planes)


def choose_four_segment_ranges(
    unit_planes: Sequence[float], max_height_mm: float
) -> tuple[tuple[int, int], ...]:
    """Choose four contiguous unit ranges minimizing the tallest segment."""
    if len(unit_planes) < 5:
        raise ValueError("four segments require at least four units")
    heights = [right - left for left, right in zip(unit_planes, unit_planes[1:])]
    # The male tongue is recessed into the lower segment's final 6 mm, so the
    # finished print envelope has no axial projection beyond its unit planes.
    connector_projection_mm = 0.0
    if max(heights) + connector_projection_mm >= max_height_mm:
        raise ValueError("candidate boundaries cannot fit one unit plus connector projection")
    unit_count = len(heights)
    best: tuple[tuple[float, float, tuple[int, int, int]], tuple[tuple[int, int], ...]] | None = None
    for cuts in combinations(range(1, unit_count), 3):
        bounds = (0, *cuts, unit_count)
        spans = tuple(
            float(unit_planes[bounds[index + 1]] - unit_planes[bounds[index]])
            for index in range(4)
        )
        finished_spans = tuple(
            span + (connector_projection_mm if index < 3 else 0.0)
            for index, span in enumerate(spans)
        )
        if any(span >= max_height_mm for span in finished_spans):
            continue
        ranges = tuple(
            (bounds[index] + 1, bounds[index + 1]) for index in range(4)
        )
        score = (max(finished_spans), max(finished_spans) - min(finished_spans), cuts)
        if best is None or score < best[0]:
            best = (score, ranges)
    if best is None:
        raise ValueError("candidate boundaries do not satisfy the finished-part height limit")
    return best[1]


def _outer_radius(contract: Any, z_mm: float) -> float:
    arm = contract.arm
    fraction = min(1.0, max(0.0, z_mm / float(arm.nominal_length_mm)))
    root = 0.5 * float(arm.root_diameter_mm)
    tip = 0.5 * float(arm.tip_diameter_mm)
    return root + fraction * (tip - root)


def _channel_point(contract: Any, z_mm: float, angle_deg: float) -> tuple[float, float, float]:
    radius = 0.55 * _outer_radius(contract, z_mm)
    angle = math.radians(angle_deg)
    return radius * math.cos(angle), radius * math.sin(angle), z_mm


def _root_transition_points(
    contract: Any, angle_deg: float
) -> tuple[cq.Vector, cq.Vector, cq.Vector, cq.Vector]:
    cfg = contract.integration
    angle = math.radians(angle_deg)
    radial = cq.Vector(math.cos(angle), math.sin(angle), 0.0)
    start = radial * float(cfg["root_tendon_entry_radius_mm"]) + cq.Vector(
        0.0, 0.0, float(cfg["root_tendon_entry_z_mm"])
    )
    join_z = float(cfg["root_tendon_transition_join_z_mm"])
    join = cq.Vector(*_channel_point(contract, join_z, angle_deg))
    next_point = cq.Vector(*_channel_point(contract, join_z + 1.0, angle_deg))
    end_direction = (next_point - join).normalized()
    start_direction = -radial
    first_control = start + start_direction * float(
        cfg["root_tendon_transition_start_handle_mm"]
    )
    second_control = join - end_direction * float(
        cfg["root_tendon_transition_end_handle_mm"]
    )
    return start, first_control, second_control, join


def _bezier_point(controls: Sequence[cq.Vector], fraction: float) -> cq.Vector:
    t = fraction
    u = 1.0 - t
    return (
        controls[0] * (u * u * u)
        + controls[1] * (3.0 * u * u * t)
        + controls[2] * (3.0 * u * t * t)
        + controls[3] * (t * t * t)
    )


def make_root_transition_passage(
    contract: Any, angle_deg: float, radius_mm: float
) -> cq.Shape:
    """Sweep a round lead-in with matched tangents at root and native channel."""
    controls = _root_transition_points(contract, angle_deg)
    path = cq.Edge.makeBezier(list(controls))
    start_tangent = (controls[1] - controls[0]).normalized()
    profile = cq.Wire.makeCircle(radius_mm, controls[0], start_tangent)
    passage = cq.Solid.sweep(profile, [], path, makeSolid=True, isFrenet=True)
    if not passage.isValid() or len(passage.Solids()) != 1:
        raise ValueError(f"invalid root tendon transition at {angle_deg:g} degrees")
    return passage.clean()


def _channel_samples(
    contract: Any,
    planes: Sequence[float],
    angle_deg: float,
    segment_boundaries: Sequence[float] = (),
) -> tuple[tuple[float, float, float], ...]:
    """Sample the inlet transition and the native internal tendon channel."""
    controls = _root_transition_points(contract, angle_deg)
    transition = tuple(
        tuple(_bezier_point(controls, index / 16.0).toTuple())
        for index in range(1, 16)
    )
    join_z = float(contract.integration["root_tendon_transition_join_z_mm"])
    internal_planes = sorted(
        {
            float(z_mm)
            for z_mm in (*planes, *segment_boundaries)
            if z_mm > join_z + 1.0e-8
        }
    )
    internal = tuple(
        _channel_point(contract, z_mm, angle_deg)
        for z_mm in internal_planes
    )
    return (tuple(controls[0].toTuple()), *transition, tuple(controls[3].toTuple()), *internal)


def _paper_profile_polygons(contract: Any) -> list[list[tuple[float, float]]]:
    """Generate the paper's discrete logarithmic-spiral quadrilateral units."""
    count = int(contract.arm.unit_count)
    spiral = derive_from_contract(contract)
    delta = spiral.delta_theta_rad
    b = spiral.b
    gamma = spiral.beta
    eb = math.exp(2.0 * math.pi * b)
    a = spiral.a_mm
    central_factor = spiral.a1_mm / a
    p0 = (a, 0.0)
    p1 = (a * gamma * math.cos(delta), a * gamma * math.sin(delta))
    q0 = (central_factor * a, 0.0)
    q1 = (central_factor * a * gamma * math.cos(delta), central_factor * a * gamma * math.sin(delta))
    dx, dy = q1[0] - q0[0], q1[1] - q0[1]
    rotation = -math.atan2(dy, dx)
    ca, sa = math.cos(rotation), math.sin(rotation)
    base = [(x * ca - y * sa, x * sa + y * ca) for x, y in (p0, p1, q1, q0)]
    polygons: list[list[tuple[float, float]]] = []
    current_x = 0.0
    for index in range(count):
        scale = gamma**index
        scaled = [(x * scale, y * scale) for x, y in base]
        shift_x = current_x - scaled[3][0]
        shift_y = -scaled[3][1]
        polygon = [(x + shift_x, y + shift_y) for x, y in scaled]
        polygons.append(polygon)
        current_x = shift_x + scaled[2][0]
    def clip(poly: list[tuple[float, float]], plane: float, keep_greater: bool) -> list[tuple[float, float]]:
        output: list[tuple[float, float]] = []
        previous = poly[-1]
        previous_inside = previous[0] >= plane if keep_greater else previous[0] <= plane
        for current in poly:
            current_inside = current[0] >= plane if keep_greater else current[0] <= plane
            if current_inside != previous_inside:
                fraction = (plane - previous[0]) / (current[0] - previous[0])
                output.append((plane, previous[1] + fraction * (current[1] - previous[1])))
            if current_inside:
                output.append(current)
            previous, previous_inside = current, current_inside
        return output

    tip_peak = max(x for x, y in polygons[0] if abs(y - max(v for _, v in polygons[0])) < 1.0e-9)
    base_peak = min(x for x, y in polygons[-1] if abs(y - max(v for _, v in polygons[-1])) < 1.0e-9)
    clipped = [clip(clip(polygon, tip_peak, True), base_peak, False) for polygon in polygons]
    clipped = [polygon for polygon in clipped if len(polygon) >= 3]
    all_x = [x for polygon in clipped for x, _ in polygon]
    all_y = [y for polygon in clipped for _, y in polygon]
    axial_scale = float(contract.arm.nominal_length_mm) / (base_peak - tip_peak)
    radial_scale = (0.5 * float(contract.arm.root_diameter_mm)) / max(all_y)
    x0 = tip_peak
    transformed = [
        [
            (
                float(contract.arm.nominal_length_mm) - (x - x0) * axial_scale,
                max(0.05, y * radial_scale),
            )
            for x, y in polygon
        ]
        for polygon in clipped
    ]
    compacted: list[list[tuple[float, float]]] = []
    for polygon in transformed:
        compact: list[tuple[float, float]] = []
        for point in polygon:
            if not compact or math.dist(point, compact[-1]) > 1.0e-7:
                compact.append(point)
        if len(compact) > 2 and math.dist(compact[0], compact[-1]) <= 1.0e-7:
            compact.pop()
        compacted.append(compact)
    return compacted


def compute_profile_planes(
    contract: Any,
    profiles: Sequence[Sequence[tuple[float, float]]] | None = None,
) -> tuple[float, ...]:
    """Return root-to-tip boundaries of the actual clipped CAD unit profiles."""
    profiles = list(profiles if profiles is not None else _paper_profile_polygons(contract))
    if len(profiles) != int(contract.arm.unit_count):
        raise ValueError("CAD profile count must match the configured unit count")
    planes = [0.0]
    for unit_index, polygon in enumerate(reversed(profiles), start=1):
        z_values = [float(point[0]) for point in polygon]
        z_min, z_max = min(z_values), max(z_values)
        if abs(z_min - planes[-1]) > 1.0e-5:
            raise ValueError(
                f"CAD unit profile {unit_index} does not meet its predecessor: "
                f"{z_min:.6f} != {planes[-1]:.6f} mm"
            )
        if z_max <= planes[-1]:
            raise ValueError(f"CAD unit profile {unit_index} has no positive axial span")
        planes.append(z_max)
    nominal_length = float(contract.arm.nominal_length_mm)
    if abs(planes[-1] - nominal_length) > 1.0e-5:
        raise ValueError("CAD profile extent does not match the nominal arm length")
    planes[0] = 0.0
    planes[-1] = nominal_length
    return tuple(planes)


def _revolved_profile(polygon: Sequence[tuple[float, float]]) -> cq.Shape:
    return (
        cq.Workplane("XY")
        .polyline(polygon)
        .close()
        .revolve(360.0, (0.0, 0.0), (1.0, 0.0))
        .val()
        .rotate((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), -90.0)
    )


def _cylinder_between(
    radius_mm: float,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
) -> cq.Shape:
    direction = cq.Vector(end[0] - start[0], end[1] - start[1], end[2] - start[2])
    length = direction.Length
    if length <= 0.0:
        raise ValueError("cylinder endpoints must be distinct")
    return cq.Solid.makeCylinder(
        radius_mm,
        length,
        cq.Vector(*start),
        direction.normalized(),
    )


def _dovetail_points(contract: Any, clearance_mm: float = 0.0) -> list[tuple[float, float]]:
    joint = contract.arm.dovetail
    half_bottom = 0.5 * float(joint.bottom_width_mm)
    half_top = 0.5 * float(joint.top_width_mm)
    half_height = 0.5 * float(joint.profile_height_mm)
    angle = math.radians(float(joint.rotation_deg))
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    points = [
        (-half_bottom, -half_height),
        (half_bottom, -half_height),
        (half_top, half_height),
        (-half_top, half_height),
    ]
    rotated = [
        (x * cos_a - y * sin_a, x * sin_a + y * cos_a)
        for x, y in points
    ]
    if clearance_mm <= 0.0:
        return rotated
    return _offset_convex_polygon(rotated, clearance_mm)


def _offset_convex_polygon(
    points: Sequence[tuple[float, float]], offset_mm: float
) -> list[tuple[float, float]]:
    """Offset every CCW edge by the same outward normal distance."""
    shifted: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for first, second in zip(points, (*points[1:], points[0])):
        dx, dy = second[0] - first[0], second[1] - first[1]
        length = math.hypot(dx, dy)
        if length <= 1.0e-12:
            raise ValueError("dovetail profile contains a zero-length edge")
        normal = (dy / length, -dx / length)
        shifted.append(
            (
                (first[0] + normal[0] * offset_mm, first[1] + normal[1] * offset_mm),
                (dx, dy),
            )
        )
    output: list[tuple[float, float]] = []
    for index, current in enumerate(shifted):
        previous = shifted[index - 1]
        p, v = previous
        q, w = current
        denominator = v[0] * w[1] - v[1] * w[0]
        if abs(denominator) <= 1.0e-12:
            raise ValueError("dovetail offset has parallel adjacent edges")
        delta = (q[0] - p[0], q[1] - p[1])
        scale = (delta[0] * w[1] - delta[1] * w[0]) / denominator
        output.append((p[0] + scale * v[0], p[1] + scale * v[1]))
    return output


def _dovetail_prism(
    contract: Any,
    z_mm: float,
    height_mm: float,
    clearance_mm: float = 0.0,
) -> cq.Shape:
    points = _dovetail_points(contract, clearance_mm)
    return (
        cq.Workplane("XY")
        .workplane(offset=z_mm)
        .polyline(points)
        .close()
        .extrude(height_mm)
        .val()
    )


def _profile_outer_radius_at_z(
    contract: Any,
    profiles: Sequence[Sequence[tuple[float, float]]],
    unit_index: int,
    z_mm: float,
) -> float:
    polygon = profiles[int(contract.arm.unit_count) - unit_index]
    radii: list[float] = []
    for (z0, r0), (z1, r1) in zip(polygon, (*polygon[1:], polygon[0])):
        if min(z0, z1) - 1.0e-8 <= z_mm <= max(z0, z1) + 1.0e-8:
            if abs(z1 - z0) <= 1.0e-10:
                radii.extend((float(r0), float(r1)))
            else:
                fraction = (z_mm - z0) / (z1 - z0)
                radii.append(float(r0 + fraction * (r1 - r0)))
    if not radii:
        raise ValueError(f"no CAD profile section at z={z_mm:.6f} mm in unit {unit_index}")
    return max(radii)


def _continuous_arm_body(
    contract: Any,
    planes: Sequence[float],
    paper_profiles: Sequence[Sequence[tuple[float, float]]],
) -> cq.Shape:
    z_start = float(planes[0])
    z_end = float(planes[-1])
    core = cq.Solid.makeCone(
        max(0.25, 0.10 * _outer_radius(contract, z_start)),
        max(0.25, 0.10 * _outer_radius(contract, z_end)),
        z_end - z_start,
        cq.Vector(0.0, 0.0, z_start),
        cq.Vector(0.0, 0.0, 1.0),
    )
    profiles = [_revolved_profile(polygon) for polygon in paper_profiles]
    body = core.fuse(*profiles).clean()
    segment_envelope = cq.Solid.makeBox(
        300.0,
        300.0,
        z_end - z_start + 0.02,
        cq.Vector(-150.0, -150.0, z_start - 0.01),
    )
    body = body.intersect(segment_envelope).clean()
    hole_radius = max(0.40, 0.5 * float(contract.arm.tendon_diameter_mm) + 0.15)
    join_z = float(contract.integration["root_tendon_transition_join_z_mm"])
    entry_z = float(contract.integration["root_tendon_entry_z_mm"])
    entry_radius = float(contract.integration["root_tendon_entry_radius_mm"])
    for angle_deg in (0.0, 120.0, 240.0):
        angle = math.radians(angle_deg)
        radial = (math.cos(angle), math.sin(angle), 0.0)
        entry = (
            entry_radius * radial[0],
            entry_radius * radial[1],
            entry_z,
        )
        body_surface = (
            0.5 * float(contract.arm.root_diameter_mm) * radial[0],
            0.5 * float(contract.arm.root_diameter_mm) * radial[1],
            entry_z,
        )
        body = body.cut(make_root_transition_passage(contract, angle_deg, hole_radius))
        body = body.cut(_cylinder_between(hole_radius, entry, body_surface))
        channel_points = (
            _channel_point(contract, join_z, angle_deg),
            *tuple(
                _channel_point(contract, z_mm, angle_deg)
                for z_mm in planes
                if z_mm > join_z + 1.0e-8
            ),
        )
        for first, second in zip(channel_points, channel_points[1:]):
            body = body.cut(_cylinder_between(hole_radius, first, second))
    return body.clean()


def _clip_arm_section(body: cq.Shape, z_start: float, z_end: float) -> cq.Shape:
    if z_end <= z_start:
        raise ValueError("arm segment Z limits must be increasing")
    envelope = cq.Solid.makeBox(
        300.0,
        300.0,
        z_end - z_start,
        cq.Vector(-150.0, -150.0, z_start),
    )
    return body.intersect(envelope).clean()


def _point_segment_distance(
    point: tuple[float, float],
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    dx, dy = second[0] - first[0], second[1] - first[1]
    length2 = dx * dx + dy * dy
    if length2 <= 1.0e-12:
        return math.dist(point, first)
    t = max(
        0.0,
        min(
            1.0,
            ((point[0] - first[0]) * dx + (point[1] - first[1]) * dy)
            / length2,
        ),
    )
    projection = (first[0] + t * dx, first[1] + t * dy)
    return math.dist(point, projection)


def _point_polygon_distance(
    point: tuple[float, float], polygon: Sequence[tuple[float, float]]
) -> float:
    inside = False
    x, y = point
    for index, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(index + 1) % len(polygon)]
        if (y1 > y) != (y2 > y):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < crossing_x:
                inside = not inside
    if inside:
        return 0.0
    return min(
        _point_segment_distance(point, polygon[index], polygon[(index + 1) % len(polygon)])
        for index in range(len(polygon))
    )


def _minimum_dovetail_tendon_clearance(
    contract: Any, boundary_z_mm: float
) -> float:
    joint = contract.arm.dovetail
    hole_radius = max(0.40, 0.5 * float(contract.arm.tendon_diameter_mm) + 0.15)
    female_points = _dovetail_points(contract, float(joint.clearance_per_side_mm))
    minimum = float("inf")
    for sample_index in range(61):
        z_mm = boundary_z_mm + float(joint.engagement_mm) * sample_index / 60.0
        for angle_deg in (0.0, 120.0, 240.0):
            x, y, _ = _channel_point(contract, z_mm, angle_deg)
            distance = _point_polygon_distance((x, y), female_points)
            minimum = min(minimum, distance - hole_radius)
    return minimum


def build_arm_module(contract: Any) -> ArmBuildResult:
    paper_profiles = _paper_profile_polygons(contract)
    # Keep the ideal spiral arc planes separate from the clipped CAD profile
    # planes. Connector cuts are intentionally placed inside selected CAD
    # unit profiles, not at the interfaces between adjacent units.
    planes = compute_profile_planes(contract, paper_profiles)
    split_units = tuple(int(unit) for unit in contract.arm.split_unit_indices)
    boundary_z = tuple(
        0.5 * (float(planes[unit - 1]) + float(planes[unit])) + offset
        for unit, offset in zip(split_units, contract.arm.split_unit_offsets_mm)
    )
    z_limits = (0.0, *boundary_z, float(contract.arm.nominal_length_mm))
    z_ranges = tuple((z_limits[index], z_limits[index + 1]) for index in range(4))
    range_units = (1, *split_units, int(contract.arm.unit_count))
    unit_ranges = tuple(
        (range_units[index], range_units[index + 1]) for index in range(4)
    )
    continuous_body = _continuous_arm_body(contract, planes, paper_profiles)
    segments = {
        f"arm_segment_{index:02d}": _clip_arm_section(continuous_body, *z_range)
        for index, z_range in enumerate(z_ranges, start=1)
    }
    dovetails: list[DovetailInterface] = []
    locks: list[LockFeature] = []
    segment_names = tuple(segments)
    joint = contract.arm.dovetail
    lock_hole_radius = 0.5 * float(joint.lock_pin_hole_diameter_mm)
    lock_pin_radius = 0.5 * float(joint.lock_pin_diameter_mm)
    tendon_hole_radius = max(0.40, 0.5 * float(contract.arm.tendon_diameter_mm) + 0.15)
    for index, (unit_index, z_mm) in enumerate(zip(split_units, boundary_z), start=1):
        engagement = float(joint.engagement_mm)
        male = _dovetail_prism(contract, z_mm, engagement)
        female = _dovetail_prism(
            contract,
            z_mm - 0.02,
            engagement + 0.32,
            clearance_mm=float(joint.clearance_per_side_mm),
        )
        minimum_tendon_clearance = _minimum_dovetail_tendon_clearance(
            contract, z_mm
        )
        if minimum_tendon_clearance < 1.0:
            raise ValueError(
                f"dovetail {index} leaves only {minimum_tendon_clearance:.3f} mm "
                "clearance to a tendon bore"
            )
        pin_z = z_mm + 0.5 * engagement
        outer_radius = _profile_outer_radius_at_z(
            contract, paper_profiles, unit_index, pin_z
        )
        pin_length = 2.0 * outer_radius + 2.0
        pin_angle = math.radians(float(joint.lock_pin_azimuth_deg))
        pin_axis = cq.Vector(math.cos(pin_angle), math.sin(pin_angle), 0.0)
        pin_start = cq.Vector(0.0, 0.0, pin_z) - pin_axis * (0.5 * pin_length)
        pin_cutter = cq.Solid.makeCylinder(
            lock_hole_radius,
            pin_length,
            pin_start,
            pin_axis,
        )
        pin = cq.Solid.makeCylinder(
            lock_pin_radius,
            pin_length,
            pin_start,
            pin_axis,
        )
        pin_normal = (-math.sin(pin_angle), math.cos(pin_angle))
        pin_tendon_clearance = min(
            abs(pin_normal[0] * x + pin_normal[1] * y)
            - tendon_hole_radius
            - lock_hole_radius
            for x, y, _ in (
                _channel_point(contract, pin_z, angle_deg)
                for angle_deg in (0.0, 120.0, 240.0)
            )
        )
        if pin_tendon_clearance < 1.0:
            raise ValueError(
                f"dovetail lock pin {index} leaves only {pin_tendon_clearance:.3f} mm "
                "clearance to a tendon bore"
            )
        lower_name = segment_names[index - 1]
        upper_name = segment_names[index]
        segments[lower_name] = segments[lower_name].fuse(male).cut(pin_cutter).clean()
        segments[upper_name] = segments[upper_name].cut(female).cut(pin_cutter).clean()
        dovetails.append(
            DovetailInterface(
                name=f"dovetail_{index:02d}",
                unit_index=unit_index,
                boundary_z_mm=z_mm,
                male=male,
                female_cutter=female,
                engagement_mm=engagement,
                clearance_per_side_mm=float(joint.clearance_per_side_mm),
                rotation_deg=float(joint.rotation_deg),
                minimum_tendon_clearance_mm=minimum_tendon_clearance,
                lock_pin_azimuth_deg=float(joint.lock_pin_azimuth_deg),
                lock_pin_length_mm=pin_length,
            )
        )
        locks.append(
            LockFeature(
                name=f"dovetail_lock_{index:02d}",
                kind="full_width_removable_pin",
                proxy=pin,
                insertion_clearance_mm=float(joint.lock_pin_hole_diameter_mm)
                - float(joint.lock_pin_diameter_mm),
                unit_index=unit_index,
                center_z_mm=pin_z,
                diameter_mm=float(joint.lock_pin_diameter_mm),
                hole_diameter_mm=float(joint.lock_pin_hole_diameter_mm),
                axis_azimuth_deg=float(joint.lock_pin_azimuth_deg),
                length_mm=pin_length,
                tendon_clearance_mm=pin_tendon_clearance,
            )
        )
    centerlines = tuple(
        TendonChannel(
            name=f"tendon_{index:02d}",
            angle_deg=angle_deg,
            samples=_channel_samples(contract, planes, angle_deg, boundary_z),
        )
        for index, angle_deg in enumerate((0.0, 120.0, 240.0), start=1)
    )
    assembled = cq.Compound.makeCompound(list(segments.values()))
    spans = tuple(float(shape.BoundingBox().zlen) for shape in segments.values())
    for index, (name, shape) in enumerate(segments.items(), start=1):
        if not shape.isValid() or len(shape.Solids()) != 1:
            raise ValueError(
                f"arm print segment {name} must be one valid connected solid; "
                f"found {len(shape.Solids())} solids"
            )
        if shape.BoundingBox().zlen >= float(contract.arm.max_segment_height_mm):
            raise ValueError(
                f"arm print segment {index} exceeds the configured Z height limit"
            )
    tip_anchors: list[TipAnchor] = []
    for index, channel in enumerate(centerlines, start=1):
        point = channel.samples[-1]
        outer = cq.Solid.makeCylinder(0.60, 3.0, cq.Vector(point[0], point[1], 997.0), cq.Vector(0, 0, 1))
        inner = cq.Solid.makeCylinder(0.30, 3.2, cq.Vector(point[0], point[1], 996.9), cq.Vector(0, 0, 1))
        tip_anchors.append(TipAnchor(f"tip_tendon_anchor_{index:02d}", outer.cut(inner)))
    return ArmBuildResult(
        print_segments=segments,
        segment_ranges=unit_ranges,
        segment_z_ranges_mm=z_ranges,
        segment_spans_mm=spans,
        segment_boundary_z_mm=boundary_z,
        tendon_centerlines=centerlines,
        dovetails=tuple(dovetails),
        lock_features=tuple(locks),
        tip_anchors=tuple(tip_anchors),
        assembled_proxy=assembled,
        root_diameter_mm=float(contract.arm.root_diameter_mm),
        tip_diameter_mm=float(contract.arm.tip_diameter_mm),
        geometry_source="paper_discrete_logarithmic_spiral_profile",
        unit_profile_count=int(contract.arm.unit_count),
    )
