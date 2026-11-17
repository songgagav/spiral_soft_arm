from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


HERE = Path(__file__).resolve().parent
TITLE = "5 m 水深工况下 1 m 三缆对数螺旋机械臂几何推导与模型更新"
REPORT_DATE = "2026-11-10"
OUTPUT_MD = HERE / "V27_5m水深_1m三缆臂螺旋函数推导.md"
OUTPUT_DOCX = HERE / "V27_5m水深_1m三缆臂螺旋函数推导.docx"


def _mm(value: float) -> str:
    return f"{value:.6f}"


def _set_run_font(
    run,
    name: str = "Microsoft YaHei",
    size_pt: float | None = None,
    bold: bool | None = None,
    color: str | None = None,
):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run.font.color.rgb = RGBColor.from_string(color) if color else RGBColor(0, 0, 0)
    if size_pt is not None:
        run.font.size = Pt(size_pt)
    if bold is not None:
        run.bold = bold


def _set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def _set_cell_borders(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "5")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "D9E0E5")


def _set_cell_margins(cell, top=90, start=120, bottom=90, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn("w:" + m))
        if node is None:
            node = OxmlElement("w:" + m)
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def _add_text(doc, text: str, *, size: float = 10.5, bold: bool = False, color: str | None = None, align=None):
    paragraph = doc.add_paragraph()
    if align is not None:
        paragraph.alignment = align
    paragraph.paragraph_format.space_after = Pt(5)
    paragraph.paragraph_format.line_spacing = 1.16
    run = paragraph.add_run(text)
    _set_run_font(run, size_pt=size, bold=bold)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    return paragraph


def _heading(doc, text: str, level: int = 1):
    paragraph = doc.add_paragraph(style=f"Heading {level}")
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_before = Pt(11 if level == 1 else 7)
    paragraph.paragraph_format.space_after = Pt(5)
    run = paragraph.add_run(text)
    _set_run_font(run, size_pt=14 if level == 1 else 11.5, bold=True)
    return paragraph


def _add_equation(doc, path: Path, description: str, width_in: float = 5.85):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(1)
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run()
    inline = run.add_picture(str(path), width=Inches(width_in))
    doc_pr = inline._inline.docPr
    doc_pr.set("descr", description)
    return paragraph


def _add_table(doc, rows: list[tuple[str, str]], headers=("项目", "V27 取值")):
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    table.columns[0].width = Cm(5.0)
    table.columns[1].width = Cm(11.1)
    cells = table.rows[0].cells
    for index, text in enumerate(headers):
        cells[index].text = text
        _set_cell_shading(cells[index], "1F5D84")
    for key, value in rows:
        cells = table.add_row().cells
        cells[0].text = key
        cells[1].text = value
    for row_index, row in enumerate(table.rows):
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            _set_cell_margins(cell)
            _set_cell_borders(cell)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(1)
                paragraph.paragraph_format.line_spacing = 1.05
                for run in paragraph.runs:
                    _set_run_font(run, size_pt=9.4, bold=(row_index == 0))
                    if row_index == 0:
                        run.font.color.rgb = RGBColor(255, 255, 255)
        if row_index > 0 and row_index % 2 == 0:
            for cell in row.cells:
                _set_cell_shading(cell, "F1F5F7")
    return table


def _markdown(p: dict, segment_data: dict) -> str:
    fw_abs = p["freshwater_absolute_pressure_kpa"]
    sea_abs = p["seawater_absolute_pressure_kpa"]
    split_summary = "；".join(
        f"单元 {entry['split_joint_unit']} 内 Z={entry['boundary_z_mm']:.3f} mm"
        for entry in segment_data["dovetail_interfaces"]
    )
    segment_ranges = "、".join(
        f"{entry['unit_range_in_arm'][0]}–{entry['unit_range_in_arm'][1]}"
        for entry in segment_data["segments"]
    )
    max_print_height = max(
        entry["finished_print_height_mm"] for entry in segment_data["segments"]
    )
    segment_rows = "\n".join(
        f"| {index} | {entry['unit_range_in_arm'][0]}–{entry['unit_range_in_arm'][1]} | "
        f"{entry['local_bounds_mm']['z'][1] - entry['local_bounds_mm']['z'][0]:.2f} | `{entry['file']}` |"
        for index, entry in enumerate(segment_data["segments"], start=1)
    )
    return f"""# {TITLE}

**候选版本：** V27-1M-M2006<br>
**文档性质：** 工程几何推导稿，不是期刊发表稿，也不是水下验证报告<br>
**日期：** {REPORT_DATE}

## 摘要

本文依据 SpiRobs 对数螺旋软体机器人论文的几何方程，重新计算项目 V27 一米三缆机械臂的连续螺旋函数及离散单元尺寸。输入采用论文一米样机的目标长度 1,000 mm、尖端/根部尺寸 5/120 mm 和 42 个离散单元。把该尺寸比代入论文中心线弧长方程后，数值求得增长参数 `b={p['b']:.12f}`，并得到 `a={p['a_mm']:.12f} mm`、`a₁={p['a1_mm']:.12f} mm` 和 `θ₀={p['theta0_rad']:.12f} rad`。按每个四边形单元对应一个角区间离散，步长为 `{p['delta_theta_deg']:.12f}°`，相邻缩放比为 `{p['beta']:.12f}`；42 个中心线弧长区间的解析求和回到 1,000 mm。

5 m 水深仅作为淡水/海水环境边界。按代表性密度 1,000/1,025 kg/m³ 估算，5 m 外部静水表压约为 49.03/50.26 kPa。若干仓在近海平面气压下封闭，外壳差压可先按表压估算；最终仍要根据封仓气压、温度和压力测试工况确定。水深不进入对数螺旋方程；本推导不等于 TPU 强度、密封或整机耐压验证。

**关键词：** 对数螺旋；软体机械臂；三缆驱动；中心线弧长；五米水深

## 1. 设计对象与输入条件

| 项目 | 数值或解释 |
|---|---:|
| 中心线弧长目标 | 1,000 mm |
| 尖端/根部目标尺寸 | 5/120 mm |
| 离散单元 | 42 个四边形单元、42 个角区间、43 条边界射线 |
| 拉索与打印分段 | 3 路；四段打印、根部整体快换 |
| 设计水深 | 淡水与海水均为 5 m |

这里把论文中报出的尖端/根部尺寸，作为论文宽度函数 δ(θ) 在两端的目标宽度。二维宽度与最终三维截面外径完全相等，是本轮 CAD 几何采用的建模假设；三缆样机的截面修型、弹性轴、孔道、连接榫和打印公差可能改变最终实体测得的包络尺寸，需另行从 CAD/实物量测确认。

## 2. 论文几何方程

原始对数螺旋及其增长参数为：

$$
ρ(θ)=a·e^(bθ),  b=cot(ψ)
$$

中心螺旋系数为：

$$
ρ_c(θ)=a₁·e^(bθ),  a₁=(a/2)(e^(2πb)+1)
$$

机器人宽度和中心线弧长公式分别为：

$$
δ(θ)=a·e^(bθ)(e^(2πb)-1)
$$

$$
L(0,θ₀)=[√(1+b²)·a₁/b]·(e^(bθ₀)-1)
$$

## 3. 由端点尺寸和一米长度求解参数

尖端设为 θ=0，根部设为 θ=θ₀。根尖目标宽度比为：

$$
δ(θ₀)/δ(0)=120/5=24=e^(bθ₀)
$$

因此 θ₀=ln(24)/b。由 δ(0)=5 mm 得到 `a=5/(e^(2πb)-1)`；代入中心线定义后，`a₁=(5/2)·coth(πb)`。将这些关系代入论文长度公式，化为一个只含 b 的方程：

$$
1000 = 57.5·√(1+b²)/[b·tanh(πb)]
$$

对正根进行数值二分求解，得到：

| 参数 | 计算值 |
|---|---:|
| `b` | {p['b']:.12f} |
| `a` | {p['a_mm']:.12f} mm |
| `a₁` | {p['a1_mm']:.12f} mm |
| `θ₀` | {p['theta0_rad']:.12f} rad = {p['theta0_pi']:.12f}π |
| 极角切线角 `ψ` | {p['tangent_angle_psi_deg']:.9f}° |
| 论文锥度角 `φ` | {p['taper_angle_phi_deg']:.9f}° |

故本次连续函数为：

$$
ρ(θ)={p['a_mm']:.12f}·e^({p['b']:.12f}θ) mm
$$

$$
ρ_c(θ)={p['a1_mm']:.12f}·e^({p['b']:.12f}θ) mm
$$

$$
δ(θ)=5·e^({p['b']:.12f}θ) mm,  0≤θ≤{p['theta0_rad']:.12f}
$$

端点代回为 δ(0)=5 mm、δ(θ₀)=120 mm；中心线长度回算为 {p['centerline_length_reconstructed_mm']:.9f} mm。论文方程定义的是中心线弧长，不应与总装的轴向投影长度混称。

## 4. 42 单元离散化

论文通过固定角度区间构造一个四边形单元。V27 因此按 42 个单元对应 42 个等角区间、43 条边界射线处理：

$$
Δθ=θ₀/42={p['delta_theta_rad']:.12f} rad={p['delta_theta_deg']:.12f}°
$$

相邻单元比例为：

$$
β=e^(bΔθ)=24^(1/42)={p['beta']:.12f}
$$

中心线的弧长坐标可写成 `K(e^(bθ)-1)`，其中 `K=√(1+b²)·a₁/b={p['centerline_scale_mm']:.12f} mm`。第 i 个区间的长度为：

$$
ℓ_i=K[e^(b(i+1)Δθ)-e^(biΔθ)],  i=0,…,41
$$

对 42 个理想角区间求和后，中间项相消，得到 `K(e^(bθ₀)-1)=1,000 mm`。尖端侧首个理想区间约 `{min(p['unit_interval_lengths_mm']):.6f} mm`，根部侧末个理想区间约 `{max(p['unit_interval_lengths_mm']):.6f} mm`。这些是连续中心线的弧长区间，不等同于三维 CAD 单元投影后的轴向包围尺寸。图 1 显示连续宽度包络和 43 条离散边界射线。

![V27螺旋包络](V27_螺旋包络与中心线弧长.png)

**图 1.** 对数螺旋宽度相对于中心线弧长呈线性变化；点列表示 42 个角区间的边界射线。

固定 `Δθ=30°` 与其余三项约束并不完全相容：固定 42 个角区间和 24:1 端点比时，方程给出 `b≈0.144515`，中心线长度约 945.50 mm，比目标短约 54.50 mm。因此 V27 将论文中的 30°示例视作离散参考，而由一米长度和端点尺寸求得实际步长。

## 5. 五米水深的压力边界

静水表压按 `p_g=ρgh` 计算，取 `h=5 m`、`g=9.80665 m/s²`，并使用淡水 1,000 kg/m³、代表性海水 1,025 kg/m³：

| 介质 | 假定密度 | 5 m 表压 | 加 101.325 kPa 标准大气压后的绝对压力 |
|---|---:|---:|---:|
| 淡水 | 1,000 kg/m³ | {p['freshwater_gauge_pressure_kpa']:.3f} kPa | {fw_abs:.3f} kPa |
| 海水 | 1,025 kg/m³ | {p['seawater_gauge_pressure_kpa']:.3f} kPa | {sea_abs:.3f} kPa |

这些是密度假设下的静水压力估算；温度、当地盐度和水面气压没有实测。压力数值不改变 `a`、`b`、`θ₀` 或 `Δθ`。本次没有对 TPU 单元的压力变形、蠕变、疲劳、燕尾锁止、密封件寿命或舱体耐压作结构计算或试验；这些仍是独立验证项目。

## 6. V27 模型更新与导出

更新后的模型仍采用 42 个单元、三路拉索和四段臂体，根部快换法兰、M2006 整板驱动模块以及固定传动/轴封/湿侧线轮基座沿用 V27 模块接口。三个燕尾接口切入既有关节单元 5、10、18 内部，切面为：{split_summary}。第 5、10 单元使用其 CAD 轮廓中面；第 18 单元的切面相对中面向根部移 6 mm，以免末段软臂实体断开。各段范围为 {segment_ranges}；燕尾榫轴向咬合 12 mm 并以横向锁销固定。当前最大打印段高度为 {max_print_height:.3f} mm，低于 300 mm V27 合同限值。打印段如下：

| 打印段 | 单元范围 | 局部 Z 包络 (mm) | 导出文件 |
|---:|---:|---:|---|
{segment_rows}

四个 STL 各自平移到局部坐标系 `zmin=0`，XY 仍以机械臂中心为基准。另有四段臂体 STEP、完整 V27 总装 STEP、独立驱动和固定基座 STEP。CAD 导出流程完成总装预检并将 STEP 重新导入以确认文件可读；这些检查只支持当前 CAD 文件的几何/装配状态。

![V27总装预览](V27_总装半透明审查.png)

**图 2.** V27 一米臂体与现有模块化根部总装的半透明审查图。

## 7. 结论和适用范围

V27 连续螺旋函数及 42 区间配置由论文的端点宽度比、中心线长度关系和固定区间缩放关系导出；数值满足目标中心线弧长 1,000 mm 和理论宽度 5/120 mm。打印分段按设计切入单元 5、10、18 内部，以宽燕尾和横向锁销组合；第 18 单元切面向根部偏移 6 mm。5 m 深度只形成环境压力边界，不参与螺旋参数求解。三维外形尺寸与二维 `δ` 的对应、切片后的薄壁/支撑、材料刚度、根部承载、拉索摩擦、海水兼容性、5 m 水密和 30 分钟运行仍需后续验证。

## 参考文献

1. Wang, Z., Freris, N. M., & Wei, X. *SpiRobs: Logarithmic spiral-shaped robots for versatile grasping across scales*. Device, 3(4), 100646 (2025). https://doi.org/10.1016/j.device.2024.100646.
2. 作者预印本：arXiv:2303.09861, https://arxiv.org/abs/2303.09861.

## 附录：复算数据与复现文件

| 项目 | 复算值 |
|---|---:|
| 根尖宽度比 | {p['root_width_mm'] / p['tip_width_mm']:.0f}:1 |
| 原始螺旋系数 `a` | {p['a_mm']:.12f} mm |
| 中心螺旋系数 `a₁` | {p['a1_mm']:.12f} mm |
| 增长参数 `b` | {p['b']:.12f} |
| 根部相位 `θ₀` | {p['theta0_rad']:.12f} rad |
| 单元角步长 `Δθ` | {p['delta_theta_deg']:.12f}° |
| 相邻单元比例 `β` | {p['beta']:.12f} |
| 中心线弧长 | {p['centerline_length_reconstructed_mm']:.6f} mm |
| 单元弧长范围 | {min(p['unit_interval_lengths_mm']):.3f}–{max(p['unit_interval_lengths_mm']):.3f} mm |

数值记录位于 `V27螺旋参数.json`，计算实现位于 `spiral_parameters.py`。`build_spiral_derivation_report.py` 生成本报告的 Markdown 与 DOCX，`generate_v27_assembly.py` 生成 V27 的 CAD 文件。重新导出后仍需检查切片、材料试件、受力、密封和水下运行；报告中的公式回算不替代这些实体验证。
"""


def _configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.85)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)

    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(28, 39, 48)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.16
    for style_name, size in (("Title", 21), ("Heading 1", 14), ("Heading 2", 11.5)):
        style = doc.styles[style_name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style._element.rPr.rFonts.set(qn("w:ascii"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
    title_style_ppr = doc.styles["Title"]._element.pPr
    if title_style_ppr is not None:
        title_border = title_style_ppr.find(qn("w:pBdr"))
        if title_border is not None:
            title_style_ppr.remove(title_border)

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header_run = header.add_run("V27 · 1 m 三缆对数螺旋机械臂")
    _set_run_font(header_run, size_pt=8.5, color="52616B")
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run(f"工程推导稿  |  {REPORT_DATE}  |  非水下验证报告")
    _set_run_font(footer_run, size_pt=8.2, color="52616B")


def _build_docx(p: dict, segment_data: dict) -> None:
    doc = Document()
    _configure_document(doc)
    split_summary = "；".join(
        f"单元 {entry['split_joint_unit']} 内 Z={entry['boundary_z_mm']:.3f} mm"
        for entry in segment_data["dovetail_interfaces"]
    )
    segment_ranges = "、".join(
        f"{entry['unit_range_in_arm'][0]}–{entry['unit_range_in_arm'][1]}"
        for entry in segment_data["segments"]
    )
    max_print_height = max(
        entry["finished_print_height_mm"] for entry in segment_data["segments"]
    )
    props = doc.core_properties
    props.title = TITLE
    props.subject = "论文公式推导、5 m 静水压力边界及 V27 CAD 更新"
    props.author = "V27 engineering design note"
    props.keywords = "SpiRobs, logarithmic spiral, 1 m soft arm, 5 m depth"

    title = doc.add_paragraph(style="Title")
    title_ppr = title._p.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)
    title.paragraph_format.space_before = Pt(12)
    title.paragraph_format.space_after = Pt(6)
    title_run = title.add_run(TITLE)
    _set_run_font(title_run, size_pt=20.5, bold=True)
    subtitle = _add_text(doc, f"V27-1M-M2006  ·  工程几何推导稿  ·  {REPORT_DATE}", size=10, color="52616B", align=WD_ALIGN_PARAGRAPH.LEFT)
    subtitle.paragraph_format.space_after = Pt(10)

    _heading(doc, "摘要", 1)
    _add_text(
        doc,
        f"本文依据 SpiRobs 论文的对数螺旋几何方程，重新计算 V27 一米三缆机械臂的连续螺旋函数及离散单元尺寸。输入为中心线弧长 1,000 mm、尖端/根部目标尺寸 5/120 mm 和 42 个单元。求得 b={p['b']:.12f}、a={p['a_mm']:.12f} mm、a₁={p['a1_mm']:.12f} mm、θ₀={p['theta0_rad']:.12f} rad。按每个四边形对应一个角区间离散，Δθ={p['delta_theta_deg']:.6f}°、β={p['beta']:.9f}。5 m 水深估算表压为淡水 {p['freshwater_gauge_pressure_kpa']:.2f} kPa、代表性海水 {p['seawater_gauge_pressure_kpa']:.2f} kPa；该压力不进入螺旋方程，也不代表实体通过耐压或水密验证。",
    )
    _add_table(
        doc,
        [
            ("中心线弧长", "1,000 mm（论文 Eq. 5）"),
            ("尖端 / 根部目标宽度", "5 / 120 mm；按 δ(θ) 端点解释"),
            ("离散方式", "42 个单元 = 42 个角区间、43 条边界射线"),
            ("实际角步长 / 单元比例", f"{p['delta_theta_deg']:.6f}° / {p['beta']:.9f}"),
            ("设计环境", "淡水、海水；最大水深 5 m"),
            ("模型状态", "V27 CAD 候选；未通过打印和水下实体验证"),
        ],
    )

    _heading(doc, "1 设计对象与论文来源", 1)
    _add_text(
        doc,
        "论文报告了一米长三缆 SpiRob 样机，尖端/根部尺寸约为 5/120 mm，共 42 个离散单元。论文把对数螺旋离散为固定角度区间形成的四边形，并用中心螺旋弧长描述臂体长度。本报告将论文尺寸作为 V27 的几何目标；二维宽度 δ 与最终三维截面外径相等，是当前模型采用的假设，截面修型、弹性轴、拉索孔和打印公差仍可能改变实体实测尺寸。",
    )
    curve_path = HERE / "V27_螺旋包络与中心线弧长.png"
    picture_p = doc.add_paragraph()
    picture_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    picture_run = picture_p.add_run()
    picture = picture_run.add_picture(str(curve_path), width=Inches(5.95))
    picture._inline.docPr.set("descr", "V27 中心线弧长从零到一米，宽度由 5 mm 连续增至 120 mm，标出 43 条角度边界射线")
    caption = _add_text(doc, "图 1  连续宽度包络与 42 个离散角区间", size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    caption.paragraph_format.space_after = Pt(3)

    _heading(doc, "2  论文方程", 1)
    _add_text(doc, "论文以极坐标对数螺旋作为原始轮廓，并由相差 2π 的轮廓点中点构造中心螺旋。", size=10.5)
    assets = HERE / "report_assets"
    for filename, desc in (
        ("eq01_spiral.png", "原始极坐标对数螺旋及增长参数"),
        ("eq02_centerline.png", "中心螺旋参数"),
        ("eq03_width.png", "论文定义的机器人宽度函数"),
        ("eq04_length.png", "论文中心线弧长方程"),
    ):
        _add_equation(doc, assets / filename, desc, width_in=5.7)

    _heading(doc, "3 由端点尺寸与长度求解参数", 1)
    _add_text(doc, "令尖端对应 θ=0，根部对应 θ=θ₀。宽度函数两端之比消去 a，给出相位跨度与增长参数的关系：")
    _add_equation(doc, assets / "eq05_ratio.png", "根尖宽度比等于指数相位增长", width_in=4.1)
    _add_text(doc, "尖端宽度 δ(0)=5 mm 进而确定 a。将 a₁ 写成双曲函数形式并代入论文长度公式，得到一个仅含 b 的方程：")
    _add_equation(doc, assets / "eq06_scalar.png", "由 1000 毫米中心线长度得到的单变量方程", width_in=4.4)
    _add_text(doc, f"以正根二分求解得到 b={p['b']:.12f}。随后 θ₀=ln(24)/b={p['theta0_rad']:.12f} rad；a={p['a_mm']:.12f} mm；a₁={p['a1_mm']:.12f} mm。论文锥度角 φ={p['taper_angle_phi_deg']:.6f}°，极角切线角 ψ={p['tangent_angle_psi_deg']:.6f}°。")
    _add_text(doc, f"因此原始螺旋为 ρ(θ)={p['a_mm']:.6f}·e^({p['b']:.9f}θ) mm；中心螺旋为 ρ_c(θ)={p['a1_mm']:.6f}·e^({p['b']:.9f}θ) mm；宽度为 δ(θ)=5·e^({p['b']:.9f}θ) mm，0≤θ≤{p['theta0_rad']:.6f} rad。端点回代得到 5/120 mm，中心线长度回算为 {p['centerline_length_reconstructed_mm']:.6f} mm。")

    _heading(doc, "4  42 单元离散化与单元长度", 1)
    _add_text(doc, "论文用固定角度区间构造一个四边形单元。V27 按 42 个单元对应 42 个区间，边界为 43 条射线；相邻单元比例依据论文的 β 公式计算。")
    _add_equation(doc, assets / "eq07_discrete.png", "42 个角区间的角步长与相邻缩放比例", width_in=5.7)
    _add_text(doc, f"令 K=√(1+b²)·a₁/b={p['centerline_scale_mm']:.9f} mm，则中心线弧长 s(θ)=K(e^(bθ)-1)。第 i 区间的弧长是 s((i+1)Δθ)-s(iΔθ)。")
    _add_equation(doc, assets / "eq08_arc_intervals.png", "中心线弧长与第 i 个单元区间的精确弧长", width_in=5.7)
    _add_text(doc, f"42 个理想角区间求和后，得到中心线长度 {p['centerline_length_reconstructed_mm']:.6f} mm；尖端侧首区间约 {min(p['unit_interval_lengths_mm']):.3f} mm，根部侧末区间约 {max(p['unit_interval_lengths_mm']):.3f} mm。它们是连续中心线弧长区间，不等于三维 CAD 单元投影后的轴向包围尺寸。固定 Δθ=30°、42 个区间和 24:1 端点比例会使长度仅约 945.50 mm；故本版采用由长度方程导出的 {p['delta_theta_deg']:.6f}°。")

    _heading(doc, "5  五米水深压力边界", 1)
    _add_text(doc, "静水表压按 p_g=ρgh 估算，取 g=9.80665 m/s²。海水密度 1,025 kg/m³ 是代表值，温度和实际盐度未测。绝对压力另按标准大气压 101.325 kPa 相加；若干仓在近海平面气压下封闭，外壳差压可先按表压估算，最终按封仓气压、温度和测试工况确定。")
    _add_equation(doc, assets / "eq09_pressure.png", "静水表压估算方程", width_in=2.8)
    _add_table(
        doc,
        [
            ("淡水（ρ=1,000 kg/m³）", f"表压 {p['freshwater_gauge_pressure_kpa']:.3f} kPa；绝对压力 {p['freshwater_absolute_pressure_kpa']:.3f} kPa"),
            ("海水（ρ=1,025 kg/m³）", f"表压 {p['seawater_gauge_pressure_kpa']:.3f} kPa；绝对压力 {p['seawater_absolute_pressure_kpa']:.3f} kPa"),
        ],
        headers=("介质假设", "5 m 压力估算"),
    )
    _add_text(doc, "水深不进入论文的几何方程，因此不会改变 a、b、θ₀ 或 Δθ。此处未计算 TPU 的压力变形、疲劳、燕尾强度、轴封寿命或舱体压溃，也没有进行压力舱试验。")

    doc.add_page_break()
    _heading(doc, "6  V27 模型更新与导出", 1)
    _add_text(doc, f"模型在现有 V27 模块化总装上更新了论文螺旋剖面。三个燕尾接口切入既有关节单元 5、10、18 内部，切面为：{split_summary}。第 5、10 单元使用各自 CAD 轮廓中面；第 18 单元切面相对中面向根部偏移 6 mm，以避免末段软臂实体断开。各打印段范围为 {segment_ranges}；燕尾榫轴向咬合 12 mm，并以横向锁销固定。当前最大打印段高度为 {max_print_height:.3f} mm，低于 300 mm V27 合同限值。三台 M2006 驱动模块、固定传动密封基座和根部快换接口沿用。各 STL 以自身最低 Z 面为 z=0，XY 仍以臂体中心为基准。")
    _add_table(
        doc,
        [
            (f"段 {i}: 单元 {entry['unit_range_in_arm'][0]}–{entry['unit_range_in_arm'][1]}", f"Z={entry['local_bounds_mm']['z'][1]-entry['local_bounds_mm']['z'][0]:.2f} mm；{entry['file']}")
            for i, entry in enumerate(segment_data["segments"], start=1)
        ],
        headers=("臂体打印段", "局部包围盒 / 文件"),
    )
    assembly_image = HERE / "V27_总装半透明审查.png"
    assembly_p = doc.add_paragraph()
    assembly_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    assembly_inline = assembly_p.add_run().add_picture(str(assembly_image), width=Inches(3.2))
    assembly_inline._inline.docPr.set("descr", "V27 一米机械臂、根部基座与电子仓的半透明总装预览")
    cap = _add_text(doc, "图 2  更新后的 V27 一米模块化总装 CAD 预览", size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    cap.paragraph_format.space_after = Pt(4)
    _add_text(doc, "CadQuery 导出流程完成装配预检，STEP 文件重新导入后可读。此结果证明的是当前 CAD 文件生成和回读状态，不表示已经打印或验证水下性能。", size=10)

    _heading(doc, "7  结论与验证边界", 1)
    _add_text(doc, f"按论文中心线弧长方程反求后，连续函数满足 1,000 mm 弧长及 5/120 mm 理论端点宽度；42 个四边形对应 42 个角区间。打印段在单元 5、10、18 内以燕尾榫和横向锁销连接，第 18 单元切面向根部偏移 6 mm。")
    _add_text(doc, "打印前仍需完成切片与试块检查；随后验证拉索/燕尾强度、载荷与行程、材料兼容、5 m 等效压力与水密，以及 30 分钟热运行。论文空中样机不能替代本项目实测。")
    _heading(doc, "参考文献", 1)
    _add_text(doc, "[1] Wang, Z., Freris, N. M., & Wei, X. SpiRobs: Logarithmic spiral-shaped robots for versatile grasping across scales. Device 3(4), 100646 (2025). DOI: 10.1016/j.device.2024.100646.", size=8.5)
    _add_text(doc, "[2] 作者预印本，arXiv:2303.09861（https://arxiv.org/abs/2303.09861）；本文引用其几何定义、长度关系和单元比例式。", size=8.5)
    _heading(doc, "附录  复算数据与复现文件", 1)
    _add_table(
        doc,
        [
            ("根尖宽度比", f"{p['root_width_mm'] / p['tip_width_mm']:.0f}:1"),
            ("原始螺旋系数 a", f"{p['a_mm']:.12f} mm"),
            ("中心螺旋系数 a₁", f"{p['a1_mm']:.12f} mm"),
            ("增长参数 b", f"{p['b']:.12f}"),
            ("根部相位 θ₀", f"{p['theta0_rad']:.12f} rad"),
            ("单元角步长 Δθ", f"{p['delta_theta_deg']:.12f}°"),
            ("相邻单元比例 β", f"{p['beta']:.12f}"),
            (
                "中心线弧长",
                f"{p['centerline_length_reconstructed_mm']:.6f} mm",
            ),
            (
                "单元弧长范围",
                f"{min(p['unit_interval_lengths_mm']):.3f}–"
                f"{max(p['unit_interval_lengths_mm']):.3f} mm",
            ),
        ],
        headers=("项目", "复算值"),
    )
    _add_text(
        doc,
        "数值记录位于 V27螺旋参数.json，计算实现位于 spiral_parameters.py。"
        "build_spiral_derivation_report.py 生成本报告的 Markdown 与 DOCX，"
        "generate_v27_assembly.py 生成 V27 CAD 文件。公式回算不替代切片、"
        "材料试件、受力、密封和水下运行验证。",
        size=9.5,
    )
    doc.save(OUTPUT_DOCX)


def main() -> None:
    p = json.loads((HERE / "V27螺旋参数.json").read_text(encoding="utf-8"))
    segment_data = json.loads((HERE / "V27打印段导出.json").read_text(encoding="utf-8"))
    OUTPUT_MD.write_text(_markdown(p, segment_data), encoding="utf-8", newline="\n")
    _build_docx(p, segment_data)
    print(OUTPUT_MD)
    print(OUTPUT_DOCX)


if __name__ == "__main__":
    main()
