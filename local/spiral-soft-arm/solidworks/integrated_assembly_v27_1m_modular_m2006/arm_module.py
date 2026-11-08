from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Any, Sequence

import cadquery as cq


@dataclass(frozen=True)
class TendonChannel:
    name: str
    angle_deg: float
    samples: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class DovetailInterface:
    name: str
    boundary_z_mm: float
    male: cq.Shape
    female_cutter: cq.Shape


@dataclass(frozen=True)
class LockFeature:
    name: str
    kind: str
    proxy: cq.Shape
    insertion_clearance_mm: float


@dataclass(frozen=True)
class TipAnchor:
    name: str
    proxy: cq.Shape


@dataclass(frozen=True)
class ArmBuildResult:
    print_segments: dict[str, cq.Shape]
    segment_ranges: tuple[tuple[int, int], ...]
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
    """Return root-to-tip unit boundary planes for the paper-scale arm."""
    arm = contract.arm
    count = int(arm.unit_count)
    if count < 2:
        raise ValueError("the logarithmic arm requires at least two units")
    scale = (float(arm.root_diameter_mm) / float(arm.tip_diameter_mm)) ** (
        1.0 / (count - 1)
    )
    root_to_tip_weights = [scale ** (count - 1 - index) for index in range(count)]
    factor = float(arm.nominal_length_mm) / sum(root_to_tip_weights)
    planes = [0.0]
    for weight in root_to_tip_weights:
        planes.append(planes[-1] + factor * weight)
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


def _channel_samples(contract: Any, planes: Sequence[float], angle_deg: float) -> tuple[tuple[float, float, float], ...]:
    """Actual root entry starts radially, then blends into the axial arm route."""
    angle = math.radians(angle_deg)
    root_radius = 0.55 * _outer_radius(contract, 0.0)
    first = (root_radius * math.cos(angle), root_radius * math.sin(angle), 0.0)
    second_radius = root_radius + 1.0
    second = (
        second_radius * math.cos(angle),
        second_radius * math.sin(angle),
        1.0e-9,
    )
    return (first, second, *tuple(_channel_point(contract, z, angle_deg) for z in planes[1:]))


def _paper_profile_polygons(contract: Any) -> list[list[tuple[float, float]]]:
    """Generate the paper's discrete logarithmic-spiral quadrilateral units."""
    count = int(contract.arm.unit_count)
    delta = math.radians(30.0)
    b = math.log(float(contract.arm.root_diameter_mm) / float(contract.arm.tip_diameter_mm)) / ((count - 1) * delta)
    gamma = math.exp(b * delta)
    eb = math.exp(2.0 * math.pi * b)
    central_factor = 0.5 * (1.0 + eb)
    a = 1.0
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


def _dovetail_prism(z_mm: float, height_mm: float, clearance_mm: float = 0.0) -> cq.Shape:
    points = [
        (-5.0 - clearance_mm, -4.0 - clearance_mm),
        (5.0 + clearance_mm, -4.0 - clearance_mm),
        (7.0 + clearance_mm, 4.0 + clearance_mm),
        (-7.0 - clearance_mm, 4.0 + clearance_mm),
    ]
    return (
        cq.Workplane("XY")
        .workplane(offset=z_mm)
        .polyline(points)
        .close()
        .extrude(height_mm)
        .val()
    )


def _segment_body(
    contract: Any,
    planes: Sequence[float],
    unit_range: tuple[int, int],
) -> cq.Shape:
    start_unit, end_unit = unit_range
    z_start = float(planes[start_unit - 1])
    z_end = float(planes[end_unit])
    core = cq.Solid.makeCone(
        max(0.25, 0.10 * _outer_radius(contract, z_start)),
        max(0.25, 0.10 * _outer_radius(contract, z_end)),
        z_end - z_start,
        cq.Vector(0.0, 0.0, z_start),
        cq.Vector(0.0, 0.0, 1.0),
    )
    paper_profiles = _paper_profile_polygons(contract)
    plates: list[cq.Shape] = []
    for unit_number in range(start_unit, end_unit + 1):
        paper_index = int(contract.arm.unit_count) - unit_number
        plates.append(_revolved_profile(paper_profiles[paper_index]))
    body = core.fuse(*plates).clean()
    segment_envelope = cq.Solid.makeBox(
        300.0,
        300.0,
        z_end - z_start,
        cq.Vector(-150.0, -150.0, z_start),
    )
    body = body.intersect(segment_envelope).clean()
    hole_radius = max(0.40, 0.5 * float(contract.arm.tendon_diameter_mm) + 0.15)
    for angle_deg in (0.0, 120.0, 240.0):
        samples = _channel_samples(contract, planes, angle_deg)
        for first, second in zip(samples, samples[1:]):
            if max(first[2], second[2]) < z_start - 0.1 or min(first[2], second[2]) > z_end + 0.1:
                continue
            body = body.cut(_cylinder_between(hole_radius, first, second))
    return body.clean()


def build_arm_module(contract: Any) -> ArmBuildResult:
    planes = compute_unit_planes(contract)
    ranges = choose_four_segment_ranges(planes, contract.arm.max_segment_height_mm)
    segments = {
        f"arm_segment_{index:02d}": _segment_body(contract, planes, unit_range)
        for index, unit_range in enumerate(ranges, start=1)
    }
    boundary_z = tuple(float(planes[end]) for _, end in ranges[:-1])
    dovetails: list[DovetailInterface] = []
    locks: list[LockFeature] = []
    segment_names = tuple(segments)
    for index, z_mm in enumerate(boundary_z, start=1):
        male = _dovetail_prism(z_mm - 6.0, 6.0)
        female = _dovetail_prism(z_mm - 6.05, 6.6, clearance_mm=0.30)
        pin = cq.Solid.makeCylinder(
            1.25,
            18.0,
            cq.Vector(-9.0, 0.0, z_mm + 3.0),
            cq.Vector(1.0, 0.0, 0.0),
        )
        lower_name = segment_names[index - 1]
        upper_name = segment_names[index]
        segments[lower_name] = segments[lower_name].fuse(male).cut(pin).clean()
        segments[upper_name] = segments[upper_name].cut(female).cut(pin).clean()
        dovetails.append(
            DovetailInterface(
                name=f"dovetail_{index:02d}",
                boundary_z_mm=z_mm,
                male=male,
                female_cutter=female,
            )
        )
        locks.append(
            LockFeature(
                name=f"dovetail_lock_{index:02d}",
                kind="cross_pin",
                proxy=pin,
                insertion_clearance_mm=2.0,
            )
        )
    centerlines = tuple(
        TendonChannel(
            name=f"tendon_{index:02d}",
            angle_deg=angle_deg,
            samples=_channel_samples(contract, planes, angle_deg),
        )
        for index, angle_deg in enumerate((0.0, 120.0, 240.0), start=1)
    )
    assembled = cq.Compound.makeCompound(list(segments.values()))
    spans = tuple(float(planes[end] - planes[start - 1]) for start, end in ranges)
    tip_anchors: list[TipAnchor] = []
    for index, channel in enumerate(centerlines, start=1):
        point = channel.samples[-1]
        outer = cq.Solid.makeCylinder(0.60, 3.0, cq.Vector(point[0], point[1], 997.0), cq.Vector(0, 0, 1))
        inner = cq.Solid.makeCylinder(0.30, 3.2, cq.Vector(point[0], point[1], 996.9), cq.Vector(0, 0, 1))
        tip_anchors.append(TipAnchor(f"tip_tendon_anchor_{index:02d}", outer.cut(inner)))
    return ArmBuildResult(
        print_segments=segments,
        segment_ranges=ranges,
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
