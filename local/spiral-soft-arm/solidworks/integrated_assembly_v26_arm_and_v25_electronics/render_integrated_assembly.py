"""Render whole-assembly and root-interface reviews for B32 V26."""
from __future__ import annotations

from pathlib import Path

import cadquery as cq


HERE = Path(__file__).resolve().parent


def colour(name: str) -> tuple[float, float, float, float]:
    if name == "B32_v10_arm_sections_and_dovetails":
        return (.83, .86, .89, .78)
    if "upper_panel" in name or "fairing" in name:
        return (.48, .58, .63, .25)
    if "top_plate" in name or "root_guard" in name:
        return (.70, .76, .80, .46)
    if "canister" in name or "bottom_lid" in name:
        return (.23, .67, .72, .20)
    if "M3508" in name or "motor" in name:
        return (.28, .34, .39, .96)
    if "wet_reel" in name:
        return (.86, .52, .16, .96)
    if "shaft" in name or "bearing" in name or "seal" in name:
        return (.62, .68, .72, .96)
    if "21700" in name:
        return (.12, .65, .42, .96)
    if "C620" in name:
        return (.10, .22, .31, .96)
    if "controller" in name or "buck_5v" in name:
        return (.14, .45, .78, .96)
    if "UPS" in name:
        return (.78, .23, .29, .96)
    if "regulator" in name:
        return (.86, .57, .18, .96)
    if "PD1002" in name:
        return (.44, .33, .72, .96)
    if "ideal_diode" in name:
        return (.13, .63, .66, .96)
    if "BMS" in name:
        return (.69, .55, .13, .96)
    if "M28" in name or "M12" in name:
        return (.10, .61, .58, .94)
    if "cable" in name or "tendon" in name:
        return (.82, .17, .14, 1.0)
    if "shelf" in name or "backing" in name or "rail" in name:
        return (.40, .50, .56, .58)
    return (.53, .59, .64, .88)


def _actor(shape: cq.Shape, rgba: tuple[float, float, float, float]):
    import vtk
    vertices, faces = shape.tessellate(1.2, .22)
    points = vtk.vtkPoints()
    for vertex in vertices:
        points.InsertNextPoint(vertex.x, vertex.y, vertex.z)
    cells = vtk.vtkCellArray()
    for face in faces:
        cells.InsertNextCell(3)
        for node in face:
            cells.InsertCellPoint(int(node))
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(poly)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*rgba[:3])
    actor.GetProperty().SetOpacity(rgba[3])
    actor.GetProperty().SetSpecular(.15)
    actor.GetProperty().SetSpecularPower(18)
    return actor


def _save_scene(components: dict[str, cq.Shape], names: list[str], path: Path,
                position: tuple[float, float, float],
                focal: tuple[float, float, float], scale: float,
                title: str) -> None:
    import vtk
    from PIL import Image, ImageDraw, ImageFont

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(1500, 1100)
    window.SetMultiSamples(0)
    scene = vtk.vtkRenderer()
    scene.SetBackground(.94, .965, .98)
    scene.SetUseDepthPeeling(1)
    window.AddRenderer(scene)
    for name in names:
        scene.AddActor(_actor(components[name], colour(name)))
    camera = scene.GetActiveCamera()
    camera.ParallelProjectionOn()
    camera.SetPosition(*position)
    camera.SetFocalPoint(*focal)
    camera.SetViewUp(0, 0, 1)
    camera.SetParallelScale(scale)
    scene.ResetCameraClippingRange()
    window.Render()
    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.SetInputBufferTypeToRGB()
    capture.ReadFrontBufferOff()
    capture.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(path))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()
    window.Finalize()

    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    font = (ImageFont.truetype(str(font_path), 28)
            if font_path.is_file() else ImageFont.load_default())
    draw.rounded_rectangle((24, 22, 1080, 84), radius=13, fill="white")
    draw.text((42, 35), title, font=font, fill=(28, 46, 60))
    image.save(path)


def render_v26_images(components: dict[str, cq.Shape]) -> dict[str, str]:
    whole = HERE / "B32_v26_整机半透明预览.png"
    root = HERE / "B32_v26_根部与电子仓接口近景.png"
    all_names = list(components)
    _save_scene(
        components, all_names, whole,
        (1050, -1350, 410), (0, 0, 100), 550,
        "B32 V26｜原机械臂、三路驱动与V25电子仓整机",
    )
    root_names = [
        name for name in components
        if name == "B32_v10_arm_sections_and_dovetails"
        or name == "v23_integral_top_plate_and_drive_chamber"
        or name.startswith("v10_root_guard_")
        or name.startswith("drive_")
        or name.startswith("v24_")
        or name.startswith("v25_")
    ]
    _save_scene(
        components, root_names, root,
        (520, -720, 130), (0, 0, -70), 235,
        "B32 V26根部接口｜机械臂、拉索驱动与电子仓",
    )
    return {"whole_preview": whole.name, "root_preview": root.name}
