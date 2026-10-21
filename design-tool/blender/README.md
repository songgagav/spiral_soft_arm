# Blender 阶段 A 几何候选

本目录包含阶段 A 的四组输入参数和本地 Blender 生成器。在仓库根目录使用 Blender 5.2.2 LTS 运行：

```powershell
& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\generate_candidates.py'
& 'D:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'design-tool\blender\validate_candidates.py'
```

固定候选为 A35/A36/B31/B32，参数为 `p=0.5` 和 `delta_theta_deg=30`。候选 JSON 是模型输入的唯一来源。几何长度使用毫米，角度使用度，腱线位置和切除比例使用百分数；加载器只在入口处将百分数转换为无量纲小数。

本地 OpenSpiRobs 源码快照没有 Git 元数据，因此 `source_lock.json` 记录了文件 SHA-256，并将本地提交号记为 `null`，同时固定上游参考提交 `f563e69f292a6b8cac1946dc45ad9e60d8795391`。本地 GUI 源码与上游版本有差异：本地缺少 `num_cables` 和 `teardrop_holes`，且 `cable3_cut_pos` 默认值为 25%，上游固定版本默认值为 0%。本生成器未实现泪滴孔。`cone_angle1_deg` 和 `cone_angle2_deg` 作为版本追踪字段保留，但本地三腱路径不使用它们。

报告分别记录原始连续理论公式给出的中心线长度，以及本地生成器对中心轴直线段求和得到的长度。前者是 550 mm 设计目标；后者是离散化诊断值，可能较短。CAD 目标不等同于制造公差或材料强度认证。TPU 质量估算是根据网格体积和密度计算的理论 100% 实体质量；实际打印质量应由选定工艺的切片结果给出。

为避免布尔并集处出现共面端盖接缝，弹性轴在每个壳体端部外延伸 0.5 mm。报告单独记录最终主体的包围盒高度和 550 mm 理论中心线长度。`cut_on` 形状使用明确标注的三重径向裁切近似，不声称与上游生成器的截面裁切完全相同。尖端和基部直径根据生成网格的端部带区测量；展开轮廓尺寸仍作为参考保存在报告中。报告按变体记录 STL 往返拓扑检查结果。在本次 V0.1.3 运行中，`cut_off` 往返后为闭合双流形；`cut_on` 不是，在修复前仅供比较。实测基部外接直径约 62.7 mm，低于 68 ± 1 mm 目标，因此这些候选还不能作为满足目标尺寸的打印版本。
