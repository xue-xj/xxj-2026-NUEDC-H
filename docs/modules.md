# 模块说明与阅读顺序

公开版未附带电机示例及集成依赖，MCU 构建前请按 [外部依赖说明](external-dependencies.md) 补齐文件。本地完整工程验证记录不代表公开目录可直接构建。

V1.0 按采集、推理、通信、显示及电机控制组织代码。

## 泰山派 Linux 端

| 文件 | 职责 |
| --- | --- |
| `__main__.py` | 命令行参数与配置加载，启动入口 |
| `diagnostics.py` | 依赖、模型文件与图传插件预检查 |
| `application.py` | 启动顺序、线程协调、图传故障隔离、显示与退出清理 |
| `config.py` | 配置解析与约束校验 |
| `data_types.py` | 原始帧、检测框与推理结果的数据结构 |
| `latest_slot.py` | 线程安全的单槽最新值交换，避免视频队列积压 |
| `capture.py` | V4L2 摄像头采集 |
| `inference.py` | 消费最新帧并发布检测结果 |
| `detector.py`、`yolov8.py` | RKNN 模型加载、预处理、推理与后处理 |
| `geometry.py` | ROI/letterbox 坐标转换、目标选择及 800 宽坐标映射 |
| `serial_link.py`、`protocol.py` | 坐标发送策略与七字节协议编解码 |
| `preview.py` | 检测结果与对应原图的本地显示 |
| `rtsp.py` | RTSP 编码与图传服务 |

`core.py` 和 `runtime.py` 仅保留原导入路径的兼容导出，不再承载业务实现。
启动入口、配置字段和模型接入方式见 README 与模型说明。

数据流：摄像头 → 最新帧 → RKNN 推理 → 最新结果 → 坐标选择 → UART → MSPM0。
本地预览使用检测结果对应的原图；图传可以共享识别摄像头，也可以配置独立摄像头。

## MSPM0 控制端

| 文件 | 职责 |
| --- | --- |
| `main.c` | 外设初始化、应用初始化与循环调度 |
| `app_settings.h` | 两种模式的 PID、目标、限幅、阶段时间及电机参数 |
| `ball_control.c/.h` | 按键模式切换、定点到位判断、小车阶段补偿、PID 与遥测调度 |
| `coord_receiver.c/.h` | 接收视觉坐标、校验并发布新坐标标志 |
| `pid.c/.h` | PID 计算 |
| `gimbal.c/.h` | 云台动作接口及遥测 |
| `Emm_V5.c/.h` | 商家提供的电机驱动示例代码 |
| `usart`、`fifo`、`delay` | 底层串口、缓冲与延时 |

新增 C 文件放在工程根目录，沿用 CCS 托管工程的源文件发现方式。导入工程后执行 Clean/Rebuild，
在编译日志中确认 `ball_control.c` 被编译；本机未安装 TI 工具链，尚未完成 CCS 构建与实板验证。

注意：PID 的 dt 为算法标称值，循环含串口等待；小车阶段仍是本地循环计时，并非小车实测反馈。
默认丢球处理采用静默策略，详见协议说明。

## 验证

主机执行 `PYTHONPATH=taishan python -m unittest discover -s tests -q`，当前 28 项通过。
测试覆盖模块接口、控制参数及执行序列、协议、坐标和生命周期。
源码哈希清单用于底层文件一致性检查；控制参考序列用于回归测试，两者不代替 TI 编译和实板验证。
模型需单独提供，完整状态见 validation.md。
