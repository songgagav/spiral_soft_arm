"""Paper equations and explicit unit conversions for stage-A geometry."""
from __future__ import annotations

import math


def count_units(theta_max_pi: float, delta_theta_deg: float) -> int:
    """Match DesignTool's cutoff rule, with a small tolerance at integer edges."""
    if delta_theta_deg <= 0 or theta_max_pi <= 2:
        raise ValueError("theta_max_pi 必须大于 2，且 delta_theta_deg 必须为正数")
    raw = (theta_max_pi - 2.0) * 180.0 / delta_theta_deg
    return max(1, int(math.floor(raw + 1e-9)))


def paper_metrics(a_mm: float, b: float, num_units: int, delta_theta_deg: float) -> dict[str, float]:
    """Return continuous SpiRobs theory values for fixed p=0.5 geometry."""
    if a_mm <= 0 or b <= 0 or num_units < 1 or delta_theta_deg <= 0:
        raise ValueError("a、b、num_units 和 delta_theta_deg 必须为正数")
    delta = math.radians(delta_theta_deg)
    theta = num_units * delta
    central_scale = 0.5 * (math.exp(2.0 * math.pi * b) + 1.0)
    tip = a_mm * (math.exp(2.0 * math.pi * b) - 1.0)
    base = tip * math.exp(b * theta)
    length = central_scale * a_mm * math.sqrt(1.0 + b * b) / b * math.expm1(b * theta)
    return {
        "tip_diameter_mm": tip,
        "base_diameter_mm": base,
        "centerline_length_mm": length,
    }


def discrete_chord_length_mm(a_mm: float, b: float, num_units: int, delta_theta_deg: float) -> float:
    """Sum the straight central-spiral links used by the local generator."""
    delta = math.radians(delta_theta_deg)
    gamma = math.exp(b * delta)
    central_scale = 0.5 * (math.exp(2.0 * math.pi * b) + 1.0)
    first_chord = central_scale * a_mm * math.sqrt(1.0 + gamma * gamma - 2.0 * gamma * math.cos(delta))
    return first_chord * math.expm1(num_units * math.log(gamma)) / (gamma - 1.0)


def _polar_to_cart(theta: float, radius: float) -> tuple[float, float]:
    return radius * math.cos(theta), radius * math.sin(theta)


def build_unfold_polygons(
    a_mm: float, b: float, delta_theta_deg: float, p: float, num_units: int
) -> list[list[tuple[float, float]]]:
    """Port DesignTool._build_unfold_polygons for the primary 3-cable profile."""
    dtheta = math.radians(max(1, int(delta_theta_deg)))
    gamma = math.exp(b * dtheta)
    eb = math.exp(2.0 * math.pi * b)
    central_factor = (1.0 - p) + p * eb
    p0 = _polar_to_cart(0.0, a_mm)
    p1 = _polar_to_cart(dtheta, a_mm * math.exp(b * dtheta))
    q0 = _polar_to_cart(0.0, central_factor * a_mm)
    q1 = _polar_to_cart(dtheta, central_factor * a_mm * math.exp(b * dtheta))
    dq = q1[0] - q0[0], q1[1] - q0[1]
    angle = -math.atan2(dq[1], dq[0])
    ca, sa = math.cos(angle), math.sin(angle)

    def rotate(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return x * ca - y * sa, x * sa + y * ca

    base = [rotate(point) for point in (p0, p1, q1, q0)]
    result: list[list[tuple[float, float]]] = []
    current_x = 0.0
    for index in range(max(1, num_units)):
        scale = gamma**index
        scaled = [(x * scale, y * scale) for x, y in base]
        q0_scaled, q1_scaled = scaled[3], scaled[2]
        dx, dy = current_x - q0_scaled[0], -q0_scaled[1]
        result.append([(x + dx, y + dy) for x, y in scaled])
        current_x = dx + q1_scaled[0]
    return result


def _clip_polygon_x(poly: list[tuple[float, float]], plane_x: float, keep_greater: bool) -> list[tuple[float, float]]:
    """Clip a 2D profile polygon against one axial half-plane."""
    if not poly:
        return []
    output = []
    previous = poly[-1]
    previous_inside = previous[0] >= plane_x - 1e-9 if keep_greater else previous[0] <= plane_x + 1e-9
    for current in poly:
        current_inside = current[0] >= plane_x - 1e-9 if keep_greater else current[0] <= plane_x + 1e-9
        if current_inside != previous_inside:
            dx = current[0] - previous[0]
            if abs(dx) > 1e-12:
                fraction = (plane_x - previous[0]) / dx
                output.append((plane_x, previous[1] + fraction * (current[1] - previous[1])))
        if current_inside:
            output.append(current)
        previous, previous_inside = current, current_inside
    compact = []
    for point in output:
        if not compact or abs(point[0] - compact[-1][0]) > 1e-9 or abs(point[1] - compact[-1][1]) > 1e-9:
            compact.append(point)
    if len(compact) > 1 and abs(compact[0][0] - compact[-1][0]) <= 1e-9 and abs(compact[0][1] - compact[-1][1]) <= 1e-9:
        compact.pop()
    return compact


def profile_peak_planes(polygons: list[list[tuple[float, float]]]) -> tuple[float, float]:
    """Return the end of the tip-width plateau and start of the base-width plateau."""
    if not polygons or not polygons[0] or not polygons[-1]:
        raise ValueError("轮廓不能为空")
    def peak_x(poly, latest: bool) -> float:
        peak_y = max(y for _x, y in poly)
        tolerance = max(1e-9, abs(peak_y) * 1e-10)
        xs = [x for x, y in poly if y >= peak_y - tolerance]
        return max(xs) if latest else min(xs)

    tip_plane = peak_x(polygons[0], latest=True)
    base_plane = peak_x(polygons[-1], latest=False)
    if base_plane <= tip_plane:
        raise ValueError("基部峰值截面必须位于尖端峰值截面之后")
    return tip_plane, base_plane


def build_body_profile_polygons(
    a_mm: float, b: float, delta_theta_deg: float, p: float, num_units: int
) -> list[list[tuple[float, float]]]:
    """Trim source overhangs at actual tip/base peak planes and rebase the body at Z=0."""
    source = build_unfold_polygons(a_mm, b, delta_theta_deg, p, num_units)
    tip_plane, base_plane = profile_peak_planes(source)
    clipped = []
    for poly in source:
        points = _clip_polygon_x(poly, tip_plane, True)
        points = _clip_polygon_x(points, base_plane, False)
        if len(points) < 3:
            continue
        area = abs(sum(points[i][0] * points[(i + 1) % len(points)][1]
                       - points[(i + 1) % len(points)][0] * points[i][1]
                       for i in range(len(points))) / 2.0)
        if area > 1e-9:
            clipped.append([(x - tip_plane, y) for x, y in points])
    if not clipped:
        raise ValueError("端面裁切后没有有效轮廓")
    return clipped


def local_profile_metrics(
    a_mm: float, b: float, num_units: int, delta_theta_deg: float
) -> dict[str, float]:
    """Measure the source-like unfolded profile's axial span and tip/base diameters."""
    source = build_unfold_polygons(a_mm, b, delta_theta_deg, 0.5, num_units)
    tip_plane, base_plane = profile_peak_planes(source)
    polygons = build_body_profile_polygons(a_mm, b, delta_theta_deg, 0.5, num_units)
    tip_diameter = 2.0 * max(y for _x, y in polygons[0])
    base_diameter = 2.0 * max(y for _x, y in polygons[-1])
    length = max(x for x, _y in polygons[-1])
    raw_length = max(x for poly in source for x, _y in poly) - min(x for poly in source for x, _y in poly)
    return {
        "discrete_axis_span_mm": length,
        "local_tip_diameter_mm": tip_diameter,
        "local_base_diameter_mm": base_diameter,
        "raw_profile_span_mm": raw_length,
        "tip_peak_plane_source_z_mm": tip_plane,
        "base_peak_plane_source_z_mm": base_plane,
    }


def percent_to_fraction(value_pct: float) -> float:
    if not 0.0 <= value_pct <= 100.0:
        raise ValueError("百分比必须在 0 到 100 之间")
    return value_pct / 100.0


def mm_to_m(value_mm: float) -> float:
    return value_mm * 0.001


def mm3_to_m3(value_mm3: float) -> float:
    return value_mm3 * 1e-9


def kg_mm2_to_kg_m2(value_kg_mm2: float) -> float:
    return value_kg_mm2 * 1e-6
