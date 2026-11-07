# V27 1 米模块化 M2006 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 V27 候选，将机械臂重构为论文对应的 1 m、42 单元、四段式三缆臂体，并建立整根臂体快换、三 M2006 整板快换以及固定传动/轴封/湿侧线轮基座。

**Architecture:** V27 是与 V26 并列的新候选，不修改 V26 依赖链。实现分为参数合同、臂体模块、根部快换模块、驱动/固定基座、工程核算和总装导出六个职责明确的 Python 模块；CadQuery 负责实体，纯 Python 数学函数负责拉索、线轮、载荷和验收数据，`unittest` 先锁定合同与失败边界。

**Tech Stack:** Python 3.12/3.13、CadQuery 2.8、OCCT STEP、NumPy、Matplotlib、标准库 `unittest`/`json`/`hashlib`。

**Spec:** `docs/superpowers/specs/2026-11-08-one-meter-modular-m2006-redesign.md`

## Global Constraints

- 新建 `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/`；不得覆盖 V26、V25、V23、V20、V10、B32 或论文源文件。
- 机械臂合同为 1,000 mm 名义长度、42 单元、三缆、四个打印段、尖端/根部约 Ø5/Ø120 mm；分段只能落在单元边界。
- 四段组合成一个现场快换臂体模块；四段本身不作为现场逐段快换件。
- 根部快换采用约 Ø130 × 5 mm 止口、两枚不对称 Ø6 mm 定位销和六颗 M5 紧固件（候选 PCD Ø160 mm）；尺寸必须参数化并通过碰撞审查。
- 三台 M2006 和共同安装板整体更换；C610 保持为固定电气系统，不纳入首版电机板模块。
- 轴封座、支承轴承、传动轴和湿侧线轮固定在基座；拆电机板不得拔轴或扰动轴封唇口。
- 拉索基线为 Ø0.5 mm UHMWPE；三路线轮切线、根部入口和臂内通道方向必须共线，入口倒角不得形成急折。
- 250 mm 六边形顶盘外包络冻结；三根传动轴位置可在 V27 内优化但必须记录相对 V26 的坐标差。
- 每个打印段按实际打印方向的 Z 包络小于 300 mm，以适配 350 × 350 × 320 mm 打印空间并保留工艺余量。
- 工况为淡水/海水、最大 5 m、单次约 30 分钟；机械任务为水下抓取并保持 1 kg 级物体、低速完成完全展开到设计极限卷曲，不含高速鞭击验收。
- 所有 CAD、核算和网格结果只能标记为候选/代理/已审查，不得标记为打印、强度、水密或水下资格通过。
- Windows 命令从嵌套 Git 根目录运行；优先使用 `C:\Users\MOSS\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -X utf8`。

## Review Focus

- 42 单元分段遇到任一段超过 300 mm 时必须失败并报告候选边界，不能切穿单元或缩放单元蒙混通过；由 Task 2 的 `test_no_segment_exceeds_print_height` 固定。
- 根部法兰或驱动板错误地依靠螺钉孔/联轴器校正位置时必须失败；由 Task 3 的定位合同测试和 Task 4 的电机轴对中测试固定。
- 三路线轮出口虽在俯视图对齐但侧视不共线时必须失败；由 Task 4 的三维直线误差与夹角测试固定。
- 未知目标物排水体积不能被默认为有利浮力；由 Task 5 的零排水最不利 1 kg 载荷测试固定。
- STEP 导出成功但缺少组件、来源哈希或固定轴支撑时不得发布；由 Task 6 的重导入/组件合同测试和 Task 7 的交付清单测试固定。

---

## File Map

所有新增实现位于 `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/`：

- `parameters.json`：唯一 V27 数值合同、来源相对路径、容差和输出文件名。
- `model_contract.py`：加载/验证参数，定义 `V27Contract` 及来源哈希清单。
- `arm_module.py`：生成 42 单元臂体、四段边界、段内燕尾和连续拉索通道。
- `root_quick_change.py`：生成刚性根部适配法兰、止口、定位销、M5 孔和三路拉索端头代理。
- `drive_and_base.py`：导入 M2006，生成共同电机板、可分离联轴器、固定轴承/传动轴/轴封/湿侧线轮和 250 mm 顶盘基座。
- `engineering_audit.py`：计算三路路径差、线轮容量、M2006 拉力预算、1 kg 水下载荷和根部弯矩代理。
- `generate_v27_assembly.py`：组合 V25 电子仓选择件和 V27 三模块，执行碰撞/接口审查并导出 STEP/JSON。
- `render_v27.py`：输出整机半透明图、三模块分解图、根部快换近景和拉索/传动剖视图。
- `test_parameters.py`：参数、来源和版本边界测试。
- `test_arm_module.py`：1 m、42 单元、四段、燕尾和通道测试。
- `test_root_quick_change.py`：法兰、止口、定位销、紧固件、端头和工具空间测试。
- `test_drive_and_base.py`：三 M2006 整板、固定传动/轴封、线轮共线和拆装空间测试。
- `test_engineering_audit.py`：路径差、容量、载荷、转矩/拉力和失败边界测试。
- `test_v27_integration.py`：完整组件、碰撞、STEP 重导入、输出清单和状态措辞测试。
- `README.md`：装配边界、拆装顺序、仍未验证事项和运行命令。
- `来源与SHA256.csv`：论文、M2006、C610、V25/V26 输入和新增输出哈希。

## Task 1: Freeze the V27 Contract and Sources

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/model_contract.py`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_parameters.py`
- Modify: `docs/superpowers/specs/2026-11-08-one-meter-modular-m2006-redesign.md`

**Interfaces:**
- Consumes: paper PDF, `hardware/reference/RoboMaster_M2006_P36.STEP`, `hardware/reference/RoboMaster_C610.STEP`, V25 generator/parameters, V26 parameters.
- Produces: `load_contract(path: Path | None = None) -> V27Contract`, `validate_contract(contract: V27Contract) -> None`, `build_source_manifest(contract: V27Contract) -> dict[str, SourceRecord]`.

- [ ] **Step 1: Write the failing parameter contract tests**

Create tests named `test_candidate_identity_and_version_boundary`, `test_paper_geometry_contract`, `test_modular_interface_contract`, `test_water_and_payload_contract`, and `test_all_sources_exist`. Assert exact candidate ID `V27-1M-M2006`, 1,000 mm, 42 units, 4 segments, 3 tendons, 5/120 mm tip/root diameters, 0.5 mm UHMWPE, 250 mm plate, 300 mm segment limit, 3 M2006 motors, 5 m, 30 minutes, and 1 kg low-speed task.

- [ ] **Step 2: Run tests and verify the contract does not exist**

Run:

```powershell
& 'C:\Users\MOSS\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 local\spiral-soft-arm\solidworks\integrated_assembly_v27_1m_modular_m2006\test_parameters.py -v
```

Expected: FAIL because `parameters.json`/`model_contract.py` is absent.

- [ ] **Step 3: Add the parameter file and typed contract loader**

Define dataclasses `SourceRecord`, `ArmContract`, `RootInterfaceContract`, `DriveContract`, `EnvironmentContract`, and `V27Contract`. `validate_contract` must reject a source under the V26 output directory as a writable target, a segment limit above 300 mm, motor count other than 3, missing fixed transmission members, or release status containing `validated`, `qualified`, `print-ready`, or `waterproof`.

- [ ] **Step 4: Add source hashing with repository-relative paths**

`build_source_manifest` records SHA-256, byte size and role for the paper PDF, official M2006/C610 STEP, V25 source generator/parameters and V26 parameters. It must not copy or edit those sources.

- [ ] **Step 5: Run the parameter tests**

Run the Step 2 command.

Expected: all Task 1 tests PASS and each source hash is 64 hexadecimal characters.

- [ ] **Step 6: Commit the approved design and contract**

```powershell
git add docs/superpowers/specs/2026-11-08-one-meter-modular-m2006-redesign.md docs/superpowers/plans/2026-11-08-one-meter-modular-m2006-redesign.md
git add -f local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/model_contract.py local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_parameters.py
git commit -m "design: define V27 modular M2006 contract"
```

## Task 2: Build the 1 m Four-Segment Arm Module

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/arm_module.py`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_arm_module.py`

**Interfaces:**
- Consumes: `V27Contract` from Task 1.
- Produces: `ArmBuildResult`, `compute_unit_planes(contract: V27Contract) -> tuple[float, ...]`, `choose_four_segment_ranges(unit_planes: Sequence[float], max_height_mm: float) -> tuple[tuple[int, int], ...]`, `build_arm_module(contract: V27Contract) -> ArmBuildResult`.

- [ ] **Step 1: Write failing pure-geometry tests**

Add `test_42_units_span_nominal_one_meter`, `test_four_ranges_cover_each_unit_once`, `test_no_segment_exceeds_print_height`, and `test_segmentation_rejects_impossible_height`. Assert the ranges are contiguous, start at unit 1, end at unit 42, never split a unit, and every segment's Z span is `< 300.0` mm. The impossible-height test passes a limit below the longest individual unit and expects `ValueError`.

- [ ] **Step 2: Run Task 2 tests and verify failure**

Run the new test file with the bundled Python.

Expected: FAIL because `arm_module` is absent.

- [ ] **Step 3: Implement unit planes and deterministic four-range selection**

Use the paper logarithmic-spiral geometry/42-unit contract rather than scaling V26 solids. `choose_four_segment_ranges` returns exactly four contiguous ranges and minimizes the maximum segment height subject to unit-boundary cuts and `< 300 mm`.

- [ ] **Step 4: Write failing CadQuery arm tests**

Add `test_arm_bounds_and_diameters`, `test_three_tendon_channels_are_continuous`, `test_three_internal_dovetails_exist`, `test_each_dovetail_has_positive_lock`, and `test_arm_result_names_four_print_segments`. Use shape bounds and sampled channel centerlines; do not treat a single fused solid as proof of channel continuity.

- [ ] **Step 5: Implement `build_arm_module`**

Return named solids for four print segments, three dovetail male/female interfaces, three positive-lock features, three tendon-channel centerline records, and the assembled arm proxy. Keep the four prints separate in the assembly; do not fuse across the service boundaries.

- [ ] **Step 6: Run Task 2 tests**

Expected: all pure-geometry and CadQuery tests PASS; report 42 units, four segments and maximum segment height below 300 mm.

- [ ] **Step 7: Commit**

```powershell
git add -f local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/arm_module.py local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_arm_module.py
git commit -m "feat: add V27 one meter arm module"
```

## Task 3: Build the Root Quick-Change and Tendon Terminals

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_quick_change.py`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_quick_change.py`

**Interfaces:**
- Consumes: `V27Contract`, `ArmBuildResult`.
- Produces: `RootInterfaceResult`, `build_root_interface(contract: V27Contract, arm: ArmBuildResult) -> RootInterfaceResult`, `audit_root_interface(result: RootInterfaceResult) -> dict[str, float | bool]`.

- [ ] **Step 1: Write failing interface tests**

Add `test_register_sets_centering_not_screws`, `test_two_dowels_are_asymmetric`, `test_six_m5_holes_on_160_pcd`, `test_flange_envelope_within_180`, `test_tool_clearance_for_all_fasteners`, `test_three_tendon_terminals_are_keyed`, and `test_terminal_secondary_retention_exists`. Assert the nominal Ø130 × 5 mm register and Ø6 mm dowels come from `parameters.json`, while allowing later parameter edits without literals in geometry code.

- [ ] **Step 2: Run Task 3 tests and verify failure**

Expected: FAIL because `root_quick_change` is absent.

- [ ] **Step 3: Implement the rigid root adapter and base-side receiver**

Create separate named shapes for arm-side flange, base-side receiver, metal backing proxy, two dowel proxies and six captive fastener/tool envelopes. The TPU arm root must seat in the rigid adapter; M5 threads cannot be represented as load-bearing threads directly in TPU.

- [ ] **Step 4: Implement three keyed tendon terminals**

Create three numbered 120° terminal stations with keyhole capture proxies, a visible adjustment stroke and a secondary retention feature. Keep the cable path straight through each station and include a replaceable straight section for a future load cell without installing one.

- [ ] **Step 5: Run Task 3 tests and inspect the audit values**

Expected: all tests PASS; audit reports positive register engagement, asymmetric dowels, six accessible tools and no tendon terminal crossing.

- [ ] **Step 6: Commit**

```powershell
git add -f local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_quick_change.py local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_quick_change.py
git commit -m "feat: add V27 root quick change"
```

## Task 4: Build the Fixed Transmission Base and Whole M2006 Drive Module

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/drive_and_base.py`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_drive_and_base.py`

**Interfaces:**
- Consumes: `V27Contract`, `RootInterfaceResult`, official M2006 STEP.
- Produces: `DriveModuleResult`, `FixedBaseResult`, `optimize_drive_axes(contract: V27Contract, root: RootInterfaceResult) -> tuple[DriveAxis, DriveAxis, DriveAxis]`, `build_drive_module(...) -> DriveModuleResult`, `build_fixed_base(...) -> FixedBaseResult`, `audit_tendon_alignment(...) -> tuple[TendonAlignment, ...]`.

- [ ] **Step 1: Write failing layout and ownership tests**

Add `test_three_motors_share_one_removable_plate`, `test_c610_not_part_of_removable_plate`, `test_spools_shafts_bearings_and_seals_belong_to_fixed_base`, `test_motor_removal_does_not_remove_or_unseat_shafts`, and `test_top_plate_envelope_is_250_mm`. Component ownership is asserted by exact component names/prefixes, not viewport visibility.

- [ ] **Step 2: Write failing three-dimensional alignment tests**

Add `test_each_spool_tangent_hits_matching_root_inlet`, `test_spool_axis_is_perpendicular_to_tendon_direction`, and `test_plan_and_side_alignment_both_pass`. Set contract tolerances to maximum lateral line error `0.25 mm` and angular error `0.5°`; a fixture with correct XY but wrong Z must fail.

- [ ] **Step 3: Run Task 4 tests and verify failure**

Expected: FAIL because `drive_and_base` is absent.

- [ ] **Step 4: Implement deterministic drive-axis optimization**

`optimize_drive_axes` solves three 120° stations using the matching root inlet centerline as the authority. It minimizes tangent-to-inlet distance while preserving the root flange, fastener tool envelopes, 250 mm plate and dry-chamber wall clearance. It records each V27 axis coordinate and delta from V26.

- [ ] **Step 5: Implement fixed transmission/seal chains**

For each axis create separately named wet spool, supported transmission shaft, inner/outer bearing proxies, axial shoulder/retainer, oil-seal envelope and external labyrinth. Bearings carry radial load; a shoulder/retainer carries axial location; the seal is not modeled as a bearing.

- [ ] **Step 6: Implement the removable three-M2006 plate**

Import the official M2006 STEP three times. Create a common rigid plate with its own register/dowels and fasteners, plus three visible dry-side separable coupling envelopes with axial insertion clearance. The installed position must be set by the plate register/dowels, not by forcing motor shafts into couplings.

- [ ] **Step 7: Run Task 4 tests**

Expected: all ownership, removal, plate-envelope and 3D alignment tests PASS; report exactly three axis records and three V26 coordinate deltas.

- [ ] **Step 8: Commit**

```powershell
git add -f local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/drive_and_base.py local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_drive_and_base.py
git commit -m "feat: add V27 M2006 drive cartridge"
```

## Task 5: Calculate Tendon Travel, Spool Capacity and Load Budgets

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/engineering_audit.py`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_engineering_audit.py`

**Interfaces:**
- Consumes: `V27Contract`, arm channel centerlines, drive axes/spool geometry.
- Produces: `TendonTravelReport`, `SpoolCapacityReport`, `ForceBudgetReport`, `RootLoadReport`, `compute_tendon_travel(...)`, `compute_spool_capacity(...)`, `compute_force_budget(...)`, `compute_root_load(...)`, `write_engineering_report(...) -> Path`.

- [ ] **Step 1: Write failing formula tests with hand-checkable fixtures**

Add `test_path_difference_from_sampled_centerlines`, `test_spool_capacity_includes_twenty_percent_margin`, `test_force_equals_torque_over_effective_radius_after_losses`, and `test_root_moment_from_force_and_lever_arm`. Use small numeric fixtures with exact expected values; do not use V27 CAD as the only oracle.

- [ ] **Step 2: Write failure-boundary tests**

Add `test_unknown_displacement_uses_worst_case_one_kg_weight`, `test_capacity_below_required_travel_is_not_qualified`, `test_nonpositive_efficiency_is_rejected`, `test_seal_and_tendon_friction_are_never_omitted`, and `test_report_never_claims_hardware_validation`. The unknown-displacement case must use 9.80665 N rather than assuming buoyancy.

- [ ] **Step 3: Run Task 5 tests and verify failure**

Expected: FAIL because `engineering_audit` is absent.

- [ ] **Step 4: Implement the pure calculation functions**

Keep formulas independent of CadQuery. Inputs include motor continuous torque, spool minimum/maximum effective radii, seal drag, tendon friction efficiency, sampled path lengths, target dry mass, optional displaced volume, water density, lever arms and impact factor. Reports must carry both values and assumptions.

- [ ] **Step 5: Generate the V27 engineering audit without forcing a pass**

Calculate full-extension to both design extreme curls for all three tendons, required turns/capacity with 20% margin, low-speed force budget, worst-case 1 kg zero-buoyancy load and root fastener/dowel load inputs. If available inputs do not prove positive margin, set `qualified: false` and list the missing measurement; never tune hidden constants to pass.

- [ ] **Step 6: Run Task 5 tests**

Expected: all formula and failure-boundary tests PASS; generated JSON is finite and includes assumptions, margins and qualification state.

- [ ] **Step 7: Commit**

```powershell
git add -f local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/engineering_audit.py local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_engineering_audit.py
git commit -m "feat: add V27 tendon and load audit"
```

## Task 6: Integrate, Audit, Export and Render V27

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`

**Interfaces:**
- Consumes: all Task 1-5 result types; selected electronic-canister components returned by V25 `build_v25_components()` without importing its M3508 assembly as the V27 drive.
- Produces: `V27AssemblyResult`, `build_v27_assembly(contract: V27Contract) -> V27AssemblyResult`, `audit_v27_assembly(result: V27AssemblyResult) -> dict[str, object]`, `export_v27(result: V27AssemblyResult) -> dict[str, Path]`, `render_v27(result: V27AssemblyResult) -> dict[str, Path]`.

- [ ] **Step 1: Write failing component and source-boundary tests**

Add `test_required_three_module_components_exist`, `test_v25_electronics_are_selected_without_m3508_drive`, `test_no_component_name_uses_m3508`, `test_v26_outputs_are_not_modified`, and `test_fixed_and_removable_ownership_survives_integration`.

- [ ] **Step 2: Write failing collision and service tests**

Add `test_no_forbidden_solid_intersections`, `test_arm_can_translate_out_after_fasteners_and_terminals_removed`, `test_drive_plate_can_translate_out_after_couplings_released`, `test_all_service_fasteners_have_tool_envelopes`, and `test_fixed_shafts_remain_supported_in_drive_removed_state`.

- [ ] **Step 3: Write failing export/readback tests**

Add `test_export_creates_four_named_step_outputs`, `test_full_step_readback_has_valid_solids_and_bounds`, `test_audit_contains_alignment_load_and_source_sections`, and `test_status_is_candidate_not_release`. Required STEP outputs are arm module, M2006 drive module, fixed base and full assembly.

- [ ] **Step 4: Run Task 6 tests and verify failure**

Expected: FAIL because integration/export modules are absent.

- [ ] **Step 5: Implement assembly composition and audits**

Build the arm, root interface, drive module and fixed base; import only the V25 electronic-canister/power-interface components required by the contract. Audit forbidden intersections separately from intentional fits, and list every intentional contact pair explicitly.

- [ ] **Step 6: Implement STEP exports and readback**

Export:

- `SpiRobs_v27_1m_四段臂体模块.step`
- `SpiRobs_v27_M2006三电机驱动模块.step`
- `SpiRobs_v27_固定传动密封基座.step`
- `SpiRobs_v27_1m模块化总装.step`

Re-import each output, record file size, solid count and bounds, and fail if any required module is absent or the full assembly is not approximately 1,000 mm plus its root/base stack in Z.

- [ ] **Step 7: Implement four review renders**

Render a half-transparent full assembly, exploded three-module view, root quick-change close-up and section showing the M2006 coupling/fixed bearing/shaft/seal/wet spool chain. Keep removable modules opaque in exploded view and fixed base semi-transparent.

- [ ] **Step 8: Run Task 6 tests and visually inspect PNGs**

Expected: tests PASS; images show no clipped geometry, swapped motor direction, hidden tangent error or misleading sealed/open volume.

- [ ] **Step 9: Commit**

```powershell
git add -f local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/*.step local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/*.png local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/*.json
git commit -m "feat: integrate V27 modular M2006 assembly"
```

## Task 7: Document, Hash and Run the Final Gate

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/来源与SHA256.csv`
- Modify: `README.md`

**Interfaces:**
- Consumes: all V27 source/output/audit files.
- Produces: reproducible commands, source/output hashes, disassembly sequence and an explicit list of unverified physical gates.

- [ ] **Step 1: Add a failing delivery-contract test**

Extend `test_v27_integration.py` with `test_delivery_manifest_is_complete_and_hashes_match`, `test_readme_lists_arm_and_drive_swap_sequences`, `test_readme_lists_unverified_physical_gates`, and `test_root_readme_links_v27_without_replacing_v26`.

- [ ] **Step 2: Run the delivery tests and verify failure**

Expected: FAIL because README/hash files and root link are absent.

- [ ] **Step 3: Write the V27 README and root project link**

Document the two independent replacement procedures, required post-swap zero/preload calibration, fixed seal boundary, C610 ownership, input sources, generation commands, output files, audit interpretation and the exact statement that CAD does not prove printing, strength, 5 m water-tightness, 30-minute thermal behavior or 1 kg task success.

- [ ] **Step 4: Generate and verify the hash CSV**

Hash every source named in Task 1 plus V27 Python/JSON/STEP/PNG/README outputs. Sort paths deterministically, use repository-relative UTF-8 paths, and re-read the CSV to verify all current hashes.

- [ ] **Step 5: Run the complete V27 test suite**

Run:

```powershell
& 'C:\Users\MOSS\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m unittest discover -s local\spiral-soft-arm\solidworks\integrated_assembly_v27_1m_modular_m2006 -p 'test_*.py' -v
```

Expected: all tests PASS with no skipped geometry, export or hash tests.

- [ ] **Step 6: Run repository and artifact checks**

```powershell
git diff --check
git status --short --branch
```

Expected: no whitespace errors; only intended V27/spec/plan/root README files are modified or staged. The six pre-existing unrelated untracked plan/spec files remain untouched unless separately requested.

- [ ] **Step 7: Perform final visual and evidence review**

Open all four latest PNGs and confirm module color/opacity, motor orientation, line/spool alignment, root service access and fixed/removable boundaries. Compare the final JSON statements to the spec and ensure no physical test is reported as completed.

- [ ] **Step 8: Commit**

```powershell
git add README.md
git add -f local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/来源与SHA256.csv local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py
git commit -m "docs: publish V27 modular assembly evidence"
```

## Final Completion Criteria

- V27 exists as an isolated candidate and V26 source/output hashes remain unchanged.
- The arm geometry reports 1,000 mm nominal length, 42 units, four unit-boundary segments and `< 300 mm` maximum segment print height.
- The root interface has positive centering, asymmetric angle location, six accessible fasteners and three keyed tendon terminals.
- The removable drive module contains exactly three official-shape M2006 motors on one plate; fixed shafts, bearings, seals and wet spools remain supported when it is removed.
- All three tendon paths pass both XY and Z/angle alignment tolerances.
- Spool capacity includes at least 20% travel margin or is explicitly marked unqualified.
- The engineering report uses a conservative 1 kg/9.80665 N case when target displacement is unknown and never claims physical qualification.
- Four STEP files re-import with valid solids/bounds; four review PNGs pass visual inspection.
- Full test discovery, hash verification and `git diff --check` pass before completion is claimed.

