# M3508 官方参考资料索引

获取日期：2026-11-02。PDF 与 STEP 均从 RoboMaster 官方产品页的“文档下载”区取得。

## 已下载

- RoboMaster_M3508_P19_User_Guide.pdf — [官方链接](https://cdn-hz.robomaster.com/robomasters/public/document/RoboMaster%20M3508%20P19%20Brushless%20DC%20Gear%20Motor%20V1.0.pdf)
- RoboMaster_M3508_Maintenance_Manual.pdf — [官方链接](https://cdn-hz.robomaster.com/tem/3724/RoboMaster%20M3508%E7%9B%B4%E6%B5%81%E6%97%A0%E5%88%B7%E5%87%8F%E9%80%9F%E7%94%B5%E6%9C%BA%E4%BF%9D%E5%85%BB%E6%89%8B%E5%86%8C.pdf)
- RoboMaster_M3508_Accessories_Kit_Guide.pdf — [官方链接](https://cdn-hz.robomaster.com/robomasters/public/document/RoboMaster%20M3508%20Accessories%20Kit%20V1.0.pdf)
- DJI_M3508_P19_official.stp — [官方产品页](https://www.robomaster.com/zh-CN/products/components/general/M3508)，下载项为“RoboMaster M3508直流无刷减速电机（STEP）”；文件大小 4,595,780 bytes；SHA256 12E62A62C12495210FEB74F1272F4D71CFFED070FD91A601D646B6C2A6D57087。

## 已核对的官方机械接口

- 电机外径：42 mm；总长：98.4 mm；机身标称长度：66.7 mm。
- 输出轴：Ø10 mm D 形；轴端 M5-6H 螺纹深度 10 mm；轴伸 27.3 mm。
- 安装孔：4×M4×0.7。
- 官方 STEP 导入为 24 个有效实体。源坐标输出轴中心约为 (-1.788736799, 18.268279471) mm，轴端 z=113.740998830 mm；D 平面法向角约 112.241273°。装配只平移该 STEP，将轴心对齐到 (0,0)，轴端对齐到 z=-68.7 mm，保留源文件绕轴角度。
- 产品页公布最大连续扭矩 3 N·m；该性能参数不代表本地传动已完成负载验证。

## 几何与验证边界

本地 v18 装配已将官方 STEP 作为电机母件，并把轴套 D 孔方向对齐真实模型中的 D 平面。卡簧槽位置约 14.2 mm、槽宽约 1.0 mm 来自用户提供的说明文件，官方图纸未标注，仍需实物测量。轴套配合间隙、螺纹啮合、延长轴、齿轮啮合、线束空间和线轮拉索载荷均未通过实物验证。
