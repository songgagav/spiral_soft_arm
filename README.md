# Spiral Soft Arm 研究仓库

本仓库基于 [Open Spiral Robots（OpenSpiRobs）](https://github.com/ZhanchiWang/Open-Spiral-Robots) 派生，保留其对数螺旋软体机器人设计工具，并继续整理本地 B32 软体臂的 CAD、仿真、制造准备和验证记录。本仓库由本地项目维护，不代表上游项目的官方版本或状态。

## 当前研究状态

- **设计工具**：提供 Python 图形界面，可生成机器人几何并导出 STEP/STL 与 MuJoCo XML。安装和使用方法见 [`design-tool/README.md`](design-tool/README.md)。
- **B32 主体**：几何验收记录显示，论文构形 STEP 可回读为单实体，STL 网格闭合；指定的 5 组仿真工况数值运行稳定。这些结果仅说明对应文件和工况通过了记录中的检查，不代表实物性能已验证。
- **最新底座候选**：[`electronics_enclosure_v9`](local/spiral-soft-arm/solidworks/electronics_enclosure_v9/) 包含三段机械臂、在关节单元 6 和 13 内部拆分的燕尾接口、250 mm 六边形顶盘，以及湿侧电机和线轮的切线出线布局。该目录记录了静态 CAD 干涉检查结果；它仍是审图与试样设计候选。
- **打印与实物验证**：当前记录只允许推进 80 mm TPU 95A 工艺短样；全长 TPU 打印工艺、实际电机张力、线轮绕线和导向、动态间隙、紧固耐久及整机抓取性能都没有完成验证。记录中的 100 g 抓取仿真工况未通过。
- **水下验证**：5 m 淡水/海水运行仍是设计目标，尚无压力、密封、腐蚀、供电或 30 分钟运行验证。v9 外罩与水连通，不是承压壳体。

详细状态和放行条件见 [`当前状态与放行条件.md`](local/spiral-soft-arm/preprint/v2/当前状态与放行条件.md)；v9 几何边界和待验证项见该候选目录中的 [`README`](local/spiral-soft-arm/solidworks/electronics_enclosure_v9/README_%E6%B0%B4%E5%B9%B3%E8%BD%AC%E4%BD%8D%E4%B8%8E%E7%BA%BF%E8%BD%AE%E5%88%87%E7%BA%BF%E5%AF%B9%E5%AD%94.md)。

## 仓库内容

- [`design-tool/`](design-tool/) — 上游设计工具及其使用文档。
- [`local/spiral-soft-arm/`](local/spiral-soft-arm/) — 本地 B32 几何、仿真、打印准备和分版本 CAD 候选。
- [`fabrication/`](fabrication/) — CAD/STL 几何分割工具和制造说明；当前分割器只切分几何，不会自动生成装配接头。
- [`hardware/`](hardware/) — 硬件参考模型和资料。
- [`datasets/`](datasets/) 与 [`extensions/`](extensions/) — 数据和扩展模块。
- [`related-papers/`](related-papers/) — 研究论文参考资料。

## 启动设计工具

需要 Python 3.10 或更高版本。依赖安装、启动步骤和界面说明见 [`design-tool/README.md`](design-tool/README.md)。

## 上游来源与引用

设计工具及研究基础来自 [Zhanchi Wang 的 Open-Spiral-Robots](https://github.com/ZhanchiWang/Open-Spiral-Robots)。如使用上游工作，请按其项目页面要求引用：

```bibtex
@software{wang_openspirob,
  title        = {OpenSpiRobs: Open Spiral Robots Toolkit},
  author       = {Wang, Zhanchi},
  year         = {2026},
  url          = {https://github.com/ZhanchiWang/Open-Spiral-Robots}
}
```

## 许可证

本仓库适用根目录 [`LICENSE`](LICENSE) 中的 **PolyForm Noncommercial License 1.0.0**。该协议限制商业用途；需要商业使用时，应向相关版权持有人另行确认许可。

仓库内的第三方资料仍按其各自条款处理。特别是 [`related-papers/`](related-papers/) 中未修改的论文副本采用 CC BY-NC-ND 4.0，不由本仓库的 LICENSE 重新授权；硬件供应商文件也保留其原有版权和使用条件。请在复用前查看相应目录的说明。
