"""Place the selected electronics in the frozen B32 v23 mechanical assembly.

Hardware without a manufacturer drawing is deliberately a labelled envelope.
The output is an assembly review candidate, not a watertight or print release.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import cadquery as cq

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
H = P["hardware"]
SOURCE = (HERE / P["source_assembly"]).resolve()
spec = importlib.util.spec_from_file_location("b32_v23_frozen_source", SOURCE)
v23 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v23
spec.loader.exec_module(v23)


def box(bounds: list[float] | tuple[float, ...]) -> cq.Shape:
    x0, x1, y0, y1, z0, z1 = bounds
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0, y0, z0))


def cyl(radius: float, z0: float, z1: float, x: float = 0, y: float = 0) -> cq.Shape:
    return cq.Solid.makeCylinder(radius, z1-z0, cq.Vector(x, y, z0))


def y_cyl(radius: float, y0: float, y1: float, x: float, z: float) -> cq.Shape:
    return cq.Solid.makeCylinder(radius, y1-y0, cq.Vector(x, y0, z), cq.Vector(0, 1, 0))


def rotated(shape: cq.Shape, angle: float) -> cq.Shape:
    return shape.rotate((0, 0, 0), (0, 0, 1), angle)


def selected_parts() -> tuple[dict[str, cq.Shape], list[str]]:
    parts: dict[str, cq.Shape] = {}
    bodies: list[str] = []
    cell = H["cells"]
    holder = None
    for i, (x, y) in enumerate(cell["centres_xy"], 1):
        body = cyl(cell["diameter"]/2, *cell["z"], x, y)
        name = f"v24_21700_cell_{i}"
        parts[name] = body
        bodies.append(name)
        sleeve = cyl(12.9, -106, -32, x, y).cut(cyl(11.4, -107, -31, x, y))
        holder = sleeve if holder is None else holder.fuse(sleeve)
    parts["v24_4S_cell_carrier"] = holder.clean()
    parts["v24_cell_carrier_shelf"] = box((-52, 7, -29, 29, -110, -107))

    for key in ("controller", "ups", "regulator", "pd1002", "ideal_diode", "bms"):
        name = f"v24_{key}_envelope"
        parts[name] = box(H[key]["aabb"])
        bodies.append(name)

    # Three genuine C620 case envelopes.  Radial thickness faces the canister
    # wall; the 49.4 mm dimension is vertical next to the existing motor ports.
    c = H["c620"]
    r = c["centres_radius"]
    z0, z1 = c["z"]
    for angle in c["angles_deg"]:
        name = f"v24_C620_{int(angle):03d}_envelope"
        parts[name] = rotated(box((r-5.75, r+5.75, -12.9, 12.9, z0, z1)), angle)
        bodies.append(name)
        parts[f"v24_C620_{int(angle):03d}_backing"] = rotated(
            box((r+6.75, r+8.75, -13.5, 13.5, z0-2, z1+2)), angle
        )

    # Removable backing plates leave a 1 mm fitting gap and expose all board
    # faces from the bottom lid.  Actual PCB hole coordinates are not guessed.
    parts["v24_controller_backing"] = box((25, 27, -27, 27, -180, -93))
    parts["v24_UPS_backing"] = box((5, 7, -26, 26, -200, -96))
    parts["v24_regulator_backing"] = box((-46, -44, -40, 40, -212, -108))
    for key in ("controller", "ups", "regulator"):
        b = H[key]["aabb"]
        parts[f"v24_{key}_lower_rail"] = box((b[0]-2, b[1]+2, b[2], b[3], b[4]-3, b[4]-1))

    # Service-deck modules lie below the three tall boards.  Open space around
    # the central M28 rear connector is preserved for its crimp/solder tails.
    parts["v24_PD1002_shelf"] = box((-25, 25, -55, -19, -227, -225))
    parts["v24_ideal_diode_shelf"] = box((17, 49, -39, -21, -219, -217))
    parts["v24_BMS_shelf"] = box((-32, 32, 18, 52, -227, -225))

    m28 = H["m28_power"]
    parts["v24_M28_inside_stem_proxy"] = cyl(
        m28["inside_stem_diameter_proxy"]/2, *m28["inside_z"]
    )
    parts["v24_M28_outside_flange_proxy"] = cyl(
        m28["outside_flange_diameter_proxy"]/2, -245, -240
    )
    m12 = H["m12_type_c"]
    x, y, z = m12["centre_xyz"]
    parts["v24_M12_USB_C_inside_stem_proxy"] = y_cyl(7.2, y, y+18, x, z)
    parts["v24_M12_USB_C_outside_flange_proxy"] = y_cyl(11, y-10, y-5, x, z)
    return parts, bodies


def modified_canister(source: dict[str, cq.Shape]) -> dict[str, cq.Shape]:
    shell = source["v10_central_electronics_canister"]
    lid = source["v10_central_electronics_canister_lid"]
    # Close the old rectangular Type-C cutout with the same annular shell
    # section, then create the selected radial M12 interface beside the PD bay.
    patch = cyl(68, -225, -216).cut(cyl(63, -226, -215)).intersect(
        box((-69, -60, -7, 7, -225, -216))
    )
    shell = shell.fuse(patch).clean()
    shell = shell.fuse(y_cyl(11, -73, -66, 0, -202))
    shell = shell.cut(y_cyl(H["m12_type_c"]["panel_bore_proxy"]/2,
                             -75, -48, 0, -202)).clean()
    lid = lid.cut(cyl(H["m28_power"]["panel_bore_proxy"]/2,
                        -241, -226)).clean()
    return {"v24_central_electronics_canister": shell,
            "v24_central_bottom_lid_M28_bore": lid}


def assemble() -> tuple[dict[str, cq.Shape], list[str]]:
    original = v23.build_v23_assembly_components()
    # Preserve the B32 arm, v23 top/drive chamber, wet reels and root shroud.
    # Replace every obsolete v10 electronics, harness and canister proxy.
    kept = {
        name: shape for name, shape in original.items()
        if not name.startswith("v10_")
        or name.startswith("v10_root_guard_")
        or name.startswith("v10_upper_panel_")
    }
    # v23's battery lead was tied to the previous board positions.
    kept.pop("v23_battery_to_BMS_two_core_harness", None)
    hardware, bodies = selected_parts()
    shell = modified_canister(original)
    components = {**kept, **shell, **hardware}
    for name, shape in components.items():
        if not shape.isValid() or not shape.Solids():
            raise ValueError(f"Invalid geometry: {name}")
    return components, bodies


def hardware_audit(components: dict[str, cq.Shape], bodies: list[str]) -> dict:
    inner = cyl(63, -227, -26)
    boundary = {}
    interior_parts = [name for name in components if name.startswith("v24_")
                      and name not in {"v24_central_electronics_canister",
                                       "v24_central_bottom_lid_M28_bore"}
                      and "M28" not in name and "M12" not in name]
    for name in interior_parts:
        outside = components[name].cut(inner).Volume()
        boundary[name] = round(outside, 5)
        if outside > 0.02:
            raise ValueError(f"Hardware outside nominal dry-cavity volume: {name}, {outside}")
    shell = components["v24_central_electronics_canister"]
    shell_hits = {}
    for name in interior_parts:
        volume = shell.intersect(components[name]).Volume()
        if volume > 0.02:
            shell_hits[name] = round(volume, 4)
    if shell_hits:
        raise ValueError(f"New internal parts intersect the pressure wall: {shell_hits}")
    # The only frozen v23 items entering the Ø126 cavity are the radial wire
    # sleeves; the canister wall itself was checked separately above.
    preserved_mechanics = [name for name in components
                           if "pass_through" in name and not name.startswith("v24_")]
    mechanical_hits = []
    for first in interior_parts:
        aa = components[first].BoundingBox()
        for second in preserved_mechanics:
            bb = components[second].BoundingBox()
            if (aa.xmax <= bb.xmin or bb.xmax <= aa.xmin
                    or aa.ymax <= bb.ymin or bb.ymax <= aa.ymin
                    or aa.zmax <= bb.zmin or bb.zmax <= aa.zmin):
                continue
            volume = components[first].intersect(components[second]).Volume()
            if volume > 0.02:
                mechanical_hits.append({"parts": [first, second],
                                        "volume_mm3": round(volume, 4)})
    if mechanical_hits:
        raise ValueError(f"New internal parts intersect frozen mechanics: {mechanical_hits}")
    overlaps = []
    for i, first in enumerate(bodies):
        for second in bodies[i+1:]:
            a, b = components[first], components[second]
            aa, bb = a.BoundingBox(), b.BoundingBox()
            if (aa.xmax <= bb.xmin or bb.xmax <= aa.xmin
                    or aa.ymax <= bb.ymin or bb.ymax <= aa.ymin
                    or aa.zmax <= bb.zmin or bb.zmax <= aa.zmin):
                continue
            volume = a.intersect(b).Volume()
            if volume > 0.02:
                overlaps.append({"parts": [first, second], "volume_mm3": round(volume, 4)})
    if overlaps:
        raise ValueError(f"Selected hardware envelopes overlap: {overlaps}")
    return {"hardware_envelopes": len(bodies), "interior_parts_checked": len(interior_parts),
            "outside_nominal_cavity_mm3": boundary,
            "internal_to_shell_volume_overlaps": shell_hits,
            "internal_to_frozen_mechanics_volume_overlaps": mechanical_hits,
            "hardware_to_hardware_volume_overlaps": overlaps,
            "unconfirmed_dimensions": ["BMS case", "PD1002 connectors and screw holes",
                                       "M28 cutout and rear depth", "M12 Type-C cutout and rear depth",
                                       "all PCB hole patterns and wire bend radii"]}


def colour(name: str) -> cq.Color:
    if name.startswith("v24_21700"): return cq.Color(.17, .68, .45)
    if "cell_carrier" in name: return cq.Color(.42, .52, .58, .55)
    if "C620" in name: return cq.Color(.12, .23, .32)
    if "controller" in name: return cq.Color(.17, .47, .76)
    if "UPS" in name: return cq.Color(.77, .22, .27)
    if "regulator" in name: return cq.Color(.83, .54, .16)
    if "BMS" in name: return cq.Color(.72, .58, .12)
    if "PD1002" in name: return cq.Color(.47, .36, .77)
    if "ideal_diode" in name: return cq.Color(.19, .65, .68)
    if "M28" in name or "M12" in name: return cq.Color(.17, .66, .63)
    if "canister" in name or "bottom_lid" in name: return cq.Color(.48, .70, .76, .24)
    return v23._assembly_color(name)


def export() -> dict:
    components, bodies = assemble()
    audit = hardware_audit(components, bodies)
    electronic_names = [n for n in components if n.startswith("v24_")]
    subassembly = cq.Assembly(name="B32_v24_selected_electronics_canister")
    for name in electronic_names:
        subassembly.add(components[name], name=name, color=colour(name))
    substep = HERE / "B32_v24_选定硬件电子仓.step"
    subassembly.export(str(substep), exportType="STEP", unit="MM")
    full = cq.Assembly(name="B32_v24_selected_hardware_full_assembly")
    for name, shape in components.items():
        full.add(shape, name=name, color=colour(name))
    fullstep = HERE / "B32_v24_三路M3508与选定电子仓总装.step"
    full.export(str(fullstep), exportType="STEP", unit="MM")
    readback = cq.importers.importStep(str(substep)).val()
    if not readback.isValid():
        raise ValueError("v24 electronics STEP did not reimport as a valid BREP")
    full_readback = cq.importers.importStep(str(fullstep)).val()
    if not full_readback.isValid():
        raise ValueError("v24 full assembly STEP did not reimport as a valid BREP")
    audit.update({"component_count": len(components), "electronics_step": substep.name,
                  "full_assembly_step": fullstep.name, "electronics_step_valid": True,
                  "full_assembly_step_valid": True,
                  "full_assembly_step_solids": len(full_readback.Solids()),
                  "electronics_step_solids": len(readback.Solids()),
                  "battery_format": H["cells"]["type"]})
    (HERE / "装配空间审查.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    render_preview(components, bodies)
    return audit


def render_preview(components: dict[str, cq.Shape], bodies: list[str]) -> None:
    import vtk
    from PIL import Image, ImageDraw, ImageFont

    selected = {n: s for n, s in components.items() if n.startswith("v24_")}
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(1650, 980)
    window.SetMultiSamples(0)
    for i in range(2):
        scene = vtk.vtkRenderer()
        scene.SetViewport(i*.5, 0, (i+1)*.5, 1)
        scene.SetBackground(.945, .967, .98)
        window.AddRenderer(scene)
        for name, shape in selected.items():
            vertices, faces = shape.tessellate(1.2, .2)
            if not faces: continue
            points = vtk.vtkPoints()
            for v in vertices: points.InsertNextPoint(v.x, v.y, v.z)
            triangles = vtk.vtkCellArray()
            for face in faces:
                triangles.InsertNextCell(3)
                for node in face: triangles.InsertCellPoint(int(node))
            poly = vtk.vtkPolyData()
            poly.SetPoints(points)
            poly.SetPolys(triangles)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(poly)
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(*colour(name).toTuple()[:3])
            actor.GetProperty().SetOpacity(.20 if "canister" in name else
                                           .45 if "lid" in name else
                                           .85 if "shelf" in name or "backing" in name else 1)
            scene.AddActor(actor)
        camera = scene.GetActiveCamera()
        camera.ParallelProjectionOn()
        camera.SetFocalPoint(0, 0, -130)
        if i == 0:
            camera.SetPosition(330, -470, 190)
            camera.SetViewUp(0, 0, 1)
            camera.SetParallelScale(145)
        else:
            camera.SetPosition(0, -550, -125)
            camera.SetViewUp(0, 0, 1)
            camera.SetParallelScale(145)
        scene.ResetCameraClippingRange()
    window.Render()
    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.SetInputBufferTypeToRGB()
    capture.ReadFrontBufferOff()
    capture.Update()
    preview = HERE / "B32_v24_电子仓半透明装配预览.png"
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(preview))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()
    window.Finalize()
    im = Image.open(preview).convert("RGB")
    draw = ImageDraw.Draw(im)
    fontpath = Path("C:/Windows/Fonts/msyh.ttc")
    font = ImageFont.truetype(str(fontpath), 25) if fontpath.is_file() else ImageFont.load_default()
    draw.rounded_rectangle((20, 20, 1140, 82), radius=12, fill="white")
    draw.text((35, 32), "B32 v24 选定硬件电子仓｜透视与侧视", font=font, fill=(29, 47, 63))
    im.save(preview)


if __name__ == "__main__":
    print(json.dumps(export(), ensure_ascii=False, indent=2))
