# 多机器人阵列图形界面

此扩展提供一个基于 PySide6 的简易图形界面，用于生成圆形机器人阵列 XML，并在 MuJoCo 交互式查看器中打开模型。

## 环境要求

- Python 环境需安装：
  - `mujoco`
  - `PySide6`

如果使用仓库的 `design-tool/.venv` 虚拟环境，请运行：

```powershell
.\design-tool\.venv\Scripts\python -m pip install -r design-tool\requirements.txt
```

## 启动

```powershell
.\design-tool\.venv\Scripts\python extensions\multi-robot-array\array_gui.py
```

## 使用方法

1. 选择 MuJoCo XML 输入文件（`robot.xml`）。
2. 调整阵列参数：
   - `offset_y_mm`（默认 80）
   - `count`（默认 6）
   - `base_rot_deg`（默认 0）
   - `tilt_x_deg`（默认 -30）
3. 点击：
   - `Open MuJoCo Viewer (Input)` 检查输入 XML。
   - `Open MuJoCo Viewer (Array)` 生成阵列 XML 并打开查看器。
4. 点击 `Export XML` 导出最终阵列 XML。

## 输出

阵列 XML 写入：

```
extensions/multi-robot-array/output/robot_array.xml
```

查看器使用的预览 XML 位于：

```
extensions/multi-robot-array/output/_preview_robot_array.xml
```

## 命令行生成器

也可以直接运行以下命令生成阵列：

```powershell
.\design-tool\.venv\Scripts\python extensions\multi-robot-array\generate_array.py --help
```
