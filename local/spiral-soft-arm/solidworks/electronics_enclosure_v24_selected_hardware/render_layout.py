"""Dimensioned plan views of the v24 electronics layout parameters."""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
from matplotlib.transforms import Affine2D

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
H = P["hardware"]
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def area(ax, title):
    ax.add_patch(Circle((0, 0), 68, facecolor="#e2edf2", edgecolor="#4c707f", lw=2))
    ax.add_patch(Circle((0, 0), 63, fill=False, edgecolor="#89abb8", lw=1.5, ls="--"))
    ax.set_xlim(-78, 78)
    ax.set_ylim(-78, 78)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=13, weight="bold", pad=8)
    ax.axis("off")


def rect(ax, xy, width, height, color, title, angle=0, size=9):
    p = Rectangle(xy, width, height, facecolor=color, edgecolor="#1e3440", lw=1.3)
    if angle:
        p.set_transform(Affine2D().rotate_deg_around(0, 0, angle) + ax.transData)
    ax.add_patch(p)
    x, y = xy[0]+width/2, xy[1]+height/2
    if angle:
        t = math.radians(angle)
        x, y = x*math.cos(t)-y*math.sin(t), x*math.sin(t)+y*math.cos(t)
    ax.text(x, y, title, ha="center", va="center", color="white", fontsize=size,
            weight="bold", rotation=angle if angle in (0, 180) else 0)


fig, axs = plt.subplots(1, 3, figsize=(16.5, 6.2), facecolor="white")
area(axs[0], "上层｜电芯、三只 C620、主控")
for x, y in H["cells"]["centres_xy"]:
    axs[0].add_patch(Circle((x, y), 10.775, facecolor="#24a875", edgecolor="#175d48", lw=1.2))
axs[0].text(-20, 0, "21700 × 4", ha="center", va="center", fontsize=9,
            color="white", weight="bold")
for a in H["c620"]["angles_deg"]:
    rect(axs[0], (44.25, -12.9), 11.5, 25.8, "#23465b", "C620", a, 8)
rect(axs[0], (28, -26), 10, 52, "#2872b6", "STM32", size=8)

area(axs[1], "中层｜稳压器、UPS、主控")
rect(axs[1], (-43, -40), 39, 80, "#d89435", "24 V 稳压", size=10)
rect(axs[1], (8, -25), 15, 50, "#c84b55", "UPS", size=9)
rect(axs[1], (28, -26), 10, 52, "#2872b6", "STM32", size=8)

area(axs[2], "底层｜双电源输入、充放电与保护")
rect(axs[2], (-24, -55), 48, 34, "#7457b4", "PD1002", size=9)
rect(axs[2], (18, -39), 30, 16, "#27a6aa", "理想二极管", size=8)
rect(axs[2], (-30, 20), 60, 30, "#ae9033", "4S40A BMS*", size=8)
axs[2].add_patch(Circle((0, 0), 14.5, facecolor="#526c78", edgecolor="#253d47"))
axs[2].text(0, 0, "M28\n电源", ha="center", va="center", color="white", fontsize=8)
axs[2].add_patch(Circle((0, -68), 7.7, facecolor="#2ba6a4", edgecolor="#215d5b"))
axs[2].annotate("M12 Type-C", xy=(0, -68), xytext=(32, -70), fontsize=9,
                arrowprops={"arrowstyle": "->", "color": "#334c59"})

fig.text(.5, .045, "实线外圆 Ø136 mm，虚线内圆 Ø126 mm；示意为不同高度的投影，*BMS 外形为待实测占位。",
         ha="center", fontsize=11, color="#3e5662")
fig.tight_layout(rect=(0, .09, 1, .88), w_pad=1.8)
fig.savefig(HERE / "B32_v24_电子仓分层布局图.png", dpi=170, facecolor="white")
