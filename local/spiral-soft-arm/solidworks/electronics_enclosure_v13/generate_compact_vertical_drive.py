"""B32 v13 compact layout: three vertical M2006 motors in one dry hull.

The motor envelopes use manufacturer dimensions. Bearings, seals and static
gaskets remain packaging placeholders, not rated pressure hardware.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import cadquery as cq
import numpy as np

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
OLD = HERE.parent / "electronics_enclosure_v12"
base = json.loads((OLD / "parameters.json").read_text(encoding="utf-8"))
source = HERE.parent / "electronics_enclosure_v10" / "generate_modular_arm.py"
spec = importlib.util.spec_from_file_location("b32_v10_geometry_v13", source)
v10 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v10)
v10.CFG = base
v5 = v10.v5
v5.CFG = {**v5.CFG, "base_plate_diameter_mm": 250.0}


def cyl(r: float, z0: float, z1: float, x: float = 0, y: float = 0) -> cq.Shape:
    return cq.Solid.makeCylinder(r, z1-z0, cq.Vector(x,y,z0))


def ring(ro: float, ri: float, z0: float, z1: float,
         x: float = 0, y: float = 0) -> cq.Shape:
    return cyl(ro,z0,z1,x,y).cut(cyl(ri,z0-.1,z1+.1,x,y)).clean()


def xy(angle: float, radial: float, tangent: float = 0) -> tuple[float,float]:
    a=math.radians(angle)
    return (radial*math.cos(a)-tangent*math.sin(a),
            radial*math.sin(a)+tangent*math.cos(a))


def make_arm_and_plate() -> tuple[list[cq.Shape],list[cq.Shape],cq.Shape,dict[str,cq.Shape],list[dict]]:
    config=v5.motor_module.load_config()
    config["layout"]["motor_center_radius_mm"]=55.0
    config["layout"]["spool_center_offset_from_motor_center_mm"]=52.0
    config["motor_saddles"]["foot_radial_offset_mm"]=25.1
    config["plate"]["diameter_mm"]=250.0
    config["plate"]["fixture_hole_radius_mm"]=v5.CFG["base_plate_fixture_radius_mm"]
    source_mount=v5.motor_module.build_motor_mount(config)
    config["motor_reference"]["outer_diameter_mm"]=40.0
    config["motor_saddles"]["inner_diameter_mm"]=41.2
    mount=v10.make_horizontal_mount(config,source_mount)
    sections,pins,seams=v10.make_arm_sections(mount.arm)
    # The frozen arm's root channel openings, after its source orientation,
    # must land at the same 60/180/300 degree azimuths as the plate holes.
    rotation=P["arm_root_rotation_deg"]
    sections=[s.rotate((0,0,0),(0,0,1),rotation) for s in sections]
    pins=[s.rotate((0,0,0),(0,0,1),rotation) for s in pins]
    plate,_=v10.make_plate(mount)
    # Supersede the inherited 0.8 mm lead-ins with clear 1.5 x 45 degree
    # chamfers on both faces. Keep the 4.2 mm cylindrical bore unchanged.
    depth=P["tendon_mouth_chamfer_depth_mm"]
    bore=P["tendon_bore_diameter_mm"]/2
    mouth=P["tendon_mouth_diameter_mm"]/2
    for angle in P["tendon_angles_deg"]:
        hx,hy=xy(angle,P["tendon_hole_radius_mm"])
        plate=plate.cut(cq.Solid.makeCone(mouth,bore,depth,
                        cq.Vector(hx,hy,-8),cq.Vector(0,0,1)))
        plate=plate.cut(cq.Solid.makeCone(bore,mouth,depth,
                        cq.Vector(hx,hy,-depth),cq.Vector(0,0,1)))
    plate=plate.clean()
    plate,guard=v10.make_root_guard(plate)
    return sections,pins,plate,guard,seams


def make_hull() -> tuple[cq.Shape,cq.Shape,cq.Shape,cq.Shape]:
    # One plain printed tube, one removable roof and one existing service lid.
    ro=P["dry_hull_outer_radius_mm"]
    ri=P["dry_hull_inner_radius_mm"]
    top=P["dry_hull_top_z_mm"]
    bottom=P["dry_hull_bottom_z_mm"]
    tube=ring(ro,ri,bottom,top)
    tube=tube.fuse(ring(102,ri,top-4,top)).fuse(ring(102,ri,bottom,bottom+5))
    roof=cyl(102,-44,-36)
    # The roof is detachable as a complete motor/shaft cartridge.
    for angle in (60,180,300):
        x,y=xy(angle,P["motor_center_radius_mm"],P["reel_core_radius_mm"])
        roof=roof.cut(cyl(11.1,-45,-35,x,y))
    bolt_xy=[xy(a,98) for a in range(0,360,45)]
    for x,y in bolt_xy:
        roof=roof.cut(cyl(1.65,-45,-35,x,y))
        tube=tube.cut(cyl(1.35,-49,-39,x,y))
    # Gasket seat shown as a simple flat annular recess. Groove dimensions
    # need final O-ring selection before a pressure-boundary print.
    roof=roof.cut(ring(94.5,92.5,-44.01,-43.2))
    lid=cyl(102,bottom-10,bottom).fuse(cyl(ri-.6,bottom,bottom+3))
    lid=lid.cut(cyl(6,bottom-10.1,bottom+3.1))
    for x,y in bolt_xy:
        lid=lid.cut(cyl(1.65,bottom-10.1,bottom+.1,x,y))
        tube=tube.cut(cyl(1.35,bottom-5,bottom+1,x,y))
    # Auxiliary Type-C service opening; a rated sealed connector is pending.
    tube=tube.cut(v5.box(-103,-88,-5,5,-224,-218))
    gland=ring(9,6,bottom-18,bottom-7)
    return tube.clean(),roof.clean(),lid.clean(),gland


def make_drive(angle: float) -> dict[str,cq.Shape]:
    x,y=xy(angle,P["motor_center_radius_mm"],P["reel_core_radius_mm"])
    # 53.3 mm body + 11.5 mm output shaft = 64.8 mm overall envelope.
    # The body split is a packaging proxy; the official envelope is 24.4 x 64.8.
    body=cyl(12.2,-112,-58.7,x,y)
    shaft6=cyl(3,-58.7,-47.2,x,y)
    # Face and 3 x M3 mount pattern on 19 mm PCD, without modeling threads.
    face=ring(11.6,3,-58.7,-56.5,x,y)
    for k in range(3):
        px,py=xy(angle+120*k,9.5)
        face=face.cut(cyl(1.5,-58.8,-56.4,x+px,y+py))
    motor=body.fuse(shaft6).fuse(face).clean()
    adapter=ring(13.5,6.7,-56.5,-53.5,x,y)
    for k in range(3):
        px,py=xy(angle+120*k,9.5)
        adapter=adapter.cut(cyl(1.65,-56.6,-53.4,x+px,y+py))
    for k in range(3):
        px,py=xy(angle+60+120*k,12.3)
        adapter=adapter.fuse(cyl(1.5,-53.5,-44,x+px,y+py))
    adapter=adapter.clean()
    # Independent shaft carries reel side loads; motor shaft is coupled in dry space.
    drive_shaft=cyl(4,-46.5,-10,x,y)
    coupling=ring(6.5,3.05,-53,-44.5,x,y)
    bearing=ring(11,4,-43,-36,x,y)
    oil_seal=ring(8,4,-35.5,-30.5,x,y)
    seal_holder=ring(12,8.05,-36,-27.5,x,y)
    fixed_labyrinth=ring(11,8.4,-27.5,-25.5,x,y)
    rotating_labyrinth=ring(7.8,4,-27,-24.5,x,y)
    # Wet reel under the top plate; 2 mm axial plate clearance.
    reel=ring(10,4.05,-24.5,-23,x,y)
    reel=reel.fuse(ring(6.5,4.05,-23,-12,x,y))
    reel=reel.fuse(ring(10,4.05,-12,-10,x,y)).clean()
    return {"motor":motor,"motor_adapter":adapter,"output_shaft":shaft6,"independent_shaft":drive_shaft,
            "coupling":coupling,"bearing":bearing,"oil_seal":oil_seal,
            "seal_holder":seal_holder,"fixed_labyrinth":fixed_labyrinth,
            "rotating_labyrinth":rotating_labyrinth,"wet_reel":reel}


def make_internal_envelopes() -> dict[str,cq.Shape]:
    # Keep original electronics and 21700 placement. C610 replaces old ESCs.
    electronics={k:s for k,s in v5.make_electronics().items() if not k.startswith("ESC_")}
    electronics.update(v5.make_battery())
    for i,(x0,x1,y0,y1,z0,z1) in enumerate(((44,51,-26,-4,-126,-76),
                                              (44,51,4,26,-126,-76),
                                              (44,51,-11,11,-186,-136)),1):
        electronics[f"C610_{i}_envelope"]=v5.box(x0,x1,y0,y1,z0,z1)
    return electronics


def tendon_exit_proxy(angle: float) -> cq.Shape:
    tx,ty=xy(angle,P["motor_center_radius_mm"])
    hx,hy=xy(angle,30.6)
    start=cq.Vector(tx,ty,-18)
    finish=cq.Vector(hx,hy,-8.8)
    axis=finish-start
    return cq.Solid.makeCylinder(.8,axis.Length,start,axis.normalized())


def tendon_root_channel_proxy(angle: float) -> cq.Shape:
    hx,hy=xy(angle,P["tendon_hole_radius_mm"])
    return cyl(.8,P["tendon_hole_entry_z_mm"],5,hx,hy)


def render(parts: list[tuple[cq.Shape,tuple[float,float,float],float]],
           sections: list[cq.Shape]) -> None:
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    from PIL import Image,ImageDraw,ImageFont
    window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.SetSize(2100,1050)
    def actor(shape,color,opacity):
        vertices,faces=shape.tessellate(1.6,.18)
        points=vtk.vtkPoints();points.SetNumberOfPoints(len(vertices))
        for j,p in enumerate(vertices):points.SetPoint(j,p.x,p.y,p.z)
        polys=vtk.vtkCellArray()
        for face in faces:
            polys.InsertNextCell(3)
            for node in face:polys.InsertCellPoint(int(node))
        data=vtk.vtkPolyData();data.SetPoints(points);data.SetPolys(polys)
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(data)
        item=vtk.vtkActor();item.SetMapper(mapper)
        item.GetProperty().SetColor(*color);item.GetProperty().SetOpacity(opacity)
        return item
    for i in (0,1):
        scene=vtk.vtkRenderer();scene.SetViewport(i*.5,0,(i+1)*.5,1)
        scene.SetBackground(.94,.96,.98);scene.SetUseDepthPeeling(1)
        window.AddRenderer(scene)
        if i==0:
            for j,section in enumerate(sections):
                scene.AddActor(actor(section,((.76,.37,.22),(.87,.48,.24),(.93,.63,.31))[j],1))
        for shape,color,opacity in parts:scene.AddActor(actor(shape,color,opacity))
        camera=scene.GetActiveCamera();camera.ParallelProjectionOn()
        camera.SetFocalPoint(0,0,145 if i==0 else -32)
        camera.SetPosition(650,-540,530 if i==0 else 265)
        camera.SetViewUp(0,0,1);camera.SetParallelScale(490 if i==0 else 170)
        scene.ResetCameraClippingRange()
    window.SetAlphaBitPlanes(1);window.SetMultiSamples(0);window.Render()
    grab=vtk.vtkWindowToImageFilter();grab.SetInput(window)
    grab.SetInputBufferTypeToRGB();grab.Update()
    data=grab.GetOutput();w,h,_=data.GetDimensions()
    pixels=vtk_to_numpy(data.GetPointData().GetScalars()).reshape(h,w,3)[::-1]
    image=Image.fromarray(pixels.copy());draw=ImageDraw.Draw(image)
    font=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",30)
    small=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",20)
    draw.text((35,18),"B32 v13 | 紧凑竖装共用干仓",font=font,fill=(27,47,61))
    draw.text((1075,18),"半透明观察：电机在干仓，线盘在湿侧",font=font,fill=(27,47,61))
    draw.text((35,1007),"尺寸布局候选：顶板可拆，电机与轴封可从上方检修；水密与公差待定型。",font=small,fill=(45,63,75))
    image.save(HERE/"B32_v13_紧凑竖装总装预览.png")


def draw_plan() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle,RegularPolygon,Rectangle
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei"]
    plt.rcParams["axes.unicode_minus"]=False
    fig,ax=plt.subplots(figsize=(9,9),dpi=180)
    ax.add_patch(RegularPolygon((0,0),6,radius=125,orientation=math.radians(30),
                                fill=False,edgecolor="#385063",linewidth=2))
    ax.add_patch(Circle((0,0),96,fill=False,edgecolor="#267687",linewidth=2))
    ax.add_patch(Circle((0,0),90,fill=False,edgecolor="#267687",linestyle="--"))
    ax.add_patch(Rectangle((13,-43.75),18,87.5,fill=False,edgecolor="#527e42",linewidth=1.5))
    ax.add_patch(Rectangle((-39.5,-40),39,80,fill=False,edgecolor="#527e42",linewidth=1.5))
    routes=[]
    for i,angle in enumerate((60,180,300),1):
        cx,cy=xy(angle,P["motor_center_radius_mm"],6.5)
        tx,ty=xy(angle,P["motor_center_radius_mm"])
        hx,hy=xy(angle,30.6)
        ax.add_patch(Circle((cx,cy),12.2,facecolor="#1c4054",alpha=.75))
        ax.add_patch(Circle((cx,cy),10,fill=False,edgecolor="#c89627",linewidth=2))
        ax.plot([tx,hx],[ty,hy],color="#c47a1a",linewidth=2)
        ax.add_patch(Circle((hx,hy),3.3,fill=False,edgecolor="#14844d",linewidth=2))
        ax.plot(hx,hy,"o",color="#c74f36",markersize=5)
        ax.text(cx+5,cy+5,str(i),fontsize=10)
        routes.append(math.dist((tx,ty,-18),(hx,hy,-8.8)))
    ax.set_aspect("equal");ax.set_xlim(-140,140);ax.set_ylim(-140,140)
    ax.grid(alpha=.2);ax.set_xlabel("X / mm");ax.set_ylabel("Y / mm")
    ax.set_title("v13 顶视：卷芯切点、顶盘孔与实测臂根开口径向对齐")
    ax.text(-132,-130,"绿圈：臂根开口  红点：顶盘孔  橙线：卷芯切线",fontsize=8.5,color="#34505c")
    fig.tight_layout();fig.savefig(HERE/"B32_v13_线盘线孔俯视.png");plt.close(fig)


def draw_chamfer_detail() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei"]
    plt.rcParams["axes.unicode_minus"]=False
    z=np.array([-8,-6.5,-1.5,0],dtype=float)
    r=np.array([3.6,2.1,2.1,3.6],dtype=float)
    fig,ax=plt.subplots(figsize=(8,5.5),dpi=180)
    ax.fill_betweenx(z,-8,-r,color="#9aadb9",alpha=.85)
    ax.fill_betweenx(z,r,8,color="#9aadb9",alpha=.85)
    ax.plot(-r,z,color="#27485b",linewidth=2)
    ax.plot(r,z,color="#27485b",linewidth=2)
    ax.axvline(0,color="#d77d20",linestyle="--",linewidth=1)
    ax.annotate("孔径 4.2 mm",xy=(2.1,-4),xytext=(4.6,-4),
                arrowprops={"arrowstyle":"->","color":"#28485b"},fontsize=10)
    ax.annotate("双面 1.5 × 45°",xy=(3.05,-7.45),xytext=(4.0,-10),
                arrowprops={"arrowstyle":"->","color":"#28485b"},fontsize=10)
    ax.text(0,1.15,"上侧孔口 Ø7.2 mm",ha="center",fontsize=11)
    ax.text(0,-10.4,"湿侧入口 Ø7.2 mm",ha="center",fontsize=11)
    ax.set_xlim(-9,9);ax.set_ylim(-11,2.2);ax.set_aspect("equal")
    ax.set_xlabel("线孔中心的径向截面 / mm")
    ax.set_ylabel("高度 z / mm")
    ax.set_title("B32 v13 顶盘拉索孔倒角剖面（三处相同）")
    ax.grid(alpha=.18)
    fig.tight_layout();fig.savefig(HERE/"B32_v13_线孔双面倒角剖面.png");plt.close(fig)


def main() -> None:
    sections,pins,plate,guard,seams=make_arm_and_plate()
    # A real section of the rotated arm, not the layout sketch, decides
    # whether the root openings coincide with the three plate holes.
    root_probe=[]
    off_axis_probe=[]
    plate_probe=[]
    lower_mouth_probe=[]
    upper_mouth_probe=[]
    bore_wall_probe=[]
    tangent_error=[]
    for angle in P["tendon_angles_deg"]:
        hx,hy=xy(angle,P["tendon_hole_radius_mm"])
        root_probe.append(round(sections[0].intersect(cyl(1.5,0,5,hx,hy)).Volume(),6))
        ox,oy=xy(angle+30,P["tendon_hole_radius_mm"])
        off_axis_probe.append(round(sections[0].intersect(cyl(1.5,0,5,ox,oy)).Volume(),6))
        plate_probe.append(round(plate.intersect(cyl(1.0,-8,0,hx,hy)).Volume(),6))
        px,py=xy(angle,P["tendon_hole_radius_mm"]+3.0)
        lower_mouth_probe.append(round(plate.intersect(cyl(.2,-8,-7.95,px,py)).Volume(),6))
        upper_mouth_probe.append(round(plate.intersect(cyl(.2,-.05,0,px,py)).Volume(),6))
        bore_wall_probe.append(round(plate.intersect(cyl(.2,-4,-3.95,px,py)).Volume(),6))
        cx,cy=xy(angle,P["motor_center_radius_mm"],P["reel_core_radius_mm"])
        tx,ty=xy(angle,P["motor_center_radius_mm"])
        travel=np.array([hx-tx,hy-ty,P["tendon_hole_entry_z_mm"]-P["reel_center_z_mm"]])
        radial_normal=np.array([tx-cx,ty-cy,0.0])
        tangent_error.append(round(abs(float(np.dot(travel,radial_normal))) /
                                   (np.linalg.norm(travel)*np.linalg.norm(radial_normal)),9))
    if any(v>.001 for v in root_probe+plate_probe+tangent_error):
        raise RuntimeError("reel tangent, plate hole, and actual arm root channel are not aligned")
    if any(v<.1 for v in off_axis_probe):
        raise RuntimeError("root channel probe cannot distinguish channel from nearby solid")
    if any(v>.001 for v in lower_mouth_probe+upper_mouth_probe) or any(v<.005 for v in bore_wall_probe):
        raise RuntimeError("tendon port chamfer profile does not match the requested mouth and bore")
    tube,roof,lid,gland=make_hull()
    drives=[make_drive(a) for a in (60,180,300)]
    tendons=[tendon_exit_proxy(a) for a in (60,180,300)]
    root_tendons=[tendon_root_channel_proxy(a) for a in (60,180,300)]
    internals=make_internal_envelopes()
    fairing={k:v for k,v in v10.make_fairing().items() if k.startswith("upper_panel_")}
    assembly=cq.Assembly(name="B32_v13_compact_vertical_shared_dry_chamber")
    for i,s in enumerate(sections,1):assembly.add(s,name=f"arm_section_{i}",color=cq.Color(.76,.39,.22))
    for i,s in enumerate(pins,1):assembly.add(s,name=f"cross_pin_{i}_proxy")
    assembly.add(plate,name="hex_plate_250mm",color=cq.Color(.25,.39,.49))
    assembly.add(tube,name="single_dry_hull_tube",color=cq.Color(.20,.38,.47))
    assembly.add(roof,name="removable_roof_with_gasket_seat",color=cq.Color(.33,.52,.59))
    assembly.add(lid,name="bottom_service_lid",color=cq.Color(.50,.56,.62))
    assembly.add(gland,name="shore_cable_gland_proxy")
    for i,d in enumerate(drives,1):
        for key,shape in d.items():
            color=cq.Color(.80,.60,.18) if key=="wet_reel" else cq.Color(.14,.28,.36)
            assembly.add(shape,name=f"drive_{i}_{key}",color=color)
    for i,shape in enumerate(tendons,1):
        assembly.add(shape,name=f"tendon_{i}_straight_exit_proxy",color=cq.Color(.90,.47,.12))
    for i,shape in enumerate(root_tendons,1):
        assembly.add(shape,name=f"tendon_{i}_through_plate_into_arm_root_proxy",color=cq.Color(.90,.47,.12))
    for key,shape in internals.items():assembly.add(shape,name=key)
    for key,shape in {**fairing,**guard}.items():assembly.add(shape,name=key,color=cq.Color(.70,.79,.84))
    assembly.export(str(HERE/"B32_v13_M2006竖装共用干仓总装.step"),exportType="STEP",unit="MM")
    preview=[(plate,(.20,.33,.44),.82),(tube,(.20,.37,.49),.30),
             (roof,(.30,.51,.60),.30),(lid,(.50,.55,.61),.70)]
    for d in drives:
        preview += [(d["motor"],(.08,.20,.29),1),(d["wet_reel"],(.90,.65,.16),1),
                    (d["oil_seal"],(.80,.29,.22),1),(d["motor_adapter"],(.48,.57,.60),.9)]
    preview += [(s,(.90,.47,.12),1) for s in tendons]
    preview += [(s,(.90,.47,.12),1) for s in root_tendons]
    for key,shape in internals.items():
        if key in ("STM32_controller_envelope","voltage_regulator_envelope","UPS_module_envelope") or key.startswith("21700_cell_") or key.startswith("C610_"):
            preview.append((shape,(.29,.54,.34) if not key.startswith("21700") else (.57,.44,.28),.85))
    preview += [(s,(.73,.82,.86),.20) for s in fairing.values()]
    preview += [(s,(.57,.78,.84),.28) for s in guard.values()]
    render(preview,sections)
    draw_plan()
    draw_chamfer_detail()
    def dims(shape):
        b=shape.BoundingBox();return [round(b.xlen,2),round(b.ylen,2),round(b.zlen,2)]
    # Static packaging checks are for layout review, not pressure or print release.
    critical={k:s for k,s in internals.items() if k.endswith("_envelope") or k.startswith("21700_cell_")}
    overlap={f"motor_{i}_{k}":round(d["motor"].intersect(s).Volume(),3)
             for i,d in enumerate(drives,1) for k,s in critical.items()}
    overlap={k:v for k,v in overlap.items() if v>.01}
    clearance_rank=sorted((round(d["motor"].distance(s),3),i,k)
                          for i,d in enumerate(drives,1) for k,s in critical.items())
    min_clearance=clearance_rank[0][0]
    adapter_overlap={f"adapter_{i}_{k}":round(d["motor_adapter"].intersect(s).Volume(),3)
                     for i,d in enumerate(drives,1) for k,s in critical.items()}
    adapter_overlap={k:v for k,v in adapter_overlap.items() if v>.01}
    horizontal=P["motor_center_radius_mm"]-P["tendon_hole_radius_mm"]
    audit={"status":P["status"],"motor_envelope_mm":[24.4,64.8],
           "arm_root_rotation_deg":P["arm_root_rotation_deg"],
           "arm_root_channel_probe_overlap_mm3":root_probe,
           "arm_root_off_axis_30deg_probe_overlap_mm3":off_axis_probe,
           "plate_hole_probe_overlap_mm3":plate_probe,
           "tendon_mouth_chamfer_depth_mm":P["tendon_mouth_chamfer_depth_mm"],
           "tendon_mouth_diameter_mm":P["tendon_mouth_diameter_mm"],
           "lower_mouth_probe_overlap_mm3":lower_mouth_probe,
           "upper_mouth_probe_overlap_mm3":upper_mouth_probe,
           "cylindrical_bore_wall_probe_overlap_mm3":bore_wall_probe,
           "reel_3d_tangent_cosine_error":tangent_error,
           "motor_center_xy_mm":[xy(a,P["motor_center_radius_mm"],6.5) for a in (60,180,300)],
           "reel_to_hole_planar_mm":round(horizontal,2),"reel_tangent_to_hole_3d_mm":round(math.hypot(horizontal,9.2),2),
           "shaft_orientation":"vertical; reel tangent and arm tendon radial aligned in plan",
           "section_heights_mm":[round(s.BoundingBox().zlen,2) for s in sections],
           "print_part_envelopes_mm":{"dry_tube":dims(tube),"roof":dims(roof),
                                       "lid":dims(lid),"hex_plate":dims(plate)},
           "motor_to_electronics_overlap_mm3":overlap,
           "motor_to_electronics_min_clearance_mm":min_clearance,
           "motor_to_electronics_closest_pairs_mm":clearance_rank[:5],
           "adapter_to_electronics_overlap_mm3":adapter_overlap,
           "reel_to_plate_overlap_mm3":[round(d["wet_reel"].intersect(plate).Volume(),3) for d in drives],
           "motor_to_tube_overlap_mm3":[round(d["motor"].intersect(tube).Volume(),3) for d in drives],
           "reel_to_fixed_labyrinth_overlap_mm3":[round(d["wet_reel"].intersect(d["fixed_labyrinth"]).Volume(),3) for d in drives],
           "fixed_to_rotating_labyrinth_overlap_mm3":[round(d["fixed_labyrinth"].intersect(d["rotating_labyrinth"]).Volume(),3) for d in drives],
           "seal_status":"placeholder geometry; purchased seal and pressure rating pending",
           "service":"remove six upper flat panels and hex plate; release three wet reels, then lift roof/motor cartridge",
           "seams":seams}
    (HERE/"装配布置审计.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (HERE/"SHA256SUMS.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.writer(stream);writer.writerow(("file","sha256","bytes"))
        for f in sorted(HERE.iterdir(),key=lambda x:x.name):
            if f.is_file() and f.name!="SHA256SUMS.csv":
                writer.writerow((f.name,hashlib.sha256(f.read_bytes()).hexdigest(),f.stat().st_size))
    print(json.dumps({k:audit[k] for k in ("section_heights_mm","print_part_envelopes_mm",
                                             "motor_to_electronics_overlap_mm3","reel_to_plate_overlap_mm3",
                                             "motor_to_tube_overlap_mm3")},ensure_ascii=False))


if __name__=="__main__":main()
