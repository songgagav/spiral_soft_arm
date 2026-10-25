"""B32 v15: vertical M2006 motors and horizontal tangential reel shafts.

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
spec = importlib.util.spec_from_file_location("b32_v10_geometry_v15", source)
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


def tangent_cylinder(radius: float, t0: float, t1: float,
                     radial: float, z: float, angle: float) -> cq.Shape:
    x,y=xy(angle,radial,t0)
    axis=cq.Vector(*xy(angle,0,1),0)
    return cq.Solid.makeCylinder(radius,t1-t0,cq.Vector(x,y,z),axis)


def tangent_ring(ro: float, ri: float, t0: float, t1: float,
                 radial: float, z: float, angle: float) -> cq.Shape:
    return tangent_cylinder(ro,t0,t1,radial,z,angle).cut(
        tangent_cylinder(ri,t0-.1,t1+.1,radial,z,angle)).clean()


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
    for angle in P["plate_standoff_angles_deg"]:
        sx,sy=xy(angle,P["plate_standoff_radius_mm"])
        plate=plate.cut(cyl(1.7,-8.1,.1,sx,sy))
    return sections,pins,plate,guard,seams


def make_plate_standoffs() -> list[cq.Shape]:
    return [ring(5,1.7,-36,-8,*xy(a,P["plate_standoff_radius_mm"]))
            for a in P["plate_standoff_angles_deg"]]


def make_hull() -> tuple[cq.Shape,cq.Shape,cq.Shape,cq.Shape]:
    # One plain printed tube, one removable roof and one existing service lid.
    ro=P["dry_hull_outer_radius_mm"]
    ri=P["dry_hull_inner_radius_mm"]
    top=P["dry_hull_top_z_mm"]
    bottom=P["dry_hull_bottom_z_mm"]
    tube=ring(ro,ri,bottom,top)
    flange=ro+6
    tube=tube.fuse(ring(flange,ri,top-4,top)).fuse(ring(flange,ri,bottom,bottom+5))
    roof=cyl(flange,top,-36)
    # The roof is detachable as a complete motor/shaft cartridge.
    for angle in (60,180,300):
        x,y=xy(angle,P["motor_center_radius_mm"],P["motor_tangential_offset_mm"])
        roof=roof.cut(cyl(11.1,-45,-35,x,y))
        roof=roof.cut(ring(14.8,13.7,-36.8,-35.9,x,y))
        for k in range(3):
            bx,by=xy(angle+120*k,16.7)
            roof=roof.cut(cyl(1.35,-40,-35.9,x+bx,y+by))
            mx,my=xy(angle+60+120*k,15.8)
            roof=roof.cut(cyl(1.35,-44.1,-40,x+mx,y+my))
            rx,ry=xy(angle+30+120*k,12.5)
            roof=roof.cut(cyl(1.35,-44.1,-40,x+rx,y+ry))
    for angle in P["plate_standoff_angles_deg"]:
        sx,sy=xy(angle,P["plate_standoff_radius_mm"])
        roof=roof.cut(cyl(1.35,-41,-35.9,sx,sy))
    for sx,sy in ((35,-31),(35,40.25)):
        roof=roof.cut(cyl(1.35,-44.1,-40,sx,sy))
    bolt_xy=[xy(a,ro+2) for a in range(0,360,45)]
    for x,y in bolt_xy:
        roof=roof.cut(cyl(1.65,-45,-35,x,y))
        tube=tube.cut(cyl(1.35,-49,-39,x,y))
    # Gasket seat shown as a simple flat annular recess. Groove dimensions
    # need final O-ring selection before a pressure-boundary print.
    roof=roof.cut(ring(ri+3.5,ri+1.5,top-.01,top+.8))
    lid=cyl(flange,bottom-10,bottom).fuse(cyl(ri-.6,bottom,bottom+3))
    gx,gy=P["shore_tether_gland_xy_mm"]
    lid=lid.cut(cyl(6,bottom-10.1,bottom+3.1,gx,gy))
    lid=lid.cut(ring(ri+3.5,ri+1.5,bottom-.8,bottom+.01))
    for x,y in bolt_xy:
        lid=lid.cut(cyl(1.65,bottom-10.1,bottom+.1,x,y))
        tube=tube.cut(cyl(1.35,bottom-5,bottom+1,x,y))
    # Auxiliary Type-C service opening; a rated sealed connector is pending.
    tube=tube.cut(v5.box(-108,-93,-5,5,bottom+11,bottom+17))
    gland=ring(9,6,bottom-18,bottom-7,gx,gy)
    return tube.clean(),roof.clean(),lid.clean(),gland


def make_drive(angle: float) -> dict[str,cq.Shape]:
    r=P["motor_center_radius_mm"]
    t=P["motor_tangential_offset_mm"]
    z=P["reel_axis_z_mm"]
    x,y=xy(angle,r,t)
    body=cyl(12.2,-120,-66.7,x,y)
    motor_output=cyl(3,-66.7,-55.2,x,y)
    face=ring(11.6,3,-66.7,-64.5,x,y)
    for k in range(3):
        px,py=xy(angle+120*k,9.5)
        face=face.cut(cyl(1.5,-66.8,-64.4,x+px,y+py))
    motor=body.fuse(motor_output).fuse(face).clean()
    adapter=ring(19,6.7,-64.5,-61.5,x,y)
    for k in range(3):
        px,py=xy(angle+120*k,9.5)
        adapter=adapter.cut(cyl(1.65,-64.6,-61.4,x+px,y+py))
        px,py=xy(angle+60+120*k,15.8)
        adapter=adapter.fuse(cyl(3,-61.5,-44,x+px,y+py))
        adapter=adapter.cut(cyl(1.65,-64.6,-43.9,x+px,y+py))
    adapter=adapter.clean()
    # The motor stays vertical. A dry 90-degree gear space turns motion into
    # a horizontal tangential shaft. The purchased gear teeth remain TBD.
    vertical_shaft=cyl(4,-54.5,-26,x,y)
    coupling=cyl(6.5,-61,-47.5,x,y)
    coupling=coupling.cut(cyl(3.05,-61.1,-54.85,x,y))
    coupling=coupling.cut(cyl(4.05,-54.85,-47.4,x,y)).clean()
    vertical_bearing=ring(11,4.05,-43.5,-36.5,x,y)
    bearing_retainer=ring(15,4.1,-45.5,-44,x,y)
    for k in range(3):
        px,py=xy(angle+30+120*k,12.5)
        bearing_retainer=bearing_retainer.cut(cyl(1.65,-45.6,-43.9,x+px,y+py))
        px,py=xy(angle+60+120*k,15.8)
        bearing_retainer=bearing_retainer.cut(cyl(3.15,-45.6,-43.9,x+px,y+py))
    # A simple sealed pod is attached to the shared dry roof. Its sole
    # rotating water boundary is the horizontal reel shaft outlet.
    pod=ring(P["right_angle_pod_outer_radius_mm"],13.5,-36,-12,x,y)
    pod=pod.cut(tangent_cylinder(10.05,3.5,t+1,r,z,angle))
    pod_cap=cyl(P["right_angle_pod_outer_radius_mm"],-12,-10,x,y)
    pod_cap=pod_cap.cut(ring(14.8,13.7,-12.01,-11.4,x,y))
    for k in range(3):
        px,py=xy(angle+120*k,16.7)
        hole=cyl(1.65,-36.1,-9.9,x+px,y+py)
        pod=pod.cut(hole)
        pod_cap=pod_cap.cut(hole)
    pod=pod.clean();pod_cap=pod_cap.clean()
    base_gasket=ring(14.7,13.8,-36.7,-35.95,x,y)
    cap_gasket=ring(14.7,13.8,-12.05,-11.45,x,y)
    reel_shaft=tangent_cylinder(4,-4,18,r,z,angle)
    reel_bearing=tangent_ring(9,4.05,11,16,r,z,angle)
    seal_holder=tangent_ring(10,8.05,5.3,10.3,r,z,angle)
    oil_seal=tangent_ring(8,4,5.3,10.3,r,z,angle)
    fixed_labyrinth=tangent_ring(11,8.4,4.3,5.3,r,z,angle)
    rotating_labyrinth=tangent_ring(7.8,4.05,4,4.8,r,z,angle)
    reel=tangent_ring(P["reel_flange_radius_mm"],4.05,-4,-2,r,z,angle)
    reel=reel.fuse(tangent_ring(6.5,4.05,-2,2,r,z,angle))
    reel=reel.fuse(tangent_ring(P["reel_flange_radius_mm"],4.05,2,4,r,z,angle)).clean()
    gear_space=cyl(10,-32,-14,x,y)
    return {"motor":motor,"motor_adapter":adapter,"output_shaft":motor_output,
            "vertical_drive_shaft":vertical_shaft,"coupling":coupling,
            "bearing":vertical_bearing,"bearing_retainer":bearing_retainer,
            "right_angle_pod":pod,"right_angle_pod_cap":pod_cap,
            "pod_base_gasket":base_gasket,"pod_cap_gasket":cap_gasket,
            "independent_shaft":reel_shaft,
            "reel_bearing":reel_bearing,"oil_seal":oil_seal,
            "seal_holder":seal_holder,"fixed_labyrinth":fixed_labyrinth,
            "rotating_labyrinth":rotating_labyrinth,"wet_reel":reel,
            "right_angle_gear_space_proxy":gear_space}


def make_internal_envelopes() -> dict[str,cq.Shape]:
    # Move the entire legacy stack down as a unit. This clears the roof and
    # preserves its established battery/regulator/UPS axial order.
    shift=cq.Vector(0,0,P["electronics_shift_z_mm"])
    raw={k:s for k,s in v5.make_electronics().items()
         if not k.startswith("ESC_") and not k.startswith("service_deck_shell_tab_")
         and not k.endswith("harness_corridor")}
    raw.update(v5.make_battery())
    electronics={k:s.translate(shift) for k,s in raw.items()}
    for key in list(electronics):
        if key.startswith("battery_") or key.startswith("21700_cell_"):
            electronics[key]=electronics[key].translate(cq.Vector(-5,0,0))
        elif key.startswith("STM32_"):
            electronics[key]=electronics[key].translate(cq.Vector(-10,0,0))
        elif key.startswith("UPS_"):
            electronics[key]=electronics[key].translate(cq.Vector(-15,0,0))
    # The inherited battery posts run through the regulator envelope. Move
    # them 11 mm outward on Y, while keeping the battery sleeves unchanged.
    electronics["battery_support_A"]=electronics["battery_support_A"].translate(cq.Vector(0,-11,0))
    electronics["battery_support_B"]=electronics["battery_support_B"].translate(cq.Vector(0,11,0))
    # The Type-C receptacle reaches the new wall opening instead of hanging
    # 31 mm inside the dry space.
    for key in ("USB_C_PD_input_envelope","USB_C_receptacle_proxy","PD_input_mount_shelf"):
        electronics[key]=electronics[key].translate(cq.Vector(-31,0,0))
    electronics["service_deck"]=ring(P["service_deck_radius_mm"],8,-247,-244)
    gx,gy=P["shore_tether_gland_xy_mm"]
    electronics["service_deck"]=electronics["service_deck"].cut(cyl(6,-247.1,-243.9,gx,gy))
    # Connect the four-cell sleeve assembly to its two long support posts.
    tray=v5.box(-51,1,-26,26,-129,-125)
    for y0,y1 in ((-48,-25),(25,48)):
        tray=tray.fuse(v5.box(-30,-20,y0,y1,-129,-125))
    electronics["battery_lower_bridge_tray"]=tray.clean()
    for i,(x0,x1,y0,y1,z0,z1) in enumerate(((44,51.3,-26,-4,-146,-96),
                                              (44,51.3,4,26,-146,-96),
                                              (44,51.3,-11,11,-206,-156)),1):
        electronics[f"C610_{i}_envelope"]=v5.box(x0,x1,y0,y1,z0,z1)
    rack=v5.box(51.3,55.3,-30,30,-214,-90)
    for y in (-18,18):
        for z in (-196,-166,-136,-106):
            rack=rack.cut(v5.x_cyl(1.65,51.2,55.4,y,z))
    electronics["C610_common_mount_rail"]=rack.clean()
    for y in (-27,27):
        electronics[f"C610_rail_support_{'n' if y<0 else 'p'}"]=cyl(3,-244,-214,53.3,y)
    # The UPS and both tall PCB rails are anchored to the service deck.
    electronics["UPS_support_shelf"]=v5.box(-24,-3,26,63,-128,-125)
    for tag,x in (("n",-22),("p",-8)):
        electronics[f"UPS_shelf_post_{tag}"]=cyl(3,-244,-128,x,55)
    for y in (-40.25,40.25):
        tag='n' if y<0 else 'p'
        electronics[f"STM32_lower_post_{tag}"]=cyl(3,-244,-222,35,y)
        upper_y=-31 if y<0 else y
        electronics[f"STM32_upper_post_{tag}"]=cyl(3,-70,-44,35,upper_y)
    electronics["STM32_upper_offset_bracket_n"]=v5.box(32,38,-41,-28,-70,-67)
    for y in (-36.25,36.25):
        electronics[f"regulator_lower_post_{'n' if y<0 else 'p'}"]=cyl(3,-244,-230,-46,y)
    for y in (-13,13):
        electronics[f"boost_shelf_post_{'n' if y<0 else 'p'}"]=cyl(2.5,-244,-240,12,y)
    return electronics


def make_cable_keepouts() -> dict[str,cq.Shape]:
    keepouts={}
    for i,angle in enumerate(P["tendon_angles_deg"],1):
        mx,my=xy(angle,P["motor_center_radius_mm"],P["motor_tangential_offset_mm"])
        keepouts[f"motor_{i}_rear_wire_keepout"]=cyl(4,-138,-120,mx,my)
    # A smooth candidate corridor for the 4 mm2 pair follows the empty
    # perimeter lane and reaches the UPS side. Its purchased cable OD and
    # minimum bend radius must still be measured.
    waypoints=[(0,-72,-255),(0,-72,-220),(-20,-72,-170),(-60,-60,-150),
               (-72,-10,-150),(-70,50,-140),(-30,70,-130),(-15,65,-117)]
    edge=cq.Edge.makeSpline([cq.Vector(*p) for p in waypoints])
    path=cq.Wire.assembleEdges([edge])
    plane=cq.Plane(origin=cq.Vector(*waypoints[0]),normal=cq.Vector(0,0,1))
    keepouts["shore_tether_to_UPS_keepout"]=cq.Workplane(plane).circle(5).sweep(path,isFrenet=True).val()
    return keepouts


def reel_tangent_point() -> tuple[float,float]:
    # Tangent from the horizontal reel core circle (radial/z plane) to the
    # chamfered plate port. This is one straight 3D segment, without a guide.
    center=np.array([P["reel_center_radius_mm"],P["reel_axis_z_mm"]],dtype=float)
    hole=np.array([P["tendon_hole_radius_mm"],P["tendon_hole_entry_z_mm"]],dtype=float)
    v=hole-center
    radius=P["reel_core_radius_mm"]+P["tendon_proxy_radius_mm"]
    d2=float(np.dot(v,v))
    if d2<=radius*radius:raise RuntimeError("tendon hole lies inside reel core")
    perp=np.array([-v[1],v[0]])
    base=(radius*radius/d2)*v
    offset=(radius*math.sqrt(d2-radius*radius)/d2)*perp
    choices=(center+base+offset,center+base-offset)
    radial,z=max(choices,key=lambda p:p[1])
    return float(radial),float(z)


def tendon_exit_proxy(angle: float) -> cq.Shape:
    radial,z=reel_tangent_point()
    tx,ty=xy(angle,float(radial))
    hx,hy=xy(angle,30.6)
    start=cq.Vector(tx,ty,float(z))
    finish=cq.Vector(hx,hy,-8.8)
    axis=finish-start
    return cq.Solid.makeCylinder(P["tendon_proxy_radius_mm"],axis.Length,start,axis.normalized())


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
        for part_index,(shape,color,opacity) in enumerate(parts):
            if i==1 and part_index==0:opacity=.12  # see horizontal reels under plate
            scene.AddActor(actor(shape,color,opacity))
        camera=scene.GetActiveCamera();camera.ParallelProjectionOn()
        camera.SetFocalPoint(0,0,145 if i==0 else -32)
        camera.SetPosition(650,-540,530 if i==0 else 90)
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
    draw.text((35,18),"B32 v15 | 竖电机、横线盘轴",font=font,fill=(27,47,61))
    draw.text((1075,18),"半透明观察：干式直角传动舱与湿侧线盘",font=font,fill=(27,47,61))
    draw.text((35,1007),"线盘轴沿俯视切向；拉索从卷芯切点直达线孔。直角齿轮、轴封和水密待实物定型。",font=small,fill=(45,63,75))
    image.save(HERE/"B32_v15_半透明总装预览.png")


def draw_plan() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle,RegularPolygon,Rectangle,Polygon
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei"]
    plt.rcParams["axes.unicode_minus"]=False
    fig,ax=plt.subplots(figsize=(9,9),dpi=180)
    ax.add_patch(RegularPolygon((0,0),6,radius=125,orientation=math.radians(30),
                                fill=False,edgecolor="#385063",linewidth=2))
    ax.add_patch(Circle((0,0),P["dry_hull_outer_radius_mm"],fill=False,edgecolor="#267687",linewidth=2))
    ax.add_patch(Circle((0,0),P["dry_hull_inner_radius_mm"],fill=False,edgecolor="#267687",linestyle="--"))
    ax.add_patch(Rectangle((13,-43.75),18,87.5,fill=False,edgecolor="#527e42",linewidth=1.5))
    ax.add_patch(Rectangle((-39.5,-40),39,80,fill=False,edgecolor="#527e42",linewidth=1.5))
    routes=[]
    for angle in P["plate_standoff_angles_deg"]:
        sx,sy=xy(angle,P["plate_standoff_radius_mm"])
        ax.add_patch(Circle((sx,sy),5,fill=False,edgecolor="#7c63a4",linewidth=1.4))
    for i,angle in enumerate((60,180,300),1):
        cx,cy=xy(angle,P["motor_center_radius_mm"],P["motor_tangential_offset_mm"])
        rx,ry=xy(angle,P["reel_center_radius_mm"])
        tang_r,tang_z=reel_tangent_point()
        tx,ty=xy(angle,tang_r)
        hx,hy=xy(angle,30.6)
        ax.add_patch(Circle((cx,cy),12.2,facecolor="#1c4054",alpha=.75))
        ax.plot([cx,rx],[cy,ry],color="#697a86",linewidth=3)
        outline=[xy(angle,P["reel_center_radius_mm"]+dr,dt)
                 for dr,dt in ((-10.5,-4),(10.5,-4),(10.5,4),(-10.5,4))]
        ax.add_patch(Polygon(outline,closed=True,facecolor="#d0a638",alpha=.65,
                             edgecolor="#875e18",linewidth=1.6))
        sx0,sy0=xy(angle,P["reel_center_radius_mm"],-5)
        sx1,sy1=xy(angle,P["reel_center_radius_mm"],5)
        ax.plot([sx0,sx1],[sy0,sy1],color="#355269",linewidth=2)
        ax.plot([tx,hx],[ty,hy],color="#c47a1a",linewidth=2)
        ax.add_patch(Circle((hx,hy),3.3,fill=False,edgecolor="#14844d",linewidth=2))
        ax.plot(hx,hy,"o",color="#c74f36",markersize=5)
        ax.text(cx+5,cy+5,str(i),fontsize=10)
        routes.append(math.dist((tx,ty,tang_z),(hx,hy,-8.8)))
    ax.set_aspect("equal");ax.set_xlim(-140,140);ax.set_ylim(-140,140)
    ax.grid(alpha=.2);ax.set_xlabel("X / mm");ax.set_ylabel("Y / mm")
    ax.set_title("v15 顶视：竖电机经直角传动驱动水平切向线盘轴")
    ax.text(-132,-130,"深蓝：电机  灰线：线盘轴  橙线：直线切线出线",fontsize=8.5,color="#34505c")
    fig.tight_layout();fig.savefig(HERE/"B32_v15_线盘线孔俯视.png");plt.close(fig)


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
    ax.set_title("B32 v15 顶盘拉索孔双面倒角剖面（三处相同）")
    ax.grid(alpha=.18)
    fig.tight_layout();fig.savefig(HERE/"B32_v15_线孔双面倒角剖面.png");plt.close(fig)


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
        tangent_r,tangent_z=reel_tangent_point()
        travel=np.array([P["tendon_hole_radius_mm"]-tangent_r,
                         P["tendon_hole_entry_z_mm"]-tangent_z])
        normal=np.array([tangent_r-P["reel_center_radius_mm"],
                         tangent_z-P["reel_axis_z_mm"]])
        tangent_error.append(round(abs(float(np.dot(travel,normal))) /
                                   (np.linalg.norm(travel)*np.linalg.norm(normal)),9))
    if any(v>.001 for v in root_probe+plate_probe+tangent_error):
        raise RuntimeError("reel tangent, plate hole, and actual arm root channel are not aligned")
    if any(v<.1 for v in off_axis_probe):
        raise RuntimeError("root channel probe cannot distinguish channel from nearby solid")
    if any(v>.001 for v in lower_mouth_probe+upper_mouth_probe) or any(v<.005 for v in bore_wall_probe):
        raise RuntimeError("tendon port chamfer profile does not match the requested mouth and bore")
    tube,roof,lid,gland=make_hull()
    standoffs=make_plate_standoffs()
    drives=[make_drive(a) for a in (60,180,300)]
    tendons=[tendon_exit_proxy(a) for a in (60,180,300)]
    root_tendons=[tendon_root_channel_proxy(a) for a in (60,180,300)]
    internals=make_internal_envelopes()
    cable_keepouts=make_cable_keepouts()
    fairing={k:v for k,v in v10.make_fairing().items() if k.startswith("upper_panel_")}
    assembly=cq.Assembly(name="B32_v15_vertical_motor_tangential_horizontal_reel")
    for i,s in enumerate(sections,1):assembly.add(s,name=f"arm_section_{i}",color=cq.Color(.76,.39,.22))
    for i,s in enumerate(pins,1):assembly.add(s,name=f"cross_pin_{i}_proxy")
    assembly.add(plate,name="hex_plate_250mm",color=cq.Color(.25,.39,.49))
    assembly.add(tube,name="single_dry_hull_tube",color=cq.Color(.20,.38,.47))
    assembly.add(roof,name="removable_roof_with_gasket_seat",color=cq.Color(.33,.52,.59))
    assembly.add(lid,name="bottom_service_lid",color=cq.Color(.50,.56,.62))
    assembly.add(gland,name="shore_cable_gland_proxy")
    for i,s in enumerate(standoffs,1):
        assembly.add(s,name=f"hex_plate_standoff_{i}",color=cq.Color(.46,.42,.60))
    for i,d in enumerate(drives,1):
        for key,shape in d.items():
            if key in ("right_angle_gear_space_proxy","output_shaft"):continue
            color=cq.Color(.80,.60,.18) if key=="wet_reel" else cq.Color(.14,.28,.36)
            assembly.add(shape,name=f"drive_{i}_{key}",color=color)
    for i,shape in enumerate(tendons,1):
        assembly.add(shape,name=f"tendon_{i}_straight_exit_proxy",color=cq.Color(.90,.47,.12))
    for i,shape in enumerate(root_tendons,1):
        assembly.add(shape,name=f"tendon_{i}_through_plate_into_arm_root_proxy",color=cq.Color(.90,.47,.12))
    for key,shape in internals.items():assembly.add(shape,name=key)
    for key,shape in cable_keepouts.items():assembly.add(shape,name=key,color=cq.Color(.96,.74,.18))
    for key,shape in {**fairing,**guard}.items():assembly.add(shape,name=key,color=cq.Color(.70,.79,.84))
    assembly.export(str(HERE/"B32_v15_垂直电机水平线盘总装.step"),exportType="STEP",unit="MM")
    preview=[(plate,(.20,.33,.44),.82),(tube,(.20,.37,.49),.30),
             (roof,(.30,.51,.60),.30),(lid,(.50,.55,.61),.70)]
    preview += [(s,(.46,.42,.60),.95) for s in standoffs]
    for d in drives:
        preview += [(d["motor"],(.08,.20,.29),1),(d["wet_reel"],(.90,.65,.16),1),
                    (d["oil_seal"],(.80,.29,.22),1),(d["motor_adapter"],(.48,.57,.60),.9),
                    (d["bearing"],(.57,.58,.62),1),(d["independent_shaft"],(.67,.67,.70),1),
                    (d["right_angle_pod"],(.29,.50,.66),.30),
                    (d["right_angle_pod_cap"],(.29,.50,.66),.34),
                    (d["right_angle_gear_space_proxy"],(.92,.37,.25),.24)]
    preview += [(s,(.90,.47,.12),1) for s in tendons]
    preview += [(s,(.90,.47,.12),1) for s in root_tendons]
    for key,shape in internals.items():
        if key in ("STM32_controller_envelope","voltage_regulator_envelope","UPS_module_envelope") or key.startswith("21700_cell_") or key.startswith("C610_"):
            preview.append((shape,(.29,.54,.34) if not key.startswith("21700") else (.57,.44,.28),.85))
    preview += [(s,(.98,.76,.16),.45) for s in cable_keepouts.values()]
    preview += [(s,(.73,.82,.86),.20) for s in fairing.values()]
    preview += [(s,(.57,.78,.84),.28) for s in guard.values()]
    render(preview,sections)
    draw_plan()
    draw_chamfer_detail()
    def dims(shape):
        b=shape.BoundingBox();return [round(b.xlen,2),round(b.ylen,2),round(b.zlen,2)]
    # Static packaging checks are for layout review, not pressure or print release.
    critical={k:s for k,s in internals.items() if k.endswith("_envelope") or k.startswith("21700_cell_")}
    component_pairs=list(critical.items())
    component_overlap={f"{ka}__{kb}":round(sa.intersect(sb).Volume(),3)
                       for i,(ka,sa) in enumerate(component_pairs)
                       for kb,sb in component_pairs[i+1:]}
    component_overlap={k:v for k,v in component_overlap.items() if v>.01}
    hull_overlap={f"{name}__{key}":round(shell.intersect(shape).Volume(),3)
                  for name,shell in (("roof",roof),("tube",tube),("lid",lid))
                  for key,shape in critical.items()}
    hull_overlap={k:v for k,v in hull_overlap.items() if v>.01}
    overlap={f"motor_{i}_{k}":round(d["motor"].intersect(s).Volume(),3)
             for i,d in enumerate(drives,1) for k,s in critical.items()}
    overlap={k:v for k,v in overlap.items() if v>.01}
    clearance_rank=sorted((round(d["motor"].distance(s),3),i,k)
                          for i,d in enumerate(drives,1) for k,s in critical.items())
    min_clearance=clearance_rank[0][0]
    adapter_overlap={f"adapter_{i}_{k}":round(d["motor_adapter"].intersect(s).Volume(),3)
                     for i,d in enumerate(drives,1) for k,s in critical.items()}
    adapter_overlap={k:v for k,v in adapter_overlap.items() if v>.01}
    drive_hull_overlap={f"drive_{i}_{key}__{name}":round(shape.intersect(shell).Volume(),3)
                        for i,d in enumerate(drives,1) for key,shape in d.items()
                        if key!="right_angle_gear_space_proxy"
                        for name,shell in (("tube",tube),("roof",roof),("lid",lid))}
    drive_hull_overlap={k:v for k,v in drive_hull_overlap.items() if v>.01}
    cable_component_overlap={f"{name}__{key}":round(route.intersect(shape).Volume(),3)
                             for name,route in cable_keepouts.items()
                             for key,shape in critical.items()}
    cable_component_overlap={k:v for k,v in cable_component_overlap.items() if v>.01}
    structures={k:s for k,s in internals.items() if k not in critical}
    structure_component_overlap={f"{name}__{key}":round(support.intersect(shape).Volume(),3)
                                 for name,support in structures.items()
                                 for key,shape in critical.items()}
    structure_component_overlap={k:v for k,v in structure_component_overlap.items() if v>.01}
    drive_structure_overlap={f"drive_{i}_{dk}__{ek}":round(dv.intersect(ev).Volume(),3)
                             for i,d in enumerate(drives,1) for dk,dv in d.items()
                             if dk!="right_angle_gear_space_proxy"
                             for ek,ev in structures.items()}
    drive_structure_overlap={k:v for k,v in drive_structure_overlap.items() if v>.01}
    structure_hull_overlap={f"{name}__{key}":round(shell.intersect(support).Volume(),3)
                            for name,shell in (("roof",roof),("tube",tube),("lid",lid))
                            for key,support in structures.items()}
    structure_hull_overlap={k:v for k,v in structure_hull_overlap.items() if v>.01}
    cable_structure_overlap={f"{name}__{key}":round(route.intersect(support).Volume(),3)
                             for name,route in cable_keepouts.items()
                             for key,support in structures.items()}
    cable_structure_overlap={k:v for k,v in cable_structure_overlap.items() if v>.01}
    physical_drive_parts={k:v for k,v in drives[0].items()
                          if k not in ("right_angle_gear_space_proxy","output_shaft")}
    intentional_contacts={frozenset(("right_angle_pod","pod_base_gasket")),
                          frozenset(("right_angle_pod","pod_cap_gasket"))}
    drive_part_overlap={f"{ka}__{kb}":round(sa.intersect(sb).Volume(),3)
                        for i,(ka,sa) in enumerate(physical_drive_parts.items())
                        for kb,sb in list(physical_drive_parts.items())[i+1:]
                        if frozenset((ka,kb)) not in intentional_contacts}
    drive_part_overlap={k:v for k,v in drive_part_overlap.items() if v>.01}
    tendon_solid_overlap={}
    for i,line in enumerate(tendons,1):
        for name,solid in (("plate",plate),("roof",roof),("tube",tube)):
            v=round(line.intersect(solid).Volume(),3)
            if v>.01:tendon_solid_overlap[f"tendon_{i}__{name}"]=v
        for j,d in enumerate(drives,1):
            for key in ("wet_reel","right_angle_pod","right_angle_pod_cap","seal_holder"):
                v=round(line.intersect(d[key]).Volume(),3)
                if v>.01:tendon_solid_overlap[f"tendon_{i}__drive_{j}_{key}"]=v
        for j,post in enumerate(standoffs,1):
            v=round(line.intersect(post).Volume(),3)
            if v>.01:tendon_solid_overlap[f"tendon_{i}__standoff_{j}"]=v
    pod_standoff_overlap={f"drive_{i}__standoff_{j}":round(d["right_angle_pod"].intersect(post).Volume(),3)
                          for i,d in enumerate(drives,1) for j,post in enumerate(standoffs,1)}
    pod_standoff_overlap={k:v for k,v in pod_standoff_overlap.items() if v>.01}
    drive_plate_overlap={f"drive_{i}_{key}":round(shape.intersect(plate).Volume(),3)
                         for i,d in enumerate(drives,1) for key,shape in d.items()
                         if key not in ("right_angle_gear_space_proxy","output_shaft")}
    drive_plate_overlap={k:v for k,v in drive_plate_overlap.items() if v>.01}
    adapter_tube_clearance=min(d["motor_adapter"].distance(tube) for d in drives)
    if (component_overlap or hull_overlap or overlap or adapter_overlap or
        drive_hull_overlap or drive_structure_overlap or cable_component_overlap or
        structure_component_overlap or structure_hull_overlap or
        cable_structure_overlap or drive_part_overlap or tendon_solid_overlap or
        pod_standoff_overlap or drive_plate_overlap or adapter_tube_clearance<3):
        print(json.dumps({"component":component_overlap,"hull":hull_overlap,
                          "motor":overlap,"adapter":adapter_overlap,
                          "drive_hull":drive_hull_overlap,"drive_structure":drive_structure_overlap,
                          "cable_component":cable_component_overlap,
                          "structure_component":structure_component_overlap,
                          "structure_hull":structure_hull_overlap,
                          "cable_structure":cable_structure_overlap,
                          "drive_part":drive_part_overlap,"tendon_solid":tendon_solid_overlap,
                          "pod_standoff":pod_standoff_overlap,"drive_plate":drive_plate_overlap,
                          "adapter_tube_clearance":adapter_tube_clearance},ensure_ascii=False))
        raise RuntimeError("physical packaging collision detected; inspect overlap audit")
    print_parts=sections+[tube,roof,lid,plate]+standoffs
    print_parts += [d[k] for d in drives for k in ("right_angle_pod","right_angle_pod_cap","wet_reel")]
    if any((s.BoundingBox().zlen>250 or s.BoundingBox().xlen>350 or
            s.BoundingBox().ylen>350) for s in print_parts):
        raise RuntimeError("a printed part exceeds 350 x 350 x 250 mm effective bounds")
    tangent_r,tangent_z=reel_tangent_point()
    horizontal=tangent_r-P["tendon_hole_radius_mm"]
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
           "motor_center_xy_mm":[xy(a,P["motor_center_radius_mm"],P["motor_tangential_offset_mm"]) for a in (60,180,300)],
           "reel_tangent_r_z_mm":[round(tangent_r,3),round(tangent_z,3)],
           "reel_to_hole_planar_mm":round(horizontal,2),
           "reel_tangent_to_hole_3d_mm":round(math.hypot(horizontal,P["tendon_hole_entry_z_mm"]-tangent_z),2),
           "shaft_orientation":"motor vertical; reel shaft horizontal tangential; tendon radial in plan",
           "section_heights_mm":[round(s.BoundingBox().zlen,2) for s in sections],
           "print_part_envelopes_mm":{"dry_tube":dims(tube),"roof":dims(roof),
                                       "lid":dims(lid),"hex_plate":dims(plate),
                                       "plate_standoff":dims(standoffs[0]),
                                       "dry_gear_pod":dims(drives[0]["right_angle_pod"]),
                                       "wet_reel":dims(drives[0]["wet_reel"])},
           "critical_component_pair_overlap_mm3":component_overlap,
           "critical_component_to_hull_overlap_mm3":hull_overlap,
           "motor_to_electronics_overlap_mm3":overlap,
           "motor_to_electronics_min_clearance_mm":min_clearance,
           "motor_to_electronics_closest_pairs_mm":clearance_rank[:5],
           "adapter_to_electronics_overlap_mm3":adapter_overlap,
           "drive_to_hull_overlap_mm3":drive_hull_overlap,
           "adapter_to_tube_min_clearance_mm":round(adapter_tube_clearance,3),
           "cable_keepout_to_critical_component_overlap_mm3":cable_component_overlap,
           "mount_structure_to_critical_component_overlap_mm3":structure_component_overlap,
           "drive_to_mount_structure_overlap_mm3":drive_structure_overlap,
           "mount_structure_to_hull_overlap_mm3":structure_hull_overlap,
           "cable_keepout_to_mount_structure_overlap_mm3":cable_structure_overlap,
           "drive_part_unintended_overlap_mm3":drive_part_overlap,
           "tendon_to_solid_overlap_mm3":tendon_solid_overlap,
           "dry_pod_to_plate_standoff_overlap_mm3":pod_standoff_overlap,
           "drive_to_hex_plate_overlap_mm3":drive_plate_overlap,
           "pod_cap_to_hex_plate_min_clearance_mm":round(min(d["right_angle_pod_cap"].distance(plate) for d in drives),3),
           "pod_static_gasket_compression_proxy":"0.05 mm contact at pod base and cap; not a pressure design",
           "roof_to_battery_min_clearance_mm":round(min(roof.distance(v) for k,v in critical.items() if k.startswith("21700_cell_")),3),
           "top_plate_support_count":len(standoffs),
           "motor_mount":"3-hole M3 PCD19 proxy; dry-side adapter and three spacer posts per motor",
           "shaft_load_path":"wet reel -> horizontal 8 mm shaft -> pod bearing -> dry 90-degree gear set (selection pending) -> vertical shaft/bearing -> motor",
           "shore_tether_corridor":"smooth 10 mm diameter keepout from off-axis bottom gland to UPS input region",
           "reel_to_plate_overlap_mm3":[round(d["wet_reel"].intersect(plate).Volume(),3) for d in drives],
           "motor_to_tube_overlap_mm3":[round(d["motor"].intersect(tube).Volume(),3) for d in drives],
           "reel_to_fixed_labyrinth_overlap_mm3":[round(d["wet_reel"].intersect(d["fixed_labyrinth"]).Volume(),3) for d in drives],
           "fixed_to_rotating_labyrinth_overlap_mm3":[round(d["fixed_labyrinth"].intersect(d["rotating_labyrinth"]).Volume(),3) for d in drives],
           "seal_status":"placeholder geometry; purchased seal and pressure rating pending",
           "service":"remove six upper flat panels and hex plate; release three wet reels, then lift roof/motor cartridge; bottom lid opens to electronics",
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
