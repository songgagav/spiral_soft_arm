"""Render the dimensioned radial section of the v23 tendon entrance."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
import numpy as np

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
OUT = HERE / "B32_v23_拉索直线与根部过渡尺寸图.png"


def main() -> None:
    d = P["drive_layout"]
    root = P["root_tendon_transition"]
    reel_r = float(d["reel_center_radius_mm"])
    reel_z = float(d["reel_center_local_xyz_mm"][2])
    root_r = float(d["tendon_hole_radius_mm"])
    # This radius is the outer winding centreline plus the cable radius in v20.
    winding_radius = 9.9
    vx, vz = root_r-reel_r, -reel_z
    q = vx*vx+vz*vz
    bx, bz = winding_radius*winding_radius/q*vx, winding_radius*winding_radius/q*vz
    s = winding_radius*math.sqrt(q-winding_radius*winding_radius)/q
    options = ((reel_r+bx-s*(-vz), reel_z+bz-s*vx),
               (reel_r+bx+s*(-vz), reel_z+bz+s*vx))
    tangent = max(options, key=lambda point: point[1])
    length = math.hypot(root_r-tangent[0], -tangent[1])
    unit = ((root_r-tangent[0])/length, -tangent[1]/length)
    bottom_r = root_r-8.0*unit[0]/unit[1]
    slope = (float(root["native_channel_tip_radius_mm"])
             -float(root["native_channel_base_radius_mm"])) / float(root["native_channel_length_mm"])
    channel_u = np.array([slope, 1.0])/math.hypot(slope, 1.0)
    p0 = np.array([root_r, 0.0])
    p1 = p0 + float(root["start_handle_mm"])*np.array(unit)
    p3 = np.array([float(root["native_channel_base_radius_mm"])
                   +slope*float(root["join_z_mm"]), float(root["join_z_mm"])])
    p2 = p3 - float(root["end_handle_mm"])*channel_u
    controls = np.array([p0, p1, p2, p3])
    t = np.linspace(0, 1, 400)
    curve = ((1-t[:, None])**3*controls[0] + 3*(1-t[:, None])**2*t[:, None]*controls[1]
             +3*(1-t[:, None])*t[:, None]**2*controls[2]+t[:, None]**3*controls[3])

    font_path = "C:/Windows/Fonts/msyh.ttc"
    font_manager.fontManager.addfont(font_path)
    font = FontProperties(fname=font_path)
    plt.rcParams["font.family"] = font.get_name()
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(12, 8), dpi=170)
    fig.patch.set_facecolor("#f4f8fb")
    ax.set_facecolor("#f9fcfe")
    ax.add_patch(Rectangle((0, -8), 110, 8, facecolor="#6e8da1", alpha=.36,
                           edgecolor="#28495b", linewidth=1.5, label="8 mm 六边形顶盘"))
    ax.add_patch(Rectangle((0, -44), 68, 24, facecolor="#7ba6b0", alpha=.25,
                           edgecolor="#316577", linewidth=1.5, label="电子筒顶面 Z=-20"))
    ax.add_patch(Circle((reel_r, reel_z), 10.5, facecolor="#e5b15a", alpha=.42,
                        edgecolor="#996015", linewidth=2, label="线轮外缘 Ø21"))
    ax.plot([tangent[0], root_r], [tangent[1], 0], color="#db503e", linewidth=3,
            label="线轮切点 → 根部入口：直线")
    liner_a = np.array(tangent) + 10*np.array(unit)
    liner_b = np.array([root_r, 0])-9*np.array(unit)
    ax.plot([liner_a[0], liner_b[0]], [liner_a[1], liner_b[1]], color="#21a29a",
            linewidth=6, alpha=.55, label="Ø4.0/Ø2.2 导管")
    ax.plot(curve[:, 0], curve[:, 1], color="#df6f38", linewidth=3,
            label="软臂根部平滑导入段")
    z_native = np.linspace(0, 72, 120)
    ax.plot(float(root["native_channel_base_radius_mm"])+slope*z_native,
            z_native, color="#526979", linewidth=2, linestyle="--",
            label="原 B32 腱道中心线")
    ax.scatter([tangent[0], bottom_r, root_r, p3[0]],
               [tangent[1], -8, 0, p3[1]], color="#9a3025", s=44, zorder=5)
    labels = [
        (tangent[0], tangent[1], "线轮上侧切点", (2, 3)),
        (bottom_r, -8, f"顶盘下口 R={bottom_r:.2f}", (2, -8)),
        (root_r, 0, "顶盘上口 R=30.6", (2, -6)),
        (p3[0], p3[1], "Z=60 接原腱道", (3, 3)),
    ]
    for x, y, label, shift in labels:
        ax.annotate(label, (x, y), xytext=(x+shift[0], y+shift[1]),
                    fontproperties=font, fontsize=10, color="#273c48")
    ax.text(73, 56, f"直线段 {length:.2f} mm\n顶盘内约 33.0 mm\n根部最小弯曲半径约 9.06 mm",
            fontproperties=font, fontsize=11, va="top",
            bbox={"facecolor": "white", "edgecolor": "#b7c8d0", "boxstyle": "round,pad=.6"})
    ax.set(xlim=(0, 110), ylim=(-44, 75), xlabel="距中心轴的半径 R / mm",
           ylabel="Z / mm")
    ax.set_title("B32 v23 线轮切线、顶盘斜孔及软臂根部导入", fontproperties=font,
                 fontsize=18, pad=16)
    ax.grid(alpha=.17)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="lower left", prop=font, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
