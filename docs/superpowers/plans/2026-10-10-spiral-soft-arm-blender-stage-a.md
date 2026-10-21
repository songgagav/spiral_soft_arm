# Blender 阶段 A 几何建模实施计划

> **供代理执行者阅读：** 执行本计划中的各项任务时必须使用 `superpowers:executing-plans` 技能。使用 `- [ ]` 复选框记录进度。

**目标：** 在用户本机 Blender 中参数化生成并验证三缆对数螺旋软臂的 A35、A36、B31、B32 四个主体候选，输出可复现的 `.blend`、STL 与几何检查报告。

**实现结构：** 四份带显式单位的 JSON 作为唯一输入；纯 Python 几何函数复核理论值并生成离散单元轮廓；Blender Python 在本机创建三维主体、弹性轴与三腱孔，保存场景并导出 STL；验证脚本重导入 STL，计算尺寸、网格有效性、最小壁厚、质量和重心。OpenSpiRobs 代码只作为公式和几何行为的本地参考。

**技术栈：** Blender 5.2.2 LTS 及其 Python/bpy/mathutils；Python 标准库 `json`、`hashlib`、`unittest`；本地 OpenSpiRobs `design-tool/DesignTool.py`。

**设计说明：** `docs/superpowers/specs/2026-10-10-spiral-soft-arm-prototype-design.md`

## 全局约束

- 使用 `D:\SteamLibrary\steamapps\common\Blender\blender.exe`，版本固定为 Blender 5.2.2 LTS。
- 初始候选固定 `p=0.5`、`delta_theta_deg=30`；A35=(N35, a=3.74959 mm, b=0.139608)、A36=(N36, a=3.43438 mm, b=0.140105)、B31=(N31, a=5.37465 mm, b=0.137107)、B32=(N32, a=4.90484 mm, b=0.137820)。
- 按本地生成器截止角关系使用 `theta_max_pi` 起始值 A35=7.9、A36=8.0、B31=7.3、B32=7.4，并验证实际单元数。
- 阶段 A 只生成软臂主体、弹性轴和三条腱孔；不生成底座、电机、电调、线轮和末端锚固件。
- JSON 长度字段使用 `_mm`、角度字段使用 `_deg`、孔位置/切除比例使用 `_pct`；百分数只在入口转换一次。
- Blender 网格坐标按 mm；STL 导出后重新导入的包围盒误差不得超过 0.1 mm；进入 SI 模型时长度乘 0.001 转为 m，质量用 kg、转动惯量用 kg·m²。
- 本地工作副本没有 `.git` 元数据；记录本地源文件 SHA-256，不填写虚构的本地提交号。上游参考提交固定为 `f563e69f292a6b8cac1946dc45ad9e60d8795391`。
- 报告的 TPU 质量是按材料密度计算的理论实体质量；不得将其乘以填充率来冒充切片打印质量。
- 阶段 A 的几何公差是 CAD 目标，不替代打印样条确定的制造公差或安全强度阈值。

## 审查重点

- `theta_max_pi` 的边界和浮点误差会改变整数单元数；参数测试必须断言 7.3→31、7.4→32、7.9→35、8.0→36。
- 百分数/小数混用会让腱孔位置偏移；参数测试必须检查 50.0% 在入口转换为 0.5，内部不重复除以 100。
- 三缆模式误设为双缆或额外切除造成穿孔/薄壁；Blender 检查必须确认三个 120° 腱孔，并分别报告三缆切除启用/关闭结果。
- Blender 与 STL 的坐标/单位处理可能造成 1000 倍缩放；重导入测试必须检查 550 mm 轴向长度、68 mm 基部直径及 0.1 mm 包围盒误差，并断言 550 mm→0.550 m。
- 布尔操作可能留下非流形边、断开的单元或意外打通孔壁；网格检查必须逐对象报告封闭性、法线、连通分量和代表截面最小壁厚。

---

### 任务 1：建立候选参数与版本清单

**文件：**
- 新建： `design-tool/blender/candidates/A35.json`
- 新建： `design-tool/blender/candidates/A36.json`
- 新建： `design-tool/blender/candidates/B31.json`
- 新建： `design-tool/blender/candidates/B32.json`
- 新建： `design-tool/blender/source_lock.json`
- 新建： `design-tool/blender/record_provenance.py`
- 新建： `design-tool/blender/tests/test_candidate_inputs.py`
- 新建： `design-tool/blender/README.md`

**接口：**
- 每份候选 JSON 包含 `schema_version`、`candidate_id`、`a_mm`、`b`、`num_units`、`delta_theta_deg`、`theta_max_pi`、`p`、`target_*_mm`、腱孔参数、三缆切除参数、三缆模式和轴向/单位定义。
- 初始腱孔位置采用本地工具参考值 `tip_hole_pos_pct=50.0`、`base_hole_pos_pct=90.0`；孔径起点 `tip_hole_diameter_mm=1.2`、`base_hole_diameter_mm=3.0`。本地三缆切除起点记录为启用、`cable3_cut_pos_pct=25.0`、`cable3_cut_size_pct=14.0`；关闭状态只作为诊断覆盖值，不改写候选 JSON。
- `source_lock.json` 记录 Blender 版本、生成脚本版本 `0.1.3`、上游提交号和链接、本地 `DesignTool.py` 及相关几何/导出源文件的 SHA-256，并明确 `local_git_commit: null`。

- [ ] **步骤 1： 写候选清单测试**

在 `test_candidate_inputs.py` 中断言存在且仅存在 A35/A36/B31/B32 四组候选，参数与全局约束一致，单位后缀合法，`p=0.5`、离散角 30°、`two_cable=false`、`cable_count=3`，孔位以 `_pct` 表示。

- [ ] **步骤 2： 运行测试并确认 JSON 缺失时失败**

运行：`& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\tests\test_candidate_inputs.py'`

预期结果：测试报告缺少候选文件并以非零退出码结束。

- [ ] **步骤 3： 写入四份候选 JSON 和参数说明**

将四组 `a/b/N/theta_max_pi` 与孔道、三缆切除、轴向和单位定义写入 JSON；在 README 标明 `cone_angle1_deg/2_deg` 不参与当前三缆主体生成，以及本地与上游默认值差异。

- [ ] **步骤 4： 实现并运行来源指纹记录器**

`record_provenance.py` 使用标准库计算本地参考源文件 SHA-256，并写入 `source_lock.json`。保留上游固定提交号，不在本地无 `.git` 的副本上运行或伪造 Git 提交号。

运行：`& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\record_provenance.py'`

预期结果：清单包含四份候选、Blender 5.2.2、脚本版本、本地哈希、上游提交号及空的本地 Git 提交字段。

- [ ] **步骤 5： 重新运行候选测试**

运行：`& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\tests\test_candidate_inputs.py'`

预期结果：所有字段、枚举和版本锁检查通过。

### 任务 2：实现理论几何、边界计数和单位转换

**文件：**
- 新建： `design-tool/blender/geometry.py`
- 新建： `design-tool/blender/tests/test_geometry.py`

**接口：**
- `count_units(theta_max_pi: float, delta_theta_deg: float) -> int`
- `paper_metrics(a_mm: float, b: float, num_units: int, delta_theta_deg: float) -> dict[str, float]`，输出 `tip_diameter_mm`、`base_diameter_mm`、`centerline_length_mm`。
- `percent_to_fraction(value_pct: float) -> float`、`mm_to_m(value_mm: float) -> float`、`mm3_to_m3(value_mm3: float) -> float`、`kg_mm2_to_kg_m2(value_kg_mm2: float) -> float`。
- 阶段 A 固定 `p=0.5`；理论式不得接受或静默应用其他 `p`。

- [ ] **步骤 1： 写几何与单位测试**

测试 7.3/7.4/7.9/8.0 对应的 31/32/35/36 单元；四组候选理论长度和基部直径在舍入误差 0.01 mm 内为 550/68 mm；尖端直径在 0.01 mm 内匹配 5.265/4.848/7.345/6.755 mm；并测试 50.0%→0.5、550 mm→0.550 m、体积和转动惯量单位转换。

- [ ] **步骤 2： 运行测试确认函数未定义时失败**

运行：`& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\tests\test_geometry.py'`

预期结果：因 `geometry.py` 接口不存在而失败。

- [ ] **步骤 3： 实现几何与单位函数**

`paper_metrics` 使用 SpiRobs 理想中心线关系；`count_units` 按 `floor((theta_max_pi-2)*180/delta_theta_deg)` 计算并处理边界浮点误差；`percent_to_fraction` 拒绝小于 0 或大于 100 的输入。

- [ ] **步骤 4： 运行理论公式与转换测试**

运行：`& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\tests\test_geometry.py'`

预期结果：四组理论尺寸、单元数映射及单位换算全通过。

### 任务 3：在 Blender 中生成四组主体与三腱孔

**文件：**
- 新建： `design-tool/blender/blender_geometry.py`
- 新建： `design-tool/blender/generate_candidates.py`
- 新建： `design-tool/blender/tests/test_blender_generation.py`

**接口：**
- `build_candidate(params: dict, cable3_cut_enabled: bool) -> list[bpy.types.Object]` 创建一个候选的主体与弹性轴，不创建底座、电机、线轮或末端锚固件。
- `generate_candidates(candidate_dir: str, output_dir: str) -> list[dict]` 读取四份 JSON，生成四份 `.blend`，并保留三缆额外切除开/关的诊断对象及参数记录。
- 腱孔中心由百分数参数在入口转换为小数，按 120° 均布；每个 Blender 候选主轴沿全局 Z，截面位于 XY 平面。

- [ ] **步骤 1： 写 Blender 后台生成测试**

断言后台场景生成四个候选集合、每个候选含主体/弹性轴和三条腱孔、孔方向相隔 120°，并且集合不含电机、底座、线轮、末端锚固对象。

- [ ] **步骤 2： 运行测试确认生成器缺失时失败**

运行：`& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\tests\test_blender_generation.py'`

预期结果：生成接口缺失时非零退出。

- [ ] **步骤 3： 移植本地三缆几何到 Blender 网格生成**

在 Blender Python 中复现本地 `_build_polar_units`、`_build_unfold_polygons` 的单元轮廓和 `p=0.5` 弹性轴；绕软臂轴生成三维主体，按本地三缆分支布置三个锥形腱孔；将三缆额外切除作为可开关诊断变体。不要调用上游才有的 `teardrop_holes`，也不把 CadQuery STL 导入后称为 Blender 原生模型。

- [ ] **步骤 4： 保存候选场景和导出 STL**

将四组场景写入 `local\spiral-soft-arm\stage-a\blend\`；导出主候选及切除关闭诊断 STL 到 `local\spiral-soft-arm\stage-a\stl\`。场景采用毫米坐标，STL 导出比例为 1.0。

- [ ] **步骤 5： 运行后台生成测试**

运行：`& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\tests\test_blender_generation.py'`

预期结果：四个候选均生成；每个候选都能保存并导出 STL；切除开/关变体分别存在。

### 任务 4：检查实体、单位、尺寸并生成比较报告

**文件：**
- 新建： `design-tool/blender/validate_candidates.py`
- 新建： `design-tool/blender/tests/test_stage_a_roundtrip.py`
- 新建： `local/spiral-soft-arm/stage-a/report.json` （生成文件）
- 新建： `local/spiral-soft-arm/stage-a/comparison.png` （生成文件）

**接口：**
- `validate_mesh(obj: bpy.types.Object) -> dict` 返回封闭/流形状态、法线、连通分量、体积、包围盒和尺寸。
- `measure_minimum_walls(obj: bpy.types.Object, params: dict) -> dict` 对每个单元及三腱孔代表截面返回孔到外壁、孔到弹性轴、孔间最小材料厚度。
- `validate_candidate(candidate_id: str, blend_path: str, stl_path: str) -> dict` 输出理论值与 Blender 网格实测差值、质量/重心、STL 往返误差和 SI 单位转换。

- [ ] **步骤 1： 写实体与导入往返测试**

测试四组网格可被 Blender 重新导入；闭合网格的非流形边数为 0、法线一致；重新导入的三轴包围盒误差不超过 0.1 mm；报告含中心线长度、基部最大实体直径、尖端尺寸和三条腱孔；确认 550 mm 转成 0.550 m。

- [ ] **步骤 2： 运行测试确认验证器缺失时失败**

运行：`& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\tests\test_stage_a_roundtrip.py'`

预期结果：验证接口缺失时非零退出。

- [ ] **步骤 3： 实现网格、尺寸和截面检查**

对每个候选及切除状态分别检查主体和弹性轴；按单元截面与腱孔截面记录最小壁厚、孔距及意外穿孔。阶段 A 报告实测值，不把尚无打印样条依据的最小壁厚写成通过的制造阈值。

- [ ] **步骤 4： 实现质量、重心和单位报告**

用封闭网格体积与 TPU 数据表密度计算 100% 实体理论质量和体积加权重心；标明此值不是切片质量。长度及行程 mm→m，体积 mm³→m³，质量 kg，转动惯量 kg·mm²→kg·m²，输出转换前后数值。

- [ ] **步骤 5： 导出、重新导入并生成比较报告**

运行生成器和验证器，输出 A35/A36/B31/B32 对比表、开/关额外切除对比、四组 `.blend`/STL、截面壁厚数据及 `comparison.png`。CAD 目标检查为长度 550±5.5 mm、基部 68±1 mm、尖端目标 ±0.5 mm；超差时保留实测结果并指出差值，不修改 `p` 或 `delta_theta_deg` 来掩盖偏差。

- [ ] **步骤 6： 运行阶段 A 全量验证**

运行：`& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\tests\test_stage_a_roundtrip.py'`

预期结果：所有候选通过 STL 往返、单位和网格有效性检查；尺寸结果在公差内，或报告明确列出未通过的候选及实际值；最小壁厚完整报告但不冒充打印强度认证。
