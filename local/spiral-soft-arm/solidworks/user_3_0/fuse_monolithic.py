"""Build the one-piece 3.0 geometry and a checked trial STL.

Requires CadQuery 2.8.0 and trimesh 5.1.1. The source STEP is never modified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from cadquery import exporters, importers

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "spi_rob_20261012_131147.step"
FUSED_STEP = HERE / "spi_rob_20261012_131147_整体融合.step"
REVIEW_STL = HERE / "spi_rob_20261012_131147_整体试打.stl"
AUDIT_JSON = HERE / "融合导出审计.json"
STL_LINEAR_TOLERANCE_MM = 0.15
STL_ANGULAR_TOLERANCE_RAD = 0.10


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def mesh_topology(mesh: trimesh.Trimesh) -> dict:
    counts = np.bincount(mesh.edges_unique_inverse)
    return {
        "boundary_edges": int((counts == 1).sum()),
        "nonmanifold_edges": int((counts > 2).sum()),
        "connected_components": len(mesh.split(only_watertight=False)),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "is_volume": bool(mesh.is_volume),
    }


def main() -> None:
    imported = importers.importStep(str(SOURCE)).val()
    source_solids = imported.Solids()
    if len(source_solids) != 29:
        raise RuntimeError(f"Expected 29 source solids, found {len(source_solids)}")

    fused = source_solids[0]
    for solid in source_solids[1:]:
        fused = fused.fuse(solid)
    fused = fused.clean()
    fused_solids = fused.Solids()
    if len(fused_solids) != 1:
        raise RuntimeError(f"Expected one fused solid, found {len(fused_solids)}")
    body = fused_solids[0]
    if not body.isValid() or body.Volume() <= 0:
        raise RuntimeError("Fused solid is invalid or has non-positive volume")

    # Capture exact BRep bounds before STL meshing populates face triangulations.
    box = body.BoundingBox()
    brep_bounds = np.array(
        [[box.xmin, box.ymin, box.zmin], [box.xmax, box.ymax, box.zmax]],
        dtype=float,
    )
    brep_volume = float(body.Volume())
    exporters.export(body, str(FUSED_STEP), exportType="STEP")
    round_trip = importers.importStep(str(FUSED_STEP)).val().Solids()
    if len(round_trip) != 1 or not round_trip[0].isValid():
        raise RuntimeError("Fused STEP round-trip did not preserve one valid solid")
    step_volume_error_mm3 = abs(float(round_trip[0].Volume()) - brep_volume)
    if step_volume_error_mm3 > 0.02:
        raise RuntimeError(f"STEP round-trip volume error too large: {step_volume_error_mm3} mm^3")

    exporters.export(
        body,
        str(REVIEW_STL),
        exportType="STL",
        tolerance=STL_LINEAR_TOLERANCE_MM,
        angularTolerance=STL_ANGULAR_TOLERANCE_RAD,
    )
    raw_mesh = trimesh.load_mesh(REVIEW_STL, process=True)
    raw_mesh_volume = float(raw_mesh.volume)
    raw_topology = mesh_topology(raw_mesh)
    degenerate_faces_removed = int((raw_mesh.area_faces <= 1e-10).sum())
    if degenerate_faces_removed:
        raw_mesh.update_faces(raw_mesh.nondegenerate_faces())
        raw_mesh.remove_unreferenced_vertices()
    raw_mesh.export(str(REVIEW_STL), file_type="stl")

    final_mesh = trimesh.load_mesh(REVIEW_STL, process=True)
    final_topology = mesh_topology(final_mesh)
    if not final_mesh.is_watertight or not final_mesh.is_winding_consistent or not final_mesh.is_volume:
        raise RuntimeError(f"Final STL is not a closed, consistently wound volume: {final_topology}")
    if final_topology["connected_components"] != 1:
        raise RuntimeError(f"Expected one connected mesh component: {final_topology}")

    bounds_error_mm = float(np.max(np.abs(final_mesh.bounds - brep_bounds)))
    if bounds_error_mm > 0.02:
        raise RuntimeError(f"STL bounds differ from BRep by {bounds_error_mm} mm")
    stl_volume_error_percent = abs(float(final_mesh.volume) - brep_volume) / brep_volume * 100.0
    if stl_volume_error_percent > 0.1:
        raise RuntimeError(f"STL tessellation volume error too large: {stl_volume_error_percent:.6f}%")
    cleanup_volume_delta_mm3 = float(final_mesh.volume) - raw_mesh_volume
    if abs(cleanup_volume_delta_mm3) > 1e-5:
        raise RuntimeError(f"STL cleanup changed volume: {cleanup_volume_delta_mm3} mm^3")

    report = {
        "cadquery_version": cq.__version__,
        "trimesh_version": trimesh.__version__,
        "source_file": SOURCE.name,
        "source_sha256": sha256(SOURCE),
        "source_solid_count": len(source_solids),
        "fused_solid_count": len(fused_solids),
        "fused_step_file": FUSED_STEP.name,
        "fused_step_sha256": sha256(FUSED_STEP),
        "step_round_trip_solid_count": len(round_trip),
        "step_round_trip_volume_error_mm3": step_volume_error_mm3,
        "review_stl_file": REVIEW_STL.name,
        "review_stl_sha256": sha256(REVIEW_STL),
        "stl_triangle_count": len(final_mesh.faces),
        "degenerate_stl_faces_removed": degenerate_faces_removed,
        "raw_stl_topology": raw_topology,
        "final_stl_topology": final_topology,
        "cleanup_volume_delta_mm3": cleanup_volume_delta_mm3,
        "bounding_box_mm": {
            "x": round(float(brep_bounds[1, 0] - brep_bounds[0, 0]), 6),
            "y": round(float(brep_bounds[1, 1] - brep_bounds[0, 1]), 6),
            "z": round(float(brep_bounds[1, 2] - brep_bounds[0, 2]), 6),
        },
        "fused_brep_volume_mm3": round(brep_volume, 6),
        "stl_mesh_volume_mm3": round(float(final_mesh.volume), 6),
        "stl_volume_error_percent": round(stl_volume_error_percent, 6),
        "stl_bounds_error_mm": round(bounds_error_mm, 6),
        "stl_linear_tolerance_mm": STL_LINEAR_TOLERANCE_MM,
        "stl_angular_tolerance_rad": STL_ANGULAR_TOLERANCE_RAD,
        "qualification": "single-piece geometry review and mesh topology check only; not print, strength, or underwater qualification",
    }
    AUDIT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()