# B32 Wet-Side Actuator Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for Native execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 B32 三缆软臂改为三路湿侧水下驱动，优先评估 ApisQueen 4092，完成参数化安装件与淡水/海水 1 m/5 m MuJoCo 重算，并交付可复核的 v4 中文论文。

**Architecture:** 保留 v2 仿真、v3 论文和 motor_mount_v1 不变，在新版本目录内复用已经验证的几何/水体处理模式。以统一的电机候选 JSON 保存供应商原始声明、来源、单位和未验证项；驱动模型、CAD 和论文都读取同一候选数据。4092 先按供应商输出端数据及不确定范围建模；若取得样机，再用实测曲线替代临时曲线。M200 保留为后备。

**Tech Stack:** Python 3.13；MuJoCo 3.15.0；NumPy 2.5.4；Matplotlib 3.11.2；Trimesh 5.1.1；CadQuery；python-docx；项目现有 PowerShell 环境。

**Spec:** `docs/superpowers/specs/2026-10-11-b32-wet-side-actuator-redesign.md`

## Global Constraints

- 湿侧成本优先样机候选为 ApisQueen 4092；Blue Robotics M200 是后备，F3130 只作低单价参考。任何候选未通过接口、负载、温升和浸水验证前都不得标成最终选型。
- 4092 网页声明为 12–24 V、50:1 减速、310 g、80 W、约 0–100/0–200 rpm；24 V 空载 108 rpm，供应商扭矩表从 20 rpm / 4.5 N·m 到 100 rpm / 0.23 N·m。规格存在内部不一致，不得作为已校准连续曲线。
- 旧 B32 几何冻结值：`a=5.436777 mm`、`b=0.13699`、32 单元、`Δθ=30°`、离散角跨度 `N·Δθ=5.333π`（约 2.667 圈），并将生成器截止 `theta_max_pi=7.4` 单独记录、不可当作实际圈数；`p=0.5`、主体体积 `0.357146 L`、3 缆、弹性层 10%、尖端孔 50%/1.2 mm、根部孔 90%/3.0 mm、第三缆切割 25%/14%。
- 旧线轮 `r=6.5 mm`、10 圈、行程 `0…20π rad`、理论线长约 `0.4084 m` 作为对照；最终尺寸须与线缆和 CAD 结构一致。
- 四工况固定为淡水/海水 × 1 m/5 m；基准水温 `20°C`，淡水 `ρ=998.2 kg/m³, μ=1.002 mPa·s`，海水 `ρ=1025 kg/m³, μ=1.08 mPa·s`。
- 水下运动仿真不模拟壳体压力应力或密封可靠性。5 m 表压约 49–50 kPa；仿真不能替代压力舱结构校核或渗漏试验。
- 新文件放在 `simulation/v3/`、`solidworks/motor_mount_v2/`、`preprint/v4/`；不得改写 `simulation/v2/`、`preprint/v3/` 或 `motor_mount_v1/`。
- 当前工作目录没有 Git 元数据；不创建 worktree 或 Git 提交。验证命令在各新版本目录执行。

## Review Focus

- 电机商品标题和性能表彼此不一致：`test_candidate_claims_keep_source_conflicts` 应验证冲突被保留、标为未确认，而不是静默挑选一个值。
- 线轮目标速度可能接近 4092 空载速度：`test_output_envelope_saturation_at_task_speed` 应验证 8 rad/1 s 目标与有载速度边界、限幅日志。
- 减速输出力矩远大于旧名义腱力矩：`test_force_limit_caps_spool_torque` 应验证张力约束先于执行器输出并记录限幅通道。
- 电机质量不等于水中表观质量：`test_motor_mass_and_displaced_volume_are_separate` 应验证完整湿侧部件质量/排水体积独立进入浮力核算。
- 目标物浮力必须进入任务模型：`test_target_mass_and_displaced_volume_enter_buoyancy_balance` 应验证目标物质量与排水体积均进入浮力审计。
- 深度标签不能伪造运动压力效应：`test_same_water_depth_invariance` 应比较同水体 1 m/5 m 的线轮和末端轨迹。

---

## 文件布局

- `local/spiral-soft-arm/simulation/v3/requirements.txt`：复制并锁定 v2 仿真运行依赖。
- `local/spiral-soft-arm/simulation/v3/configs/B32湿侧基线.json`：冻结 B32 几何/任务基线和新驱动控制参数。
- `local/spiral-soft-arm/simulation/v3/configs/电机候选.json`：4092、M200、F3130 的原始数据、单位、来源、数据状态和选择标志。
- `local/spiral-soft-arm/simulation/v3/configs/水体工况.json`：淡水/海水物性与 1 m/5 m 表压。
- `local/spiral-soft-arm/simulation/v3/configs/候选搜索空间.json`：沿用 v2 的几何搜索范围，并记录执行器与材料/流体不确定性范围、硬约束和排序规则。
- `local/spiral-soft-arm/simulation/v3/candidate_data.py`：电机规格读取、来源/状态校验和候选差异报告。
- `local/spiral-soft-arm/hardware/4092_单台样机验证流程与记录模板.md`：来料、接口、负载/温升、反馈和浸水验证流程及空白记录表；没有样机时明确标记未执行。
- `local/spiral-soft-arm/simulation/v3/drive.py`：线轮侧扭矩/速度包络、位置控制、张力/行程限幅和事件审计。
- `local/spiral-soft-arm/simulation/v3/geometry.py`、`derive_parameters.py`：沿用并复核 v2 的网格分段、体积、质量、惯量和逐关节刚度/阻尼。
- `local/spiral-soft-arm/simulation/v3/generate_mjcf.py`：生成 32 单元软臂、31 个柔顺关节、三路湿侧驱动刚体、三条腱索与三只线轮。
- `local/spiral-soft-arm/simulation/v3/underwater_physics.py`：软臂、驱动组件、目标物的质量/排水体积映射和浮力审计。
- `local/spiral-soft-arm/simulation/v3/simulate.py`、`run_cases.py`：单工况和四工况运行、逐步日志和深度不变性检查。
- `local/spiral-soft-arm/simulation/v3/sweep_candidates.py`：驱动候选与不确定参数敏感性评估。
- `local/spiral-soft-arm/simulation/v3/render_results.py`、`tests/`、`results/`：测试、图表、参数/结果报告和审计数据。
- `local/spiral-soft-arm/solidworks/motor_mount_v2/parameters.json`、`generate_motor_mount.py`、`test_motor_mount.py`：4092 候选尺寸/安装参数、参数化装配生成和几何验收。
- `local/spiral-soft-arm/solidworks/motor_mount_v2/` 输出：总装 STEP、安装件 STEP、打印 STL、预览 PNG、装配/干涉审计 JSON、质量和浮力表、README。
- `local/spiral-soft-arm/preprint/v4/`：水下驱动参数报告、可审阅 Markdown、参数 JSON、图表和中文 DOCX。

## Task 1: 建立驱动候选数据和来源审计

**Files:**
- Create: `local/spiral-soft-arm/simulation/v3/configs/B32湿侧基线.json`
- Create: `local/spiral-soft-arm/simulation/v3/configs/电机候选.json`
- Create: `local/spiral-soft-arm/simulation/v3/configs/水体工况.json`
- Create: `local/spiral-soft-arm/simulation/v3/configs/候选搜索空间.json`
- Create: `local/spiral-soft-arm/simulation/v3/candidate_data.py`
- Create: `local/spiral-soft-arm/simulation/v3/tests/test_candidate_data.py`
- Create: `local/spiral-soft-arm/simulation/v3/results/电机候选来源审计.json`
- Create: `local/spiral-soft-arm/hardware/4092_单台样机验证流程与记录模板.md`

**Interfaces:**
- `load_candidates(path: Path) -> dict[str, Any]` returns raw source rows and normalized SI fields without dropping contradictory claims.
- `validate_candidates(document: dict[str, Any]) -> list[dict[str, str]]` returns candidate ID, field, severity, and issue for missing/contradictory/unverified inputs.
- `write_candidate_audit(document: dict[str, Any], issues: list[dict[str, str]], output_path: Path) -> Path` writes JSON audit.

- [x] **Step 1: Write the failing data-contract tests** for `test_candidate_claims_keep_source_conflicts`, `test_motor_candidate_units_normalize_to_si`, and `test_missing_continuous_curve_is_unqualified`.
- [x] **Step 2: Run the focused tests and confirm the initial failure**

Run from `local/spiral-soft-arm/simulation/v3/`: `python -m unittest tests.test_candidate_data -v`

Expected: FAIL because the v3 config and candidate reader do not exist.

- [x] **Step 3: Create the isolated v3 configuration and candidate reader**. Copy frozen B32 geometry/task values and four water cases from v2 without modifying v2. Preserve source values and URLs; carry forward v2 geometry search variables (`N`, `b`, elastic-layer share, derived `a`, and the `theta_max_pi` generator-cutoff rule) and add explicit motor/material/drag/force uncertainty ranges and gate-based ranking. Set 4092 `qualification_status` to `single_sample_required`; do not set `final_selected=true`.
- [x] **Step 4: Create the one-sample qualification protocol and blank record**. Cover incoming inspection, dimensions/output interface, loaded speed/torque/current, temperature and duty cycle, feedback/control behavior, and freshwater/seawater exposure. Record test setup and evidence. Any 5 m pressure test must use a properly rated setup after assembly review; a tank immersion is not 5 m qualification. Do not purchase hardware as part of this implementation; if no sample is available, leave physical gates pending and the candidate unqualified.
- [x] **Step 5: Run the focused tests**

Run: `python -m unittest tests.test_candidate_data -v`

Expected: PASS; conflicting RPM claims remain visible, SI values have units, and missing continuous/thermal data leaves the candidate unqualified.

- [x] **Step 6: Write `results/电机候选来源审计.json`** with page retrieval time, prices/availability, unavailable or contradictory fields and the next data needed from the supplier.
- [x] **Step 7: Run focused tests again**

Run: `python -m unittest tests.test_candidate_data -v`

Expected: PASS; the audit round-trips through JSON without NaN or lost source metadata.

## Task 2: Implement constrained line-wheel actuator behavior

**Files:**
- Create: `local/spiral-soft-arm/simulation/v3/drive.py`
- Create: `local/spiral-soft-arm/simulation/v3/tests/test_drive.py`
- Modify: `local/spiral-soft-arm/simulation/v3/configs/电机候选.json`

**Interfaces:**
- `output_torque_limit(speed_rad_s: float, envelope: list[dict[str, float]]) -> float` interpolates a measured/provisional output-shaft torque envelope by absolute output speed.
- `command_torque(desired_nm: float, speed_rad_s: float, spool_radius_m: float, cable_force_limit_n: float, envelope: list[dict[str, float]]) -> dict[str, Any]` clamps requested torque to output-speed and tendon-force limits.
- `apply_drive_limits(model: mujoco.MjModel, data: mujoco.MjData, controller_state: dict[str, Any], drive_config: dict[str, Any]) -> dict[str, Any]` applies three position commands with speed, output-torque, tendon-force and travel limits and returns per-channel audit rows/events.

`drive_config` also carries current, continuous/peak duration, thermal and duty-cycle constraints; values without source data stay explicitly unknown and prevent hardware qualification.

- [x] **Step 1: Write failing tests** `test_force_limit_caps_spool_torque`, `test_output_envelope_interpolation_and_reverse`, `test_output_envelope_saturation_at_task_speed`, `test_spool_travel_limits_all_channels`, and `test_event_log_records_reason_and_time`.
- [x] **Step 2: Run the focused tests and confirm they fail**

Run: `python -m unittest tests.test_drive -v`

Expected: FAIL because v3 actuator functions do not exist.

- [x] **Step 3: Implement the output-side actuator model**. For 4092, treat the integrated gearbox output as the spool drive input and use a provisional envelope only with source/qualification metadata; do not multiply its stated gearbox ratio twice. For M200, explicitly apply external reducer ratio and efficiency. Apply configured current, continuous/peak duration, thermal and duty-cycle limits when data exist; when absent, expose the unknowns and keep the candidate unqualified. Use the previous B32 tendon cap only as an unvalidated simulation limit.
- [x] **Step 4: Run the focused drive tests**

Run: `python -m unittest tests.test_drive -v`

Expected: PASS; signed torque is bounded by output envelope, configured tendon limit, and `0…20π rad` travel; saturation events identify channel and time.

## Task 3: Extend wet-body properties and generate the MJCF assembly

**Files:**
- Create: `local/spiral-soft-arm/simulation/v3/geometry.py`
- Create: `local/spiral-soft-arm/simulation/v3/derive_parameters.py`
- Create: `local/spiral-soft-arm/simulation/v3/underwater_physics.py`
- Create: `local/spiral-soft-arm/simulation/v3/generate_mjcf.py`
- Create: `local/spiral-soft-arm/simulation/v3/tests/test_model.py`
- Create: `local/spiral-soft-arm/simulation/v3/tests/test_underwater_physics.py`
- Create: `local/spiral-soft-arm/simulation/v3/tests/test_parameters.py`

**Interfaces:**
- `segment_body_properties(stl_path: Path, unit_geometry_path: Path, unit_count: int, density_kg_m3: float) -> list[dict[str, Any]]` returns per-cell mass, volume, COM and inertia data.
- `build_drive_body_properties(candidate: dict[str, Any], mounting: dict[str, Any]) -> list[dict[str, Any]]` returns three drive mass/inertia/volume/drag proxies; unknown values must carry uncertainty metadata.
- `build_target_body_properties(target_config: dict[str, Any]) -> dict[str, Any]` returns target mass, geometry, displaced volume and provenance.
- `build_volume_map(model: mujoco.MjModel, segments: list[dict[str, Any]], drive_bodies: list[dict[str, Any]], target_body: dict[str, Any]) -> dict[int, float]` maps submerged body IDs, including the target, to displaced volume.
- `apply_buoyancy(model: mujoco.MjModel, data: mujoco.MjData, volumes: dict[int, float], water_density_kg_m3: float, gravity_m_s2: float) -> dict[str, Any]` applies and audits per-body buoyancy.
- `build_mjcf(baseline: dict[str, Any], body_properties: list[dict[str, Any]], joint_table: list[dict[str, Any]], drive_bodies: list[dict[str, Any]], target_body: dict[str, Any], water_case: dict[str, Any]) -> str` returns a compilable model with target mass and geometry.

- [x] **Step 1: Write failing tests** `test_segment_volume_conservation`, `test_motor_mass_and_displaced_volume_are_separate`, `test_drive_bodies_receive_fluid_properties`, `test_target_mass_and_displaced_volume_enter_buoyancy_balance`, and `test_generated_model_has_three_independent_wet_drives`.
- [x] **Step 2: Run model/physics tests and confirm failure**

Run: `python -m unittest tests.test_parameters tests.test_underwater_physics tests.test_model -v`

Expected: FAIL because wet drive bodies and v3 configuration are absent.

- [x] **Step 3: Implement segment, target and motor body tables** using v2 methods for the unchanged B32 arm, target mass/geometry from the frozen task config, and 4092 measured dimensions/mass/displacement when available. Until measured, store supplier mass separately from a parameterized volume range; do not infer water weight from air mass alone.
- [x] **Step 4: Implement wet-drive MJCF bodies and buoyancy mapping** for three motors/reducers/spools. Keep dry controller/battery outside the water model. Apply fluid drag proxies to the submerged assemblies.
- [x] **Step 5: Run model and physics tests**

Run: `python -m unittest tests.test_parameters tests.test_underwater_physics tests.test_model -v`

Expected: PASS; total arm volume reconciles to the B32 STL, each wet drive has independent mass and displacement entries, and MuJoCo loads exactly three separate drive channels.

## Task 4: Run four environments and sensitivity sweeps

**Files:**
- Create: `local/spiral-soft-arm/simulation/v3/simulate.py`
- Create: `local/spiral-soft-arm/simulation/v3/run_cases.py`
- Create: `local/spiral-soft-arm/simulation/v3/sweep_candidates.py`
- Create: `local/spiral-soft-arm/simulation/v3/tests/test_simulation.py`
- Create: `local/spiral-soft-arm/simulation/v3/tests/test_candidate_sweep.py`
- Create: `local/spiral-soft-arm/simulation/v3/results/`

**Interfaces:**
- `run_case(config_path: Path, case_id: str, output_dir: Path, full_state_log: bool = False) -> dict[str, Any]` records per-step state, motor/line constraints and result summary.
- `run_all(config_path: Path, output_dir: Path) -> dict[str, Any]` runs `fresh_1m`, `fresh_5m`, `sea_1m`, `sea_5m` from matched initial states.
- `compare_depth_pairs(results: dict[str, dict[str, Any]]) -> dict[str, float]` returns max absolute trace differences for each water type.
- `evaluate_candidate(candidate: dict[str, Any], water_cases: list[dict[str, Any]], sensitivity: dict[str, Any]) -> dict[str, Any]` returns task/geometry/drive gates, margins and failure reasons.
- `select_best_candidate(evaluations: list[dict[str, Any]]) -> dict[str, Any] | None` returns a candidate only when every specified gate passes.

- [x] **Step 1: Write failing tests** `test_four_environment_runs`, `test_same_water_depth_invariance`, `test_motor_load_and_spool_limits_are_logged`, and `test_candidate_gate_keeps_unqualified_motor_unqualified`.
- [x] **Step 2: Run simulation tests and confirm failure**

Run: `python -m unittest tests.test_simulation tests.test_candidate_sweep -v`

Expected: FAIL because the new runner and sweep are absent.

- [x] **Step 3: Implement per-step audit fields** for output torque, speed, line travel, force/current caps, estimated current (only if sourced), continuous/peak duration, temperature/duty qualification, saturation reason, target and motor/assembly buoyancy, and model assumption status.
- [x] **Step 4: Implement matched four-case runs and candidate gates**. Preserve 1 m/5 m pressure as metadata unless an explicitly supported pressure-dependent model is added. Include target mass and buoyancy in task evaluation. Use supplier curves only as provisional ranges; report “not hardware-qualified” when sample measurements are absent. Do not emit an optimum when no candidate passes every hard gate.
- [x] **Step 5: Run simulation tests**

Run: `python -m unittest tests.test_simulation tests.test_candidate_sweep -v`

Expected: PASS; all four summaries and CSV logs exist, each water-type depth comparison is within `1e-9` for identical pressure-independent inputs, and no unqualified candidate is marked final.

- [x] **Step 6: Run four nominal environments and sensitivity analysis**

Run: `python run_cases.py --all`

Expected: four JSON/CSV case outputs, buoyancy and drive audits, finite states or explicit solver failure reasons, and 1 m/5 m comparisons. Then run `python sweep_candidates.py --config configs/候选搜索空间.json` and verify that every rejected candidate lists the failed gate.

## Task 5: Rebuild the three-drive CAD layout

**Files:**
- Create: `local/spiral-soft-arm/solidworks/motor_mount_v2/parameters.json`
- Create: `local/spiral-soft-arm/solidworks/motor_mount_v2/generate_motor_mount.py`
- Create: `local/spiral-soft-arm/solidworks/motor_mount_v2/test_motor_mount.py`
- Create: `local/spiral-soft-arm/solidworks/motor_mount_v2/README_湿侧三电机布局.md`
- Create: `local/spiral-soft-arm/solidworks/motor_mount_v2/B32_550mm_三路湿侧驱动装配.step`
- Create: `local/spiral-soft-arm/solidworks/motor_mount_v2/三路湿侧驱动安装件.step`
- Create: `local/spiral-soft-arm/solidworks/motor_mount_v2/print_stls/`
- Create: `local/spiral-soft-arm/solidworks/motor_mount_v2/电机底侧布局验收.json`
- Create: `local/spiral-soft-arm/solidworks/motor_mount_v2/电机底侧布局预览.png`

**Interfaces:**
- `load_config(path: Path) -> dict[str, Any]` reads a candidate ID, geometry source, three axis angles, mount layout and uncertainty mode.
- `build_motor_mount(config: dict[str, Any]) -> AssemblyGeometry` returns base plate, root retainers, three motor/reducer envelopes, line-wheel guides and measured clearances.
- `make_audit(assembly: AssemblyGeometry, config: dict[str, Any]) -> dict[str, Any]` records geometry source mode, dimensions, gaps, mass-property inputs, and whether the motor envelope is supplier-verified or a proxy.

- [x] **Step 1: Write failing geometry tests** `test_three_candidate_motors_are_noninterfering`, `test_motor_seats_clear_plate_and_arm`, `test_tendon_paths_remain_separated`, `test_step_round_trip_has_arm_and_mount_solids`, and `test_print_stls_are_closed`.
- [x] **Step 2: Run the focused CAD tests and confirm failure**

Run from `local/spiral-soft-arm/solidworks/motor_mount_v2/`: `python -m unittest test_motor_mount -v`

Expected: FAIL because v2 mount geometry does not exist.

- [x] **Step 3: Implement a parametric 3×120° wet-side layout** using the 4092 vendor drawing or a measured sample. Include integrated gearbox envelope, supported output shaft/coupling, spool, tendon guide, cable exit and fastener access. Keep `motor_geometry_mode` explicit; use `supplier_drawing` or `measured_sample`, never mark a provisional envelope as an exact vendor solid.
- [x] **Step 4: Generate STEP/STL, preview and clearance/mass audit**. If dimensions or output interface are still unavailable, export only a clearly labeled envelope study and leave print-ready mount acceptance false.
- [x] **Step 5: Run CAD checks**

Run: `python -m unittest test_motor_mount -v`

Expected: PASS for the selected geometry mode; every STL is watertight and translated to print Z=0, STEP round-trips, and all specified motor/arm/plate/tendon clearances are positive.

## Task 6: Produce v4 figures, report and paper

**Files:**
- Create: `local/spiral-soft-arm/simulation/v3/render_results.py`
- Create: `local/spiral-soft-arm/simulation/v3/tests/test_report.py`
- Create: `local/spiral-soft-arm/preprint/v4/B32水下驱动参数推导论文.md`
- Create: `local/spiral-soft-arm/preprint/v4/B32水下驱动参数推导论文.docx`
- Create: `local/spiral-soft-arm/preprint/v4/B32最终参数.json`
- Create: `local/spiral-soft-arm/preprint/v4/水下驱动评估报告.md`
- Create: `local/spiral-soft-arm/preprint/v4/figures/`

**Interfaces:**
- `render_summary(results_dir: Path, cad_audit_path: Path, output_dir: Path) -> list[Path]` renders four-case response, drive margins, buoyancy balance, sensitivity, and CAD envelope/clearance evidence.
- `build_final_parameters(results_dir: Path, config_dir: Path, cad_audit_path: Path) -> dict[str, Any]` returns geometry, per-joint stiffness/damping, chosen or unqualified drive candidate, torque/speed/travel limits, mass/displacement, and traceable source status.
- `build_paper(markdown_path: Path, output_path: Path, figures_dir: Path) -> None` generates the DOCX from the reviewable Markdown and figures.

- [x] **Step 1: Write failing report tests** `test_final_parameters_include_requested_fields`, `test_paper_candidate_matches_simulation_candidate`, and `test_unqualified_motor_is_not_called_optimal`.
- [x] **Step 2: Run the focused report tests and confirm failure**

Run from `local/spiral-soft-arm/simulation/v3/`: `python -m unittest tests.test_report -v`

Expected: FAIL because v4 reporting outputs do not exist.

- [x] **Step 3: Implement figures, Markdown report and parameter JSON**. List initial radius `a`, growth `b`, per-cell angle `Δθ`, actual discrete turns `N·Δθ/π`, generator cutoff `theta_max_pi`, pitch/profile parameter `p`, elastic-layer switch/share, tip/root hole positions and diameters, three cable routes, per-joint stiffness/damping, cut position/size, and drive travel/limits. Distinguish measured data, supplier claims, derived values, and assumptions; include target-object properties, full wet assembly mass/displacement, and all four water/depth outputs.
- [x] **Step 4: Implement the Chinese DOCX and references**. Cite the 4092, F3130 and M200 source pages; explain the listed price comparison and exclusions; report the 5 m gauge pressure; distinguish a motor depth claim from complete assembly qualification.
- [x] **Step 5: Run report tests**

Run: `python -m unittest tests.test_report -v`

Expected: PASS; DOCX, Markdown and JSON identify the same motor candidate and cases, and unqualified/failed searches cannot emit a “best feasible” label.

- [x] **Step 6: Render and visually review the DOCX** using the `documents` skill workflow; fix page breaks, tables, formulas and figures until every page is readable.

## Task 7: Whole-package verification and handoff

**Files:**
- Modify: `local/spiral-soft-arm/simulation/v3/results/`
- Modify: `local/spiral-soft-arm/solidworks/motor_mount_v2/README_湿侧三电机布局.md`
- Modify: `local/spiral-soft-arm/preprint/v4/水下驱动评估报告.md`

- [x] **Step 1: Run the full v3 simulation suite**

Run from `local/spiral-soft-arm/simulation/v3/`: `python -m unittest discover -s tests -v`

Expected: PASS; all data-contract, physics, drive, MJCF, simulation, search and report tests pass.

- [x] **Step 2: Re-run the four environments and candidate sweep**

Run: `python run_cases.py --all`  
Run: `python sweep_candidates.py --config configs/候选搜索空间.json`  
Run: `python render_results.py`

Expected: outputs are reproducible from recorded configs; CSV, summary JSON, plots, final parameter JSON and v4 paper agree on candidate ID, motor status and four conditions.

- [x] **Step 3: Re-run CAD exports and verification**

Run from `local/spiral-soft-arm/solidworks/motor_mount_v2/`: `python generate_motor_mount.py`  
Run: `python -m unittest test_motor_mount -v`

Expected: STEP/STL and preview regenerate; geometry audit has no unexplained interference and labels all supplier-envelope assumptions.

- [x] **Step 4: Check historical versions and unresolved physical gates**

Expected: v2 simulation, v3 paper and motor_mount_v1 remain unmodified. The final report explicitly marks whether a 4092 sample was available and tested; when not, the drive remains provisional and no hardware-qualified final motor claim is made. State separately that pressure-chamber structural validation and leak testing remain outside the MuJoCo evidence.

---

## Spec coverage self-review

- Motor cost/performance, candidate claims, fallback and one-sample qualification protocol: Tasks 1, 2 and 6; physical qualification remains pending until a sample and test evidence exist.
- Original spiral geometry, cable/elastic/holes/cut parameters, per-joint stiffness/damping: Tasks 1, 3 and 6.
- Wet-side CAD, reducer/spool interface, clearances and buoyancy: Tasks 3 and 5.
- MuJoCo drive constraints, drag, target buoyancy and four environments: Tasks 2–4.
- Sensitivity, no-feasible-candidate behavior, output logs and paper: Tasks 4 and 6.
- 5 m pressure limitations, pressure chamber/leak-test boundaries and historical artifacts: Tasks 6 and 7.

