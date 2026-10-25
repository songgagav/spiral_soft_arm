"""B32 v16 packaging model: DJI M3508 P19/C620, dry miter drive, wet reel.

Purchased parts are dimensional envelopes, not printable replacement gears or
proof that the rotating seal survives 5 m seawater service.
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
OLD = HERE.parent / "electronics_enclosure_v15" / "generate_perpendicular_drive.py"
spec = importlib.util.spec_from_file_location("b32_v15", OLD)
v15 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v15)
v15.P = P
v15.v10.CFG = v15.base
v15.v5.CFG = {**v15.v5.CFG, "base_plate_diameter_mm": 250.0}
cyl, ring, xy = v15.cyl, v15.ring, v15.xy
tcyl, tring = v15.tangent_cylinder, v15.tangent_ring


def motor_center(angle: float) -> tuple[float, float]:
    return xy(angle, P["motor_center_radius_mm"], P["motor_tangential_offset_mm"])


def make_hull() -> tuple[cq.Shape, cq.Shape, cq.Shape, cq.Shape]:
    ro, ri = P["dry_hull_outer_radius_mm"], P["dry_hull_inner_radius_mm"]
    top, bottom = P["dry_hull_top_z_mm"], P["dry_hull_bottom_z_mm"]
    flange = ro + 6
    tube = ring(ro, ri, bottom, top).fuse(ring(flange, ri, top-4, top))
    tube = tube.fuse(ring(flange, ri, bottom, bottom+5))
    roof = cyl(flange, top, -36)
    roof = roof.cut(ring(ri+3.5, ri+1.5, top-.01, top+.8))
    for angle in P["tendon_angles_deg"]:
        x, y = motor_center(angle)
        roof = roof.cut(cyl(16.5, top-.1, -35.9, x, y))
    for angle in P["plate_standoff_angles_deg"]:
        x, y = xy(angle, P["plate_standoff_radius_mm"])
        roof = roof.cut(cyl(1.65, top-.1, -35.9, x, y))
    bolts = [xy(a, ro+2) for a in range(0, 360, 45)]
    for x, y in bolts:
        roof = roof.cut(cyl(1.65, top-.1, -35.9, x, y))
        tube = tube.cut(cyl(1.35, top-5, top+5, x, y))
    # A replaceable gear cartridge is built into each removable roof pod.
    for angle in P["tendon_angles_deg"]:
        x, y = motor_center(angle)
        r, z = P["reel_center_radius_mm"], P["reel_axis_z_mm"]
        barrel = ring(27, 5.2, -72, -11, x, y)
        barrel = barrel.cut(cyl(10.3, -72.1, -63, x, y))
        barrel = barrel.cut(cyl(13.1, -63, -55, x, y))
        barrel = barrel.cut(cyl(16.2, -53, -28, x, y))
        barrel = barrel.cut(tcyl(5.2, 4, 55, r, z, angle))
        barrel = barrel.cut(tcyl(16.2, 26, 45, r, z, angle))
        nose = tcyl(14, 4, 27, r, z, angle).fuse(tcyl(19, 24, 39, r, z, angle))
        nose = nose.cut(tcyl(5.2, 3.9, 39.1, r, z, angle))
        nose = nose.cut(tcyl(11.15, 4.5, 11.5, r, z, angle))
        nose = nose.cut(tcyl(15.1, 12, 26, r, z, angle))
        nose = nose.cut(tcyl(16.2, 26, 39.1, r, z, angle))
        # M3508 front locating boss Ø26 and four M4 holes on Ø35 PCD.
        mount = ring(24, 13.2, -96, -92, x, y)
        for k in range(4):
            dx, dy = xy(angle+45+90*k, 23.5)
            mount = mount.fuse(cyl(2.5, -92, -70, x+dx, y+dy))
            bx, by = xy(angle+45+90*k, 17.5)
            mount = mount.cut(cyl(2.1, -96.1, -91.9, x+bx, y+by))
        roof = roof.fuse(barrel).fuse(nose).fuse(mount)
        for k in range(4):
            dx, dy = xy(angle+45+90*k, 22)
            roof = roof.cut(cyl(1.35, -21, -10.9, x+dx, y+dy))
    lid = cyl(flange, bottom-10, bottom).fuse(cyl(ri-.6, bottom, bottom+3))
    gx, gy = P["shore_tether_gland_xy_mm"]
    lid = lid.cut(cyl(6, bottom-10.1, bottom+3.1, gx, gy))
    lid = lid.cut(ring(ri+3.5, ri+1.5, bottom-.8, bottom+.01))
    for x, y in bolts:
        lid = lid.cut(cyl(1.65, bottom-10.1, bottom+.1, x, y))
        tube = tube.cut(cyl(1.35, bottom-5, bottom+1, x, y))
    tube = tube.cut(v15.v5.box(-108, -93, -5, 5, bottom+11, bottom+17))
    gland = ring(9, 6, bottom-18, bottom-7, gx, gy)
    return tube.clean(), roof.clean(), lid.clean(), gland


def make_drive(angle: float) -> dict[str, cq.Shape]:
    x, y = motor_center(angle)
    r, z = P["reel_center_radius_mm"], P["reel_axis_z_mm"]
    # Official M3508 drawing: Ø42 body, 66.7 mm body, 98.4 mm overall;
    # front D shaft Ø10 extends into a replaceable 10-to-10 clamp coupling.
    body = cyl(21, -162.7, -96, x, y)
    rear_endcap = cyl(21, -167.1, -162.7, x, y)
    output = cyl(5, -96, -68.7, x, y)
    gearmotor = body.fuse(rear_endcap).fuse(output)
    coupling = ring(10, 5.05, -81, -64, x, y)
    vertical_shaft = cyl(5, -68.5, -29.5, x, y)
    input_bearing = ring(13, 5.02, -63, -55, x, y)
    output_shaft = tcyl(5, -4, 44, r, z, angle)
    output_bearing = tring(15, 5.02, 12, 26, r, z, angle)
    oil_seal = tring(11, 5.02, 4.5, 11.5, r, z, angle)
    fixed_labyrinth = tring(13.8, 5.4, 4, 4.45, r, z, angle)
    reel = tring(P["reel_flange_radius_mm"], 5.05, -4, -2, r, z, angle)
    reel = reel.fuse(tring(6.5, 5.05, -2, 2, r, z, angle))
    reel = reel.fuse(tring(P["reel_flange_radius_mm"], 5.05, 2, 4, r, z, angle))
    # Cone teeth are deliberately not invented; these are catalog maximum
    # envelopes positioned by the manufacturer's 28 mm mounting distance.
    input_gear = ring(15.95, 5.02, -51, -32.52, x, y)
    output_gear = tring(15.95, 5.02, 26, 44.48, r, z, angle)
    cap = cyl(27, -11, -9, x, y)
    for k in range(4):
        dx, dy = xy(angle+45+90*k, 22)
        cap = cap.cut(cyl(1.65, -11.1, -8.9, x+dx, y+dy))
    return {"gearmotor":gearmotor, "coupling":coupling,
            "vertical_drive_shaft":vertical_shaft, "input_bearing":input_bearing,
            "input_miter_gear_envelope":input_gear,
            "output_miter_gear_envelope":output_gear,
            "output_shaft":output_shaft, "output_bearing":output_bearing,
            "oil_seal":oil_seal, "fixed_labyrinth":fixed_labyrinth,
            "wet_reel":reel, "pod_cap":cap}


def internals() -> dict[str, cq.Shape]:
    all_parts = v15.make_internal_envelopes()
    parts = {k: s for k, s in all_parts.items()
             if not k.startswith("C610_") and not k.startswith("STM32_upper_")
             and not k.startswith("regulator_lower_post_")
             and not k.startswith("regulator_M3_M4_M5_mount_rail_")
             and not k.startswith("battery_support_")
             and k!="battery_lower_bridge_tray"}
    # Turn the tall 39 x 80 x 100 regulator to lie between the motor sectors.
    key="voltage_regulator_envelope"
    parts[key]=parts[key].rotate((-20,0,0),(-20,0,1),90).translate(cq.Vector(-4,0,0))
    # Shift the 152 mm STM32 board enough to open a center lane for regulator.
    for key in list(parts):
        if key.startswith("STM32_"):
            parts[key]=parts[key].translate(cq.Vector(17,0,0)) if key=="STM32_controller_envelope" else parts[key]
        if key in ("UPS_module_envelope","UPS_support_shelf") or key.startswith("UPS_shelf_post_"):
            parts[key]=parts[key].translate(cq.Vector(27,22,0))
        if key.startswith("boost_"):
            parts[key]=parts[key].translate(cq.Vector(20,0,0))
    for i,x in enumerate((-55,8)):
        for j,y in enumerate((-15,15)):
            parts[f"regulator_post_{i}_{j}"]=cyl(3,-244,-230,x,y)
    # Hang the four-cell tray from the roof along a gap between gearmotors.
    tray=v15.v5.box(-51,8,-21,21,-129,-125)
    for y0,y1 in ((-27,-21),(21,27)):
        tray=tray.fuse(v15.v5.box(3,8,y0,y1,-129,-125))
    parts["battery_lower_bridge_tray"]=tray.clean()
    for y in (-26,26):
        parts[f"battery_roof_hanger_{'n' if y<0 else 'p'}"]=cyl(2.5,-125,-44,5,y)
    esc_boxes=(((-24.7,24.7,55,80.8,-231.5,-220),"front"),
               ((-24.7,24.7,-80.8,-55,-231.5,-220),"rear"),
               ((41,90.4,-12.9,12.9,-215,-203.5),"right"))
    for i,(bounds,tag) in enumerate(esc_boxes,1):
        x0,x1,y0,y1,z0,z1=bounds
        parts[f"C620_{i}_envelope"]=v15.v5.box(*bounds)
        parts[f"C620_{i}_mount_shelf"]=v15.v5.box(x0,x1,y0,y1,z0-2,z0)
        post_x=(x1-4) if tag=="right" else 0
        for post_y in (y0+4,y1-4):
            parts[f"C620_{i}_post_{'n' if post_y<0 else 'p'}"]=cyl(2.5,-244,z0-2,post_x,post_y)
    return parts


def draw_plan(drives: list[dict[str, cq.Shape]]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, RegularPolygon, Rectangle
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    fig, ax = plt.subplots(figsize=(9,9), dpi=180)
    ax.add_patch(RegularPolygon((0,0),6,radius=125,orientation=math.radians(30),
                                fill=False,edgecolor="#375064",linewidth=2))
    for radius, style in ((100,"-"),(94,"--")):
        ax.add_patch(Circle((0,0),radius,fill=False,edgecolor="#397d87",linestyle=style))
    for angle in P["tendon_angles_deg"]:
        x,y = motor_center(angle)
        rx,ry = xy(angle,P["reel_center_radius_mm"])
        tr,tz = v15.reel_tangent_point()
        tx,ty = xy(angle,tr)
        hx,hy = xy(angle,P["tendon_hole_radius_mm"])
        ax.add_patch(Circle((x,y),27,fill=False,edgecolor="#687f91",linewidth=1.2))
        ax.add_patch(Circle((x,y),16,color="#273e50",alpha=.65))
        ax.plot([rx,x],[ry,y],color="#565b67",linewidth=4)
        ax.add_patch(Circle((rx,ry),10.5,color="#d6a334",alpha=.72))
        ax.plot([tx,hx],[ty,hy],color="#c55b25",linewidth=2.7)
        ax.add_patch(Circle((hx,hy),3.6,fill=False,edgecolor="#258650",linewidth=2))
    ax.set_aspect("equal"); ax.set_xlim(-138,138); ax.set_ylim(-138,138)
    ax.grid(alpha=.2); ax.set_xlabel("X / mm"); ax.set_ylabel("Y / mm")
    ax.set_title("B32 v16：原厂减速电机 / 1:1 直角齿轮 / 径向切线出线")
    fig.tight_layout()
    fig.savefig(HERE/"B32_v16_线盘线孔俯视.png")
    plt.close(fig)


def render(parts: list[tuple[cq.Shape, tuple[float,float,float], float]],
           sections: list[cq.Shape]) -> None:
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    from PIL import Image, ImageDraw, ImageFont
    window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.SetSize(2100,1050)
    def actor(shape,color,opacity):
        vertices,faces=shape.tessellate(1.7,.2)
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
    for i in (0,1):
        scene=vtk.vtkRenderer();scene.SetViewport(i*.5,0,(i+1)*.5,1)
        scene.SetBackground(.94,.96,.98);scene.SetUseDepthPeeling(1);window.AddRenderer(scene)
        if i==0:
            for j,s in enumerate(sections):scene.AddActor(actor(s,((.76,.37,.22),(.87,.48,.24),(.93,.63,.31))[j],1))
        for part_index,(shape,color,opacity) in enumerate(parts):
            scene.AddActor(actor(shape,color,.12 if i==1 and part_index==0 else opacity))
        camera=scene.GetActiveCamera();camera.ParallelProjectionOn()
        camera.SetFocalPoint(0,0,145 if i==0 else -48)
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
    draw.text((35,18),"B32 v16 | 原厂减速电机 + 干式直角传动",font=font,fill=(27,47,61))
    draw.text((1075,18),"半透明齿轮舱：湿侧仅线盘和露出轴",font=font,fill=(27,47,61))
    draw.text((35,1007),"齿轮和轴封按商品包络显示；水密、轴向载荷与电子件最终支架待实物核验。",font=small,fill=(45,63,75))
    image.save(HERE/"B32_v16_半透明总装预览.png")


def main() -> None:
    sections,pins,plate,guard,seams=v15.make_arm_and_plate()
    tube,roof,lid,gland=make_hull()
    standoffs=v15.make_plate_standoffs()
    drives=[make_drive(a) for a in P["tendon_angles_deg"]]
    tendons=[v15.tendon_exit_proxy(a) for a in P["tendon_angles_deg"]]
    roots=[v15.tendon_root_channel_proxy(a) for a in P["tendon_angles_deg"]]
    boards=internals()
    fairing={k:v for k,v in v15.v10.make_fairing().items() if k.startswith("upper_panel_")}
    assembly=cq.Assembly(name="B32_v16_DJI_M3508_P19_C620_1to1_miter_drive")
    for i,s in enumerate(sections,1):assembly.add(s,name=f"arm_section_{i}",color=cq.Color(.76,.39,.22))
    for i,s in enumerate(pins,1):assembly.add(s,name=f"cross_pin_{i}_proxy")
    for name,s in (("hex_plate_250mm",plate),("dry_tube",tube),("removable_roof_pods",roof),
                   ("bottom_lid",lid),("tether_gland_proxy",gland)):
        assembly.add(s,name=name)
    for i,s in enumerate(standoffs,1):assembly.add(s,name=f"standoff_{i}")
    for i,d in enumerate(drives,1):
        for key,s in d.items():
            assembly.add(s,name=f"drive_{i}_{key}",
                         color=cq.Color(.84,.61,.2) if key=="wet_reel" else cq.Color(.19,.35,.44))
    for i,s in enumerate(tendons,1):assembly.add(s,name=f"tendon_{i}_straight_proxy")
    for i,s in enumerate(roots,1):assembly.add(s,name=f"root_tendon_{i}_proxy")
    for key,s in boards.items():assembly.add(s,name=key)
    for key,s in {**fairing,**guard}.items():assembly.add(s,name=key)
    assembly.export(str(HERE/"B32_v16_减速电机直角传动总装.step"),exportType="STEP",unit="MM")
    preview=[(plate,(.2,.33,.44),.82),(tube,(.2,.37,.49),.23),
             (roof,(.3,.51,.6),.24),(lid,(.5,.55,.61),.7)]
    preview += [(s,(.46,.42,.6),.9) for s in standoffs]
    for d in drives:
        preview += [(d["gearmotor"],(.08,.2,.29),1),
                    (d["wet_reel"],(.9,.65,.16),1),
                    (d["oil_seal"],(.8,.29,.22),1),
                    (d["output_shaft"],(.68,.68,.7),1),
                    (d["output_bearing"],(.5,.52,.58),1),
                    (d["input_miter_gear_envelope"],(.88,.47,.16),.8),
                    (d["output_miter_gear_envelope"],(.88,.47,.16),.8)]
    preview += [(s,(.9,.47,.12),1) for s in tendons+roots]
    for key,s in boards.items():
        if key.endswith("_envelope") or key.startswith("21700_cell_"):
            preview.append((s,(.29,.54,.34),.75))
    preview += [(s,(.73,.82,.86),.18) for s in fairing.values()]
    preview += [(s,(.57,.78,.84),.26) for s in guard.values()]
    render(preview,sections)
    draw_plan(drives)
    tr,tz=v15.reel_tangent_point()
    hole=P["tendon_hole_radius_mm"]
    tangent_length=math.hypot(tr-hole,tz-P["tendon_hole_entry_z_mm"])
    critical={k:s for k,s in boards.items() if k.endswith("_envelope") or k.startswith("21700_cell_")}
    collisions={f"drive_{i}__{k}":round(d["gearmotor"].intersect(s).Volume(),3)
                for i,d in enumerate(drives,1) for k,s in critical.items()}
    collisions={k:v for k,v in collisions.items() if v>.01}
    housing_hits={f"drive_{i}__tube":round(d["gearmotor"].intersect(tube).Volume(),3)
                  for i,d in enumerate(drives,1)}
    housing_hits={k:v for k,v in housing_hits.items() if v>.01}
    arm_probes=[round(sections[0].intersect(cyl(1.5,0,5,*xy(a,hole))).Volume(),6)
                for a in P["tendon_angles_deg"]]
    printed=sections+[plate,tube,roof,lid]+standoffs+[d["pod_cap"] for d in drives]
    max_boxes=[[round(s.BoundingBox().xlen,1),round(s.BoundingBox().ylen,1),
                round(s.BoundingBox().zlen,1)] for s in printed]
    audit={"status":P["status"],"gearmotor":"DJI RoboMaster M3508 P19 with factory 19:1 gearbox",
           "esc":"DJI RoboMaster C620 x3",
           "gearmotor_body_envelope_mm":[42,66.7],
           "gearmotor_overall_length_mm":98.4,
           "gearmotor_nominal_continuous_torque_Nm":3.0,
           "per_motor_rated_input_current_A":10.0,
           "three_motor_simultaneous_rated_input_current_A":30.0,
           "existing_battery_side_regulator_rated_output_A":15.0,
           "power_budget_status":"simultaneous rated motor operating points exceed 15 A; active limiting and measured duty required",
           "gearbox_output_shaft_mm":10,"miter_gear_pair":"KHK MMSA1.5-20R + MMSA1.5-20L, 1:1, module 1.5, 20 teeth, 10 mm bore",
           "output_bearing":"SKF 3200 ATN9, 10x30x14",
           "input_bearing":"SKF 6000-2RS1, 10x26x8",
           "oil_seal":"SKF 10X22X7 HMSA10 RG envelope candidate only",
           "reel_tangent_r_z_mm":[round(tr,3),round(tz,3)],
           "tangent_to_hole_length_mm":round(tangent_length,3),
           "arm_root_channel_probe_overlap_mm3":arm_probes,
           "motor_to_critical_component_overlap_mm3":collisions,
           "motor_to_dry_tube_overlap_mm3":housing_hits,
           "printed_part_envelopes_mm":max_boxes,
           "print_envelope_pass":all(x<=350 and y<=350 and z<=250 for x,y,z in max_boxes),
           "open_items":["actual tooth CAD and backlash","axial thrust and bearing life",
                         "5 m pressure and seawater seal selection","coupling and shaft fit tolerances",
                         "mechanical fastening details and support bracket clearance",
                         "15 A 24 V bus cannot power three M3508 at their simultaneous 10 A rating",
                         "C620 cable bend and connector clearance","STM32 to C620 CAN/PWM wiring map"],
           "seams":seams}
    (HERE/"装配布置审计.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (HERE/"SHA256SUMS.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.writer(stream);writer.writerow(("file","sha256","bytes"))
        for f in sorted(HERE.iterdir(),key=lambda x:x.name):
            if f.is_file() and f.name!="SHA256SUMS.csv":
                writer.writerow((f.name,hashlib.sha256(f.read_bytes()).hexdigest(),f.stat().st_size))
    print(json.dumps({"tangent_length_mm":audit["tangent_to_hole_length_mm"],
                      "motor_electronics_overlap":collisions,"motor_tube_overlap":housing_hits,
                      "print_envelope_pass":audit["print_envelope_pass"]},ensure_ascii=False))


if __name__=="__main__":
    main()
