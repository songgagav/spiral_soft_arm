"""B32 v12: three M2006 motors in one connected dry drive chamber.

The seals, static duct joints, shaft and bearings are dimensional proxies.
Nothing here certifies a printed part as a pressure boundary.
"""
from __future__ import annotations

import importlib.util
import csv
import hashlib
import json
import math
from pathlib import Path

import cadquery as cq
import numpy as np


HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
SOURCE = HERE.parent / "electronics_enclosure_v10" / "generate_modular_arm.py"
spec = importlib.util.spec_from_file_location("b32_v10_geometry", SOURCE)
v10 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v10)
v10.CFG = CFG
v5 = v10.v5
v5.CFG = {**v5.CFG,
          "motor_center_radius_mm": CFG["drive_layout"]["motor_center_radius_mm"],
          "base_plate_diameter_mm": 250.0}
v5.tendon_points = v10.straight_tendon_points


def axial_cylinder(origin: cq.Vector, axis: cq.Vector, t0: float,
                   t1: float, radius: float) -> cq.Shape:
    return cq.Solid.makeCylinder(radius, t1-t0, origin+axis*t0, axis)


def annulus(origin: cq.Vector, axis: cq.Vector, t0: float, t1: float,
            outside: float, inside: float) -> cq.Shape:
    return axial_cylinder(origin, axis, t0, t1, outside).cut(
        axial_cylinder(origin, axis, t0-.1, t1+.1, inside)).clean()


def make_cartridge(reel_center: cq.Vector, axis: cq.Vector) -> dict[str, cq.Shape]:
    """Axial coordinates use reel centre as t=0, positive toward the reel."""
    d = CFG["m2006_sealed_drive"]
    motor_offset = CFG["drive_layout"]["reel_axial_offset_from_motor_center_mm"]
    half_motor = d["motor_total_length_mm"] / 2
    motor_back = -motor_offset-half_motor
    motor_front = -motor_offset+half_motor
    rear_open = motor_back-d["pod_rear_clearance_mm"]
    pod_front = d["pod_front_t_from_reel_center_mm"]
    outer = d["pod_outer_diameter_mm"]/2
    inner = d["pod_inner_diameter_mm"]/2
    shaft_r = d["independent_round_shaft_diameter_mm"]/2
    seal_outer = d["oil_seal_envelope_mm"][1]/2

    # Closed rear service cap plus a thick front bulkhead. The counterbores
    # are represented geometrically; fit and gasket details remain open.
    pod = annulus(reel_center,axis,rear_open,-15,outer,inner)
    bulkhead = annulus(reel_center,axis,-15,pod_front,outer,shaft_r+.15)
    bulkhead = bulkhead.cut(axial_cylinder(reel_center,axis,-15,-12,11))
    bulkhead = bulkhead.cut(axial_cylinder(reel_center,axis,-11,-6,seal_outer))
    bulkhead = bulkhead.cut(axial_cylinder(reel_center,axis,-5.9,-5,
                                            6.5)).clean()
    pod = pod.fuse(bulkhead).clean()
    cap = axial_cylinder(reel_center,axis,rear_open-3,rear_open,outer)
    cap = cap.fuse(axial_cylinder(reel_center,axis,rear_open,
                                  motor_back-.1,inner-.3))
    # The former axial opening at the back is closed. A bottom radial
    # passage meets the dry duct without crossing the motor envelope.
    duct_t = CFG["shared_dry_chamber"]["rear_duct_t_from_reel_mm"]
    duct_at = reel_center + axis*duct_t
    duct_bore = CFG["shared_dry_chamber"]["cable_duct_inner_diameter_mm"]/2
    port_boss=cq.Solid.makeCylinder(8,9,
                  cq.Vector(duct_at.x,duct_at.y,-53),cq.Vector(0,0,1))
    cap=cap.fuse(port_boss)
    cap = cap.cut(cq.Solid.makeCylinder(duct_bore,11,
                  cq.Vector(duct_at.x,duct_at.y,-54),cq.Vector(0,0,1))).clean()
    motor = axial_cylinder(reel_center,axis,motor_back,motor_front,
                           d["motor_outer_diameter_mm"]/2)
    d_output = axial_cylinder(reel_center,axis,motor_front,motor_front+5,3)
    independent_shaft = axial_cylinder(reel_center,axis,-26,4,shaft_r)
    coupling = axial_cylinder(reel_center,axis,-31,-20,6)
    bearing = annulus(reel_center,axis,-19,-12,11,shaft_r)
    oil_seal = annulus(reel_center,axis,-11,-6,seal_outer,shaft_r)
    # Non-contact radial and axial turns; water is allowed into the outer
    # labyrinth. The oil seal is the dynamic pressure barrier.
    fixed_labyrinth = annulus(reel_center,axis,-5,-4.5,11,6.5)
    rotating_labyrinth = annulus(reel_center,axis,-5.8,-4.2,
                                 6.5-d["labyrinth_radial_clearance_mm"],shaft_r)
    return {"pod":pod,"rear_cap":cap,"motor":motor,"d_output":d_output,
            "shaft":independent_shaft,"coupling":coupling,"bearing":bearing,
            "oil_seal":oil_seal,"fixed_labyrinth":fixed_labyrinth,
            "rotating_labyrinth":rotating_labyrinth}


def make_shared_duct(reel_center: cq.Vector,
                     axis: cq.Vector) -> tuple[cq.Shape,cq.Shape]:
    """Connect a motor cap to a lower canister radial port in dry space."""
    c = CFG["shared_dry_chamber"]
    r_outer = c["cable_duct_outer_diameter_mm"]/2
    r_inner = c["cable_duct_inner_diameter_mm"]/2
    at = reel_center + axis*c["rear_duct_t_from_reel_mm"]
    z = c["duct_horizontal_z_mm"]
    vertical = cq.Solid.makeCylinder(r_outer,-45-c["duct_vertical_bottom_z_mm"],
                                     cq.Vector(at.x,at.y,c["duct_vertical_bottom_z_mm"]),
                                     cq.Vector(0,0,1))
    outward = cq.Vector(at.x,at.y,0).normalized()
    # The radial duct overlaps the cylinder's existing radial port boss.
    horizontal = cq.Solid.makeCylinder(r_outer,47,
                         outward*61+cq.Vector(0,0,z),outward)
    outer = vertical.fuse(horizontal).clean()
    vertical_bore = cq.Solid.makeCylinder(r_inner,-44-c["duct_vertical_bottom_z_mm"],
                         cq.Vector(at.x,at.y,c["duct_vertical_bottom_z_mm"]),
                         cq.Vector(0,0,1))
    horizontal_bore = cq.Solid.makeCylinder(r_inner,48,
                         outward*60+cq.Vector(0,0,z),outward)
    duct = outer.cut(vertical_bore.fuse(horizontal_bore)).clean()
    return duct, horizontal_bore


def make_extended_fairing() -> dict[str,cq.Shape]:
    """Extend the ventilated, non-pressure lower panels around the lowered bay."""
    outer=cq.Solid.makeLoft([v10.polygon_wire(r,z) for z,r in
                            [(-8,148),(-80,158),(-281,103)]],ruled=True)
    inner=cq.Solid.makeLoft([v10.polygon_wire(r,z) for z,r in
                            [(-7,143),(-8,143),(-80,153),
                             (-281,98),(-282,98)]],ruled=True)
    shell=outer.cut(inner)
    for angle in (60,180,300):
        shell=shell.cut(v5.rotate(v5.box(65,220,-100,65,-65,-7),angle))
    for angle in (0,120,240):
        shell=shell.cut(v5.rotate(v5.box(65,210,-30,30,-233,-110),angle))
    shell=shell.cut(v5.rotate(v5.box(65,210,-18,18,-273,-251),180))
    for angle in range(0,360,60):
        top_holes=((-9.75,-54),(-9.75,-32)) if angle in (0,120,240) else ((-12,10),(-12,54))
        for z,offset in (*top_holes,(-74,-50),(-74,50),(-88,-40),(-88,40),(-271,-36),(-271,36)):
            shell=shell.cut(v10.radial_hole(angle,offset,z,3.3,80,120))
    panels={}
    for angle in range(0,360,60):
        sector=v10.wedge(angle,-285,5)
        panels[f"upper_panel_{angle:03d}"]=shell.intersect(sector).intersect(
            v5.box(-250,250,-250,250,-80,-8)).clean()
        panels[f"lower_panel_{angle:03d}"]=shell.intersect(sector).intersect(
            v5.box(-250,250,-250,250,-281,-80)).clean()
    return panels


def upper_panel_inner_face(z:float) -> float:
    radius=143+(-8-z)*10/72
    return radius*math.cos(math.pi/6)


def make_extended_plate_tabs(plate:cq.Shape) -> cq.Shape:
    c=CFG["hex_plate"]
    for angle in c["face_angles_deg"]:
        offsets=(-54,-32) if angle in (0,120,240) else (10,54)
        for offset in offsets:
            extension=cq.Solid.makeLoft([
                v10.tab_wire(angle,offset,107,upper_panel_inner_face(z)-.25,
                             c["tab_tangential_width_mm"]/2,z)
                for z in (-8,-18)],ruled=True)
            hole_z=-9.75 if angle in (0,120,240) else c["tab_hole_z_mm"]
            extension=extension.cut(v10.radial_hole(angle,offset,hole_z,
                        c["tab_hole_diameter_mm"],100,40))
            plate=plate.fuse(extension)
    return plate.clean()


def make_extended_splices() -> dict[str,cq.Shape]:
    def inner_face(z:float) -> float:
        radius=143+(-8-z)*10/72 if z>=-80 else 153+(z+80)*55/201
        return radius*math.cos(math.pi/6)
    brackets={}
    for angle in range(0,360,60):
        for sign in (-1,1):
            profile=[(-70,53),(-74,50),(-80,45),(-88,40),(-92,37)]
            wires=[v10.tab_wire(angle,sign*offset,inner_face(z)-5.3,
                                inner_face(z)-.3,4.5,z) for z,offset in profile]
            bracket=cq.Solid.makeLoft(wires,ruled=True)
            for z,offset in ((-74,50),(-88,40)):
                bracket=bracket.cut(v10.radial_hole(angle,sign*offset,z,3.3,110,45))
            brackets[f"panel_splice_{angle:03d}_{'p' if sign>0 else 'm'}"]=bracket.clean()
    return brackets


def make_canister_supports() -> list[cq.Shape]:
    """Three removable dry-canister supports, using blind fastener bores."""
    supports=[]
    for angle in (0,120,240):
        radial,_=v10.frame(angle)
        x,y=47*radial.x,47*radial.y
        column=v5.cyl(5,-53,-8,x,y)
        column=column.fuse(v5.cyl(2,-57,-53,x,y))
        column=column.cut(v5.cyl(2.15,-20,-7.9,x,y)).clean()
        supports.append(column)
    return supports


def render_shared_preview(sections:list[cq.Shape], plate:cq.Shape,
                          shell:cq.Shape,lid:cq.Shape,cartridges:list[dict[str,cq.Shape]],
                          ducts:list[cq.Shape],reels:list[cq.Shape],
                          fairing:dict[str,cq.Shape],guard:dict[str,cq.Shape],
                          supports:list[cq.Shape]) -> None:
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    from PIL import Image,ImageDraw,ImageFont
    window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.SetSize(2100,1050)
    def actor(shape:cq.Shape,color:tuple[float,float,float],opacity:float=1):
        vertices,faces=shape.tessellate(1.3,.17)
        points=vtk.vtkPoints();points.SetNumberOfPoints(len(vertices))
        for j,p in enumerate(vertices): points.SetPoint(j,p.x,p.y,p.z)
        polys=vtk.vtkCellArray()
        for face in faces:
            polys.InsertNextCell(3)
            for node in face: polys.InsertCellPoint(int(node))
        data=vtk.vtkPolyData();data.SetPoints(points);data.SetPolys(polys)
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(data)
        item=vtk.vtkActor();item.SetMapper(mapper)
        item.GetProperty().SetColor(*color);item.GetProperty().SetOpacity(opacity)
        return item
    for index in (0,1):
        scene=vtk.vtkRenderer();scene.SetViewport(index*.5,0,(index+1)*.5,1)
        scene.SetBackground(.94,.96,.98);scene.SetUseDepthPeeling(1)
        window.AddRenderer(scene)
        if index==0:
            for i,part in enumerate(sections):
                scene.AddActor(actor(part,[(.76,.37,.22),(.88,.50,.23),(.93,.65,.30)][i]))
        scene.AddActor(actor(plate,(.20,.33,.44),.85 if index else 1))
        scene.AddActor(actor(shell,(.20,.37,.49),.38 if index else .65))
        scene.AddActor(actor(lid,(.50,.55,.61),.75))
        for c in cartridges:
            scene.AddActor(actor(c["pod"],(.19,.57,.64),.37))
            scene.AddActor(actor(c["rear_cap"],(.48,.62,.68),.6))
            scene.AddActor(actor(c["motor"],(.09,.21,.31),1))
            scene.AddActor(actor(c["oil_seal"],(.80,.30,.23),1))
        for duct in ducts: scene.AddActor(actor(duct,(.19,.59,.65),.8))
        for support in supports: scene.AddActor(actor(support,(.54,.58,.62),.9))
        for reel in reels: scene.AddActor(actor(reel,(.90,.65,.16),1))
        for panel in fairing.values(): scene.AddActor(actor(panel,(.74,.82,.86),.22))
        for panel in guard.values(): scene.AddActor(actor(panel,(.57,.78,.84),.28))
        camera=scene.GetActiveCamera();camera.ParallelProjectionOn()
        camera.SetFocalPoint(0,0,155 if index==0 else -35)
        camera.SetPosition(620,-510,480 if index==0 else 260)
        camera.SetViewUp(0,0,1);camera.SetParallelScale(490 if index==0 else 185)
        scene.ResetCameraClippingRange()
    window.SetAlphaBitPlanes(1);window.SetMultiSamples(0);window.Render()
    grab=vtk.vtkWindowToImageFilter();grab.SetInput(window)
    grab.SetInputBufferTypeToRGB();grab.Update()
    data=grab.GetOutput();w,h,_=data.GetDimensions()
    pixels=vtk_to_numpy(data.GetPointData().GetScalars()).reshape(h,w,3)[::-1]
    image=Image.fromarray(pixels.copy());draw=ImageDraw.Draw(image)
    font=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",30)
    note=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",20)
    draw.text((38,22),"B32 v12 | 共用隔水电机仓总装",font=font,fill=(27,47,61))
    draw.text((1080,22),"局部：深蓝电机在半透明干仓内，金色线盘在湿侧",font=font,fill=(27,47,61))
    draw.text((38,1005),"水密边界候选：三处轴封 + 三条干侧布线管 + 电子仓；外罩开口仅供观察/排水。",font=note,fill=(45,63,75))
    image.save(HERE/"B32_M2006共用隔水仓_总装预览.png")


def draw_views(mount: object, cartridges: list[dict[str,cq.Shape]],
               motor_config: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon, Rectangle
    from matplotlib import font_manager
    font_manager.fontManager.addfont("C:/Windows/Fonts/msyh.ttc")
    plt.rcParams["font.family"] = font_manager.FontProperties(
        fname="C:/Windows/Fonts/msyh.ttc").get_name()
    plt.rcParams["axes.unicode_minus"] = False
    fig,(top,detail) = plt.subplots(1,2,figsize=(16,8),dpi=160)
    hex_xy=[(125*math.cos(math.radians(-30+60*i)),
             125*math.sin(math.radians(-30+60*i))) for i in range(6)]
    top.add_patch(Polygon(hex_xy,closed=True,facecolor="#dce6ed",
                          edgecolor="#3c5b70",linewidth=2,alpha=.55))
    top.add_patch(Circle((0,0),68,facecolor="#95aab5",alpha=.18))
    for i,angle in enumerate(mount.motor_angles,1):
        center=np.array(mount.motor_centers[i-1][:2])
        axis=np.array(mount.motor_axes[i-1][:2])
        normal=np.array([-axis[1],axis[0]])
        reel=np.array(mount.reel_centers[i-1][:2])
        def rectangle(c: np.ndarray,half:float,radius:float,color:str,alpha:float):
            corners=[c-axis*half-normal*radius,c+axis*half-normal*radius,
                     c+axis*half+normal*radius,c-axis*half+normal*radius]
            top.add_patch(Polygon(corners,closed=True,facecolor=color,
                                  edgecolor="#334c5d",alpha=alpha))
        pod_mid=reel+axis*(-52.7)
        rectangle(pod_mid,47.7,20,"#418391",.45)
        rectangle(center,32.4,12.2,"#326475",.8)
        rectangle(reel,4,10,"#d7a333",.95)
        duct_at=reel+axis*CFG["shared_dry_chamber"]["rear_duct_t_from_reel_mm"]
        top.add_patch(Circle(duct_at,6,facecolor="#40a7a9",edgecolor="#295b64"))
        cable=v10.straight_tendon_points(angle,motor_config["plate"]["tendon_hole_radius_mm"])
        top.plot(cable[:,0],cable[:,1],color="#bf4445",linewidth=2)
        top.scatter([cable[-1,0]],[cable[-1,1]],color="#bf4445",s=25)
        top.text(*center,f"M2006-{i}",ha="center",va="center",color="white",fontsize=8)
    top.set(xlim=(-155,155),ylim=(-155,155),xlabel="X / mm",ylabel="Y / mm",
            title="俯视：3 电机在干仓内；红线切线出线至孔")
    top.set_aspect("equal");top.grid(alpha=.2)

    # A scaled axial layout of one cartridge, not a manufactured section.
    bands=[(-103.4,-100.4,20,"后端盖","#728691"),
           (-100.4,-15,20,"干侧电机筒","#82a7b0"),
           (-96.4,-31.6,12.2,"M2006","#286172"),
           (-31,-20,6,"联轴器","#7c6b5d"),
           (-19,-12,11,"独立轴承","#9e774d"),
           (-15,-5,20,"前端密封座","#7a9ba4"),
           (-11,-6,8,"骨架油封占位","#bf6b52"),
           (-5.8,-4.2,11,"迷宫间隙","#54748a"),
           (-4,4,10,"湿侧线盘","#d7a333")]
    legend_handles=[]
    for t0,t1,rad,label,color in bands:
        patch=Rectangle((t0,-rad),t1-t0,rad*2,
                        facecolor=color,edgecolor="#263e49",alpha=.75,label=label)
        detail.add_patch(patch)
        legend_handles.append(patch)
    detail.add_patch(Rectangle((-26,-4),30,8,facecolor="#55595d",alpha=.8))
    detail.axvline(-5,color="#296b91",linestyle="--")
    detail.text(-4.5,-26,"湿侧 →",color="#296b91",fontsize=10)
    detail.set(xlim=(-110,17),ylim=(-34,30),xlabel="沿输出轴方向 / mm",
               ylabel="径向 / mm",title="单轴剖面布局：独立轴承担线盘载荷")
    detail.set_aspect("equal");detail.grid(alpha=.2)
    detail.legend(handles=legend_handles,loc="upper center",bbox_to_anchor=(.5,-.22),
                  ncol=3,fontsize=8,frameon=False)
    fig.suptitle("B32 v12｜共用隔水仓：电机干侧、线盘湿侧",fontsize=17)
    fig.tight_layout(rect=(0,.1,1,.96))
    fig.savefig(HERE/"B32_M2006共用隔水仓_俯视与轴封.png")
    plt.close(fig)


def main() -> None:
    motor_cfg=v5.motor_module.load_config()
    drive=CFG["drive_layout"]
    motor_cfg["layout"]["motor_center_radius_mm"]=55.0
    motor_cfg["layout"]["spool_center_offset_from_motor_center_mm"]=52.0
    motor_cfg["motor_saddles"]["foot_radial_offset_mm"]=25.1
    motor_cfg["plate"]["diameter_mm"]=250.0
    motor_cfg["plate"]["fixture_hole_radius_mm"]=v5.CFG["base_plate_fixture_radius_mm"]
    source_mount=v5.motor_module.build_motor_mount(motor_cfg)
    motor_cfg["motor_reference"]["outer_diameter_mm"]=40.0
    motor_cfg["motor_saddles"]["inner_diameter_mm"]=41.2
    mount=v10.make_horizontal_mount(motor_cfg,source_mount)
    sections,pins,seams=v10.make_arm_sections(mount.arm)
    rotation=drive["source_arm_rotation_deg"]
    sections=[part.rotate((0,0,0),(0,0,1),rotation) for part in sections]
    pins=[part.rotate((0,0,0),(0,0,1),rotation) for part in pins]
    plate,_=v10.make_plate(mount)
    plate=make_extended_plate_tabs(plate)
    plate,guard=v10.make_root_guard(plate)
    dz=CFG["shared_dry_chamber"]["electronics_canister_shift_z_mm"]
    shift=cq.Vector(0,0,dz)
    shell,lid,gland=(shape.translate(shift) for shape in
                      v10.make_shell_with_clear_tendon_radials())
    # Close the legacy side observation slot. Observation belongs on the
    # ventilated outer fairing, not on the shared dry pressure boundary.
    shell=shell.fuse(v5.box(-70,-60,-5,5,-222.8+dz,-219.2+dz)).clean()
    fairing=make_extended_fairing()
    splices=make_extended_splices()
    supports=make_canister_supports()
    cartridges=[]
    ducts=[]
    duct_port_bores=[]
    for center,axis in zip(mount.reel_centers,mount.motor_axes):
        origin,direction=cq.Vector(*center),cq.Vector(*axis)
        cartridges.append(make_cartridge(origin,direction))
        duct,bore=make_shared_duct(origin,direction)
        ducts.append(duct)
        duct_port_bores.append(bore)
    unintended={
        f"axis_{i}_{label}":round(a.intersect(b).Volume(),5)
        for i,c in enumerate(cartridges,1)
        for label,a,b in (("pod_bearing",c["pod"],c["bearing"]),
                          ("pod_oil_seal",c["pod"],c["oil_seal"]),
                          ("pod_rotating_labyrinth",c["pod"],c["rotating_labyrinth"]),
                          ("motor_independent_shaft",c["motor"],c["shaft"]),
                          ("fixed_rotating_labyrinth",c["fixed_labyrinth"],c["rotating_labyrinth"]))}
    if any(volume>.01 for volume in unintended.values()):
        raise RuntimeError(f"A cartridge has an unintended solid overlap: {unintended}")
    mount.motors=[c["pod"] for c in cartridges]
    electronics={key:shape for key,shape in v5.make_electronics().items()
                 if not key.startswith("ESC_")}
    electronics={key:shape.translate(shift) for key,shape in electronics.items()}
    for i,(y0,y1,z0,z1) in enumerate(((-33,-11,-104,-54),
                                      (11,33,-104,-54),(-11,11,-165,-115)),1):
        electronics[f"C610_{i}_dry_envelope"]=v5.box(40,47.3,y0,y1,z0+dz,z1+dz)

    assembly=cq.Assembly(name="B32_v12_shared_dry_chamber_wet_reels")
    for i,part in enumerate(sections,1):
        assembly.add(part,name=f"arm_section_{i:02d}",color=cq.Color(.76,.39,.22))
    for i,pin in enumerate(pins,1): assembly.add(pin,name=f"cross_pin_{i}_proxy")
    assembly.add(plate,name="250mm_hex_plate",color=cq.Color(.24,.38,.48))
    for i,part in enumerate(mount.root_rims,1): assembly.add(part,name=f"root_retainer_{i}")
    for i,part in enumerate(mount.saddles,1): assembly.add(part,name=f"pod_saddle_{i}")
    for i,part in enumerate(mount.spools,1):
        assembly.add(part,name=f"wet_reel_{i}",color=cq.Color(.86,.64,.20))
    for i,cartridge in enumerate(cartridges,1):
        for key,part in cartridge.items():
            color=cq.Color(.24,.47,.55) if key=="pod" else cq.Color(.65,.67,.66)
            assembly.add(part,name=f"axis_{i}_{key}_proxy",color=color)
    for i,duct in enumerate(ducts,1):
        assembly.add(duct,name=f"shared_dry_cable_duct_{i}",color=cq.Color(.32,.63,.69))
    for i,support in enumerate(supports,1):
        assembly.add(support,name=f"canister_blind_bolt_support_{i}",color=cq.Color(.55,.59,.62))
    assembly.add(shell,name="lower_shared_dry_canister")
    assembly.add(lid,name="center_canister_lid")
    assembly.add(gland,name="shore_tether_gland_proxy")
    for key,part in {**fairing,**guard,**splices}.items():
        assembly.add(part,name=key,color=cq.Color(.73,.80,.84))
    v5.add_parts(assembly,{key:part.translate(shift) for key,part in
                           v5.make_battery().items()})
    v5.add_parts(assembly,electronics)
    out=HERE/"B32_M2006共用隔水仓_湿侧线盘总装.step"
    assembly.export(str(out),exportType="STEP",unit="MM")
    draw_views(mount,cartridges,motor_cfg)
    render_shared_preview(sections,plate,shell,lid,cartridges,ducts,
                          mount.spools,fairing,guard,supports)
    def bbox_dims(shape:cq.Shape) -> list[float]:
        bb=shape.BoundingBox()
        return [round(bb.xlen,3),round(bb.ylen,3),round(bb.zlen,3)]
    fairing_all=cq.Compound.makeCompound(list(fairing.values()))
    audit={"candidate":CFG["model"],"status":CFG["status"],
           "motor_centers_mm":mount.motor_centers,
           "reel_centers_mm":mount.reel_centers,
           "axes":mount.motor_axes,
           "section_heights_mm":[round(p.BoundingBox().zlen,3) for p in sections],
           "pod_to_center_canister_clearance_mm":[round(c["pod"].distance(shell),3) for c in cartridges],
           "reel_to_plate_hole_path_mm":[round(float(np.linalg.norm(v10.straight_tendon_points(a,motor_cfg["plate"]["tendon_hole_radius_mm"])[-1]-v10.straight_tendon_points(a,motor_cfg["plate"]["tendon_hole_radius_mm"])[0])),3) for a in mount.motor_angles],
           "duct_to_canister_intersection_mm3":[round(duct.intersect(shell).Volume(),3) for duct in ducts],
           "duct_to_cap_intersection_mm3":[round(duct.intersect(c["rear_cap"]).Volume(),3) for duct,c in zip(ducts,cartridges)],
           "duct_to_motor_overlap_mm3":[round(duct.intersect(c["motor"]).Volume(),3) for duct,c in zip(ducts,cartridges)],
           "wet_reel_to_dry_canister_overlap_mm3":[round(reel.intersect(shell).Volume(),3) for reel in mount.spools],
           "support_to_motor_pod_overlap_mm3":[round(sum(s.intersect(c["pod"]).Volume() for c in cartridges),3) for s in supports],
           "canister_body_height_mm":round(shell.BoundingBox().zlen,3),
           "fairing_panel_max_height_mm":round(max(p.BoundingBox().zlen for p in fairing.values()),3),
           "fairing_panel_max_xy_mm":round(max(max(p.BoundingBox().xlen,p.BoundingBox().ylen) for p in fairing.values()),3),
           "fabrication_envelopes_xyz_mm":{"hex_plate_with_tabs":bbox_dims(plate),
                "dry_canister_shell":bbox_dims(shell),"one_upper_panel":bbox_dims(fairing["upper_panel_000"]),
                "one_lower_panel":bbox_dims(fairing["lower_panel_000"]),
                "full_fairing_assembled":bbox_dims(fairing_all)},
           "pod_to_plate_overlap_mm3":[round(c["pod"].intersect(plate).Volume(),3) for c in cartridges],
           "pod_to_reel_clearance_mm":[round(c["pod"].distance(reel),3) for c,reel in zip(cartridges,mount.spools)],
           "cartridge_unintended_overlaps_mm3":unintended,
           "pod_to_fairing_overlap_mm3":[round(sum(c["pod"].intersect(p).Volume() for p in fairing.values()),3)
                                          for c in cartridges],
           "spool_to_hole_collinearity_mm":[round(float(max(np.linalg.norm(np.cross(pt-line[0],line[-1]-line[0]))/
                                                   np.linalg.norm(line[-1]-line[0]) for pt in line)),7)
                                            for angle in mount.motor_angles
                                            for line in [v10.straight_tendon_points(angle,motor_cfg["plate"]["tendon_hole_radius_mm"])]],
           "seal_status":"8x16x5 mm package is schematic; pressure rating, shaft finish, gland design and tests pending",
           "canister_motor_cable_glands":"three dry ducts to common canister; static joint seals and detachable couplings not detailed",
           "seams":seams}
    (HERE/"装配布置审计.json").write_text(
        json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    with (HERE/"SHA256SUMS.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.writer(stream)
        writer.writerow(("file","sha256","bytes"))
        for file in sorted(HERE.iterdir(),key=lambda p:p.name):
            if not file.is_file() or file.name=="SHA256SUMS.csv": continue
            writer.writerow((file.name,hashlib.sha256(file.read_bytes()).hexdigest(),file.stat().st_size))
    print(json.dumps({key:audit[key] for key in ("section_heights_mm","pod_to_center_canister_clearance_mm",
                          "pod_to_plate_overlap_mm3","pod_to_fairing_overlap_mm3",
                          "reel_to_plate_hole_path_mm","duct_to_canister_intersection_mm3",
                          "spool_to_hole_collinearity_mm")},ensure_ascii=False))


if __name__=="__main__": main()
