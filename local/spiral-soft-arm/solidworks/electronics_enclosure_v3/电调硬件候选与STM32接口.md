# B32 湿侧电机电调候选（STM32 主控）

更新：2026-10-20。当前电机参考为 ApisQueen 4092，卖家页面标称 12–24 V、无刷、80 W，并提供“motor and ESC”配套选项。页面给出的配套 ESC 指令为双向 PWM：1.0–1.5 ms 反转、1.5 ms 停止、1.5–2.0 ms 正转；页面没有公开 ESC 型号、持续/峰值电流、是否依赖霍尔信号、尺寸或水下等级。该页面目前还显示缺货。配套款仍是最值得先询价和台架试机的方案，不能仅凭电机网页冻结电气设计。页面标题的 0–200 rpm、8 Nm 与参数表中的 24 V 空载 108 rpm、最高 4.5 Nm 也不一致，需卖家给出对应具体型号的正式数据表。

## 候选

| 候选 | 每个电机配置 | 关键匹配点 | 主要限制 | 当前判断 |
| --- | --- | --- | --- | --- |
| ApisQueen 4092 配套 mini ESC | 每台电机配 1 个 | 原厂页面提供配套选项；双向 PWM 脉宽明确；针对该电机销售 | 额定电压范围、持续/峰值电流、Hall 线/相线定义、外形和散热均未公布 | 首选询价；在拿到数据表/接线图并完成台架试机前不下单冻结 |
| ST STEVAL-PTOOL4A | 每个电机 1 块，共 3 块 | 12–28 V、最高 20 A RMS、最高 250 W；STM32G473 + STDRIVE101；有 Hall/编码器接口设计预留、三相电流采样、过流/欠压/温度保护；能直连 24 V 总线；ST 提供 MCSDK/FOC/六步配置 | 默认程序面向另一台电机，4092 需重配/生成固件；外部主控接口虽有 UART/CAN/Throttle，具体控制命令及 CAN 固件需要开发；电路板外形和散热片需拿 CAD/实物测量，重新核对电子仓 | 推荐作为可控的研发原型备选，低速闭环须以电机 Hall/编码器实物信号验证 |
| ODrive S1 | 每个电机 1 块，共 3 块 | 12–48 V；支持 Hall/编码器；CAN、UART、PWM/Step-Dir 等控制；单轴速度、位置、扭矩/电流控制；板外廓 66×50 mm | 官方标 IP20、要求非冷凝环境；建议装散热板时连续电流 40 A（无散热时典型上限 20 A），对 80 W 电机偏大；三板成本和热管理较高；当前 CAD 的 ESC 包络小于该板，必须改模型 | 高级控制备选；先确认 4092 的 Hall 类型、相电流及电机参数，再制作三块板安装架并重新校核仓内空间 |
| Roboteq FBLG2360T | 两块：一块双通道带两台，另一块用单通道带第三台 | 60 V；2×40 A 连续、2×60 A/30 s；Hall/编码器；CAN；FOC/正弦/梯形控制 | 单块 140×140×25 mm、452 g；两块价格和体积都很高，无法装入当前 Ø124 mm 中央电子仓；对 80 W 电机严重过配 | 仅作台架/工业系统备选，不用于当前紧凑仓布局 |

## 不建议直接采用的板

ST STEVAL-ESC001V1 虽带 STM32F303、PWM/CAN 控制和 20 Arms/30 A 峰值能力，但额定输入是 3S–6S LiPo，即 11.1–22.2 V；它不满足保持 24 V 电源母线的要求。该板是无人机用途的无感 FOC，原厂配套低速齿轮电机应优先核实 Hall 反馈/低速启动能力。不能把该板“带 STM32”当成其适合 4092 的证据。

## 推荐控制结构

主控采用中央 STM32，负责三路执行器的位置/速度目标、传感器、互锁和故障处理；每台电机配独立的 ESC/电机控制器，由其本地 MCU 完成换相、电流环和保护。三轴优先用 CAN 总线传目标及读取故障/速度；若采用 ApisQueen 配套款，则按其页面脉宽使用三路定时器 PWM，并增加急停、使能和掉线停机逻辑。不要由一个普通 STM32 GPIO 直接驱动三相 MOSFET 功率级。

## 电池与母线核算（暂按 4S1P）

四节、每节 8000 mAh 串联时，电池组仍为 8 Ah，不是 32 Ah。按常见 3.7 V 标称电压估算，4S 标称约 14.8 V、能量约 118 Wh；满充电压 16.8 V。三台电机若同时达到页面标称 80 W，合计约 240 W。15 分钟按 240 W 计算为 60 Wh 负载侧能量，计入 24 V 升压损耗后电池需提供更多能量；在 14.8 V 电池端，连续输入电流粗略约 19 A（假设升压效率 85%），低电量时电流会更高。是否能运行 15 分钟取决于电芯持续放电倍率、实测电机功耗、变换器效率和截止电压，当前不能仅由 8 Ah 容量判定通过。

如果要在岸上 24 V 断电时维持同一 24 V 母线，需另定 4S→24 V 升压和无缝切换/防反灌方案；电源转换器应按三台电机的实测堵转/启动峰值电流选型。不能将电池直接并到 24 V 岸电上。电芯型号及持续放电倍率也要先确认，8000 mAh 容量值本身不代表它能连续输出约 20–25 A。

## 采购/冻结前向卖家确认

1. 4092 的相线、Hall/编码器线定义、极数/减速比和转速反馈位置；是否能以规定转速低速起停。
2. 配套 mini ESC 的准确型号、输入范围（必须覆盖 24 V 母线）、连续/峰值电流、峰值持续时间、PWM 脉宽/刷新率/上电默认状态、欠压/过流/过温保护。
3. 电机与 ESC 是否支持反转、制动/再生；如使用再生制动，24 V UPS/升压模块如何吸收回灌能量。
4. 80 W 是电输入还是轴输出；堵转/启动电流、最大连续相电流、30 分钟工作温升。
5. 8000 mAh 电芯的真实型号、规格书、持续/脉冲放电电流、充电限制、温度限制和保护要求。
6. 选定具体 ESC 后取 STEP/PCB 外形、孔位、接插件方向和散热面尺寸，再更新 `electronics_enclosure_v3` 元件包络与穿舱图。

## 资料来源

- ApisQueen 4092 原厂销售页（电机参数、配套 mini ESC 选项和 PWM 脉宽）：<https://www.waterproofmotor.com/products/apisqueen-12-24v-0-200rpm-4092-ip68-brushless-dc-waterproof-motor-gear-motor-for-rov-boat-underwater-thruster>
- ST STEVAL-PTOOL4A 产品页与规格：<https://www.st.com/en/evaluation-tools/steval-ptool4a.html>
- ST STEVAL-PTOOL4A 用户手册：<https://www.st.com/resource/en/user_manual/um3374-getting-started-with-the-stevalptool4a-reference-evaluation-board-stmicroelectronics.pdf>
- ODrive S1 官方数据表：<https://docs.odriverobotics.com/v/latest/hardware/s1-datasheet.html>
- ODrive S1 官方产品页：<https://shop.odriverobotics.com/products/odrive-s1>
- Roboteq FBLG2360T 官方产品页：<https://www.roboteq.com/products/products-brushless-dc-motor-controllers/fbl-family/fblg2360t-detail>
