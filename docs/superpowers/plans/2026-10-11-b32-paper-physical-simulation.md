# B32 论文式软臂物理仿真与打印前复核 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以论文式 B32 打印实体为基准，生成无 Blender 的三腱弹性关节仿真、由仿真状态导出的效果图和经复核的打印前 V2 交付包。

**Architecture:** 用 Python 生成 MuJoCo MJCF：32 个刚体计算单元由 31 个有刚度/阻尼的三维关节连接，三条空间腱索按 120° 布置并由独立力执行器驱动。仿真状态独立导出 JSON/PNG；打印 STEP/STL 仍是未受力的一体 TPU 实体，避免把变形预览误当成可打印几何。

**Tech Stack:** Python 3.13、MuJoCo、NumPy、Matplotlib、项目现有 B32 STEP/STL、PowerShell ZIP 工具；Blender 不参与本次生成。

**Spec:** `docs/superpowers/specs/2026-10-11-b32-paper-physical-simulation-design.md`

## Global Constraints

- 几何基线为 550 mm、B32、32 单元、三腱、`p=0.5`、`Δθ=30°`。
- 打印软臂为 TPU 95A 一体式弹性主体，不能将刚性塑料的弯曲姿态当作真实结构结果。
- MuJoCo 长度用 m、质量用 kg、重力用 m/s²；CAD 和 STL 长度用 mm。
- 每个仿真结果记录未实测的刚度/阻尼/拉力假设，不得声称材料或抓取性能已经认证。
- 不调用 Blender；当前 STEP 作为 SolidWorks 可导入的打印实体基线。
- 旧 rigid-links 的静态中心线摆位文件保留追溯，但不得进入 V2 打印包。

## Review Focus

- mm 到 m 或重力方向错误导致臂长/质量/姿态错误：单元、总长、重力与缆长测试。
- 执行器正负号导致收线变成放线：每根腱索的长度变化方向测试。
- 单元链、导向点错序导致无效或断开的腱路：MuJoCo 加载及腱路数/长度测试。
- 自碰撞代理过粗或漏检导致穿模：仿真接触统计和中心线/碰撞代理最小间隙检查。
- 未标定材料参数造成虚假的性能结论：刚度敏感性分析和报告假设字段检查。

---

### Task 1: 仿真接口与失败用例

**Files:**
- Create: `local/spiral-soft-arm/simulation/v1/tests/test_model.py`
- Create: `local/spiral-soft-arm/simulation/v1/tests/test_simulation.py`

**Interfaces:**
- Tests consume `generate_mjcf.build_mjcf(params) -> str` and `simulate.run_case(model_path, case) -> dict`.
- Model must expose 32 bodies, 31 ball joints, 3 spatial tendons and 3 motor actuators.

- [ ] 写测试：生成 MJCF 的长度单位、重力、单元/关节/腱索/执行器数量正确。
- [ ] 运行测试并确认因仿真模块尚不存在而按预期失败。
- [ ] 写测试：MuJoCo 结果稳定，拉索收线后路径长度减小，最大偏移非零且状态数值有限。
- [ ] 运行测试并确认失败来自缺少实现，而不是测试环境异常。

### Task 2: 生成论文参数化 MuJoCo 模型

**Files:**
- Create: `local/spiral-soft-arm/simulation/v1/B32参数.json`
- Create: `local/spiral-soft-arm/simulation/v1/generate_mjcf.py`
- Create: `local/spiral-soft-arm/simulation/v1/B32_three_tendon.xml`
- Modify: `local/spiral-soft-arm/simulation/v1/tests/test_model.py`

**Interfaces:**
- `build_mjcf(params: dict) -> str` validates units, link count, cable angles, joint properties and control range.
- Joint stiffness/damping are explicit JSON inputs and vary by station; they are not inferred as experimentally measured TPU properties.

- [ ] 实现 32 个变尺寸刚体代理、31 个受限柔顺球关节、基座固定、三条空间腱索和三路有界执行器。
- [ ] 在 SI 制中显式写入 0.550 m 长度、TPU 假设密度、重力、软臂与底座接触设置。
- [ ] 运行单元测试并用 MuJoCo 编译 XML，核对模型对象数量。

### Task 3: 运行受力仿真并报告接触/稳定性

**Files:**
- Create: `local/spiral-soft-arm/simulation/v1/simulate.py`
- Create: `local/spiral-soft-arm/simulation/v1/run_cases.json`
- Create: `local/spiral-soft-arm/simulation/v1/simulation_results.json`
- Modify: `local/spiral-soft-arm/simulation/v1/tests/test_simulation.py`

**Interfaces:**
- `run_case(model_path: Path, case: dict) -> dict` returns control history, tendon lengths, tip trajectory, maximum displacement, contact counts, finite-state status and assumptions.
- Cases cover neutral, each of the three individual tendon pulls, and a balanced multi-tendon pull.

- [ ] 实现低力、慢速执行器阶跃并在重力下积分；记录每个阶段的状态与腱长。
- [ ] 以三组刚度倍数运行敏感性分析；除非有 TPU 试验数据，不作强度或负载合格判定。
- [ ] 检查仿真发散、异常穿透、执行器饱和和腱路长度单调性；测试需失败时指出具体工况。

### Task 4: 从仿真状态生成 SolidWorks 辅助预览

**Files:**
- Create: `local/spiral-soft-arm/simulation/v1/render_simulation.py`
- Create: `local/spiral-soft-arm/simulation/v1/B32_仿真姿态对比.png`
- Create: `local/spiral-soft-arm/simulation/v1/B32_simulated_pose_preview.stl`

**Interfaces:**
- `render_results(results: dict, stl_path: Path, output_path: Path) -> None` renders neutral and simulated poses from computed states; the deformed STL is explicitly visualization-only.

- [ ] 基于 MuJoCo 的单元坐标弯折论文式网格，输出中性与受力姿态对照图。
- [ ] 进行视图尺度、包围盒、网格闭合和变形姿态来源检查；禁止静态摆放理论中心线冒充仿真。

### Task 5: 复核几何和更新打印前 V2 包

**Files:**
- Create: `local/spiral-soft-arm/preprint/v2/预打印复核报告.md`
- Create: `local/spiral-soft-arm/preprint/v2/README_打样包说明.md`
- Create: `local/spiral-soft-arm/preprint/v2/printable_parts.json`
- Create: `local/spiral-soft-arm/preprint/B32_论文式仿真与打印前交付包_v2.zip`
- Modify: `local/spiral-soft-arm/solidworks/paper_v1/论文构形使用说明.md`

**Interfaces:**
- V2 report consumes the STEP/STL geometry report, MuJoCo simulation report and renderer output.
- ZIP contains only current printable STL/STEP, simulation files, preview, Chinese print/assembly notes and manifest; historical invalid rigid-link previews are excluded.

- [ ] 重新读取 STEP/STL 包围盒、闭合性和三腱孔，准确记录切削前目标与最终尺寸。
- [ ] 更新材料、装配、试验和未验证性能边界；将可打印件与仿真辅助网格分开。
- [ ] 构建 V2 ZIP 并逐项列出内容，检查压缩包能重新读取。

### Whole-task verification

- [ ] `python -m unittest discover -s local/spiral-soft-arm/simulation/v1/tests -v`
- [ ] 运行仿真 CLI 生成最新 JSON/PNG/STL；所有状态有限、XML 加载成功、三个驱动方向均有响应。
- [ ] 重新读取 STEP/STL 包围盒并检查 STL 闭合；读取 V2 ZIP 清单并确认不含旧无效卷曲件。
