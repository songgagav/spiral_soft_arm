import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PARAMETERS_PATH = HERE / "parameters.json"


@dataclass(frozen=True)
class SourceRecord:
    role: str
    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class DovetailContract:
    bottom_width_mm: float
    top_width_mm: float
    profile_height_mm: float
    rotation_deg: float
    engagement_mm: float
    clearance_per_side_mm: float
    lock_pin_diameter_mm: float
    lock_pin_hole_diameter_mm: float
    lock_pin_azimuth_deg: float


@dataclass(frozen=True)
class ArmContract:
    nominal_length_mm: float
    unit_count: int
    segment_count: int
    tendon_count: int
    tip_diameter_mm: float
    root_diameter_mm: float
    tendon_material: str
    tendon_diameter_mm: float
    max_segment_height_mm: float
    split_unit_indices: tuple[int, ...]
    split_unit_offsets_mm: tuple[float, ...]
    dovetail: DovetailContract


@dataclass(frozen=True)
class RootInterfaceContract:
    top_plate_circumdiameter_mm: float
    flange_max_diameter_mm: float
    register_diameter_mm: float
    register_height_mm: float
    dowel_count: int
    dowel_diameter_mm: float
    dowel_angles_deg: tuple[float, ...]
    fastener_count: int
    fastener_thread: str
    fastener_clearance_diameter_mm: float
    fastener_pcd_mm: float
    minimum_tool_clearance_mm: float


@dataclass(frozen=True)
class DriveContract:
    motor_model: str
    motor_count: int
    c610_part_of_removable_module: bool
    fixed_transmission_members: tuple[str, ...]
    tendon_alignment_lateral_tolerance_mm: float
    tendon_alignment_angular_tolerance_deg: float
    tendon_tangent_radius_mm: float
    spool_core_radius_mm: float
    spool_effective_radius_mm: float
    spool_tangent_z_mm: float


@dataclass(frozen=True)
class EnvironmentContract:
    media: tuple[str, ...]
    max_depth_m: float
    run_time_min: float
    payload_mass_kg: float
    motion_profile: str
    high_speed_whipping_required: bool


@dataclass(frozen=True)
class V27Contract:
    schema_version: str
    candidate_id: str
    units: str
    release_status: str
    output_directory: Path
    arm: ArmContract
    root_interface: RootInterfaceContract
    drive: DriveContract
    integration: dict[str, Any]
    environment: EnvironmentContract
    source_specs: dict[str, dict[str, str]]


def _tupled(data: dict[str, Any], key: str) -> tuple[Any, ...]:
    return tuple(data[key])


def load_contract(path: Path | None = None) -> V27Contract:
    parameter_path = (path or PARAMETERS_PATH).resolve()
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    arm_raw = dict(raw["arm"])
    arm_raw["split_unit_indices"] = _tupled(arm_raw, "split_unit_indices")
    arm_raw["split_unit_offsets_mm"] = _tupled(arm_raw, "split_unit_offsets_mm")
    arm_raw["dovetail"] = DovetailContract(**arm_raw["dovetail"])
    arm = ArmContract(**arm_raw)
    root_raw = dict(raw["root_interface"])
    root_raw["dowel_angles_deg"] = _tupled(root_raw, "dowel_angles_deg")
    root = RootInterfaceContract(**root_raw)
    drive_raw = dict(raw["drive"])
    drive_raw["fixed_transmission_members"] = _tupled(
        drive_raw, "fixed_transmission_members"
    )
    drive = DriveContract(**drive_raw)
    environment_raw = dict(raw["environment"])
    environment_raw["media"] = _tupled(environment_raw, "media")
    environment = EnvironmentContract(**environment_raw)
    contract = V27Contract(
        schema_version=raw["schema_version"],
        candidate_id=raw["candidate_id"],
        units=raw["units"],
        release_status=raw["release_status"],
        output_directory=parameter_path.parent,
        arm=arm,
        root_interface=root,
        drive=drive,
        integration=dict(raw["integration"]),
        environment=environment,
        source_specs=raw["sources"],
    )
    validate_contract(contract)
    return contract


def validate_contract(contract: V27Contract) -> None:
    forbidden_status_words = ("validated", "qualified", "print-ready", "waterproof")
    status = contract.release_status.lower()
    if any(word in status for word in forbidden_status_words):
        raise ValueError("V27 release status must remain a candidate statement")
    if "integrated_assembly_v26" in str(contract.output_directory).lower():
        raise ValueError("V27 may not write into the V26 output directory")
    if contract.arm.max_segment_height_mm > 300.0:
        raise ValueError("segment print-height limit may not exceed 300 mm")
    if contract.drive.motor_count != 3:
        raise ValueError("V27 requires exactly three M2006 motors")
    required_fixed = {"seal_housings", "bearings", "shafts", "wet_spools"}
    if set(contract.drive.fixed_transmission_members) != required_fixed:
        raise ValueError("fixed transmission members are incomplete")
    if contract.arm.unit_count != 42 or contract.arm.segment_count != 4:
        raise ValueError("paper geometry requires 42 units and four print segments")
    if len(contract.arm.split_unit_indices) != contract.arm.segment_count - 1:
        raise ValueError("one internal profile cut is required per adjacent segment pair")
    if len(contract.arm.split_unit_offsets_mm) != len(contract.arm.split_unit_indices):
        raise ValueError("each internal profile cut requires one axial offset")
    if tuple(sorted(set(contract.arm.split_unit_indices))) != contract.arm.split_unit_indices:
        raise ValueError("dovetail split-unit indices must be strictly increasing")
    if any(index < 2 or index > contract.arm.unit_count for index in contract.arm.split_unit_indices):
        raise ValueError("dovetail split-unit indices must identify existing arm units")
    if any(abs(offset) > 10.0 for offset in contract.arm.split_unit_offsets_mm):
        raise ValueError("split-unit offsets must stay within the selected profile unit")
    joint = contract.arm.dovetail
    if (
        joint.bottom_width_mm <= 0.0
        or joint.top_width_mm <= joint.bottom_width_mm
        or joint.profile_height_mm <= 0.0
        or joint.engagement_mm <= 0.0
        or joint.clearance_per_side_mm < 0.0
        or joint.lock_pin_diameter_mm <= 0.0
        or joint.lock_pin_hole_diameter_mm < joint.lock_pin_diameter_mm
    ):
        raise ValueError("dovetail and locking-pin dimensions are not physically ordered")
    if contract.root_interface.top_plate_circumdiameter_mm != 250.0:
        raise ValueError("the 250 mm top-plate envelope is frozen")
    integration = contract.integration
    if not (
        0.0 < integration["drive_register_inner_radius_mm"]
        < integration["drive_plate_clearance_radius_mm"]
        < integration["drive_register_outer_radius_mm"]
        < integration["fixed_drive_register_seat_inner_radius_mm"]
        < integration["fixed_drive_register_seat_outer_radius_mm"]
    ):
        raise ValueError("drive-register radii do not preserve fit and service clearance")
    if (
        len(integration["drive_register_z_mm"]) != 2
        or len(integration["fixed_drive_register_seat_z_mm"]) != 2
        or integration["drive_register_z_mm"][0]
        >= integration["drive_register_z_mm"][1]
        or integration["fixed_drive_register_seat_z_mm"][0]
        >= integration["fixed_drive_register_seat_z_mm"][1]
    ):
        raise ValueError("drive-register axial ranges must be increasing pairs")
    if integration["canister_motor_port_relief_diameter_mm"] <= 14.0:
        raise ValueError("canister motor-port relief must clear the 14 mm source bosses")
    if len(integration["cell_shelf_relief_slots_x_mm"]) != 2:
        raise ValueError("cell shelf requires reliefs at both crossing support backings")
    if len(integration["c610_board_angles_deg"]) != 3:
        raise ValueError("three C610 board angles are required")
    if not (
        0.0 < integration["root_tendon_entry_radius_mm"]
        < 0.5 * contract.arm.root_diameter_mm
        < contract.drive.tendon_tangent_radius_mm
    ):
        raise ValueError("root tendon route radii are not ordered")
    if (
        integration["root_tendon_entry_z_mm"] != contract.drive.spool_tangent_z_mm
        or integration["root_tendon_transition_join_z_mm"] <= 0.0
    ):
        raise ValueError("spool, root entrance and transition Z coordinates disagree")
    if (
        integration["drive_plate_dowel_radius_mm"]
        - integration["drive_plate_dowel_hole_diameter_mm"] / 2.0
        <= integration["fixed_drive_register_seat_outer_radius_mm"]
    ):
        raise ValueError("drive-plate dowels must clear the central register seat")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_source_manifest(contract: V27Contract) -> dict[str, SourceRecord]:
    manifest: dict[str, SourceRecord] = {}
    for key, spec in contract.source_specs.items():
        role = spec["role"]
        if key != role:
            raise ValueError(f"source key/role mismatch: {key} != {role}")
        path = (contract.output_directory / spec["path"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        manifest[key] = SourceRecord(
            role=role,
            path=path,
            sha256=_sha256(path),
            size_bytes=path.stat().st_size,
        )
    return manifest
