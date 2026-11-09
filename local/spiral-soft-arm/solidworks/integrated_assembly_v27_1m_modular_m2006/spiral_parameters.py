from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any


@dataclass(frozen=True)
class PaperSpiralParameters:
    nominal_length_mm: float
    tip_width_mm: float
    root_width_mm: float
    unit_count: int
    unit_interval_count: int
    b: float
    a_mm: float
    a1_mm: float
    theta0_rad: float
    theta0_pi: float
    theta0_turns: float
    delta_theta_rad: float
    delta_theta_deg: float
    beta: float
    tangent_angle_psi_deg: float
    taper_angle_phi_deg: float
    centerline_scale_mm: float
    centerline_length_reconstructed_mm: float
    unit_boundary_theta_rad: tuple[float, ...]
    unit_interval_lengths_mm: tuple[float, ...]
    freshwater_density_kg_m3: float
    seawater_density_kg_m3: float
    gravity_m_s2: float
    water_depth_m: float
    ambient_pressure_kpa: float
    freshwater_gauge_pressure_kpa: float
    seawater_gauge_pressure_kpa: float
    freshwater_absolute_pressure_kpa: float
    seawater_absolute_pressure_kpa: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _length_from_b(b: float, tip_width_mm: float, diameter_ratio: float) -> float:
    if b <= 0.0:
        return math.inf
    a1 = 0.5 * tip_width_mm / math.tanh(math.pi * b)
    return math.sqrt(1.0 + b * b) * a1 * (diameter_ratio - 1.0) / b


def _solve_b(
    nominal_length_mm: float, tip_width_mm: float, diameter_ratio: float
) -> float:
    """Solve the positive root of paper Eq. (5) after applying the end ratio."""
    if nominal_length_mm <= 0.0 or tip_width_mm <= 0.0 or diameter_ratio <= 1.0:
        raise ValueError("length, tip width, and root/tip ratio must be positive and ordered")

    def residual(value: float) -> float:
        return _length_from_b(value, tip_width_mm, diameter_ratio) - nominal_length_mm

    low = 1.0e-9
    high = 1.0
    while residual(high) > 0.0:
        high *= 2.0
        if high > 64.0:
            raise ValueError("could not bracket a positive spiral-growth solution")
    for _ in range(160):
        middle = 0.5 * (low + high)
        if residual(middle) > 0.0:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


def derive_paper_spiral(
    *,
    nominal_length_mm: float,
    tip_width_mm: float,
    root_width_mm: float,
    unit_count: int,
    water_depth_m: float,
    freshwater_density_kg_m3: float = 1000.0,
    seawater_density_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    ambient_pressure_kpa: float = 101.325,
) -> PaperSpiralParameters:
    """Derive the paper's logarithmic spiral and equal-angle arc intervals.

    Each discrete quadrilateral unit represents one angular interval. Water depth
    is recorded as an environmental pressure context and does not enter b/a/theta.
    """
    if unit_count < 1:
        raise ValueError("unit_count must be at least one")
    if water_depth_m < 0.0:
        raise ValueError("water depth cannot be negative")
    ratio = float(root_width_mm) / float(tip_width_mm)
    b = _solve_b(float(nominal_length_mm), float(tip_width_mm), ratio)
    theta0 = math.log(ratio) / b
    q = math.exp(2.0 * math.pi * b)
    a = float(tip_width_mm) / (q - 1.0)
    a1 = 0.5 * a * (q + 1.0)
    delta = theta0 / int(unit_count)
    beta = math.exp(b * delta)
    centerline_scale = math.sqrt(1.0 + b * b) * a1 / b

    theta_bounds = tuple(index * delta for index in range(unit_count + 1))
    interval_lengths = tuple(
        centerline_scale
        * (math.exp(b * theta_bounds[index + 1]) - math.exp(b * theta_bounds[index]))
        for index in range(unit_count)
    )
    reconstructed_length = (
        math.sqrt(1.0 + b * b)
        * a1
        / b
        * (math.exp(b * theta0) - 1.0)
    )
    phi = 2.0 * math.atan(
        b * (q - 1.0) / (math.sqrt(1.0 + b * b) * (q + 1.0))
    )
    pressure_fresh = (
        float(freshwater_density_kg_m3) * float(gravity_m_s2) * float(water_depth_m) / 1000.0
    )
    pressure_sea = (
        float(seawater_density_kg_m3) * float(gravity_m_s2) * float(water_depth_m) / 1000.0
    )
    return PaperSpiralParameters(
        nominal_length_mm=float(nominal_length_mm),
        tip_width_mm=float(tip_width_mm),
        root_width_mm=float(root_width_mm),
        unit_count=int(unit_count),
        unit_interval_count=int(unit_count),
        b=b,
        a_mm=a,
        a1_mm=a1,
        theta0_rad=theta0,
        theta0_pi=theta0 / math.pi,
        theta0_turns=theta0 / (2.0 * math.pi),
        delta_theta_rad=delta,
        delta_theta_deg=math.degrees(delta),
        beta=beta,
        tangent_angle_psi_deg=math.degrees(math.atan2(1.0, b)),
        taper_angle_phi_deg=math.degrees(phi),
        centerline_scale_mm=centerline_scale,
        centerline_length_reconstructed_mm=reconstructed_length,
        unit_boundary_theta_rad=theta_bounds,
        unit_interval_lengths_mm=interval_lengths,
        freshwater_density_kg_m3=float(freshwater_density_kg_m3),
        seawater_density_kg_m3=float(seawater_density_kg_m3),
        gravity_m_s2=float(gravity_m_s2),
        water_depth_m=float(water_depth_m),
        ambient_pressure_kpa=float(ambient_pressure_kpa),
        freshwater_gauge_pressure_kpa=pressure_fresh,
        seawater_gauge_pressure_kpa=pressure_sea,
        freshwater_absolute_pressure_kpa=float(ambient_pressure_kpa) + pressure_fresh,
        seawater_absolute_pressure_kpa=float(ambient_pressure_kpa) + pressure_sea,
    )


def derive_from_contract(contract: Any) -> PaperSpiralParameters:
    arm = contract.arm
    return derive_paper_spiral(
        nominal_length_mm=arm.nominal_length_mm,
        tip_width_mm=arm.tip_diameter_mm,
        root_width_mm=arm.root_diameter_mm,
        unit_count=arm.unit_count,
        water_depth_m=contract.environment.max_depth_m,
    )
