# V27 阶梯护甲外观恢复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 V27 简化六边形外罩改回具有明显肩部、四道六边形外凸环带和倒角窗框的阶梯护甲，同时保留当前维护接口和机械结构。

**Architecture:** 以提交 `59bf1e5` 的 V27 外罩实现为造型参考，恢复四道 8 mm 高、4 mm 外凸的型面跟随环带和窗口边框；保留当前 12 块上下分板、M3 Ø3.4 mm/±35 mm 紧固孔、两个底部工具让位窝、电子仓/传动布局和根部护圈。原定独立闭合环带经整装维护审查后改为六面平面肋条并融合进对应面板。总装审计验证各下板径向拆出和驱动模块 280 mm 抽出，重新计算实际 STEP 外廓并重新导出预览、审计和哈希清单。

**Tech Stack:** Python 3.12、CadQuery 2.8、unittest、STEP、Matplotlib/Pillow、JSON、SHA-256。

**Spec:** `docs/superpowers/specs/2026-11-13-v27-return-to-stepped-cover-design.md`

> Review correction: the originally planned closed support rings trapped the service panels, and frame 02 lost independent support after lower-panel removal. The review ruling below supersedes the original separate-frame and bottom-frame removal notes: fuse six flat ribs into each matching panel, then remove the six lower rib-panels individually/radially.

## Global Constraints

- 只在 `E:\Spiral_Robots\.worktrees\spiral-soft-arm-v27` 的 `feat/v27-modular-m2006` 分支工作。
- 保留外罩轮廓站点 `[-236,98]`, `[-110,162]`, `[-80,162]`, `[64,162]` mm；服务分界 `Z=-80 mm`；12 块平面面板。
- 恢复四道视觉环带中心 `Z=[-232,-84,-76,60] mm`，每道高度 `8 mm`、径向厚度 `4 mm`；每道由六个平面侧肋组成并融合进对应的上/下板，不产生闭合独立框件；名义最大外廓约 Ø332 mm。
- 保留当前面板 M3 Ø3.4 mm/±35 mm、48 孔；四道外环的每个紧固点使用 Ø3.4 mm 贯通孔与外侧 Ø8 mm × 2 mm 头部/工具浅窝，工具检验采用 Ø8 mm 浅窝加 Ø2.5 mm 驱动杆的阶梯包络。lower panel 05 上两个 Ø8.6 mm × 2.5 mm 底部工具让位窝另行保留；不得回退至旧 Ø3.2 mm/±50 mm 孔位。
- 外罩可见紧固接口统一使用 M3；逐项核对 48 个孔的贯通、框体支承、同轴关系及外侧工具可达性。M3 螺母/嵌件接收方式仍标为未定，不假定完整实物紧固方案已验证。
- 保留窗框宽 8 mm、外凸 2.5 mm、切角 5 mm、每侧让口 1.5 mm；窗孔净尺寸和外水连通性不变。
- 驱动板负 Z 抽出前拆除六块下部一体肋面板；服务顺序包括 24 颗 M3、线束和三只横销，抽出行程 280 mm。上部面板及其肋条保持安装。
- 350 × 350 × 320 mm 是打印机标称空间。CAD 包围盒通过不代表 Brim、摆放、翘曲、打印强度或水下验证通过。
- 使用 `$py = 'C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe'`。

## Review Focus

- 四道肋条与对应上下板、窗口边框、M12 接口及硬件包络的融合/相交：增加单体有效性、实体支承和几何回归断言并在 Task 2 中验证。
- 统一 M3 接口是否实际可装拆：检查每个螺钉位的 Ø8 × 2 mm 浅窝、Ø3.4 mm 贯通轴线与 Ø2.5 mm 驱动杆路径，并在 README/审查记录中保留未定螺母或嵌件方案。
- 下部斜环带及 M12 服务窗/两处 M3 工具让位的局部冲突：测试退让范围和 Ø8 mm 工具包络；Task 2。
- 上下拼缝附近 `Z=-84/-76 mm` 两道独立环带和相邻面板支承关系：测试各面螺孔同轴、面板支承和无非预期交叠；Task 2。
- Ø332 mm 外廓与 350 mm 平台的边距：从导出 STEP 读取实际边界，在 Task 3 中与名义参数分开记录。
- 驱动模块拆卸时各保留环带是否阻挡 280 mm 负 Z 路径：更新障碍清单并运行连续扫掠测试；Task 3。

---

### Task 1: 先锁定阶梯环带与外观契约

**Files:**
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_cover.py`
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`

**Interfaces:**
- `RootCoverResult.band_centers_mm` 必须列出四个特征中心 `[-232,-84,-76,60]`；组件表不得包含 `fixed_cover_frame_01…04` 闭合环件。
- 参数仍使用 `root_cover.frame_z_centers_mm`，有序为 `[-232,-84,-76,60]`。
- 面板紧固接口必须维持 M3、通孔 Ø3.4 mm、切向偏移 `[-35,35]` mm、48 孔；工具外廓 Ø8 mm，两个边框让位直径 Ø8.6 mm、深 2.5 mm。

- [x] **Step 1: Add failing ring geometry tests**

  断言四道视觉环带的 Z 区间分别为 `[-236,-228]`、`[-88,-80]`、`[-80,-72]`、`[56,64]` mm，并在各六面服务板上验证对应肋条存在；面板保持有效单体，中央两道之间有浅槽。

- [x] **Step 2: Run the new tests against current three-frame geometry**

  Run: `& $py -X utf8 -m unittest test_root_cover.V27RootCoverTests.test_cover_restores_four_stepped_armor_bands -v`

  Expected: FAIL because current cover returns three bands and merges the two central rows.

- [x] **Step 3: Add failing layout and access assertions**

  断言名义外罩型面直径为 324 mm、名义外凸环带直径约 332 mm；实际面板/完整外罩 STEP 包围盒分别作为不同字段记录；所有 48 个 M3 轴线在环带与面板上同轴贯通，并有 Ø8 × 2 mm 浅窝和 Ø2.5 mm 驱动杆通道。

- [x] **Step 4: Run integration assertions against current audit**

  Run: `& $py -X utf8 -m unittest test_v27_integration.V27CoverIntegrationTests -v`

  Expected: FAIL on the three-frame and 324 mm-only contract.

---

### Task 2: 恢复四道型面跟随环带和窗口框

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_cover.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_cover.py`

**Interfaces:**
- `build_root_cover(contract) -> RootCoverResult` 保持既有签名。
- `_face_band_segment(...)` 按每面型面半径构造环带肋条，与相应服务面板融合为一个有效实体；在融合后打通 M3 孔并切 Ø8 × 2 mm 外侧沉孔。
- 窗口围框仍由 `add_window_surround(...)` 生成，尺寸沿用配置中的 8/2.5/5/1.5 mm。

- [x] **Step 1: Keep four distinct frame specs in regression tests**

  用四个规定中心建立 band feature spec；逐道检查面板中的实际外凸量和单体数量。

- [x] **Step 2: Run focused geometry tests to see required failures**

  Run: `& $py -X utf8 -m unittest test_root_cover -v`

  Expected: failures only for current three-frame merge and Ø332 stepped-envelope assertions.

- [x] **Step 3: Restore four band rows in `root_cover.py`**

  复用型面半径函数和 `_face_band_segment`，分别生成底部斜带、中央下带、中央上带和顶部带的六个平面面肋；外缘为面板外表面径向外扩 4 mm，保持每带 8 mm 高。底带与 M12 窗口相交处保持连接器净空，并保留 M3 工具路径。

- [x] **Step 4: Preserve current holes and window reliefs**

  对所有四排 M3 孔在肋条融合后沿真实面外法线贯穿，并在肋条外侧加工 Ø8 × 2 mm 浅窝；不打穿 8 mm 高肋条，以保留孔底支承。保留两处下部 Ø8.6 mm × 2.5 mm 浅让位，避免恢复旧孔径/孔距。检修窗开口保持原尺寸且外水连通。

- [x] **Step 5: Run focused cover tests**

  Run: `& $py -X utf8 -m unittest test_root_cover -v`

  Expected: PASS; 四道环带视觉特征由各面板的一体肋条形成，12 块面板为有效单体且包围盒在 350 × 350 × 320 mm 名义空间内；所有可见外罩紧固点使用统一 M3 接口。

---

### Task 3: 更新总装碰撞、维护路径和外廓审计

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`

**Interfaces:**
- `cover_layout` 记录四道视觉环带半径/范围和支持中心，不生成独立 frame component bounds。
- `service.drive_removal_sweep` 继续移除 `fixed_cover_frame_01`，并把 frame 02–04 保留为真实固定障碍。
- `panel_fastener_interface` 继续报告 M3、Ø3.4 mm、±35 mm、48 孔、Ø8 mm 工具包络和两个浅让位。

- [x] **Step 1: Add failing audit and service tests**

  断言审计报告四道视觉环带和一体面板结构，不输出独立闭合框实体；明确上部六板连同其肋条是 drive sweep 保留障碍；完整 STEP 的实际包围盒和最大径向尺寸同时写入审计；外罩可见紧固接口均报告为 M3、Ø8 × 2 mm 浅窝，并保留接收件与头型未定状态。

- [x] **Step 2: Run integration tests to capture stale three-band assumptions**

  Run: `& $py -X utf8 -m unittest test_v27_integration.V27CoverIntegrationTests -v`

  Expected: FAIL on frame count/third frame range and missing Ø332 ring envelope fields.

- [x] **Step 3: Update hardcoded frame mappings and sweep names**

  删除面板与独立框的接触对，将四道环带保留为造型/审计特征数据；驱动模块 sweep 仅排除六块下部肋面板，上部六块面板及肋条留作障碍物。

- [x] **Step 4: Record nominal and measured cover dimensions separately**

  审计同时写 `nominal_profile_circumdiameter_mm=324`、`nominal_outer_armor_diameter_mm=332`、面板实际径向直径、完整外罩 STEP 的实际最大径向直径及 X/Y/Z BBox；不把名义外接圆标成实测实体尺寸。

- [x] **Step 5: Run cover integration and extraction checks**

  Run: `& $py -X utf8 -m unittest test_v27_integration.V27CoverIntegrationTests -v`

  Expected: PASS; 全装配禁止碰撞为空、上部肋面板不挡 280 mm 抽出、六块下部肋面板逐一径向取出通过、根部快拆保持通过；12 块面板尺寸满足标称打印空间。中央两道肋条的接缝浅槽需保持可见且不改变 8 mm 高度、孔位与最大外廓。

---

### Task 4: 生成可比预览、更新审查资料并提交

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/preprint_review/V27打印前审查.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/V27装配审查.json` and `来源与SHA256.csv` (generated)
- Modify: `docs/superpowers/specs/2026-11-13-v27-simplified-faceted-cover-design.md` (mark superseded)

- [x] **Step 1: Preserve the current simplified cover preview as comparison baseline**

  Copy the committed current `V27_六边形包覆附件.png` to `V27_简化版包覆基线.png` before regenerating the same-named active preview.

- [x] **Step 2: Render the restored cover and side-by-side comparison**

  Keep the opaque and translucent inspection views; add `V27_包覆件改版前后对比.png` with legible Before/After labels and the same camera scale. Add a 2.0 mm high × 1.2 mm radial recess at Z=-80 mm between the touching middle bands so all four rings read clearly without changing their 8 mm height or Ø332 mm envelope.

- [x] **Step 3: Update README, preprint review, and supersession status**

  Replace current three-frame/Ø324-only claims with 12 panels, four rings, nominal Ø332 and measured STEP dimensions; state 9 mm/side nominal XY margin, unresolved M3 receivers, and that slice/print/physical checks remain pending. Mark the 2026-11-13 simplified-cover spec superseded by this approved design.

- [x] **Step 4: Regenerate V27 assets and run complete verification**

  ```powershell
  & $py -X utf8 .\generate_v27_assembly.py
  & $py -X utf8 -m unittest discover -s . -p 'test_*.py' -v
  git diff --check
  ```

  Expected: all tests pass; root cover and full assembly STEP read back as valid; all four printable segments and every cover part fit nominal bounds; collisions and service sweeps pass; manifest hashes match all deliverables.

- [x] **Step 5: Commit the verified redesign locally**

  Stage only the V27 model/output/docs and this plan/spec; leave pre-existing untracked temporary preview and 2026-11-12 experiment docs untouched. Commit as `feat(v27): restore stepped root armor`; do not push.

---

## Plan Self-Review

- Spec coverage: stepped shoulder/bands/window surrounds are in Task 2; current holes and service reliefs are preserved in Task 2; audit, removal paths and actual bounds are in Task 3; comparative preview, documentation and manifest are in Task 4.
- Review focus tests are assigned to Tasks 1–3.
- No motor, shaft, cable, seal, electronics or pressure-boundary changes are included.
- Physical validation remains explicitly outside CAD test claims.
