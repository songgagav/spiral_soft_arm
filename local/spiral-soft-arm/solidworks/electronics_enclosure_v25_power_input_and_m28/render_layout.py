"""Render the v25 electronics chamber, M28 detail and layered power layout."""
from __future__ import annotations

import json
from pathlib import Path

import cadquery as cq


HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))


def colour(name: str) -> tuple[float, float, float, float]:
    if "21700" in name: return (.12, .65, .42, 1.0)
    if "C620" in name: return (.10, .22, .31, 1.0)
    if "controller" in name: return (.14, .45, .75, 1.0)
    if "UPS" in name: return (.77, .22, .28, 1.0)
    if "regulator" in name: return (.85, .56, .17, 1.0)
    if "PD1002" in name: return (.44, .33, .72, 1.0)
    if "ideal_diode" in name: return (.13, .63, .66, 1.0)
    if "BMS" in name: return (.69, .55, .13, 1.0)
    if "buck_5v" in name: return (.16, .55, .83, 1.0)
    if "M28_service_clearance" in name: return (.22, .73, .71, .14)
    if "M28" in name: return (.12, .61, .59, .92)
    if "M12" in name: return (.14, .63, .61, .95)
    if "canister" in name or "bottom_lid" in name: return (.47, .69, .75, .22)
    if "shelf" in name or "backing" in name or "rail" in name: return (.40, .50, .56, .50)
    return (.53, .59, .64, .88)


def _actor(shape: cq.Shape, rgba: tuple[float, float, float, float]):
    import vtk
    vertices, faces = shape.tessellate(1.0, .18)
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
    actor.GetProperty().SetSpecular(.18)
    actor.GetProperty().SetSpecularPower(20)
    return actor


def _save_vtk(components: dict[str, cq.Shape], names: list[str], path: Path,
              position: tuple[float, float, float], focal: tuple[float, float, float],
              scale: float, title: str) -> None:
    import vtk
    from PIL import Image, ImageDraw, ImageFont
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(1500, 1000)
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
    font = ImageFont.truetype(str(font_path), 27) if font_path.is_file() else ImageFont.load_default()
    draw.rounded_rectangle((24, 22, 980, 82), radius=13, fill="white")
    draw.text((42, 34), title, font=font, fill=(28, 46, 60))
    image.save(path)


def render_layered_layout(path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), facecolor="white")
    for ax, title in zip(axes, ("上层｜电芯与三只 C620", "中层｜控制与电压转换", "底层｜双输入与电池保护")):
        ax.add_patch(Circle((0, 0), 68, facecolor="#e4eef3", edgecolor="#456b7b", lw=2))
        ax.add_patch(Circle((0, 0), 63, fill=False, edgecolor="#89aebb", ls="--", lw=1.4))
        ax.set(xlim=(-78, 78), ylim=(-78, 78), aspect="equal")
        ax.set_title(title, fontsize=14, weight="bold", pad=10)
        ax.axis("off")
    for x, y in ((-32.5,-12.5),(-7.5,-12.5),(-32.5,12.5),(-7.5,12.5)):
        axes[0].add_patch(Circle((x, y), 10.775, color="#24aa76", ec="#175c47"))
    axes[0].text(-20, 0, "21700×4", ha="center", va="center", color="white", weight="bold")
    for x, y, angle in ((36, 45, -30), (48, 0, 90), (36, -45, 30)):
        block = Rectangle((x-5.75, y-12.9), 11.5, 25.8,
                          facecolor="#244a60", edgecolor="#19333f", lw=1.1,
                          angle=angle, rotation_point="center")
        axes[0].add_patch(block)
        axes[0].text(x, y, "C620", ha="center", va="center", color="white",
                     fontsize=7, weight="bold")
    for x, label, w, h, color in ((-43,"24 V稳压",39,80,"#dc9633"),(8,"UPS",15,50,"#ca4c58"),(28,"STM32",10,52,"#2f78b9"),(44,"24→5 V",5,24,"#2c91ce")):
        axes[1].add_patch(Rectangle((x,-h/2),w,h,facecolor=color,edgecolor="#203640",lw=1.2))
        axes[1].text(x+w/2,0,label,ha="center",va="center",color="white",fontsize=8,weight="bold",rotation=90 if w<12 else 0)
    blocks = [((-24,-55),48,34,"PD1002","#7658b5"),((18,-39),30,16,"理想二极管","#29a4aa"),((-30,20),60,30,"4S40A BMS*","#ae9132")]
    for xy,w,h,label,color in blocks:
        axes[2].add_patch(Rectangle(xy,w,h,facecolor=color,edgecolor="#203640",lw=1.2))
        axes[2].text(xy[0]+w/2,xy[1]+h/2,label,ha="center",va="center",color="white",fontsize=8,weight="bold")
    axes[2].add_patch(Circle((0,0),14,facecolor="#556e79",edgecolor="#203640"))
    axes[2].text(0,0,"M28\n岸电",ha="center",va="center",color="white",fontsize=8)
    axes[2].text(0,-69,"M12 Type-C",ha="center",va="top",fontsize=8,color="#28505e")
    arrow = dict(arrowstyle="-|>", mutation_scale=13, lw=1.5, color="#374f5b")
    axes[2].add_patch(FancyArrowPatch((0,-62),(-5,-54),**arrow))
    axes[2].add_patch(FancyArrowPatch((0,-14),(-4,-1),**arrow))
    fig.text(.5,.035,"已确认：岸电与 Type-C 可同时接入，理想二极管防回灌，外部供电可带载并给4S电池充电；*BMS外形仍为占位。",ha="center",fontsize=10,color="#3b5562")
    fig.tight_layout(rect=(0,.08,1,.92),w_pad=1.4)
    fig.savefig(path,dpi=170,facecolor="white")
    plt.close(fig)


def render_v25_images(components: dict[str, cq.Shape]) -> dict[str, str]:
    preview = HERE / "B32_v25_电子仓半透明装配预览.png"
    detail = HERE / "B32_v25_M28沉台与承力环细节.png"
    layout = HERE / "B32_v25_电子仓分层与电源路径图.png"
    electronics = [name for name in components if name.startswith("v24_") or name.startswith("v25_")]
    _save_vtk(components, electronics, preview, (330,-470,185), (0,0,-135), 150,
              "B32 v25 选定硬件电子仓｜M28与5 V降压模块")
    m28_names = [name for name in components if "M28" in name or name == "v25_bottom_lid_with_M28_recess"]
    _save_vtk(components, m28_names, detail, (150,-230,-285), (0,0,-250), 58,
              "M28底盖接口｜5 mm沉台、承力环与插头空间")
    render_layered_layout(layout)
    return {"preview": preview.name, "m28_detail": detail.name, "layout": layout.name}
