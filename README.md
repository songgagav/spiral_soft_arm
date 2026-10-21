# Open Spiral Robots（OpenSpiRobs）

OpenSpiRobs 是用于设计和仿真对数螺旋软体机器人的研究工具包，提供便于快速迭代几何形状的图形界面、CAD 导出（STEP/STL）和 MuJoCo XML 生成，也包含可选的制造与数据集模块。

![主界面](design-tool/docs/images/main-ui.png)

## 许可证

- SPDX：PolyForm-Noncommercial-1.0.0
- 商业使用需要单独取得许可。

## 引用

若在学术研究中使用 OpenSpiRobs，请引用本仓库：

```bibtex
@software{wang_openspirob,
  title        = {OpenSpiRobs: Open Spiral Robots Toolkit},
  author       = {Wang, Zhanchi},
  year         = {2026},
  url          = {https://github.com/ZhanchiWang/Open-Spiral-Robots}
}
```

## 联系方式

- 电子邮件：zhanchi@ustc.edu.cn
- 微信号：spirobs
- 添加上述微信号可加入 OpenSpiRobs 微信群。

## 目录结构

- `design-tool/` — Python 图形界面设计工具（主要模块）
- `hardware/` — 硬件 CAD/STEP/STL 文件（可选）
- `fabrication/` — 制造和装配说明（可选）
- `datasets/` — 数据集和模型（可选）

使用方法见 `design-tool/README.md`。
