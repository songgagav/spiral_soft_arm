# B32 水下 MuJoCo 仿真与参数论文 Implementation Plan

**状态：** 已完成

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for Native execution or `superpowers:subagent-driven-development` for subagent-driven execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不覆盖 v1/v2 历史的前提下，完成 B32 淡水/海水、1 m/5 m MuJoCo 仿真，筛选当前搜索范围内的最佳可行参数，并交付可复核的中文推导论文。

**Architecture:** 在 `simulation/v2/` 建立独立的配置、几何/刚度派生、MJCF、浮力/驱动、运行器和候选搜索模块。运行器对四种水环境使用同一动作输入，并保存约束、状态和汇总；v3 论文从冻结配置与结果文件生成，报告模型边界与不确定性。

**Tech Stack:** Python 3.13；MuJoCo 3.15.0；NumPy 2.5.4；Matplotlib 3.11.2；Trimesh 5.1.1；python-docx；项目内 PowerShell 环境。

**Spec:** `docs/superpowers/specs/2026-10-11-b32-underwater-simulation-design.md`

## Global Constraints

- 不修改 `local/spiral-soft-arm/simulation/v1/`、`local/spiral-soft-arm/preprint/v1/` 或 `preprint/v2/` 历史文件。
- 名义几何基线为 `a=5.436777285 mm`、`b=0.13699`、`N=32`、`Δθ=30°`、`N·Δθ=5.333π`、`p=0.5`、3 缆、弹性层开启且占比 10%。
- B32 STL 名义体积为 `357146.451 mm³`；TPU 密度为 `1200 kg/m³`；仿真统一使用 SI 单位。
- 四环境固定为淡水/海水 × 1 m/5 m；名义水温 `20°C`，淡水 `ρ=998.2 kg/m³, μ=1.002 mPa·s`，海水 `ρ=1025 kg/m³, μ=1.08 mPa·s`。
- 目标基线为完全浸没的 `40 mm / 0.1 kg` 球体，初始球心沿用 `[0.036, 0, 0.1225] m`、支架顶面 `0.1025 m`、基座高度 `0.6 m`、悬挂朝下；名义动作时长 `2 s`，保持窗口按最后 `0.5 s` 评估。
- 3 路 M2006 P36 线轮独立受 `1 N·m` 扭矩包络、速度包络和 `0…20π rad`（10 圈）行程约束；速度包络近似为转速不超过 416 rpm（43.56 rad/s）时上限 1 N·m、416–500 rpm（52.36 rad/s）线性降至 0；`r=6.5 mm` 时理论最大行程约 `0.408 m`。
- 电机/电调放在干燥密封舱的仿真假设下工作；TPU 参数、流体阻力、摩擦和独立缆索张力上限均为显式可配置假设；仿真结果不构成压力舱校核、渗漏试验、材料强度、寿命或实机安全张力认证。
- 当前工作区没有 Git 元数据；实施在共享工作区完成，不创建 worktree 或 Git 提交，所有新增仿真和论文内容写入 v2/v3 新目录。

## Review Focus

- 单位或重力方向错误会破坏质量、浮力和姿态：`test_parameter_units_and_mass` 与 `test_buoyancy_equals_rho_g_volume` 检查 SI 转换和净力。
- 水深标签误改运动方程会造成虚假的深度效应：`test_same_water_depth_invariance` 比较同水体 1 m/5 m 结果，表压单独核对；相同输入下末端/线轮轨迹最大差值不超过 `1e-9`（SI）。
- 空间腱索、卷线角或扭矩符号错配会令收线/限位失效：`test_spool_tendon_mapping` 和 `test_motor_torque_and_travel_limits` 检查方向、长度、力矩与范围。
- 代理网格的体积误差会直接污染浮力：`test_segment_volume_conservation` 检查分段体积与 STL 总量的差值及归一化记录。
- “最佳”候选可能绕过几何/张力门槛或把未标定值当成实测：`test_candidate_gates_and_no_feasible_case` 检查门槛、无可行解分支和假设标记。

---

## 文件布局

- `local/spiral-soft-arm/simulation/v2/requirements.txt`：固定仿真运行依赖。
- `local/spiral-soft-arm/simulation/v2/configs/`：冻结 B32、四水环境、驱动和候选搜索配置。
- `local/spiral-soft-arm/simulation/v2/geometry.py`：分段几何代理、体积/质量和弹性轴截面数据。
- `local/spiral-soft-arm/simulation/v2/derive_parameters.py`：连续/离散几何复算与逐关节刚度/阻尼表。
- `local/spiral-soft-arm/simulation/v2/generate_mjcf.py`：由配置生成带 32 段、31 个柔顺球关节、3 路空间腱索和 3 个线轮的 MuJoCo 模型。
- `local/spiral-soft-arm/simulation/v2/underwater_physics.py`：分段浮力、目标球浮力、水体和压力标签。
- `local/spiral-soft-arm/simulation/v2/drive.py`：电机转矩/转速包络、线轮位置控制、腱索张力上限与行程限制。
- `local/spiral-soft-arm/simulation/v2/simulate.py`：运行单个环境并写逐步记录及摘要。
- `local/spiral-soft-arm/simulation/v2/sweep_candidates.py`：几何候选、材料/流体敏感性筛选及排序。
- `local/spiral-soft-arm/simulation/v2/render_results.py`：从 MuJoCo 状态生成论文图表。
- `local/spiral-soft-arm/simulation/v2/tests/`：配置、力学、驱动、运行器和搜索门槛测试。
- `local/spiral-soft-arm/simulation/v2/results/`：可复算输入副本、四环境 CSV/JSON、体积/刚度表、敏感性和汇总报告。
- `local/spiral-soft-arm/preprint/v3/`：中文 Markdown、DOCX、参数 JSON、论文图和仿真评估报告。

## Task 1: 冻结输入并复算几何与关节参数

**Files:**
- Create: `local/spiral-soft-arm/simulation/v2/requirements.txt`
- Create: `local/spiral-soft-arm/simulation/v2/configs/B32水下基线.json`
- Create: `local/spiral-soft-arm/simulation/v2/configs/水体工况.json`
- Create: `local/spiral-soft-arm/simulation/v2/configs/候选搜索空间.json`
- Create: `local/spiral-soft-arm/simulation/v2/geometry.py`
- Create: `local/spiral-soft-arm/simulation/v2/derive_parameters.py`
- Create: `local/spiral-soft-arm/simulation/v2/tests/test_parameters.py`
- Create: `local/spiral-soft-arm/simulation/v2/results/几何与关节参数.csv`
- Create: `local/spiral-soft-arm/simulation/v2/results/输入校验.json`

**Interfaces:**
- `load_inputs(config_dir: Path) -> dict` validates the baseline, four fluid cases and search space.
- `segment_body_properties(stl_path: Path, unit_geometry_path: Path, unit_count: int, density_kg_m3: float) -> list[dict]` returns per-segment proxy volume, mass, COM and inertia metadata; records any volume normalization against the frozen STL total.
- `derive_joint_table(baseline: dict, segments: list[dict]) -> list[dict]` returns per-joint bending/torsion stiffness and damping in SI units.
- First geometry search space: `N ∈ {31, 32, 33}`, `p=0.5`, `Δθ=30°`, `b ∈ [0.135, 0.142]` with a root solve per `N`, target envelope `550±5.5 mm × 68±1 mm`, and elastic-layer share `{5%, 10%, 15%}`. Fit `a` to the base diameter after each `b` trial; keep cable holes and third-cable cut at B32 values for this search.

- [x] 写 `test_parameter_units_and_mass`：固定基线字段、4 种流体工况、压力公式、`N·Δθ/π=16/3`、线轮 10 圈和依赖版本。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_parameters.py -v` 并确认缺少模块/配置时失败。
- [x] 实现配置读取与单位检查；将输入来源路径和文件 SHA-256 写入结果元数据。
- [x] 写 `test_segment_volume_conservation`：32 个分段代理体积之和须与 STL `357146.451 mm³` 相差不超过 1%；若归一化，输出归一化系数。
- [x] 再运行 `python -m unittest discover -s tests -p test_parameters.py -v`，确认体积用例在分段体积实现前失败。
- [x] 实现分段网格属性及逐关节 `k_bend, k_torsion, c_bend, c_torsion` 派生，输出有单位的 CSV/JSON。
- [x] 运行参数测试并手算复核总质量约 `0.428576 kg`、淡水/海水主体净向下力约 `0.71/0.61 N`。

## Task 2: 生成带空间腱索和线轮的 MuJoCo 模型

**Files:**
- Create: `local/spiral-soft-arm/simulation/v2/generate_mjcf.py`
- Create: `local/spiral-soft-arm/simulation/v2/B32_underwater.xml`
- Create: `local/spiral-soft-arm/simulation/v2/tests/test_model.py`

**Interfaces:**
- `build_mjcf(baseline: dict, body_properties: list[dict], joint_table: list[dict], water_case: dict) -> str` returns a compilable MJCF model.
- Model object inventory: 32 arm bodies, 31 ball joints, 3 spatial tendons, 3 spool hinge joints, 3 fixed spool tendons and 3 torque actuators.
- Spatial tendon length is coupled to spool rotation by an MJCF tendon equality relation initialized at the neutral pose; spool range is `0…20π rad` and effective radius is `0.0065 m`.

- [x] 写模型结构用例：MuJoCo 加载模型后核对身体、关节、腱索和执行器数量及 SI 重力。
- [x] 写 `test_fluid_properties_and_drag_enabled`：模型采用当前工况的水密度/黏度，水下刚体代理启用 fluid ellipsoid 属性。
- [x] 写 `test_spool_tendon_mapping`：小角度旋转每个线轮时，对应缆索自由长度变化方向一致且另两路不被交换。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_model.py -v`，确认因 MJCF 生成器/XML 尚未实现而失败。
- [x] 实现 32 段碰撞/流体代理、31 个弹性关节和线轮/空间腱索耦合；网格代理与分段属性表使用同一命名索引。
- [x] 配置 `option density/viscosity` 与 fluid ellipsoid 属性，接触摩擦基线沿用 v1 的 `0.8 0.02 0.002`，采用隐式积分选项；不在 XML 中以深度改变刚体材料或浮力。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_model.py -v`，预期 3 个缆路与卷线行程都可加载且方向正确。

## Task 3: 实现水下受力与受限驱动

**Files:**
- Create: `local/spiral-soft-arm/simulation/v2/underwater_physics.py`
- Create: `local/spiral-soft-arm/simulation/v2/drive.py`
- Create: `local/spiral-soft-arm/simulation/v2/tests/test_underwater_physics.py`
- Create: `local/spiral-soft-arm/simulation/v2/tests/test_drive.py`

**Interfaces:**
- `apply_buoyancy(model, data, volumes_m3: dict[int, float], fluid_density_kg_m3: float, gravity_m_s2: float) -> dict` applies each submerged body’s upward force at its world COM and returns a force audit.
- `motor_torque_limit(speed_rad_s: float, envelope: list[dict]) -> float` returns the absolute speed-dependent torque limit, capped at `1 N·m`.
- `command_torque(desired_nm: float, speed_rad_s: float, spool_radius_m: float, cable_force_limit_n: float, envelope: list[dict]) -> dict` returns signed applied torque and separate motor/tendon saturation flags.
- `apply_drive_limits(model, data, controller_state: dict, drive_config: dict) -> dict` clamps spool commands to `0…20π rad` and limits cable tension via `min(motor_torque_limit, cable_force_limit_n·spool_radius_m)`.

- [x] 写 `test_buoyancy_equals_rho_g_volume`：`F_b=ρgV`，目标球 40 mm 球体积按解析公式计算，四环境压力均按 `ρgh`。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_underwater_physics.py -v`，确认浮力函数尚未实现时失败。
- [x] 实现逐刚体浮力和目标球浮力，并检查分段合力与全体 `ρgV_total` 一致。
- [x] 写 `test_motor_torque_and_travel_limits`：输入反向保持符号、扭矩不超过 1 N·m、416–500 rpm 速度包络线性收紧、缆索力限独立生效、线轮永不越过 0 或 `20π rad`。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_drive.py -v`，确认驱动限制函数尚未实现时失败。
- [x] 实现可配置线轮位置 PD 控制及扭矩/速度/张力/角行程钳制；名义张力上限沿用 `0.15 N`，`0.30/0.60/1.00 N` 只作仿真敏感性探针并标为未经强度试验批准。
- [x] 在 `simulation/v2/` 分别运行 `python -m unittest discover -s tests -p test_underwater_physics.py -v` 和 `python -m unittest discover -s tests -p test_drive.py -v`，并检查每种饱和都有通道名和时间戳字段。

## Task 4: 运行四环境水下运动仿真

**Files:**
- Create: `local/spiral-soft-arm/simulation/v2/simulate.py`
- Create: `local/spiral-soft-arm/simulation/v2/run_cases.py`
- Create: `local/spiral-soft-arm/simulation/v2/tests/test_simulation.py`
- Create: `local/spiral-soft-arm/simulation/v2/results/淡水_1m.csv`
- Create: `local/spiral-soft-arm/simulation/v2/results/淡水_5m.csv`
- Create: `local/spiral-soft-arm/simulation/v2/results/海水_1m.csv`
- Create: `local/spiral-soft-arm/simulation/v2/results/海水_5m.csv`
- Create: `local/spiral-soft-arm/simulation/v2/results/四工况汇总.json`

**Interfaces:**
- `run_case(config_path: Path, case_id: str, output_dir: Path) -> dict` creates the model, applies buoyancy/drive each MuJoCo step and returns per-case metrics.
- Per-step CSV records time, 32 segment poses, tip pose, three cable lengths/tensions, three spool angles/speeds/torques, contact state, solver warnings and saturation flags.
- Target task success: during the final `0.5 s` of the 2 s run, the ball remains in continuous arm contact and is lifted at least `5 mm` above the support; report all failed conditions independently.

- [x] 写 `test_four_environment_runs` 与 `test_same_water_depth_invariance`：每种环境运行 2 s、状态有限、所有饱和字段存在、每步记录行数与步长一致；同水体 1 m/5 m 末端/线轮轨迹最大差值不超过 `1e-9`（SI），接触状态一致。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_simulation.py -v`，确认运行器未实现时失败。
- [x] 实现共用初始状态与动作时序的四工况运行器；同时保存每步 CSV 和含配置散列/压力/体积审计的 JSON 摘要。
- [x] 检查目标球浮力、接触、提起距离、最后 0.5 s 保持、末端误差、约束触发和数值稳定性字段。
- [x] 在同一水体内比较 1 m/5 m 的姿态与接触轨迹；压力仅为元数据时结果差异应在离散积分容差内，偏离时定位非压力输入差异。
- [x] 运行四个名义工况；保存求解器设置、引擎版本、运行时间和每个候选失败原因。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_simulation.py -v`，预期四环境和深度不变性用例通过。

## Task 5: 筛选候选并做敏感性分析

**Files:**
- Create: `local/spiral-soft-arm/simulation/v2/sweep_candidates.py`
- Create: `local/spiral-soft-arm/simulation/v2/tests/test_candidate_sweep.py`
- Create: `local/spiral-soft-arm/simulation/v2/results/候选排序.csv`
- Create: `local/spiral-soft-arm/simulation/v2/results/敏感性汇总.json`
- Create: `local/spiral-soft-arm/simulation/v2/results/最佳候选参数.json`

**Interfaces:**
- `evaluate_candidate(candidate: dict, water_cases: list[dict], sensitivity: dict) -> dict` returns geometry gates, per-case task success, peak motor torque, peak cable tension, line travel, robustness score and failure reasons.
- `select_best_candidate(evaluations: list[dict]) -> dict | None` rejects any geometry/task/drive-gate failure; returns `None` when the search has no feasible candidate.
- The first search uses `N={31,32,33}`, `b ∈ [0.135,0.142]` and elastic share `{5%,10%,15%}`; set `theta_max_pi=7.4+(N-32)/6` to reproduce the generator's integer-count rule, re-fit `a` to base diameter and solve `b` for `550 mm × 68 mm`, then recompute tip, wall, mesh volume, mass and stiffness. Keep `p`, angle step, cable holes and cut at approved B32 baselines.
- Sensitivity runs vary nominal TPU modulus by `{0.5,1.0,1.5}×`, damping ratio by `{0.5,1.0,1.5}×`, first contact-friction coefficient from the v1 baseline `0.8` by `{0.5,1.0,1.5}×`, fluid drag by `{0.5,1.0,2.0}×`, and tendon force caps by `{0.15,0.30,0.60,1.00} N`; label all non-nominal values as modeling probes.

- [x] 写 `test_candidate_gates_and_no_feasible_case`：低壁厚、超尺寸、任务失败、超过扭矩/张力/行程的候选均被拒绝；空可行集合返回 `None`。另核对模量、阻尼、摩擦、拖曳、张力上限各敏感性项都有记录。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_candidate_sweep.py -v`，确认搜索模块尚未实现时失败。
- [x] 实现几何重拟合、四环境任务评估和敏感性汇总；先运行几何门槛以跳过不合格的动态计算。
- [x] 对所有通过几何门槛的候选完成四工况名义仿真与指定的单因素敏感性；避免将未标定的材料或力上限称为实测最佳值。
- [x] 依规格的优先序排序可行候选：先满足全部门槛，再依次降低峰值扭矩、张力和收线行程；若无可行解，输出明确的“当前搜索范围内无可行解”。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_candidate_sweep.py -v`，预期门槛和无解分支用例通过；复核排序文件中的每项结果能回溯到候选配置和仿真记录。

## Task 6: 生成图表、评估报告和 v3 论文

**Files:**
- Create: `local/spiral-soft-arm/simulation/v2/render_results.py`
- Create: `local/spiral-soft-arm/simulation/v2/results/水下工况与约束图.png`
- Create: `local/spiral-soft-arm/preprint/v3/水下仿真评估报告.md`
- Create: `local/spiral-soft-arm/preprint/v3/B32水下参数推导论文.md`
- Create: `local/spiral-soft-arm/preprint/v3/B32水下参数推导论文.docx`
- Create: `local/spiral-soft-arm/preprint/v3/B32最终参数.json`
- Create: `local/spiral-soft-arm/preprint/v3/figures/`
- Create: `local/spiral-soft-arm/simulation/v2/tests/test_report.py`

**Interfaces:**
- `render_summary(results_dir: Path, output_dir: Path) -> list[Path]` renders pressure/buoyancy audit, four-environment response, spool/torque/tension and candidate sensitivity from saved numeric outputs.
- `build_paper(markdown_path: Path, output_path: Path, figures_dir: Path) -> None` generates the Chinese DOCX from Markdown and embedded figures.
- Final parameter JSON includes every field requested in the spec, exact units, derivation basis and calibrated/un-calibrated status.

- [x] 写 `test_report_uses_selected_candidate`：最终参数字段齐全、四工况结果与 JSON 摘要相同、没有可行候选时禁止填“最佳”。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_report.py -v`，确认报告生成接口尚未实现时失败。
- [x] 实现图表和 Markdown 报告，逐一说明 `a,b,Δθ,N·Δθ/π,theta_max_pi,p`、孔位/孔径、弹性层、刚度/阻尼、切割和驱动参数。
- [x] 实现 DOCX 生成并引用 MuJoCo、DJI、水体物性等来源；明确 5 m 表压约 49–50 kPa，运动仿真不能代替压力舱结构校核或渗漏试验。
- [x] 尝试用 `render_docx.py` 渲染论文；因 Windows 环境未安装 LibreOffice/`soffice.exe`，改用本机 Word 导出 PDF、PDFium 渲染全部 4 页并逐页检查；修正分页、表格、公式和图题后再次复核。
- [x] 按 `documents` skill 做最终 Word/PDF 页面布局检查，并校验 Markdown、参数 JSON、图表与 DOCX 使用同一候选和结果。
- [x] 在 `simulation/v2/` 运行 `python -m unittest discover -s tests -p test_report.py -v`，预期 DOCX、Markdown、JSON 和汇总图采用相同候选 ID 与四环境结果。

## Whole-task verification

- [x] 在 `local/spiral-soft-arm/simulation/v2/` 执行 `python -m unittest discover -s tests -v`；预期全部配置、物理、驱动、模型、运行器和候选测试通过。
- [x] 执行 `python run_cases.py --all`；预期生成淡水/海水 × 1 m/5 m 的完整记录和摘要，无非有限状态或未解释的约束越界。
- [x] 执行 `python sweep_candidates.py --config configs/候选搜索空间.json`；预期每个候选均有几何门槛结果、四工况结论和敏感性记录。
- [x] 执行 `python render_results.py` 并生成最终参数文件和论文；渲染每一页 DOCX 后人工检查布局。
- [x] 最终报告确认 v1/v2 文件未被改写，并将任何无可行解、数值不稳定或引擎限制明确写入结论。


