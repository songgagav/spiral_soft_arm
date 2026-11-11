from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any, Sequence


Point3 = tuple[float, float, float]
Centerline = Sequence[Point3]


@dataclass(frozen=True)
class TendonTravelReport:
    reference_lengths_mm: tuple[float, ...]
    extreme_lengths_mm: tuple[tuple[float, ...], ...]
    signed_deltas_mm: tuple[tuple[float, ...], ...]
    required_travel_mm: tuple[float, ...]
    assumptions: dict[str, Any]


@dataclass(frozen=True)
class SpoolCapacityReport:
    required_travel_mm: float
    margin_fraction: float
    required_with_margin_mm: float
    usable_turns: float
    minimum_effective_radius_mm: float
    maximum_effective_radius_mm: float
    available_travel_mm: float
    required_turns_at_max_radius: float
    margin_mm: float
    qualified: bool
    missing_measurements: tuple[str, ...]
    assumptions: dict[str, Any]


@dataclass(frozen=True)
class ForceBudgetReport:
    motor_continuous_torque_nm: float
    drivetrain_efficiency: float
    seal_drag_torque_nm: float
    tendon_friction_efficiency: float
    minimum_effective_radius_mm: float
    maximum_effective_radius_mm: float
    net_spool_torque_nm: float
    minimum_tendon_force_n: float
    maximum_tendon_force_n: float
    qualified: bool
    missing_measurements: tuple[str, ...]
    assumptions: dict[str, Any]


@dataclass(frozen=True)
class RootLoadReport:
    target_mass_kg: float
    displaced_volume_m3: float | None
    water_density_kg_m3: float
    gravity_m_s2: float
    buoyant_force_n: float
    net_downward_force_n: float
    lever_arm_m: float
    impact_factor: float
    root_moment_nm: float
    fastener_count: int
    dowel_count: int
    nominal_force_per_fastener_n: float
    nominal_force_per_dowel_n: float
    qualified: bool
    missing_measurements: tuple[str, ...]
    assumptions: dict[str, Any]


def _path_length(points: Centerline) -> float:
    if len(points) < 2:
        raise ValueError("a sampled centerline requires at least two points")
    return sum(
        math.dist(tuple(float(value) for value in left), tuple(float(value) for value in right))
        for left, right in zip(points, points[1:])
    )


def compute_tendon_travel(
    reference_centerlines: Sequence[Centerline],
    extreme_centerline_sets: Sequence[Sequence[Centerline]],
) -> TendonTravelReport:
    if not reference_centerlines:
        raise ValueError("at least one tendon centerline is required")
    reference = tuple(_path_length(line) for line in reference_centerlines)
    extreme_lengths: list[tuple[float, ...]] = []
    signed_deltas: list[tuple[float, ...]] = []
    for state in extreme_centerline_sets:
        if len(state) != len(reference):
            raise ValueError("every extreme state must contain every tendon")
        lengths = tuple(_path_length(line) for line in state)
        extreme_lengths.append(lengths)
        signed_deltas.append(
            tuple(length - baseline for length, baseline in zip(lengths, reference))
        )
    if not extreme_lengths:
        raise ValueError("at least one design extreme is required")
    required = tuple(
        max(delta[index] for delta in signed_deltas)
        - min(delta[index] for delta in signed_deltas)
        for index in range(len(reference))
    )
    return TendonTravelReport(
        reference_lengths_mm=reference,
        extreme_lengths_mm=tuple(extreme_lengths),
        signed_deltas_mm=tuple(signed_deltas),
        required_travel_mm=required,
        assumptions={
            "method": "piecewise_linear_sampled_centerline_length",
            "travel_definition": "full_extreme_to_extreme_wind_and_payout_range",
        },
    )


def compute_spool_capacity(
    *,
    required_travel_mm: float,
    usable_turns: float,
    minimum_effective_radius_mm: float,
    maximum_effective_radius_mm: float,
    margin_fraction: float = 0.20,
) -> SpoolCapacityReport:
    values = (
        required_travel_mm,
        usable_turns,
        minimum_effective_radius_mm,
        maximum_effective_radius_mm,
    )
    if any(value <= 0.0 for value in values):
        raise ValueError("travel, turns and effective radii must be positive")
    if maximum_effective_radius_mm < minimum_effective_radius_mm:
        raise ValueError("maximum spool radius may not be below minimum radius")
    if margin_fraction < 0.0:
        raise ValueError("capacity margin may not be negative")
    required_with_margin = required_travel_mm * (1.0 + margin_fraction)
    available = 2.0 * math.pi * minimum_effective_radius_mm * usable_turns
    required_turns = required_with_margin / (
        2.0 * math.pi * maximum_effective_radius_mm
    )
    margin = available - required_with_margin
    return SpoolCapacityReport(
        required_travel_mm=float(required_travel_mm),
        margin_fraction=float(margin_fraction),
        required_with_margin_mm=required_with_margin,
        usable_turns=float(usable_turns),
        minimum_effective_radius_mm=float(minimum_effective_radius_mm),
        maximum_effective_radius_mm=float(maximum_effective_radius_mm),
        available_travel_mm=available,
        required_turns_at_max_radius=required_turns,
        margin_mm=margin,
        qualified=margin >= 0.0,
        missing_measurements=() if margin >= 0.0 else ("additional_spool_capacity",),
        assumptions={
            "capacity_radius": "minimum_effective_radius_conservative",
            "required_turns_radius": "maximum_effective_radius_conservative",
            "capacity_margin_fraction": float(margin_fraction),
        },
    )


def compute_force_budget(
    *,
    motor_continuous_torque_nm: float,
    drivetrain_efficiency: float,
    seal_drag_torque_nm: float,
    tendon_friction_efficiency: float,
    minimum_effective_radius_mm: float,
    maximum_effective_radius_mm: float,
) -> ForceBudgetReport:
    if motor_continuous_torque_nm <= 0.0 or minimum_effective_radius_mm <= 0.0:
        raise ValueError("motor torque and effective radius must be positive")
    if maximum_effective_radius_mm < minimum_effective_radius_mm:
        raise ValueError("maximum spool radius may not be below minimum radius")
    if not 0.0 < drivetrain_efficiency <= 1.0:
        raise ValueError("drivetrain efficiency must be in (0, 1]")
    if not 0.0 < tendon_friction_efficiency <= 1.0:
        raise ValueError("tendon friction efficiency must be in (0, 1]")
    if seal_drag_torque_nm < 0.0:
        raise ValueError("seal drag torque may not be negative")
    net_torque = motor_continuous_torque_nm * drivetrain_efficiency - seal_drag_torque_nm
    if net_torque <= 0.0:
        raise ValueError("seal drag consumes the available continuous torque")
    maximum_force = net_torque / (minimum_effective_radius_mm / 1000.0) * tendon_friction_efficiency
    minimum_force = net_torque / (maximum_effective_radius_mm / 1000.0) * tendon_friction_efficiency
    assumptions = {
        "motor_continuous_torque_nm": float(motor_continuous_torque_nm),
        "drivetrain_efficiency": float(drivetrain_efficiency),
        "seal_drag_torque_nm": float(seal_drag_torque_nm),
        "tendon_friction_efficiency": float(tendon_friction_efficiency),
        "force_model": "steady_low_speed_torque_over_radius_after_losses",
    }
    return ForceBudgetReport(
        motor_continuous_torque_nm=float(motor_continuous_torque_nm),
        drivetrain_efficiency=float(drivetrain_efficiency),
        seal_drag_torque_nm=float(seal_drag_torque_nm),
        tendon_friction_efficiency=float(tendon_friction_efficiency),
        minimum_effective_radius_mm=float(minimum_effective_radius_mm),
        maximum_effective_radius_mm=float(maximum_effective_radius_mm),
        net_spool_torque_nm=net_torque,
        minimum_tendon_force_n=minimum_force,
        maximum_tendon_force_n=maximum_force,
        qualified=False,
        missing_measurements=(
            "measured_seal_drag_torque",
            "measured_drivetrain_efficiency",
            "measured_tendon_friction_efficiency",
        ),
        assumptions=assumptions,
    )


def compute_root_load(
    *,
    target_mass_kg: float,
    displaced_volume_m3: float | None,
    water_density_kg_m3: float,
    lever_arm_m: float,
    impact_factor: float,
    fastener_count: int = 6,
    dowel_count: int = 2,
) -> RootLoadReport:
    if target_mass_kg < 0.0 or water_density_kg_m3 <= 0.0:
        raise ValueError("mass must be nonnegative and water density positive")
    if displaced_volume_m3 is not None and displaced_volume_m3 < 0.0:
        raise ValueError("displaced volume may not be negative")
    if lever_arm_m < 0.0 or impact_factor < 1.0:
        raise ValueError("lever arm must be nonnegative and impact factor at least one")
    if fastener_count <= 0 or dowel_count <= 0:
        raise ValueError("positive fastener and dowel counts are required")
    gravity = 9.80665
    missing: tuple[str, ...] = ()
    if displaced_volume_m3 is None:
        buoyancy = 0.0
        missing = ("target_displaced_volume",)
    else:
        buoyancy = water_density_kg_m3 * displaced_volume_m3 * gravity
    downward = max(0.0, target_mass_kg * gravity - buoyancy)
    design_force = downward * impact_factor
    return RootLoadReport(
        target_mass_kg=float(target_mass_kg),
        displaced_volume_m3=None if displaced_volume_m3 is None else float(displaced_volume_m3),
        water_density_kg_m3=float(water_density_kg_m3),
        gravity_m_s2=gravity,
        buoyant_force_n=buoyancy,
        net_downward_force_n=downward,
        lever_arm_m=float(lever_arm_m),
        impact_factor=float(impact_factor),
        root_moment_nm=design_force * lever_arm_m,
        fastener_count=int(fastener_count),
        dowel_count=int(dowel_count),
        nominal_force_per_fastener_n=design_force / fastener_count,
        nominal_force_per_dowel_n=design_force / dowel_count,
        qualified=not missing,
        missing_measurements=missing,
        assumptions={
            "unknown_displacement_policy": "zero_buoyancy_worst_case",
            "load_distribution": "nominal_equal_share_inputs_only",
            "not_a_fastener_stress_analysis": True,
        },
    )


def _constant_curvature_state(
    centerlines: Sequence[Centerline], bend_angle_deg: float, length_mm: float
) -> tuple[tuple[Point3, ...], ...]:
    total_angle = math.radians(bend_angle_deg)
    if total_angle == 0.0:
        return tuple(tuple(point for point in line) for line in centerlines)
    radius = length_mm / total_angle
    transformed: list[tuple[Point3, ...]] = []
    for line in centerlines:
        points: list[Point3] = []
        for x_mm, y_mm, z_mm in line:
            theta = total_angle * z_mm / length_mm
            neutral_x = radius * (1.0 - math.cos(theta))
            neutral_z = radius * math.sin(theta)
            points.append(
                (
                    neutral_x + x_mm * math.cos(theta),
                    y_mm,
                    neutral_z - x_mm * math.sin(theta),
                )
            )
        transformed.append(tuple(points))
    return tuple(transformed)


def build_measurement_plan() -> dict[str, dict[str, Any]]:
    """List physical measurements that proxy calculations cannot replace."""
    pending = "pending_physical_measurement"
    return {
        "wet_mass_and_buoyancy": {
            "status": pending,
            "required_inputs": [
                "measured_arm_wet_mass_kg",
                "measured_displaced_volume_m3",
                "freshwater_and_seawater_density_kg_m3",
            ],
            "bench_method": "Weigh the fully assembled dry and flooded machine, then measure displaced volume in fresh and salt water.",
            "acceptance_evidence": "Recorded mass, displacement and residual buoyancy for each medium.",
        },
        "dynamic_root_load": {
            "status": pending,
            "required_inputs": [
                "measured_tip_load_N",
                "motion_profile",
                "root_acceleration_or_strain_trace",
            ],
            "bench_method": "Run constrained low-speed and start-stop motions with a root load cell or strain-gauged fixture.",
            "acceptance_evidence": "Peak root force and moment traces linked to the motion profile.",
        },
        "bolt_group_capacity": {
            "status": pending,
            "required_inputs": [
                "fastener_grade",
                "thread_engagement_mm",
                "printed_or_metal_mate_material",
                "torque_and_preload",
            ],
            "bench_method": "Confirm the installed bolt stack, then load the root interface in the documented worst-case direction.",
            "acceptance_evidence": "Fastener specification, torque record and static/fatigue load result.",
        },
        "low_speed_full_travel_current": {
            "status": pending,
            "required_inputs": [
                "bus_voltage_V",
                "per_motor_current_A",
                "motor_and_C610_temperature_C",
                "full_tendon_travel_command",
            ],
            "bench_method": "Log each C610 current and temperature through complete low-speed payout and take-up cycles.",
            "acceptance_evidence": "Time-aligned current, voltage and temperature log for all three routes.",
        },
        "drivetrain_efficiency": {
            "status": pending,
            "required_inputs": [
                "motor_input_torque_or_current_calibration",
                "spool_output_torque",
                "gear_lubrication_state",
            ],
            "bench_method": "Compare calibrated motor input torque with output torque at the spool under representative low-speed load.",
            "acceptance_evidence": "Efficiency versus load trace with the fitted gear pair installed.",
        },
        "seal_drag": {
            "status": pending,
            "required_inputs": [
                "seal_part_and_material",
                "journal_surface_finish",
                "dry_and_wet_breakaway_torque",
            ],
            "bench_method": "Measure breakaway and running torque of the completed shaft, seal and labyrinth assembly dry and submerged.",
            "acceptance_evidence": "Torque trace, leakage observation and test duration for both media.",
        },
        "tendon_friction": {
            "status": pending,
            "required_inputs": [
                "actual_tendon_diameter_mm",
                "route_tension_in_N",
                "route_tension_out_N",
                "bend_state",
            ],
            "bench_method": "Pull each actual tendon route at low speed through straight and bent arm states while measuring both-end tension.",
            "acceptance_evidence": "Per-route friction ratio, sliding observation, slack and rebound record.",
        },
        "spool_usable_turns": {
            "status": pending,
            "required_inputs": [
                "actual_tendon_diameter_mm",
                "first_and_last_layer_radius_mm",
                "retained_turns_before_flange_contact",
            ],
            "bench_method": "Wind the production tendon across the full spool width and count stable turns before flange contact or cross-over instability.",
            "acceptance_evidence": "Video or photographs plus turn count and layered-radius measurement for each spool.",
        },
    }


def generate_v27_engineering_audit(contract: Any) -> dict[str, Any]:
    from arm_module import build_arm_module

    arm = build_arm_module(contract)
    reference = tuple(channel.samples for channel in arm.tendon_centerlines)
    extremes = (
        _constant_curvature_state(reference, 60.0, contract.arm.nominal_length_mm),
        _constant_curvature_state(reference, -60.0, contract.arm.nominal_length_mm),
    )
    travel = compute_tendon_travel(reference, extremes)
    required_travel = max(travel.required_travel_mm)
    capacity = compute_spool_capacity(
        required_travel_mm=required_travel,
        usable_turns=6.0,
        minimum_effective_radius_mm=10.0,
        maximum_effective_radius_mm=12.0,
    )
    force = compute_force_budget(
        motor_continuous_torque_nm=1.0,
        drivetrain_efficiency=0.85,
        seal_drag_torque_nm=0.05,
        tendon_friction_efficiency=0.70,
        minimum_effective_radius_mm=10.0,
        maximum_effective_radius_mm=12.0,
    )
    root_load = compute_root_load(
        target_mass_kg=contract.environment.payload_mass_kg,
        displaced_volume_m3=None,
        water_density_kg_m3=1025.0,
        lever_arm_m=contract.arm.nominal_length_mm / 1000.0,
        impact_factor=1.5,
        fastener_count=contract.root_interface.fastener_count,
        dowel_count=contract.root_interface.dowel_count,
    )
    missing = sorted(
        {
            "measured_spool_usable_turns",
            "measured_seal_drag_torque",
            "measured_drivetrain_efficiency",
            "measured_tendon_friction_efficiency",
            "measured_dynamic_root_load",
            "arm_wet_mass_and_buoyancy",
            "bolt_group_capacity",
            "measured_low_speed_full_travel_current",
            *root_load.missing_measurements,
            *capacity.missing_measurements,
            *force.missing_measurements,
        }
    )
    return {
        "candidate_id": contract.candidate_id,
        "status": "calculation_candidate_not_physical_release",
        "hardware_validated": False,
        "qualified": False,
        "missing_measurements": missing,
        "design_extremes": {"constant_curvature_bend_angles_deg": [60.0, -60.0]},
        "tendon_travel": asdict(travel),
        "spool_capacity": asdict(capacity),
        "force_budget": asdict(force),
        "root_load": asdict(root_load),
        "measurement_plan": build_measurement_plan(),
    }


def write_engineering_report(report: dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    forbidden = ("hardware validated", "print-ready", "waterproof qualified")
    if any(phrase in payload.lower() for phrase in forbidden):
        raise ValueError("engineering report contains a forbidden release claim")
    path.write_text(payload + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    from model_contract import load_contract

    active_contract = load_contract()
    output_path = active_contract.output_directory / "V27工程审计.json"
    write_engineering_report(generate_v27_engineering_audit(active_contract), output_path)
    print(output_path)
