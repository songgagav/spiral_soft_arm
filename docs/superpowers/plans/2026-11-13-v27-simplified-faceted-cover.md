# V27 精简六棱包覆件实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留六棱简洁外观和实际维护性的前提下重做 V27 根部外罩，统一 M3 接口，并通过总装碰撞和模块抽出验证。

**Architecture:** 每个六边形面由上部面板和下部服务面板组成，共 12 个可单独打印件；分界为 Z=-80 mm。实测 280 mm 电机模块扫掠与全高板下段相撞，故下部六板在维修电机模块时先拆，上部六板保留。六个面均采用 M3 Ø3.4 mm 通孔、切向孔距 ±35 mm。中央两道 8 mm 框带合并为一条 Z=-88…-72 mm 的 16 mm 内侧框，保留 Z=-84/-76 mm 两排孔。M12 外凸边框与 lower panel 05 底部两孔重叠，在凸边内为 Ø8 mm 工具各做 Ø8.6 mm、深 2.5 mm 让位。名义轮廓外接圆 Ø324 mm；导出面板实际最大径向直径 Ø322.019 mm、装配包围盒 322 × 283.092 × 300 mm。外罩仍对外水开放，不作为承压壳。

**Tech Stack:** Python 3.12.2、CadQuery 2.8.0、`unittest`、STEP、Matplotlib/Pillow、JSON、SHA-256。

**Spec:** `docs/superpowers/specs/2026-11-13-v27-simplified-faceted-cover-design.md`

## Global Constraints

- 只在 `E:\Spiral_Robots\.worktrees\spiral-soft-arm-v27` 的 `feat/v27-modular-m2006` 分支工作。
- 保留 V27 一米/42 单元机械臂、250 mm 顶盘、三台 M2006 驱动、轴系、线轮、拉索直线路由和电子仓布局。
- 面板为 `fixed_cover_lower_panel_01…06` 与 `fixed_cover_upper_panel_01…06`；下板 Z=-236…-80 mm，上板 Z=-80…64 mm。三道支撑框分别位于底部、中央拼缝和顶部。
- 外罩紧固统一为 M3 Ø3.4 mm 通孔，切向孔距 ±35 mm；全部 48 个孔检查支承及从面外沿面法线接近的 Ø8 mm 工具包络，检查包含目标面板、支撑框等全部几何。根部/驱动结构 M5、内部支承套筒 M2.5 保持原用途。M3 螺母、嵌件或其他接收结构尚未选定，不宣称完整紧固接口已验证。
- 电机整板负 Z 抽出 280 mm 的实际服务顺序需列出 24 颗下板 M3 螺钉、六块下板和底框 01；上部六板留在位。臂体正 Z 快拆 69.5 mm 保持原路径。
- 打印机标称 350 × 350 × 320 mm。名义包围盒通过不等于切片、brim、翘曲、强度或水下放行。
- 从 V27 模型目录运行 PowerShell 命令，并设定 `$py = 'C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe'`。

## Review Focus

- 12 块面板上的电机窗、观察窗和 M12/线缆口贯通正确区域。
- 面板与三个支撑框的 M3 孔同轴、有材料支承；所有 48 个从面外沿真实面法线接近的 Ø8 mm 工具包络可达，并包含目标面板和全部支撑框。确认 M12 边框下方两处浅让位不切穿 2.4 mm 主面板。
- 全高面板产生的模块干涉通过下部服务板拆除解决，不得把碰撞从障碍列表排除。
- 280 mm 电机板与 69.5 mm 臂体拆卸顺序逐件列出，并由连续扫掠验证。
- 所有打印件在名义平台范围内；brim/平台边缘、长薄板翘曲仍待切片确认。

---

### Task 1: 上下服务面板、内侧支撑框和统一 M3 接口

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_cover.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py` (component-name migration and service-cover labels)
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py` (component-name migration)
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_cover.py`

**Interfaces:**
- `RootCoverResult.panel_names` returns all 12 pieces and exposes `lower_panel_names`/`upper_panel_names` separately.
- `RootCoverResult.frame_names` returns 3 valid recessed support rings; central ring spans 16 mm and supports both seam hole rows.
- External cover fasteners use Ø3.4 mm M3 clearance holes at ±35 mm tangent offsets.
- The two lower fasteners on service panel 05 have Ø8.6 mm shallow external tool-relief pockets, 2.5 mm deep, in the M12 bezel; panel wall is preserved.
- Cover audit distinguishes the nominal Ø324 mm profile circumdiameter from the measured export: actual panel radial diameter Ø322.019 mm and panel assembly bounds 322 × 283.092 × 300 mm.

- [x] **Step 1: Add split-panel and M3 tests**

  Add tests for six upper and six lower panels, correct Z limits/openings, 3 support frames, M3 support/holes, 48 exterior tool paths, frame flushness, and printer bounds.

- [x] **Step 2: Run the tests against the previous geometry**

  `task1-red.log` recorded the six-full-height geometry failing the pre-change assertions. The all-hole access regression also found the former ±50 mm screw spacing blocked by an adjacent panel; `task2-m3-red.log` records 114.8141 mm³ overlap.

- [x] **Step 3: Build the lower service seam and merged support ring**

  Set the service seam at Z=-80 mm; create upper/lower pieces, assign service windows, keep each piece within its specified Z segment, put fastener rows at -232/-84 for lower and -76/60 for upper, and merge the central support band to Z=-88…-72 mm while retaining both screw rows. Update M3 tangent offsets to ±35 mm.

- [x] **Step 4: Verify cover geometry**

  `test_root_cover.py -v` passes 12/12. Hole/driver checks pass for all faces and support rows; support rings are recessed by the panel thickness and the parts fit the nominal printer bounds.

---

### Task 2: Assembly interference, audit record and module maintenance paths

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/drive_and_base.py`
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_drive_and_base.py`

**Interfaces:**
- `cover_layout` records 12 panel bounds, 3 frame bounds, 324 mm nominal outer diameter, split Z, M3 hole count/spacing, and frame support positions.
- `service.drive_module_removal_sequence` lists de-energizing, removing 24 M3 lower-panel screws, removing lower panels 01–06, removing frame 01, disconnecting harnesses, removing three cross-pins, and translating the drive plate 280 mm along -Z.
- `service.drive_removal_sweep` reports lower panels 01–06 and frame 01 as removed; upper panels 01–06 remain obstacles and the sweep passes without collisions.
- Arm quick-change retains root-guard removal and 69.5 mm positive-Z sweep.

- [x] **Step 1: Add assembly and service regression tests**

  Cover tests assert 12 panel names, three frames, M3 audit fields, and the exact minimum service removal set. A unit test verifies the sweep reports every overlapping obstacle.

- [x] **Step 2: Record RED evidence**

  The old sweep failed on the lower cover; a regression test exposed that the sweep audit stopped reporting collisions after the first overlap. `task2-sweep-report-red.log` is RED; `task2-sweep-report-green.log` is GREEN after correcting collision enumeration.

- [x] **Step 3: Update assembly names, sweep and maintenance record**

  The exact split candidate was tested: every motor/plate sweep collision is below Z=-80 mm. With the six lower service panels and frame 01 removed, the 280 mm path passes and all six upper panels remain installed. The audit now lists each removed part and per-piece bounding boxes.

- [x] **Step 4: Run integration tests and STEP read-back validation**

  ```powershell
  & $py -X utf8 -m unittest test_v27_integration.V27CoverIntegrationTests.test_flat_cover_is_present_and_clear_in_full_assembly -v
  & $py -X utf8 -m unittest test_v27_integration.V27IntegrationTests.test_drive_plate_can_translate_out_after_cross_pins_removed -v
  ```

  Expected: collision audit has no forbidden intersections; 280 mm drive sweep and 69.5 mm arm sweep pass; V27 STEP parts read back valid.

---

### Task 3: Final renders, README, print review, generated files and commit

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/preprint_review/V27打印前审查.md`
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/V27装配审查.json` and current V27 STEP/PNG/`来源与SHA256.csv` outputs (generated)

- [x] **Step 1: Add render and README output-contract tests**

  Verify the opaque exterior image, translucent assembly review, lower-panel service removal image, drive/arm service sequences, and M3 specification are represented in outputs and docs.

- [x] **Step 2: Render the approved faceted appearance and service access**

  Keep opaque exterior and transparent inspection renders separate. Show the lower service-panel extraction and 24 M3 fasteners; preserve actual validated drive and arm sweep directions.

- [x] **Step 3: Update README and preprint review**

Record 6 upper + 6 lower panels, 3 recessed frames, nominal profile Ø324 mm, measured radial diameter Ø322.019 mm, panel assembly bounds 322 × 283.092 × 300 mm, M3 Ø3.4 mm/±35 mm, two tool-relief pockets and the exact motor service sequence. State that M3 receiver hardware is unresolved and slicer edge/brim, print warping, physical fit, strength and underwater tests are still pending.

- [x] **Step 4: Regenerate V27 outputs and run complete verification**

  ```powershell
  & $py -X utf8 .\generate_v27_assembly.py
  & $py -X utf8 -m unittest discover -s . -p 'test_*.py' -v
  git diff --check
  ```

  Expected: STEP re-read passes; assembly audit remains an unprinted/unqualified candidate; complete tests pass; SHA-256 manifest matches generated files.

  Final-review corrections add two shallow bezel reliefs, audit nominal versus measured panel geometry separately, and document the unresolved M3 receiver choice. The full suite ran 114 tests: 113 passed; one failed only because the SHA-256 manifest was stale after the last test-file edit. The manifest was regenerated and all 7 delivery/manifest checks then passed. The 12 cover geometry tests, full-assembly cover preflight, all other full-suite tests, STEP read-back, renders, and `git diff --check` passed. This combines the full-run results with the targeted manifest rerun; the full suite was not rerun after the manifest refresh.

- [x] **Step 5: Commit the verified cover update**

  ```powershell
  git add local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006 docs/superpowers/specs/2026-11-13-v27-simplified-faceted-cover-design.md docs/superpowers/plans/2026-11-13-v27-simplified-faceted-cover.md
  git diff --cached --check
  git commit -m "feat(v27): simplify faceted root cover"
  ```

  Result: create the approved local commit `feat(v27): simplify faceted root cover` on `feat/v27-modular-m2006`; do not push. Stage only V27 assets plus this plan/spec, leaving unrelated temporary previews and the prior guard experiment untouched.
