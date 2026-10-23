"""B32 v11: dry M2006 drive cartridges and wet tendon reels.

The pod, shaft seal and bearings are dimensional layout proxies. Nothing in
this file certifies printed parts as a pressure boundary.
"""
from __future__ import annotations

import importlib.util
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

    # Open rear service port plus a thick front bulkhead. Its machined seal
    # counterbore is represented geometrically; no press-fit tolerance given.
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
    cap = cap.fuse(axial_cylinder(reel_center,axis,rear_open-9,
                                  rear_open-3,6))
    cap = cap.cut(axial_cylinder(reel_center,axis,rear_open-9.1,
                                 motor_back,4)).clean()
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
    top.add_patch(Circle((0,0),68,facecolor="#95aab5",alpha=.3))
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
        cable=v10.straight_tendon_points(angle,motor_config["plate"]["tendon_hole_radius_mm"])
        top.plot(cable[:,0],cable[:,1],color="#bf4445",linewidth=2)
        top.scatter([cable[-1,0]],[cable[-1,1]],color="#bf4445",s=25)
        top.text(*center,f"M2006-{i}",ha="center",va="center",color="white",fontsize=8)
    top.set(xlim=(-170,170),ylim=(-170,170),xlabel="X / mm",ylabel="Y / mm",
            title="俯视：3 个干式电机筒与湿侧线盘；红线为切线出线")
    top.set_aspect("equal");top.grid(alpha=.2)

    # A scaled axial layout of one cartridge, not a manufactured section.
    bands=[(-100.4,-97.4,20,"后端盖","#728691"),
           (-97.4,-15,20,"干侧电机筒","#82a7b0"),
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
    detail.set(xlim=(-108,17),ylim=(-34,30),xlabel="沿输出轴方向 / mm",
               ylabel="径向 / mm",title="单轴剖面布局：独立轴承担线盘载荷")
    detail.set_aspect("equal");detail.grid(alpha=.2)
    detail.legend(handles=legend_handles,loc="upper center",bbox_to_anchor=(.5,-.22),
                  ncol=3,fontsize=8,frameon=False)
    fig.suptitle("B32 v11｜M2006 干侧布置 + 迷宫与骨架油封候选",fontsize=17)
    fig.tight_layout(rect=(0,.1,1,.96))
    fig.savefig(HERE/"B32_M2006干式电机与轴封布局.png")
    plt.close(fig)


def main() -> None:
    motor_cfg=v5.motor_module.load_config()
    drive=CFG["drive_layout"]
    motor_cfg["layout"]["motor_center_radius_mm"]=98.5
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
    plate,guard=v10.make_root_guard(plate)
    shell,lid,gland=v10.make_shell_with_clear_tendon_radials()
    fairing=v10.make_fairing()
    splices=v10.make_panel_splices()
    cartridges=[]
    for center,axis in zip(mount.reel_centers,mount.motor_axes):
        cartridges.append(make_cartridge(cq.Vector(*center),cq.Vector(*axis)))
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
    mount.motors=[c["pod"] for c in cartridges]  # Preview of the visible housings.
    electronics={key:shape for key,shape in v5.make_electronics().items()
                 if not key.startswith("ESC_")}
    for i,(y0,y1,z0,z1) in enumerate(((-33,-11,-104,-54),
                                      (11,33,-104,-54),(-11,11,-165,-115)),1):
        electronics[f"C610_{i}_dry_envelope"]=v5.box(40,47.3,y0,y1,z0,z1)

    assembly=cq.Assembly(name="B32_v11_M2006_dry_pods_wet_reels")
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
    assembly.add(shell,name="existing_center_dry_canister")
    assembly.add(lid,name="center_canister_lid")
    assembly.add(gland,name="shore_tether_gland_proxy")
    for key,part in {**fairing,**guard,**splices}.items():
        assembly.add(part,name=key,color=cq.Color(.73,.80,.84))
    v5.add_parts(assembly,v5.make_battery())
    v5.add_parts(assembly,electronics)
    out=HERE/"B32_M2006干式电机_湿侧线盘总装.step"
    assembly.export(str(out),exportType="STEP",unit="MM")
    draw_views(mount,cartridges,motor_cfg)
    v10.OUT_PREVIEW=HERE/"B32_M2006干式驱动_总装预览.png"
    v10.OUT_DETAIL=HERE/"B32_燕尾榫与六边形顶盘细节.png"
    v10.render_preview(sections,pins,plate,mount,shell,lid,fairing,guard,splices,seams)
    audit={"candidate":CFG["model"],"status":CFG["status"],
           "motor_centers_mm":mount.motor_centers,
           "reel_centers_mm":mount.reel_centers,
           "axes":mount.motor_axes,
           "section_heights_mm":[round(p.BoundingBox().zlen,3) for p in sections],
           "pod_to_center_canister_clearance_mm":[round(c["pod"].distance(shell),3) for c in cartridges],
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
           "canister_motor_cable_glands":"three static penetrations required; existing bores are not sealed gland designs",
           "seams":seams}
    (HERE/"装配布置审计.json").write_text(
        json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({key:audit[key] for key in ("section_heights_mm","pod_to_center_canister_clearance_mm",
                          "pod_to_plate_overlap_mm3","pod_to_fairing_overlap_mm3",
                          "spool_to_hole_collinearity_mm")},ensure_ascii=False))


if __name__=="__main__": main()
