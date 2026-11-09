from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
ASSET_DIR = HERE / "report_assets"


def _equation_image(filename: str, equation: str, width: float = 8.0) -> None:
    figure = plt.figure(figsize=(width, 0.58), dpi=300, facecolor="white")
    axis = figure.add_axes([0.015, 0.05, 0.97, 0.90])
    axis.axis("off")
    axis.text(
        0.5,
        0.5,
        equation,
        ha="center",
        va="center",
        fontsize=17,
        color="#142f45",
        math_fontfamily="stix",
    )
    figure.savefig(ASSET_DIR / filename, bbox_inches="tight", pad_inches=0.04)
    plt.close(figure)


def main() -> None:
    ASSET_DIR.mkdir(exist_ok=True)
    data = json.loads((HERE / "V27螺旋参数.json").read_text(encoding="utf-8"))
    theta = np.asarray(data["unit_boundary_theta_rad"], dtype=float)
    b = float(data["b"])
    tip = float(data["tip_width_mm"])
    length = float(data["nominal_length_mm"])
    width = tip * np.exp(b * theta)
    centerline = float(data["centerline_scale_mm"]) * (np.exp(b * theta) - 1.0)

    figure, axis = plt.subplots(figsize=(8.2, 4.5), dpi=220, facecolor="white")
    axis.plot(centerline, width, color="#1f5d84", linewidth=2.6, label="continuous envelope")
    axis.scatter(
        centerline,
        width,
        color="#e29b38",
        edgecolor="white",
        linewidth=0.45,
        s=24,
        zorder=3,
        label="43 boundary rays / 42 intervals",
    )
    axis.scatter([0, length], [tip, data["root_width_mm"]], color="#b74b3a", s=48, zorder=4)
    axis.annotate("tip 5 mm", (0, tip), xytext=(45, 15), textcoords="data", arrowprops={"arrowstyle": "-", "color": "#777"})
    axis.annotate("root 120 mm", (length, data["root_width_mm"]), xytext=(690, 102), textcoords="data", arrowprops={"arrowstyle": "-", "color": "#777"})
    axis.set_title("Paper-derived V27 spiral envelope", fontsize=13, color="#142f45", pad=10)
    axis.set_xlabel("Centerline arc length s (mm)")
    axis.set_ylabel("Envelope width δ (mm)")
    axis.set_xlim(0, length)
    axis.set_ylim(0, 130)
    axis.grid(True, color="#d8e0e6", linewidth=0.75)
    axis.legend(frameon=False, loc="upper left")
    figure.tight_layout()
    figure.savefig(HERE / "V27_螺旋包络与中心线弧长.png", bbox_inches="tight", facecolor="white")
    plt.close(figure)

    equations = {
        "eq01_spiral.png": r"$\rho(\theta)=a e^{b\theta},\qquad b=\cot\psi$",
        "eq02_centerline.png": r"$\rho_c(\theta)=a_1 e^{b\theta},\qquad a_1=\frac{a}{2}\left(e^{2\pi b}+1\right)$",
        "eq03_width.png": r"$\delta(\theta)=a e^{b\theta}\left(e^{2\pi b}-1\right)$",
        "eq04_length.png": r"$L(0,\theta_0)=\frac{\sqrt{1+b^2}\,a_1}{b}\left(e^{b\theta_0}-1\right)$",
        "eq05_ratio.png": r"$e^{b\theta_0}=\frac{120}{5}=24,\qquad \theta_0=\frac{\ln 24}{b}$",
        "eq06_scalar.png": r"$1000=57.5\,\frac{\sqrt{1+b^2}}{b\tanh(\pi b)}$",
        "eq07_discrete.png": r"$\Delta\theta=\frac{\theta_0}{42}=30.9185^\circ,\qquad \beta=e^{b\Delta\theta}=24^{1/42}=1.078604$",
        "eq08_arc_intervals.png": r"$s(\theta)=K\left(e^{b\theta}-1\right),\quad \ell_i=s((i+1)\Delta\theta)-s(i\Delta\theta)$",
        "eq09_pressure.png": r"$p_g=\rho g h,\qquad h=5\,\mathrm{m}$",
    }
    for filename, formula in equations.items():
        _equation_image(filename, formula, width=9.0 if len(formula) > 85 else 7.2)


if __name__ == "__main__":
    main()
