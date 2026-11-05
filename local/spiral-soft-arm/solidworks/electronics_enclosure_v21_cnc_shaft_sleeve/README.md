# M3508 D 轴套联轴套 CNC 首件图（Rev A）

> 当前 v23 总装将这件轴套仅用作干仓内的 D 轴扭矩联轴套；Ø16 外圆不承担湿侧轴封功能。本页保留 Rev A 首件图的原始设计假设，现行密封接口见 [v23 说明](../electronics_enclosure_v23_cable_and_seal_interfaces/README_拉索过渡与轴封接口.md)。

本目录包含一个安装在 DJI M3508 输出轴上的金属轴套/联轴套候选件。轴套外圆 Ø16 是拟定的轴封跑道；轴套把电机 D 轴接口延伸为圆柱接口。文件用于 CNC 首件评审与报价，不是批量生产放行文件。

## 文件

- `M3508_D轴套联轴套_CNC首件图_RevA.pdf`：推荐查看和打印的尺寸图，单位 mm，标注尺寸优先。
- `M3508_D轴套联轴套_CNC首件图_RevA.dxf`：二维 CAD 图。已由 DXF 读取器重新打开，包含 83 个模型空间实体。
- `M3508_D轴套联轴套_CNC模型_RevA.step`：单实体 STEP 中性模型，可用于 CAM/装配检查。
- `M3508_D轴套联轴套_CNC首件图_RevA.png`：图纸预览。
- `CNC_dimensions_and_source.json`：尺寸、来源文件哈希及 STEP 重导入检查结果。
- `generate_cnc_sleeve.py`：生成模型和图纸的脚本。

## Rev A 主要尺寸

- 总长 20.00 mm；外径 Ø16 h11。两端 0.3 × 45° 去锐边。
- 电机端 D 孔：圆弧直径 Ø10.20 `+0.05/0`，对边 AF9.20 `+0.05/0`，深 12.30 mm。
- 延长轴端圆孔：Ø10.20 `+0.05/0`，深 7.70 mm。
- 2 × M3 × 0.5-6H 径向螺纹孔，相隔 180°，孔中心距电机端面 16.20 mm；STEP 几何按 Ø2.5 mm 底孔表示，螺纹需由 CNC 工序加工。
- 中心通道不攻牙，预留轴向 M5 固定螺钉通道；螺钉长度、头型和与延长轴的装配关系需按实物总成确认。
- 轴封候选：Freudenberg B2PT 16 × 35 × 7，料号 40412791。轴套图只定义 Ø16 跑道；轴承/密封座孔不属于本零件。

## 尺寸来源和限制

电机轴名义尺寸来自官方 M3508 STEP：Ø10.00、AF9.00。源文件为 `electronics_enclosure_v18/references/official/DJI_M3508_P19_official.stp`，SHA-256 为 `12E62A62C12495210FEB74F1272F4D71CFFED070FD91A601D646B6C2A6D57087`。官方模型不提供实物制造公差，因此电机 D 孔配合值是首件拟合值。加工前需测量手头电机的轴径、对边、平面方向、有效插入长度及轴端 M5 螺纹；还需核对延长轴/齿轮和 M3 紧定螺钉位置。首件试装通过前不要批量复刻。

轴封型号仍为候选。Freudenberg 的 B2PT 资料将水介质应用列为需询问制造商，并说明其无弹簧结构在静止时仅提供有限密封。因此不能据此宣称该结构已达到 5 m 防水要求。下单轴封前，应让供应商按实际转速、压力、介质和轴材料确认适用性，并取得该型号的安装图。

轴封跑道表面要求暂按参考值标注：Ø16 h11、圆度 IT8、Rz 1.0–4.0 µm、Rmax ≤ 6.3 µm、硬度 ≥45 HRC、无螺旋导程。材料和表面处理尚未锁定，必须同时满足轴封要求和淡水/海水耐蚀要求；请供应商确认材料及热处理/涂层方案后再加工。不能将普通 3D 打印塑料作为该跑道材料。

## 模型检查状态

STEP 重导入后为 1 个有效实体，包围盒 16 × 16 × 20 mm，体积约 2404.746 mm³。DXF 文件可以正常读取。以上只检查数字文件结构和尺寸边界，不代表电机实物配合、密封性能、强度或水下试验已经验证。

## 参考资料

- [DJI RoboMaster M3508 产品页](https://www.robomaster.com/zh-CN/products/components/general/M3508)
- [Freudenberg B2PT 40412791 产品页](https://products.fst.com/global/en/categories/radial-shaft-seal-simmerring-b2pt/products/40412791)
- [Freudenberg B2PT 数据表](https://products.fst.com/pim/assets/category/datasheet/productdatasheet_b2pt_en.pdf)
- [Freudenberg/Dichtomatik 2026 径向轴封设计手册](https://dichtomatik.fst.com/-/media/files/brochures/en/2026/dichtomatik_radialshaftseals_brochure_en_2026.pdf)
