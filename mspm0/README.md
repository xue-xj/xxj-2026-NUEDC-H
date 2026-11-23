# MSPM0G3507 控制工程

公开版未附带电机示例及集成依赖，MCU 构建前请按 [外部依赖说明](../docs/external-dependencies.md) 补齐文件。本地完整工程验证记录不代表公开目录可直接构建。

负责视觉坐标接收、PID 平衡、模式切换及 Emm V5 闭环步进电机驱动器通信。

## 代码结构

- main.c：外设初始化和主循环调度。
- app_settings.h：PID、目标、限幅、阶段计时和电机参数。
- ball_control.c/.h：按键、控制状态机、PID 调用及遥测。
- coord_receiver.c/.h：视觉串口接收与七字节协议解析。
- pid.c/.h：PID 算法。
- gimbal.c/.h：电机动作与遥测接口。
- Emm_V5.c/.h：商家提供的驱动器通信示例，保留其来源声明。

## 导入构建

工程配置：MSPM0 SDK 2.10.00.04、SysConfig 1.26.2、TI Clang 4.0.4 LTS，MSPM0G3507 LQFP-48。
在 CCS 中安装兼容工具并导入本目录。工程内部名为 bujingmotor_24；已有同名工程时使用新工作区或通过 CCS 改名。

Debug 产物不随仓库分发。ti_msp_dl_config.c/.h、启动文件及链接配置由 SysConfig / SDK 提供。
执行 Clean/Rebuild，确认 ball_control.c 纳入编译；必要时按 SDK 模板核对启动文件和链接脚本。
当前未完成 TI 工具链构建验证。

## 外设

| 外设 | 引脚 | 用途 |
| --- | --- | --- |
| UART1 | PA9 RX / PA8 TX | 泰山派坐标，115200 |
| UART0 | PA10 TX / PA11 RX | Emm V5，115200 |
| PB6 | 低电平按下 | 模式切换 |

UART1 实现在 coord_receiver.c，通过 Coord_Init 开启接收中断；引脚由 empty.syscfg 配置。
实际控制周期与无目标策略见 ../docs/protocol.md。
