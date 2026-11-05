from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cadquery as cq
import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
OFFICIAL_STEP = (HERE.parent / "electronics_enclosure_v18" / "references" /
                 "official" / "DJI_M3508_P19_official.stp")

P = {
    "part": "M3508 D轴套联轴套 CNC 首件图 Rev A",
    "units": "mm",
    "source_step": str(OFFICIAL_STEP),
    "source_step_sha256": hashlib.sha256(OFFICIAL_STEP.read_bytes()).hexdigest().upper(),
    "motor_shaft_nominal": {
        "diameter_mm": 10.0,
        "across_flat_mm": 9.0,
        "D_engagement_mm": 12.3,
        "axial_thread": "M5-6H, nominal thread depth 10 mm",
        "status": "nominal dimensions measured from official DJI STEP; verify actual motor before machining"
    },
    "sleeve": {
        "overall_length_mm": 20.0,
        "outer_diameter_mm": 16.0,
        "motor_D_bore_circle_diameter_mm": 10.2,
        "motor_D_bore_across_flat_mm": 9.2,
        "motor_D_bore_depth_mm": 12.3,
        "extension_shaft_bore_diameter_mm": 10.2,
        "extension_shaft_bore_depth_mm": 7.7,
        "M3_tap_drill_mm": 2.5,
        "M3_count": 2,
        "M3_spacing_deg": 180.0,
        "M3_center_from_motor_face_mm": 16.2,
        "end_chamfer_mm": 0.3,
        "seal_land_start_mm_from_motor_face": 0.5,
        "seal_land_width_mm": 7.0,
        "seal_size": "16 x 35 x 7 mm, Freudenberg B2PT candidate 40412791",
        "material": "TBD: CNC metal; seawater corrosion resistance and seal-track hardness must both be approved",
        "seal_land_requirements": "Ø16 h11; roundness IT8; Rz 1.0-4.0 µm; Rmax <= 6.3 µm; hardness >=45 HRC; twist-free finish (verify with selected seal supplier)"
    },
    "status": "first-article CNC drawing; not a production release until motor D-shaft, extension shaft, seal, and material are confirmed"
}


def cyl(r: float, z0: float, z1: float) -> cq.Shape:
    return cq.Solid.makeCylinder(r, z1-z0, cq.Vector(0, 0, z0), cq.Vector(0, 0, 1))


def make_d_bore(radius: float, across_flat: float, z0: float, z1: float,
                flat_angle_deg: float) -> cq.Shape:
    flat_offset = across_flat - radius
    if not 0 < flat_offset < radius:
        raise ValueError("D-bore dimensions are inconsistent")
    circle = cyl(radius, z0-.01, z1+.01)
    flat_cut = cq.Solid.makeBox(radius+2-flat_offset, 2*radius+4, z1-z0+.04,
                                cq.Vector(flat_offset, -radius-2, z0-.02))
    flat_cut = flat_cut.rotate((0, 0, 0), (0, 0, 1), flat_angle_deg)
    return circle.cut(flat_cut).clean()


def make_part() -> cq.Shape:
    c = P["sleeve"]
    L = c["overall_length_mm"]
    chamfer = c["end_chamfer_mm"]
    odr = c["outer_diameter_mm"] / 2
    # Turned OD with a 0.3 x 45-degree edge break on each end.
    outside = cq.Solid.makeCone(odr-chamfer, odr, chamfer,
                                cq.Vector(0, 0, 0), cq.Vector(0, 0, 1))
    outside = outside.fuse(cyl(odr, chamfer, L-chamfer))
    outside = outside.fuse(cq.Solid.makeCone(odr, odr-chamfer, chamfer,
                                             cq.Vector(0, 0, L-chamfer), cq.Vector(0, 0, 1)))
    motor_bore = make_d_bore(
        c["motor_D_bore_circle_diameter_mm"]/2,
        c["motor_D_bore_across_flat_mm"],
        0, c["motor_D_bore_depth_mm"], 112.241273)
    ext_bore = cyl(c["extension_shaft_bore_diameter_mm"]/2,
                   c["motor_D_bore_depth_mm"], L)
    part = outside.cut(motor_bore).cut(ext_bore)
    # Two opposed M3 tap-drill passages through the wall into the extension socket.
    hole_r = c["M3_tap_drill_mm"]/2
    center_z = c["M3_center_from_motor_face_mm"]
    plus = cq.Solid.makeCylinder(hole_r, odr-5.0+.1,
                                 cq.Vector(0, odr+.1, center_z), cq.Vector(0, -1, 0))
    minus = cq.Solid.makeCylinder(hole_r, odr-5.0+.1,
                                  cq.Vector(0, -odr-.1, center_z), cq.Vector(0, 1, 0))
    part = part.cut(plus).cut(minus).clean()
    if not part.isValid() or len(part.Solids()) != 1:
        raise ValueError("Generated coupling sleeve is not a single valid solid")
    return part


def add_pdf_dim_h(ax, x1, x2, y, ext_y1, ext_y2, label, color="black"):
    ax.plot([x1, x1], [ext_y1, y], color=color, lw=.5)
    ax.plot([x2, x2], [ext_y2, y], color=color, lw=.5)
    ax.annotate("", xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="<->", lw=.65, color=color,
                                shrinkA=0, shrinkB=0, mutation_scale=7))
    ax.text((x1+x2)/2, y+1.5, label, ha="center", va="bottom", fontsize=7,
            color=color, bbox=dict(facecolor="white", edgecolor="none", pad=.4))


def add_pdf_dim_v(ax, x, y1, y2, ext_x1, ext_x2, label, color="black"):
    ax.plot([ext_x1, x], [y1, y1], color=color, lw=.5)
    ax.plot([ext_x2, x], [y2, y2], color=color, lw=.5)
    ax.annotate("", xy=(x, y2), xytext=(x, y1),
                arrowprops=dict(arrowstyle="<->", lw=.65, color=color,
                                shrinkA=0, shrinkB=0, mutation_scale=7))
    ax.text(x+1.5, (y1+y2)/2, label, ha="left", va="center", rotation=90,
            fontsize=7, color=color, bbox=dict(facecolor="white", edgecolor="none", pad=.4))


def pdf_sheet() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    c=P["sleeve"]
    fig = plt.figure(figsize=(16.54, 11.69), facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 420); ax.set_ylim(0, 297); ax.set_aspect("equal"); ax.axis("off")
    black = "#17212b"; blue = "#1672a4"; gray = "#687682"; light = "#eef2f5"
    ax.add_patch(Polygon([(8,8),(412,8),(412,289),(8,289)], closed=True,
                         fill=False, edgecolor=black, linewidth=.8))
    ax.text(16,278,"M3508 D轴套联轴套 — CNC首件图",fontsize=16,weight="bold",color=black)
    ax.text(16,270,"Rev A  |  单位：mm  |  视图比例：3:1（尺寸按标注值）",fontsize=8,color=gray)
    ax.text(16,261,"说明：该零件在现有 v20 布置上定型；D孔仅以官方STEP名义尺寸起算，首件须与实物电机校配。",
            fontsize=8,color=gray)

    # View A: motor-side D-bore end.
    sx = 2.7; cx, cy = 62, 210
    ax.add_patch(Circle((cx,cy),8*sx,fill=False,edgecolor=black,lw=1.0))
    R=5.1*sx; flat=4.1*sx
    ych=math.sqrt(R*R-flat*flat)
    th1=math.degrees(math.atan2(ych,flat)); th2=360-th1
    theta=[math.radians(th1+i*(th2-th1)/180) for i in range(181)]
    arcx=[cx+R*math.cos(t) for t in theta]; arcy=[cy+R*math.sin(t) for t in theta]
    ax.plot(arcx,arcy,color=black,lw=1.0)
    ax.plot([cx+flat,cx+flat],[cy-ych,cy+ych],color=black,lw=1.0)
    ax.plot([cx-24,cx+24],[cy,cy],color=gray,lw=.45,ls=(0,(7,2,1,2)))
    ax.plot([cx,cx],[cy-24,cy+24],color=gray,lw=.45,ls=(0,(7,2,1,2)))
    ax.text(cx,180,"A  电机端 / D孔",ha="center",fontsize=8,color=black)
    ax.annotate("D孔 Ø10.20 +0.05/0\nAF9.20 +0.05/0；深12.30±0.10",
                xy=(cx+flat,cy+ych*.2),xytext=(22,238),fontsize=7,color=black,
                arrowprops=dict(arrowstyle="->",lw=.6,color=gray))
    ax.annotate("Ø16 密封跑道",xy=(cx+8*sx,cy),xytext=(92,225),fontsize=7,color=blue,
                arrowprops=dict(arrowstyle="->",lw=.7,color=blue))

    # View B: extension-shaft socket end.
    cx2,cy2=140,210
    ax.add_patch(Circle((cx2,cy2),8*sx,fill=False,edgecolor=black,lw=1.0))
    ax.add_patch(Circle((cx2,cy2),5.1*sx,fill=False,edgecolor=black,lw=1.0))
    ax.plot([cx2-24,cx2+24],[cy2,cy2],color=gray,lw=.45,ls=(0,(7,2,1,2)))
    ax.plot([cx2,cx2],[cy2-24,cy2+24],color=gray,lw=.45,ls=(0,(7,2,1,2)))
    ax.text(cx2,180,"B  延长轴端 / 圆孔",ha="center",fontsize=8,color=black)
    ax.annotate("Ø10.20 +0.05/0\n深7.70±0.10",xy=(cx2+5.1*sx,cy2),xytext=(151,228),fontsize=7,color=black,
                arrowprops=dict(arrowstyle="->",lw=.6,color=gray))

    # Side view: 20 mm body and opposite M3 holes.
    x0,y0=203,210; L=sx*20; H=sx*16
    ax.plot([x0,x0+L],[y0-H/2,y0-H/2],color=black,lw=1)
    ax.plot([x0,x0+L],[y0+H/2,y0+H/2],color=black,lw=1)
    ax.plot([x0,x0],[y0-H/2+sx*.3,y0+H/2-sx*.3],color=black,lw=1)
    ax.plot([x0+L,x0+L],[y0-H/2+sx*.3,y0+H/2-sx*.3],color=black,lw=1)
    for xedge, yedge, dx, dy in [
        (x0,y0-H/2,x0+sx*.3,y0-H/2+sx*.3),
        (x0,y0+H/2,x0+sx*.3,y0+H/2-sx*.3),
        (x0+L,y0-H/2,x0+L-sx*.3,y0-H/2+sx*.3),
        (x0+L,y0+H/2,x0+L-sx*.3,y0+H/2-sx*.3)]:
        ax.plot([xedge,dx],[yedge,dy],color=black,lw=1)
    hole_x=x0+sx*16.2
    ax.add_patch(Circle((hole_x,y0),1.25*sx,fill=False,edgecolor=black,lw=.9))
    ax.plot([x0-4,x0+L+4],[y0,y0],color=gray,lw=.45,ls=(0,(7,2,1,2)))
    # Mark the seal journal on the cylindrical OD; this is machined, not printed.
    seal_x0=x0+sx*c["seal_land_start_mm_from_motor_face"]
    seal_x1=seal_x0+sx*c["seal_land_width_mm"]
    ax.plot([seal_x0,seal_x1],[y0+H/2,y0+H/2],color=blue,lw=2.0)
    ax.plot([seal_x0,seal_x1],[y0-H/2,y0-H/2],color=blue,lw=2.0)
    ax.text(x0+L/2,180,"侧视：M3径向紧定孔（另一侧相对 180°）",ha="center",fontsize=7.5,color=black)
    ax.annotate("Ø16 h11 密封跑道\n距电机端0.50，宽7.00",
                xy=(seal_x0+sx*3.5,y0+H/2),xytext=(263,188),fontsize=7,color=blue,
                arrowprops=dict(arrowstyle="->",lw=.7,color=blue))
    add_pdf_dim_h(ax,x0,x0+L,168, y0-H/2,y0-H/2,"20.00 ±0.05")
    add_pdf_dim_h(ax,x0,hole_x,156,y0-H/2,y0-H/2,"16.20（孔中心）")
    add_pdf_dim_v(ax,x0+L+11,y0-H/2,y0+H/2,x0+L,x0+L,"Ø16 h11")
    ax.annotate("2×M3×0.5-6H\n对置 180°，通至Ø10.2孔",
                xy=(hole_x,y0),xytext=(273,235),fontsize=7,color=black,
                arrowprops=dict(arrowstyle="->",lw=.6,color=gray))

    # Section A-A through the D flat and the axial socket.
    xx,yy=56,96; s=2.7; length=20*s; outer_h=16*s
    ax.add_patch(Polygon([(xx,yy-outer_h/2),(xx+length,yy-outer_h/2),
                          (xx+length,yy+outer_h/2),(xx,yy+outer_h/2)],
                         closed=True,facecolor=light,edgecolor=black,lw=1.0))
    # Inner void: D bore (one flat side) followed by the round extension socket.
    zsplit=xx+12.3*s
    ax.add_patch(Polygon([(xx,yy-5.1*s),(zsplit,yy-5.1*s),
                          (zsplit,yy+4.1*s),(xx,yy+4.1*s)],
                         closed=True,facecolor="white",edgecolor=black,lw=.8))
    ax.add_patch(Polygon([(zsplit,yy-5.1*s),(xx+length,yy-5.1*s),
                          (xx+length,yy+5.1*s),(zsplit,yy+5.1*s)],
                         closed=True,facecolor="white",edgecolor=black,lw=.8))
    ax.plot([xx-5,xx+length+5],[yy,yy],color=gray,lw=.45,ls=(0,(7,2,1,2)))
    ax.text(xx+length/2,128,"剖视 A—A（沿 D 平面法向）",ha="center",fontsize=8,color=black)
    add_pdf_dim_h(ax,xx,zsplit,60,yy-outer_h/2,yy-outer_h/2,"12.30 D孔深")
    add_pdf_dim_h(ax,zsplit,xx+length,60,yy-outer_h/2,yy-outer_h/2,"7.70 圆孔深")
    add_pdf_dim_v(ax,xx-10,yy-outer_h/2,yy+outer_h/2,xx,xx,"16.00")
    ax.annotate("D孔圆径Ø10.20；AF9.20",xy=(xx+9*s,yy+4.1*s),xytext=(115,120),fontsize=7,color=black,
                arrowprops=dict(arrowstyle="->",lw=.6,color=gray))
    ax.annotate("中央通道不攻牙；供 M5 轴向螺钉穿过并旋入电机轴端螺纹",
                xy=(xx+length*.7,yy),xytext=(118,89),fontsize=7,color=gray,
                arrowprops=dict(arrowstyle="->",lw=.55,color=gray))

    # General notes and title block.
    ax.plot([16,404],[49,49],color=black,lw=.7)
    notes = [
        "1. M3508输出轴名义尺寸来自官方STEP：Ø10.00 / AF9.00；STEP不含实物公差。加工前用实物测量轴径、平面及轴向槽位置。",
        "2. 本图D孔为首件拟合值：Ø10.20、AF9.20；首件按实测轴校配，未经装配检查不得批量复制。",
        "3. 轴封候选：Freudenberg B2PT 16×35×7，料号40412791；座孔Ø35 H8作为初始接口，最终以密封件专用图纸确认。",
        "4. Ø16轴封跑道参考要求：h11、圆度IT8、Rz1.0–4.0 µm、Rmax≤6.3 µm、≥45 HRC、无螺旋导程；材料及表面处理须同时满足海水腐蚀要求。",
        "5. 材料未定：CNC金属件，不得3D打印。密封跑道硬度与海水耐蚀材料方案须经供应商确认后再下单。",
        "6. Ø10.20延长轴孔及2×M3位置沿用v20布局；须与实际延长轴、齿轮和M3紧定螺钉复核。",
        "7. 0.3×45°去锐边；密封跑道不得有划伤、毛刺、涂层台阶或轴向车纹。"
    ]
    for i,t in enumerate(notes):
        ax.text(17,44-i*4.7,t,fontsize=6.35,color=black,va="top")
    # Title block
    ax.add_patch(Polygon([(271,8),(412,8),(412,35),(271,35)],closed=True,fill=False,edgecolor=black,lw=.7))
    ax.plot([271,412],[25,25],color=black,lw=.5)
    ax.plot([271,412],[17,17],color=black,lw=.5)
    ax.plot([347,347],[8,35],color=black,lw=.5)
    ax.plot([382,382],[8,17],color=black,lw=.5)
    ax.text(274,30,"零件名称",fontsize=6,color=gray); ax.text(274,26.4,"M3508 D轴套联轴套",fontsize=8,weight="bold",color=black)
    ax.text(350,30,"图号",fontsize=6,color=gray); ax.text(350,26.4,"M35-SLV-001",fontsize=7,color=black)
    ax.text(274,21,"材料 / 热处理",fontsize=6,color=gray); ax.text(274,18,"待密封供应商确认",fontsize=7,color=black)
    ax.text(350,21,"版本",fontsize=6,color=gray); ax.text(350,18,"A",fontsize=7,color=black)
    ax.text(274,13,"绘制：Codex  |  日期：2026-11-02",fontsize=6.2,color=black)
    ax.text(350,13,"比例",fontsize=6,color=gray); ax.text(350,9.5,"3:1",fontsize=7,color=black)
    ax.text(384,13,"状态",fontsize=6,color=gray); ax.text(384,9.5,"首件评审",fontsize=7,color=blue)
    fig.savefig(HERE/"M3508_D轴套联轴套_CNC首件图_RevA.pdf",bbox_inches=None)
    fig.savefig(HERE/"M3508_D轴套联轴套_CNC首件图_RevA.png",dpi=180,bbox_inches=None)
    plt.close(fig)


def add_dxf_text(msp, text, x, y, height=2.3, layer="TEXT", rotation=0):
    msp.add_text(text, dxfattribs={"insert": (x,y), "height": height,
                                  "rotation": rotation, "layer": layer, "style": "Standard"})


def add_dxf_hdim(msp, x1, x2, y, ext1, ext2, label):
    msp.add_line((x1,ext1),(x1,y),dxfattribs={"layer":"DIM"})
    msp.add_line((x2,ext2),(x2,y),dxfattribs={"layer":"DIM"})
    msp.add_line((x1,y),(x2,y),dxfattribs={"layer":"DIM"})
    for x,sgn in ((x1,1),(x2,-1)):
        msp.add_line((x,y),(x+sgn*1.5,y+1),dxfattribs={"layer":"DIM"})
        msp.add_line((x,y),(x+sgn*1.5,y-1),dxfattribs={"layer":"DIM"})
    add_dxf_text(msp,label,(x1+x2)/2-5,y+1.8,2.0,"DIM")


def dxf_sheet() -> None:
    doc=ezdxf.new("R2013",setup=True)
    doc.units=ezdxf.units.MM
    doc.header["$INSUNITS"]=4
    for name,color,lt in [("OUTLINE",7,"CONTINUOUS"),("DIM",3,"CONTINUOUS"),
                          ("CENTER",4,"CENTER"),("SEAL",5,"DASHED"),("TEXT",7,"CONTINUOUS")]:
        if name not in doc.layers: doc.layers.new(name,dxfattribs={"color":color,"linetype":lt})
    m=doc.modelspace(); m.add_lwpolyline([(8,8),(412,8),(412,289),(8,289)],close=True,dxfattribs={"layer":"OUTLINE"})
    add_dxf_text(m,"M3508 D轴套联轴套 - CNC首件图 Rev A",16,278,5.0)
    add_dxf_text(m,"单位 mm | 视图 3:1 | 尺寸按标注值 | 首件配合图，不作CAM轮廓直接加工",16,270,2.4)
    s=2.7
    # Motor-side D-bore view
    cx,cy=62,210
    m.add_circle((cx,cy),8*s,dxfattribs={"layer":"OUTLINE"})
    R=5.1*s; flat=4.1*s; yc=math.sqrt(R*R-flat*flat)
    # Major arc on the uncut side; flat chord closes the D.
    start=math.degrees(math.atan2(-yc,-flat)); end=math.degrees(math.atan2(yc,-flat))
    # ezdxf arc runs CCW; major arc from upper endpoint around the left to lower endpoint.
    upper_ang=math.degrees(math.atan2(yc,flat)); lower_ang=360-upper_ang
    m.add_arc((cx,cy),R,upper_ang,lower_ang,dxfattribs={"layer":"OUTLINE"})
    m.add_line((cx+flat,cy-yc),(cx+flat,cy+yc),dxfattribs={"layer":"OUTLINE"})
    m.add_line((cx-24,cy),(cx+24,cy),dxfattribs={"layer":"CENTER"})
    m.add_line((cx,cy-24),(cx,cy+24),dxfattribs={"layer":"CENTER"})
    add_dxf_text(m,"A 电机端 / D孔",cx-15,180,2.5)
    add_dxf_text(m,"D孔 Ø10.20 +0.05/0, AF9.20 +0.05/0, 深12.30±0.10",16,239,2.0)
    # Extension socket end view
    cx2,cy2=140,210
    m.add_circle((cx2,cy2),8*s,dxfattribs={"layer":"OUTLINE"})
    m.add_circle((cx2,cy2),5.1*s,dxfattribs={"layer":"OUTLINE"})
    m.add_line((cx2-24,cy2),(cx2+24,cy2),dxfattribs={"layer":"CENTER"})
    m.add_line((cx2,cy2-24),(cx2,cy2+24),dxfattribs={"layer":"CENTER"})
    add_dxf_text(m,"B 延长轴端 / 圆孔",cx2-19,180,2.5)
    add_dxf_text(m,"Ø10.20 +0.05/0, 深7.70±0.10",145,231,2.0)
    # Side view
    x0,y0=203,210; L=20*s; H=16*s
    m.add_lwpolyline([(x0+0.81,y0-H/2),(x0+L-.81,y0-H/2),(x0+L,y0-H/2+.81),
                      (x0+L,y0+H/2-.81),(x0+L-.81,y0+H/2),(x0+.81,y0+H/2),
                      (x0,y0+H/2-.81),(x0,y0-H/2+.81)],close=True,dxfattribs={"layer":"OUTLINE"})
    hole_x=x0+16.2*s
    m.add_circle((hole_x,y0),1.25*s,dxfattribs={"layer":"OUTLINE"})
    m.add_line((x0-4,y0),(x0+L+4,y0),dxfattribs={"layer":"CENTER"})
    m.add_line((x0+.5*s,y0+H/2),(x0+7.5*s,y0+H/2),dxfattribs={"layer":"SEAL"})
    m.add_line((x0+.5*s,y0-H/2),(x0+7.5*s,y0-H/2),dxfattribs={"layer":"SEAL"})
    add_dxf_text(m,"侧视：2×M3×0.5-6H，对置180°",202,180,2.2)
    add_dxf_text(m,"Ø16 h11密封跑道：距电机端0.50，宽7.00",260,187,2.0,"SEAL")
    add_dxf_hdim(m,x0,x0+L,167,y0-H/2,y0-H/2,"20.00±0.05")
    add_dxf_hdim(m,x0,hole_x,157,y0-H/2,y0-H/2,"16.20 孔中心")
    m.add_line((x0+L+8,y0-H/2),(x0+L+8,y0+H/2),dxfattribs={"layer":"DIM"})
    add_dxf_text(m,"Ø16 h11",x0+L+10,y0-1,2.0,"DIM",90)
    # Section view
    xx,yy=56,96; length=20*s; outer_h=16*s; split=xx+12.3*s
    m.add_lwpolyline([(xx,yy-outer_h/2),(xx+length,yy-outer_h/2),
                      (xx+length,yy+outer_h/2),(xx,yy+outer_h/2)],close=True,dxfattribs={"layer":"OUTLINE"})
    m.add_lwpolyline([(xx,yy-5.1*s),(split,yy-5.1*s),
                      (split,yy+4.1*s),(xx,yy+4.1*s)],close=True,dxfattribs={"layer":"OUTLINE"})
    m.add_lwpolyline([(split,yy-5.1*s),(xx+length,yy-5.1*s),
                      (xx+length,yy+5.1*s),(split,yy+5.1*s)],close=True,dxfattribs={"layer":"OUTLINE"})
    m.add_line((xx-5,yy),(xx+length+5,yy),dxfattribs={"layer":"CENTER"})
    add_dxf_text(m,"剖视 A-A（通过D平面）",xx+14,70,2.5)
    add_dxf_hdim(m,xx,split,60,yy-outer_h/2,yy-outer_h/2,"12.30")
    add_dxf_hdim(m,split,xx+length,60,yy-outer_h/2,yy-outer_h/2,"7.70")
    add_dxf_text(m,"Ø10.20 圆孔 / D孔圆径",118,119,2.0)
    add_dxf_text(m,"D孔 AF9.20；轴端M5螺钉通道无内螺纹",118,112,2.0)
    # Notes and title block
    notes=[
      "1. M3508 D轴名义 Ø10.00 / AF9.00 取自官方 STEP，无实物公差；首件加工前实测电机轴、平面与轴向槽。",
      "2. D孔首件拟合 Ø10.20 / AF9.20；装配后按实物轴校配，不可直接据此批量加工。",
      "3. 轴封候选 B2PT 16×35×7，料号40412791；Ø35 H8为接口建议，向密封件供应商核对专用安装图。",
      "4. Ø16跑道参考 h11、IT8、Rz1.0–4.0、Rmax≤6.3、≥45HRC、无螺旋纹；材质/处理兼顾海水耐蚀，尚待确认。",
      "5. 20.00总长、12.30 D孔深、7.70延长轴孔深、2×M3孔位沿用v20布局；与实物延长轴/齿轮复核。",
      "6. CNC金属件，不可3D打印；0.30×45°去锐边。此图为首件评审，不是批量生产放行图。"
    ]
    for i,t in enumerate(notes): add_dxf_text(m,t,16,48-i*5.3,2.0)
    m.add_lwpolyline([(271,8),(412,8),(412,35),(271,35)],close=True,dxfattribs={"layer":"OUTLINE"})
    for y in (17,25): m.add_line((271,y),(412,y),dxfattribs={"layer":"OUTLINE"})
    m.add_line((347,8),(347,35),dxfattribs={"layer":"OUTLINE"})
    m.add_line((382,8),(382,17),dxfattribs={"layer":"OUTLINE"})
    add_dxf_text(m,"零件名称",274,30,1.8,"TEXT"); add_dxf_text(m,"M3508 D轴套联轴套",274,26,2.6,"TEXT")
    add_dxf_text(m,"图号 M35-SLV-001",350,27,2.0,"TEXT")
    add_dxf_text(m,"材料/处理：待确认",274,19,2.1,"TEXT")
    add_dxf_text(m,"版本 A",350,19,2.1,"TEXT")
    add_dxf_text(m,"日期 2026-11-02",274,10,1.8,"TEXT")
    add_dxf_text(m,"比例 3:1",350,10,1.8,"TEXT")
    add_dxf_text(m,"状态 首件",384,10,1.8,"TEXT")
    doc.saveas(HERE/"M3508_D轴套联轴套_CNC首件图_RevA.dxf")


def main() -> None:
    part=make_part()
    step_path=HERE/"M3508_D轴套联轴套_CNC模型_RevA.step"
    cq.exporters.export(part,str(step_path))
    P["geometry"]={
        "valid":part.isValid(),
        "solid_count":len(part.Solids()),
        "bounding_box_mm":[round(part.BoundingBox().xlen,4),round(part.BoundingBox().ylen,4),round(part.BoundingBox().zlen,4)],
        "volume_mm3":round(part.Volume(),3)
    }
    (HERE/"CNC_dimensions_and_source.json").write_text(json.dumps(P,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    pdf_sheet()
    dxf_sheet()
    # Re-import exported STEP so the report records the neutral-file envelope too.
    imported=cq.importers.importStep(str(step_path)).val()
    P["step_reimport"]={
        "valid":imported.isValid(),"solid_count":len(imported.Solids()),
        "bounding_box_mm":[round(imported.BoundingBox().xlen,4),round(imported.BoundingBox().ylen,4),round(imported.BoundingBox().zlen,4)],
        "volume_mm3":round(imported.Volume(),3)
    }
    (HERE/"CNC_dimensions_and_source.json").write_text(json.dumps(P,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(P["geometry"],ensure_ascii=False))
    print(json.dumps(P["step_reimport"],ensure_ascii=False))
    print("OUTPUT_DIR",HERE)


if __name__=="__main__": main()
