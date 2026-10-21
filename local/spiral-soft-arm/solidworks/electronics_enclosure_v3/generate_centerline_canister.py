"""B32 central dry-canister fit study with three external wet motors.

The motor and electronics envelopes are proxies. No pressure or electrical
qualification is implied by the closed STEP or preview.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import cadquery as cq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
MOTOR_SCRIPT = (HERE / CFG["reference_motor_mount"]).resolve()
spec = importlib.util.spec_from_file_location("b32_motor_mount_v2_reference", MOTOR_SCRIPT)
motor_module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = motor_module
spec.loader.exec_module(motor_module)

for candidate in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC"):
    if any(f.name == candidate for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [candidate, "DejaVu Sans"]
        break
plt.rcParams["axes.unicode_minus"] = False

OUT_STEP = HERE / "B32_中心电子仓_三湿侧电机总装.step"
OUT_OPEN = HERE / "B32_中心电子仓_拆解与接线.step"
OUT_IMG = HERE / "B32_中心电子仓_总装与内部接线预览.png"
OUT_WIRING = HERE / "B32_中心电子仓_安装剖面与接线图.png"
OUT_AUDIT = HERE / "布局与干涉审计.json"


def cyl(radius, z0, z1, x=0.0, y=0.0):
    return cq.Solid.makeCylinder(radius, z1-z0, cq.Vector(x,y,z0), cq.Vector(0,0,1))


def box(x0,x1,y0,y1,z0,z1):
    return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))


def radial_cyl(radius, length, angle, r0, z):
    t=math.radians(angle)
    d=cq.Vector(math.cos(t),math.sin(t),0)
    return cq.Solid.makeCylinder(radius,length,cq.Vector(d.x*r0,d.y*r0,z),d)


def x_cyl(radius, x0, x1, y, z):
    return cq.Solid.makeCylinder(radius,x1-x0,cq.Vector(x0,y,z),cq.Vector(1,0,0))


def wire(points, radius=1.1):
    segments=[]
    for p,q in zip(points[:-1],points[1:]):
        a,b=cq.Vector(*p),cq.Vector(*q)
        d=b-a
        segments.append(cq.Solid.makeCylinder(radius,d.Length,a,d.normalized()))
    return cq.Compound.makeCompound(segments)


def rotate(shape, angle):
    return shape.rotate((0,0,0),(0,0,1),angle)


def make_shell():
    c=CFG["canister"]
    r=c["outer_diameter_mm"]/2
    inner=c["inner_diameter_mm"]/2
    top=c["top_z_mm"]
    bottom=c["body_bottom_z_mm"]
    shell=cyl(r,bottom,top).cut(cyl(inner,bottom-1,top-c["top_wall_mm"]))
    flange=cyl(r+7,bottom,bottom+8).cut(cyl(inner,bottom-1,bottom+9))
    shell=shell.fuse(flange)
    # Three radial bosses are integrated with the wall. Their bores enter the
    # ESC bay; real certified penetrators still need to be selected.
    for angle in (0,120,240):
        shell=shell.fuse(radial_cyl(c["motor_port_boss_diameter_mm"]/2,9,angle,r-1,-76))
        shell=shell.cut(radial_cyl(c["motor_port_bore_mm"]/2,18,angle,inner-2,-76))
    # External blind mounting posts: holes stop inside the 6 mm top wall.
    for angle in (60,180,300):
        t=math.radians(angle)
        x,y=47*math.cos(t),47*math.sin(t)
        shell=shell.fuse(cyl(5,top,-8,x,y))
        shell=shell.cut(cyl(2.25,top+3,-7,x,y))
    # Type-C cable feedthrough opening. This is a geometric proxy only; a
    # pressure-rated connector/gland must be selected before sealing the pod.
    shell=shell.cut(box(-70,-61,-4.5,4.5,-222.6,-219.4))
    # An annular gasket seat, a visual machining allowance only.
    groove=cyl(59,bottom,bottom+1.8).cut(cyl(56,bottom-1,bottom+2.8))
    shell=shell.cut(groove).clean()
    lid=cyl(r+7,bottom-10,bottom)
    lip=cyl(inner-0.6,bottom,bottom+3.0)
    lid=lid.fuse(lip)
    lid=lid.cut(cyl(c["shore_tether_port_bore_mm"]/2,bottom-11,bottom+4)).clean()
    fasteners=CFG["canister"]["flange_fastener_pattern"]
    for i in range(fasteners["count"]):
        angle=360*i/fasteners["count"]
        diameter=fasteners["clearance_diameters_mm"][i%len(fasteners["clearance_diameters_mm"])]
        t=math.radians(angle)
        x,y=fasteners["radius_mm"]*math.cos(t),fasteners["radius_mm"]*math.sin(t)
        shell=shell.cut(cyl(diameter/2,bottom-.2,bottom+8.2,x,y))
        lid=lid.cut(cyl(diameter/2,bottom-10.2,bottom+.2,x,y))
    # Separate gland body proxy aligns to the tether bore.
    gland=cyl(9,bottom-18,bottom-7).cut(cyl(6,bottom-19,bottom-6))
    return shell,lid,gland


def make_battery():
    b=CFG["battery"]
    # Four joined sleeves leave the surrounding annulus for three ESCs.
    # All four cell terminals face the top and bottom service spaces.
    holder=None
    cells={}
    cell_positions=((-32.5,-12.5),(-7.5,-12.5),(-32.5,12.5),(-7.5,12.5))
    for i,(x,y) in enumerate(cell_positions,1):
        sleeve=cyl(12.9,-106,-32,x,y)
        holder=sleeve if holder is None else holder.fuse(sleeve)
        cells[f"21700_cell_{i}"]=cyl(b["envelope_diameter_mm"]/2,-104,-104+b["envelope_length_mm"],x,y)
    for x,y in cell_positions:
        holder=holder.cut(cyl(11.4,-107,-31,x,y))
    holder=holder.clean()
    # Two posts meet the carrier below the cell ends and join the lower deck.
    post_a=cyl(2.5,-226,-106,-20,-34)
    post_b=cyl(2.5,-226,-106,-20,34)
    top_a=box(-23,-17,-37,-31,-32,-30)
    top_b=box(-23,-17,31,37,-32,-30)
    return {"battery_carrier":holder,"battery_support_A":post_a,"battery_support_B":post_b,
            "battery_top_pad_A":top_a,"battery_top_pad_B":top_b,**cells}


def make_electronics():
    items={}
    # Three seller-matched mini ESC envelopes sit close to their motor ports.
    # The user-confirmed 3 mm diameter and 25 mm axial length are modeled as
    # cylindrical proxies; wiring/thermal ratings remain unverified.
    for i,angle in enumerate((0,120,240),1):
        t=math.radians(angle)
        x,y=60*math.cos(t),60*math.sin(t)
        esc=cyl(1.5,-92.5,-67.5,x,y)
        rings=[]
        for z0 in (-91.5,-70.5):
            rings.append(cyl(3.1,z0,z0+2,x,y).cut(cyl(1.6,z0-.1,z0+2.1,x,y)))
        clip=cq.Compound.makeCompound(rings)
        items[f"ESC_{i}_envelope"]=esc
        items[f"ESC_{i}_mount_clips"]=clip
    # The long STM32 board and regulator stand vertically in separated
    # circumferential lanes. Cells and the UPS occupy the remaining axial and
    # radial space without overlapping their board envelopes.
    items["STM32_controller_envelope"]=box(13,31,-43.75,43.75,-202,-50)
    items["voltage_regulator_envelope"]=box(-39.5,-.5,-40,40,-210,-110)
    items["UPS_module_envelope"]=box(-7,11,28,60,-104.9,-52.1)
    items["BMS_envelope"]=box(-26,-8,-22.5,22.5,-223,-211)
    pd=CFG["electronic_envelopes_mm"]["usb_c_pd_input"]
    items["USB_C_PD_input_envelope"]=box(-61,-61+pd["length"],-pd["width"]/2,pd["width"]/2,
                                              -223,-223+pd["height"])
    items["USB_C_receptacle_proxy"]=box(-69,-61,-4.5,4.5,-222.5,-219.5)
    items["boost_24V_envelope"]=box(2.5,47.5,-15,15,-218,-206)
    # Two longitudinal mounting rails per tall board provide an adjustable
    # M3/M4/M5 clearance pattern. PCB hole coordinates remain to be measured.
    def rail(x0,x1,y0,y1,z0,z1,y_hole,z_holes):
        shape=box(x0,x1,y0,y1,z0,z1)
        sizes=(3.3,4.3,5.3)
        cuts=[]
        for i,z in enumerate(z_holes):
            cuts.append(x_cyl(sizes[i%3]/2,x0-1,x1+1,y_hole,z))
        return shape.cut(cq.Compound.makeCompound(cuts)).clean()
    cavity=cyl(CFG["canister"]["inner_diameter_mm"]/2,
               CFG["canister"]["body_bottom_z_mm"],CFG["canister"]["top_z_mm"])
    for label,ylo,yhi,yhole in (("low",-44,-36.5,-40.25),("high",36.5,44,40.25)):
        items[f"STM32_M3_M4_M5_mount_rail_{label}"]=rail(31,50,ylo,yhi,-202,-50,yhole,
                                                          (-194,-166,-138,-110,-82,-58)).intersect(cavity).clean()
    for label,ylo,yhi,yhole in (("low",-40,-32.5,-36.25),("high",32.5,40,36.25)):
        items[f"regulator_M3_M4_M5_mount_rail_{label}"]=rail(-52,-39.5,ylo,yhi,-210,-110,yhole,
                                                               (-202,-180,-158,-136,-118)).intersect(cavity).clean()
    # Bottom service deck carries the small power-management boards.
    items["service_deck"]=cyl(60,-227,-224).cut(cyl(8,-228,-223))
    for i,angle in enumerate((0,120,240),1):
        items[f"service_deck_shell_tab_{i}"]=rotate(box(52,61,-4,4,-227,-224),angle)
    items["PD_input_mount_shelf"]=box(-62,-32,-12,12,-224,-223)
    items["boost_mount_shelf"]=box(1,49,-17,17,-220,-218)
    items["BMS_cradle"]=box(-27,-7,-24,24,-224,-223)
    # Three sizes of spare screw interfaces are also provided in the flange;
    # these internal rails are for adjustable electronic mounting only.
    items["power_harness_corridor"]=cyl(1.4,-226,-37,0,-61)
    items["signal_harness_corridor"]=cyl(1.2,-202,-46,0,61)
    return items


def make_wire_proxies():
    routes={}
    # Battery and shore inputs converge at the UPS module; Type-C PD power is
    # boosted to 24 V and enters the UPS auxiliary input.
    for i,x in enumerate((-3.5,3.5),1):
        routes[f"battery_to_BMS_{i}"]=wire([(x,-31,-101),(x,-48,-112),(-49,-48,-178),(-18,-22,-217)],0.75)
    routes["BMS_to_UPS_backup"]=wire([(-8,0,-217),(0,25,-205),(0,58,-180),(2,59,-105),(2,59,-80)],1.0)
    routes["shore_to_UPS_main"]=wire([(0,0,-242),(0,0,-230),(0,0,-226),(0,20,-220),(0,58,-210),(0,61,-160),(0,61,-110),(2,59,-80)],1.0)
    routes["USB_C_to_PD"]=wire([(-70,0,-221),(-61,0,-221)],1.2)
    routes["PD_to_boost_24V"]=wire([(-47,0,-221),(-40,-28,-220),(-18,-28,-216),(2.5,-12,-212)],0.9)
    routes["boost_24V_to_UPS_aux"]=wire([(25,0,-206),(25,49,-206),(2,59,-190),(2,59,-105),(2,59,-80)],1.0)
    routes["UPS_to_ESC_bus"]=wire([(2,59,-80),(35,51,-80),(59,0,-80)],1.0)
    routes["controller_signal_bus"]=wire([(22,0,-198),(40,0,-190),(60,0,-170)],0.65)
    for i,angle in enumerate((0,120,240),1):
        t=math.radians(angle)
        p=lambda r,z:(r*math.cos(t),r*math.sin(t),z)
        routes[f"ESC_{i}_power_branch"]=wire([(59*math.cos(math.radians(0)),59*math.sin(math.radians(0)),-80),p(60,-80)],0.85)
        routes[f"ESC_{i}_to_motor_port"]=wire([p(60,-76),p(65,-76),p(69,-76)],1.0)
        routes[f"motor_{i}_external_harness"]=wire([p(69,-76),p(79,-76),p(81,-57),p(100,-55)],1.5)
    return routes


def make_tendons_and_guides(mount,motor_cfg):
    parts={}
    hole_radius=motor_cfg["plate"]["tendon_hole_radius_mm"]
    for i,angle in enumerate((0,120,240),1):
        t=math.radians(angle)
        rad=np.array([math.cos(t),math.sin(t)])
        tan=np.array([-math.sin(t),math.cos(t)])
        # Each motor-side spool proxy feeds below the disk, passes the outer
        # guide, and turns vertically through its matching drilled disk hole.
        p=np.array([100*rad[0]+58*tan[0],100*rad[1]+58*tan[1],-33.5])
        u=np.array([100*rad[0]+65*tan[0],100*rad[1]+65*tan[1],-10.5])
        v=np.array([64*rad[0]+65*tan[0],64*rad[1]+65*tan[1],-10.5])
        g=np.array([64*rad[0],64*rad[1],-10.5])
        h=np.array([hole_radius*rad[0],hole_radius*rad[1],-10.5])
        h_up=np.array([hole_radius*rad[0],hole_radius*rad[1],0.2])
        parts[f"tendon_{i}_route_proxy"]=wire([p,u,v,g,h,h_up],0.65)
        guide=box(59,69,-9,9,-14,-8)
        guide=guide.cut(box(58,70,-1.5,1.5,-12,-9))
        guide=guide.cut(box(62,66,-10,10,-12,-9)).clean()
        parts[f"tendon_{i}_guide_proxy"]=rotate(guide,angle)
    return parts


def color(name):
    if name.startswith("21700"): return cq.Color(0.53,0.69,0.36)
    if name.startswith("ESC_") and "envelope" in name: return cq.Color(0.91,0.48,0.23)
    if name=="UPS_module_envelope": return cq.Color(0.78,0.24,0.27)
    if name=="STM32_controller_envelope": return cq.Color(0.23,0.56,0.84)
    if name=="voltage_regulator_envelope": return cq.Color(0.82,0.68,0.18)
    if name=="USB_C_PD_input_envelope": return cq.Color(0.54,0.40,0.78)
    if name=="boost_24V_envelope": return cq.Color(0.91,0.56,0.18)
    if name=="BMS_envelope": return cq.Color(0.91,0.71,0.21)
    if "harness" in name or "route_proxy" in name or "to_" in name: return cq.Color(0.75,0.18,0.18)
    return cq.Color(0.52,0.58,0.62)


def add_parts(ass, parts, exploded=False):
    for name,shape in parts.items():
        dz=-18 if exploded and name in ("service_deck","BMS_post") else 0
        ass.add(shape.translate(cq.Vector(0,0,dz)),name=name,color=color(name))


def mesh(ax,shape,col,alpha=1,deflection=2.0):
    vertices,faces=shape.tessellate(deflection,0.30)
    if not faces: return
    p=np.array([[v.x,v.y,v.z] for v in vertices])
    f=np.array(faces,dtype=int)
    ax.add_collection3d(Poly3DCollection(p[f],facecolors=col,edgecolors="none",alpha=alpha))


def preview(mount,shell,lid,parts,tendons,motor_cfg):
    from matplotlib.patches import Circle
    fig=plt.figure(figsize=(18,10),dpi=140,facecolor="#f3f5f7")
    a=fig.add_subplot(1,3,1,projection="3d")
    mesh(a,mount.arm,"#cb784d",0.95,4)
    mesh(a,mount.plate,"#4a677b",0.96)
    for m in mount.motors: mesh(a,m,"#469ba6",0.96)
    for spool in mount.spools: mesh(a,spool,"#d4a52d",0.98)
    mesh(a,shell,"#334b61",0.95)
    mesh(a,lid,"#bb8650",0.98)
    a.set(xlim=(-140,140),ylim=(-140,140),zlim=(-270,560))
    a.set_box_aspect((280,280,830));a.view_init(elev=13,azim=-55);a.set_proj_type("ortho");a.set_axis_off()
    a.set_title("总装：电子仓在电机原占位区中央\n三台电机保留在湿侧外圈",fontsize=12)
    b=fig.add_subplot(1,3,2)
    b.set_aspect("equal");b.set_xlim(-138,138);b.set_ylim(-138,138);b.axis("off")
    b.add_patch(Circle((0,0),130,facecolor="#4a677b",edgecolor="#344d61",alpha=.12,linewidth=2))
    b.add_patch(Circle((0,0),68,facecolor="#334b61",edgecolor="#334b61",alpha=.14,linewidth=2))
    b.add_patch(Circle((0,0),64,fill=False,edgecolor="#bd7048",linestyle="--",linewidth=1.2))
    route_colors=("#ce3c36","#8b4bb0","#168b79")
    spool_offset=motor_cfg["layout"]["spool_center_offset_from_motor_center_mm"]
    spool_half_width=motor_cfg["spool_proxy"]["axial_width_mm"]/2
    motor_radius=motor_cfg["motor_reference"]["outer_diameter_mm"]/2
    hole_radius=motor_cfg["plate"]["tendon_hole_radius_mm"]
    for i,angle in enumerate((0,120,240),1):
        t=math.radians(angle);rad=np.array([math.cos(t),math.sin(t)]);tan=np.array([-math.sin(t),math.cos(t)])
        center=CFG["motor_center_radius_mm"]*rad
        spool_center=center+spool_offset*tan
        hole=hole_radius*rad
        b.add_patch(Circle(tuple(center),motor_radius,facecolor="#469ba6",edgecolor="#286a73",alpha=.86,linewidth=1.2))
        b.add_patch(Circle(tuple(spool_center),motor_cfg["spool_proxy"]["flange_outer_radius_mm"],facecolor="#d4a52d",edgecolor="#86620f",linewidth=1.2))
        b.add_patch(Circle(tuple(hole),2.1,facecolor="#f4f5f6",edgecolor="#252d32",linewidth=1.0,zorder=5))
        cable_points=np.array([CFG["motor_center_radius_mm"]*rad+(spool_offset+spool_half_width)*tan,
                               CFG["motor_center_radius_mm"]*rad+(spool_offset+11)*tan,
                               64*rad+65*tan,64*rad,hole])
        b.plot(cable_points[:,0],cable_points[:,1],color=route_colors[i-1],linewidth=1.8,zorder=4)
        b.text(spool_center[0],spool_center[1],f"卷{i}",ha="center",va="center",fontsize=7,color="#322a17",zorder=6)
        b.text(hole[0]+5*rad[0],hole[1]+5*rad[1],f"孔{i}",ha="center",va="center",fontsize=7,color="#252d32")
    b.text(0,-137,"蓝：湿侧电机　金：卷筒代理　彩线：拉索路线",ha="center",va="bottom",fontsize=8,color="#43515a")
    b.set_title("俯视根部：三只湿侧卷筒代理\n拉索经圆盘三孔穿入机械臂根部",fontsize=12)
    d=fig.add_subplot(1,3,3,projection="3d")
    mesh(d,shell,"#334b61",0.07)
    for name,shape in parts.items():
        if name.startswith("21700"): col,alpha="#93b455",0.98
        elif name.startswith("ESC_") and "envelope" in name:col,alpha="#e77b39",0.98
        elif name=="UPS_module_envelope":col,alpha="#c84242",0.98
        elif name=="STM32_controller_envelope":col,alpha="#338ac7",0.98
        elif name=="voltage_regulator_envelope":col,alpha="#ddb833",0.94
        elif name=="USB_C_PD_input_envelope":col,alpha="#8869ba",0.98
        elif name=="USB_C_receptacle_proxy":col,alpha="#543986",0.98
        elif name=="boost_24V_envelope":col,alpha="#e59028",0.98
        elif name=="BMS_envelope":col,alpha="#ddb833",0.98
        elif name in ("battery_carrier","service_deck"):col,alpha="#566672",0.16
        elif "mount" in name or "rail" in name or "post" in name or "cradle" in name or "shelf" in name or "clips" in name:col,alpha="#8998a1",0.58
        else:continue
        mesh(d,shape,col,alpha,1.2)
    d.set(xlim=(-70,70),ylim=(-70,70),zlim=(-242,-18))
    d.set_box_aspect((140,140,224));d.view_init(elev=17,azim=-52);d.set_proj_type("ortho");d.set_axis_off()
    d.set_title("内部：主控与稳压板竖装，电池错位\nUPS 输入含 Type-C PD + 24 V 升压支路",fontsize=12)
    fig.suptitle("B32 中央电子仓重画｜装配位置与物理布线候选",fontsize=18,y=.98)
    fig.text(.5,.025,"卷筒代理：有效半径 6.5 / 法兰半径 10 / 宽 8 mm；圆盘孔 3×Ø4.2，R30.6，120°。Type-C 板厚 5 mm。",ha="center",fontsize=10,color="#43515a")
    fig.subplots_adjust(left=.01,right=.99,bottom=.08,top=.89,wspace=.03)
    fig.savefig(OUT_IMG,dpi=140,bbox_inches="tight",facecolor=fig.get_facecolor())
    plt.close(fig)


def wiring_preview():
    from matplotlib.patches import Circle, Rectangle, FancyArrowPatch
    fig=plt.figure(figsize=(18,9),dpi=150,facecolor="#f3f5f7")
    ax=fig.add_subplot(1,3,1)
    ax.set_xlim(-72,72);ax.set_ylim(-72,72);ax.set_aspect("equal");ax.axis("off")
    ax.add_patch(Circle((0,0),68,fill=False,linewidth=3,edgecolor="#344d61"))
    ax.add_patch(Circle((0,0),63,fill=False,linewidth=1,linestyle="--",edgecolor="#79909e"))
    # This slice is z=-90 mm, where the controller, cell pack, UPS and ESCs
    # share the cavity. Lower-layer regulator/PD/boost boards are shown in the
    # axial panel instead of being overlaid here.
    ax.add_patch(Rectangle((13,-43.75),18,87.5,facecolor="#338ac7",alpha=.78,edgecolor="#1b5f8d"))
    ax.text(22,0,"STM32",ha="center",va="center",fontsize=9,color="white",rotation=90)
    for x in (-32.5,-7.5):
        for y in (-12.5,12.5):
            ax.add_patch(Circle((x,y),10.775,facecolor="#93b455",edgecolor="#516c36"))
    ax.text(-20,0,"4S",ha="center",va="center",fontsize=7,color="#24321d")
    ax.add_patch(Rectangle((-7,28),18,32,facecolor="#c84242",alpha=.82,edgecolor="#8c2020"))
    ax.text(2,44,"UPS",ha="center",va="center",fontsize=8,color="white",rotation=90)
    for i,a in enumerate((0,120,240),1):
        t=math.radians(a);x,y=60*math.cos(t),60*math.sin(t)
        ax.add_patch(Circle((x,y),1.5,facecolor="#e77b39",edgecolor="#a9491d"))
        ax.text(x*1.1,y*1.1,f"E{i}",ha="center",va="center",fontsize=7)
    ax.set_title("横截面 z=-90 mm\n主控 / 电池 / UPS / ESC 实际层位",fontsize=13,pad=16)

    bx=fig.add_subplot(1,3,2)
    bx.set_xlim(-235,-20);bx.set_ylim(-70,70);bx.set_aspect("auto");bx.axis("off")
    bx.add_patch(Rectangle((-230,-68),210,136,fill=False,linewidth=3,edgecolor="#344d61"))
    def zbar(z0,z1,label,color,x=0,w=16):
        bx.add_patch(Rectangle((z0,x-w/2),z1-z0,w,facecolor=color,alpha=.9,edgecolor="white"))
        bx.text((z0+z1)/2,x,label,ha="center",va="center",fontsize=8,color="white")
    zbar(-202,-50,"STM32", "#338ac7",32,10)
    zbar(-210,-110,"稳压器", "#b88e16",-20,12)
    zbar(-104,-34,"电芯", "#7b9c45",-20,12)
    zbar(-105,-52,"UPS", "#c84242",44,10)
    # These boards are only 4 mm and 12 mm thick along the plotted Z axis, so
    # keep the actual envelopes clean and label them with leaders outside the bars.
    zbar(-223,-219,"", "#7452a0",-47,18)
    zbar(-218,-206,"", "#e59028",25,18)
    bx.annotate("Type-C PD",xy=(-221,-47),xytext=(-198,-53),fontsize=7,color="#283946",
                arrowprops={"arrowstyle":"->","color":"#7452a0","lw":1.0},ha="left",va="center")
    bx.annotate("24 V 升压板",xy=(-212,25),xytext=(-193,10),fontsize=7,color="#283946",
                arrowprops={"arrowstyle":"->","color":"#e59028","lw":1.0},ha="left",va="center")
    zbar(-92.5,-67.5,"3×ESC", "#e77b39",-57,8)
    zbar(-223,-211,"BMS", "#c39c1d",-17,10)
    bx.set_title("轴向位置与分层\n不同颜色条表示实际 Z 范围",fontsize=13,pad=16)

    cx=fig.add_subplot(1,3,3)
    cx.set_xlim(0,10);cx.set_ylim(0,10);cx.axis("off")
    def node(x,y,label,col,w=2.0,h=.68,fs=9):
        cx.add_patch(Rectangle((x-w/2,y-h/2),w,h,facecolor=col,edgecolor="#ffffff",linewidth=1.4))
        cx.text(x,y,label,ha="center",va="center",fontsize=fs,color="white")
    def arr(a,b,col="#4b5964",lw=1.8):
        cx.add_patch(FancyArrowPatch(a,b,arrowstyle="-|>",mutation_scale=11,linewidth=lw,color=col,connectionstyle="arc3"))
    node(1.5,8.8,"岸上隔离 24 V","#c84242",w=2.4)
    node(5.0,8.8,"UPS 模块","#aa3440",w=2.2)
    node(1.5,6.9,"4S 21700 电池","#7b9c45",w=2.3)
    node(4.0,6.9,"BMS","#b88e16",w=1.4)
    node(1.5,5.0,"USB-C PD 输入","#7452a0",w=2.3)
    node(4.0,5.0,"24 V 升压","#e59028",w=1.8)
    arr((2.7,8.8),(3.9,8.8),"#c84242")
    arr((2.65,6.9),(3.3,6.9),"#7b9c45")
    arr((4.65,7.2),(4.9,8.45),"#b88e16")
    arr((2.65,5.0),(3.05,5.0),"#7452a0")
    arr((4.9,5.35),(5.0,8.45),"#e59028")
    # UPS output bus and three motor branches.
    cx.plot([6.1,6.25,6.25],[8.8,8.8,2.7],color="#c84242",linewidth=1.8)
    for i,y in enumerate((5.9,4.3,2.7),1):
        node(7.5,y,f"ESC {i} 12–24 V","#d87836",w=1.8,fs=8)
        node(9.35,y,f"湿侧电机 {i}","#388c97",w=1.5,fs=8)
        arr((6.25,y),(6.6,y),"#c84242",1.5)
        arr((8.4,y),(8.6,y),"#c84242",1.5)
    node(2.0,2.8,"STM32 主控","#338ac7",w=2.0)
    node(4.5,2.8,"稳压器","#b88e16",w=1.7)
    arr((5.0,8.45),(4.65,3.2),"#b88e16",1.3)
    arr((3.0,2.8),(3.6,2.8),"#338ac7",1.5)
    cx.plot([5.35,5.7,5.7],[2.8,2.8,5.9],color="#338ac7",linewidth=1.5)
    for y in (5.9,4.3,2.7):
        arr((5.7,y),(6.6,y),"#338ac7",1.2)
    cx.text(5,.55,"红：电机主电源　蓝：STM32 控制　紫/橙：Type-C 辅助输入与升压\nType-C 接 UPS 辅助输入，不按三台电机的主供电定额",ha="center",fontsize=8,color="#465560")
    cx.set_title("供电与控制关系\nUPS 主输入 / 电池 / Type-C 辅助输入",fontsize=13,pad=16)
    fig.suptitle("B32 中央电子仓：模块安装、螺丝接口与接线关系",fontsize=18,y=.98)
    fig.subplots_adjust(left=.025,right=.99,bottom=.06,top=.86,wspace=.08)
    fig.savefig(OUT_WIRING,dpi=150,bbox_inches="tight",facecolor=fig.get_facecolor())
    plt.close(fig)


def audit(mount,shell,lid,parts,wiring,tendons,motor_cfg):
    c=CFG["canister"]
    core=[name for name in parts if name.startswith("21700") or name.endswith("envelope")]
    overlaps=[]
    for i,name in enumerate(core):
        for other in core[i+1:]:
            if parts[name].intersect(parts[other]).Volume()>0.01:
                overlaps.append([name,other])
    cavity=cyl(c["inner_diameter_mm"]/2,c["body_bottom_z_mm"]+4,c["top_z_mm"]-c["top_wall_mm"])
    outside=[]
    for name in core:
        if parts[name].cut(cavity).Volume()>0.01:outside.append(name)
    shell_clearance=min(shell.distance(m) for m in mount.motors)
    saddle_clearance=min(shell.distance(s) for s in mount.saddles)
    if overlaps or outside or shell_clearance<=0 or saddle_clearance<=0:
        raise RuntimeError(f"Fit failure: overlaps={overlaps}; outside={outside}; motor gap={shell_clearance}; saddle gap={saddle_clearance}")
    lid_component_overlaps=[name for name,shape in parts.items() if shape.intersect(lid).Volume()>0.01]
    if lid_component_overlaps:
        raise RuntimeError(f"Removable lid collides with installed parts: {lid_component_overlaps}")
    tendon_hits={}
    for name,shape in tendons.items():
        if "route_proxy" not in name:continue
        solids=[shell,mount.plate,*mount.motors,*mount.saddles]
        total=sum(shape.intersect(s).Volume() for s in solids)
        if total>0.01:tendon_hits[name]=round(total,3)
    if tendon_hits:
        raise RuntimeError(f"Tendon route crosses hard geometry: {tendon_hits}")
    port_hits={name:round(shape.intersect(shell).Volume()+shape.intersect(lid).Volume(),3)
               for name,shape in wiring.items()
               if "motor_port" in name or "external_harness" in name or
               name in ("shore_to_UPS_main","USB_C_to_PD")}
    if any(value>0.01 for value in port_hits.values()):
        raise RuntimeError(f"A wire proxy misses its canister port: {port_hits}")
    return {"candidate":"centerline_canister_v3","release_status":CFG["status"],
            "original_arm_sha256":motor_module.sha256((MOTOR_SCRIPT.parent/"../paper_v1/B32_550mm_SpiRobs_打印实体.step").resolve()),
            "motor_count":len(mount.motors),"motor_centers_mm":mount.motor_centers,
            "base_plate_diameter_mm":CFG["base_plate_diameter_mm"],
            "blind_post_compatible_plate_holes":3,
            "bottom_lid_flange_fastener_holes":CFG["canister"]["flange_fastener_pattern"]["count"],
            "bottom_lid_fastener_sizes_and_counts":{"M3":4,"M4":4,"M5":4},
            "internal_rail_fastener_clearances_mm":[3.3,4.3,5.3],
            "battery":{"cells":4,"capacity_mAh_per_cell_user_confirmed":CFG["battery"]["capacity_mAh_each_user_confirmed"],
                       "topology":"4S1P_assumption",
                       "nominal_voltage_v_per_cell_user_confirmed":CFG["battery"]["nominal_voltage_v_each_user_confirmed"],
                       "nominal_voltage_estimate_v":4*CFG["battery"]["nominal_voltage_v_each_user_confirmed"],
                       "nominal_energy_estimate_Wh":4*CFG["battery"]["nominal_voltage_v_each_user_confirmed"]*CFG["battery"]["capacity_mAh_each_user_confirmed"]/1000,
                       "cell_model_and_discharge_rating_verified":False},
            "canister_outer_diameter_mm":c["outer_diameter_mm"],
            "bottom_flange_outer_diameter_mm":c["outer_diameter_mm"]+14,
            "canister_body_with_lid_height_mm":c["top_z_mm"]-(c["body_bottom_z_mm"]-10),
            "including_tether_gland_height_mm":c["top_z_mm"]-(c["body_bottom_z_mm"]-18),
            "min_motor_to_canister_mm":round(shell_clearance,3),
            "min_saddle_to_canister_mm":round(saddle_clearance,3),
            "component_envelope_overlap_pairs":overlaps,"components_outside_inner_cavity":outside,
            "lid_component_overlap_pairs":lid_component_overlaps,
            "tendon_route_hard_part_overlap_mm3":tendon_hits,
            "penetrator_route_wall_overlap_mm3":port_hits,
            "wet_motor_port_count":3,"shore_port_count":1,
            "mounting_method":"three M4 blind top posts; 12 bottom flange holes (4 each M3/M4/M5); adjustable M3/M4/M5 internal rails; removable 21700 carrier",
            "spool_positions":{"count":len(mount.spools),"placement":"one proxy at the positive-tangent output end of each of the three wet-side motor envelopes","effective_radius_mm":motor_cfg["spool_proxy"]["effective_radius_mm"],"flange_outer_radius_mm":motor_cfg["spool_proxy"]["flange_outer_radius_mm"],"axial_width_mm":motor_cfg["spool_proxy"]["axial_width_mm"],"status":"schematic proxy; shaft coupling, retention, groove and winding capacity unverified"},
            "tendon_disk_holes":{"count":len(mount.tendon_hole_centers),"center_radius_mm":motor_cfg["plate"]["tendon_hole_radius_mm"],"diameter_mm":motor_cfg["plate"]["tendon_hole_diameter_mm"],"angles_deg":motor_cfg["plate"]["tendon_hole_angles_deg"],"status":"through-holes in the base disk; route proxy passes through each corresponding hole"},
            "hardware_envelopes_user_confirmed":CFG["electronic_envelopes_mm"],
            "power_inputs":CFG["power_inputs"],
            "wiring_corridors":"24 V isolated shore input and 4S battery/BMS to UPS; USB-C PD to 24 V boost to UPS auxiliary input; three radial ESC outputs; STM32 signal bus",
            "tendon_route":"three motor-side spool proxies -> exterior guide r64 -> matching base-disk holes at radius 30.6 mm -> arm root; line path is geometric proxy",
            "unverified":["mini ESC manufacturer drawing, current rating, internal mounting detail and thermal behavior","actual PCB screw coordinates; M3/M4/M5 rails are adjustable generic provision","USB-C panel feedthrough sealing and boost-module power/current rating","UPS behavior with shore, battery, and USB-C auxiliary input simultaneously","cell model, discharge rating and 4S1P safety design","certified 5 m gland, gasket and pressure test","heat dissipation, cable bend radius, connector strain relief","runtime and UPS transfer under measured load"]}


def main():
    mc=motor_module.load_config()
    mc["layout"]["motor_center_radius_mm"]=CFG["motor_center_radius_mm"]
    mc["plate"]["diameter_mm"]=CFG["base_plate_diameter_mm"]
    mc["plate"]["fixture_hole_radius_mm"]=CFG["base_plate_fixture_radius_mm"]
    mount=motor_module.build_motor_mount(mc)
    # The original motor mount has no fasteners for a central canister. Add
    # three holes directly over the canister's blind top posts, keeping the
    # frozen arm and root retainer unchanged.
    post_cuts=[]
    for angle in (60,180,300):
        t=math.radians(angle)
        post_cuts.append(cyl(2.15,-8.2,.2,47*math.cos(t),47*math.sin(t)))
    mount.plate=mount.plate.cut(cq.Compound.makeCompound(post_cuts)).clean()
    shell,lid,gland=make_shell()
    parts={**make_battery(),**make_electronics()}
    wiring=make_wire_proxies()
    tendons=make_tendons_and_guides(mount,mc)
    report=audit(mount,shell,lid,parts,wiring,tendons,mc)
    assembly=cq.Assembly(name="B32_centerline_dry_canister_external_wet_motors")
    assembly.add(mount.arm,name="unmodified_B32_arm",color=cq.Color(.81,.38,.22))
    assembly.add(mount.plate,name="plate_260mm_with_canister_mount",color=cq.Color(.22,.34,.43))
    for i,shape in enumerate(mount.root_rims,1):
        assembly.add(shape,name=f"root_retainer_{i}",color=cq.Color(.68,.30,.20))
    for i,shape in enumerate(mount.saddles,1):
        assembly.add(shape,name=f"wet_motor_saddle_{i}",color=cq.Color(.77,.42,.27))
    for i,(motor,spool,shaft) in enumerate(zip(mount.motors,mount.spools,mount.shafts),1):
        assembly.add(motor,name=f"external_wet_motor_{i}_envelope",color=cq.Color(.32,.61,.67))
        assembly.add(spool,name=f"spool_{i}_proxy",color=cq.Color(.40,.43,.47))
        assembly.add(shaft,name=f"shaft_{i}_proxy",color=cq.Color(.56,.58,.61))
    assembly.add(shell,name="centerline_dry_canister",color=cq.Color(.25,.35,.45))
    assembly.add(lid,name="removable_bottom_lid",color=cq.Color(.68,.45,.25))
    assembly.add(gland,name="shore_tether_gland_proxy",color=cq.Color(.45,.45,.48))
    add_parts(assembly,parts)
    add_parts(assembly,wiring)
    add_parts(assembly,tendons)
    assembly.export(str(OUT_STEP),exportType="STEP",unit="MM")
    opened=cq.Assembly(name="B32_centerline_canister_opened")
    opened.add(shell,name="central_shell",color=cq.Color(.25,.35,.45))
    opened.add(lid.translate(cq.Vector(0,0,-25)),name="bottom_lid_exploded",color=cq.Color(.68,.45,.25))
    add_parts(opened,parts)
    add_parts(opened,wiring)
    opened.export(str(OUT_OPEN),exportType="STEP",unit="MM")
    preview(mount,shell,lid,parts,tendons,mc)
    wiring_preview()
    report["files"]={"assembly_step":OUT_STEP.name,"open_step":OUT_OPEN.name,"preview":OUT_IMG.name,
                     "mounting_and_wiring":OUT_WIRING.name}
    report["step_readback"]={"assembly_valid":cq.importers.importStep(str(OUT_STEP)).val().isValid(),
                             "open_valid":cq.importers.importStep(str(OUT_OPEN)).val().isValid()}
    OUT_AUDIT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"report":OUT_AUDIT.name,"motor_gap_mm":report["min_motor_to_canister_mm"],
                      "saddle_gap_mm":report["min_saddle_to_canister_mm"],"step_readback":report["step_readback"]},ensure_ascii=False))


if __name__=="__main__": main()
