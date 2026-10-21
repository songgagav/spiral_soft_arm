# 制造说明

本节介绍 SpiRobs 设计的基本打印制造流程。

## 1）导出 CAD

在设计工具中导出 **STL**（网格）或 **STEP**（实体）。

- STL 通常足以用于 3D 打印。
- 若打印前需要在 CAD 中修改几何形状，可使用 STEP。

## 2）分割超出打印范围的零件

如果导出几何超出打印机成型空间，可使用分割器将其切分为可打印的多个部分。

脚本：

- `fabrication/splitter_generator.py`

当前功能：

- 通过 CadQuery 实体求交支持 `STEP/STP`。
- 通过 VTK 网格裁切支持 `STL`。
- 支持沿一个轴（`x`、`y` 或 `z`）按最大跨度切分成多个部分。
- 支持用逗号分隔的切割位置手动指定切割平面。
- 可检查每个部分能否放入打印机成型空间，并生成 JSON 报告。
- 当前版本只进行几何切分，尚未生成键合接头、燕尾、销钉或卡扣连接件。

示例：

```powershell
python fabrication/splitter_generator.py design-tool/exports/spi_rob_20260312.step --axis x --max-span-mm 180
```

使用 STL 的示例：

```powershell
python fabrication/splitter_generator.py design-tool/exports/spi_rob_20260312.stl --axis z --max-span-mm 150
```

手动指定切割位置并检查成型空间的示例：

```powershell
python fabrication/splitter_generator.py design-tool/exports/spi_rob_20260312.step --axis x --cut-positions-mm 80,160 --build-volume-mm 256,256,256
```

输出内容：

- 与输入文件同级的 `<input>_split/` 目录。
- 命名为 `<input>_part01.step`、`<input>_part02.step` 的零件文件，或对应的 STL 文件。
- `split_report.json` 文件，记录各段边界、尺寸和可选的成型空间适配结果。

建议流程：

- 需要准确执行后续 CAD 操作时，优先使用 `STEP`。
- 只需要可打印网格时，使用 `STL`。
- 根据打印机成型空间限制和机器人结构中相对不敏感的受力方向选择切分轴。

## 3）导入切片软件

在切片软件中打开导出的文件（例如 **BambuLab Studio**）。

## 4）材料

- 推荐材料：**TPU**

## 5）切片并打印

根据 TPU 打印经验设置层高、速度和壁厚等参数，然后切片并打印。

## 6）后处理

如使用了支撑，打印后将其移除，并在装配前核对零件尺寸。

## 后续计划

下一版分割器计划加入接头结构，以便定位和重新装配，例如：

- 阶梯式接合面
- 定位销孔
- 外部锁紧套
- 可重复装配的键合接头，适用于 TPU 结构
