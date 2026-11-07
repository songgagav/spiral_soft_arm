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


@dataclass(frozen=True)
class ArmBuildResult:
    print_segments: dict[str, cq.Shape]
    segment_ranges: tuple[tuple[int, int], ...]
    segment_spans_mm: tuple[float, ...]
    segment_boundary_z_mm: tuple[float, ...]
    tendon_centerlines: tuple[TendonChannel, ...]
    dovetails: tuple[DovetailInterface, ...]
    lock_features: tuple[LockFeature, ...]
    assembled_proxy: cq.Shape
    root_diameter_mm: float
    tip_diameter_mm: float


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
    if max(heights) >= max_height_mm:
        raise ValueError("an individual unit exceeds the segment height limit")
    unit_count = len(heights)
    best: tuple[tuple[float, float, tuple[int, int, int]], tuple[tuple[int, int], ...]] | None = None
    for cuts in combinations(range(1, unit_count), 3):
        bounds = (0, *cuts, unit_count)
        spans = tuple(
            float(unit_planes[bounds[index + 1]] - unit_planes[bounds[index]])
            for index in range(4)
        )
        if any(span >= max_height_mm for span in spans):
            continue
        ranges = tuple(
            (bounds[index] + 1, bounds[index + 1]) for index in range(4)
        )
        score = (max(spans), max(spans) - min(spans), cuts)
        if best is None or score < best[0]:
            best = (score, ranges)
    if best is None:
        raise ValueError("no four-segment unit-boundary solution satisfies the height limit")
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
    plates: list[cq.Shape] = []
    for unit_number in range(start_unit, end_unit + 1):
        unit_z0 = float(planes[unit_number - 1])
        unit_z1 = float(planes[unit_number])
        unit_height = unit_z1 - unit_z0
        plate_height = unit_height if unit_number == len(planes) - 1 else 0.72 * unit_height
        plate_z1 = unit_z0 + plate_height
        plates.append(
            cq.Solid.makeCone(
                _outer_radius(contract, unit_z0),
                _outer_radius(contract, plate_z1),
                plate_height,
                cq.Vector(0.0, 0.0, unit_z0),
                cq.Vector(0.0, 0.0, 1.0),
            )
        )
    body = core.fuse(*plates).clean()
    hole_radius = max(0.40, 0.5 * float(contract.arm.tendon_diameter_mm) + 0.15)
    for angle_deg in (0.0, 120.0, 240.0):
        extension = 1.0
        cutter = _cylinder_between(
            hole_radius,
            _channel_point(contract, z_start - extension, angle_deg),
            _channel_point(contract, z_end + extension, angle_deg),
        )
        body = body.cut(cutter)
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
        male = _dovetail_prism(z_mm, 6.0)
        female = _dovetail_prism(z_mm - 0.05, 6.6, clearance_mm=0.30)
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
            )
        )
    centerlines = tuple(
        TendonChannel(
            name=f"tendon_{index:02d}",
            angle_deg=angle_deg,
            samples=tuple(_channel_point(contract, z_mm, angle_deg) for z_mm in planes),
        )
        for index, angle_deg in enumerate((0.0, 120.0, 240.0), start=1)
    )
    assembled = cq.Compound.makeCompound(list(segments.values()))
    spans = tuple(float(planes[end] - planes[start - 1]) for start, end in ranges)
    return ArmBuildResult(
        print_segments=segments,
        segment_ranges=ranges,
        segment_spans_mm=spans,
        segment_boundary_z_mm=boundary_z,
        tendon_centerlines=centerlines,
        dovetails=tuple(dovetails),
        lock_features=tuple(locks),
        assembled_proxy=assembled,
        root_diameter_mm=float(contract.arm.root_diameter_mm),
        tip_diameter_mm=float(contract.arm.tip_diameter_mm),
    )
