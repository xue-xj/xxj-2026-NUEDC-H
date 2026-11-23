# 基于泰山派与 MSPM0 的钢珠视觉平衡系统

## 发布范围与许可证

项目原创部分采用 [MIT License](LICENSE)，第三方部分按 [第三方说明](THIRD_PARTY.md) 处理。
**公开版未附带电机示例及集成依赖，MSPM0 工程需补齐文件后才能构建**，见 [外部依赖](docs/external-dependencies.md)。
模型权重与 SDK 同样需单独安装或提供。

## 项目简介

本项目 V1.0 采用 **泰山派 RK3566 / Linux + MSPM0G3507** 双板架构：泰山派负责钢珠视觉检测、本地显示和 RTSP 图传，通过 UART 下发钢珠横坐标；MSPM0 负责定点平衡、运动阶段补偿及闭环步进电机驱动器通信。

当前代码包提供应用、控制工程、模型接入接口及主机测试。模型权重未包含，实板构建与整机性能尚待验证，详见 [验证记录](docs/validation.md)。

## 系统架构

```text
USB 摄像头 → V4L2 采集 → 最新帧
                         ├→ ROI / Letterbox → RKNN 推理 → 坐标协议 → UART
                         │                                      ↓
                         │                              MSPM0G3507 控制
                         │                                      ↓
                         │                              Emm V5 → 电机
                         ├→ 本地显示
                         └→ H.264 / RTSP → 局域网监看
```

默认一个摄像头同时服务识别和图传；需要独立监看视角时，可配置第二个 USB 摄像头，仍由同一台泰山派运行。

## 功能

- 钢珠检测：ROI 裁剪、等比例补边、YOLOv8 DFL 后处理与目标坐标映射。
- 本地交互：800×480 预览，显示 ROI、检测框和钢珠坐标。
- 坐标通信：115200 波特率、七字节校验帧，同一推理结果仅发送一次。
- 运动控制：双目标依次到位保持、中心定点平衡、按键模式切换、阶段前馈与阻尼补偿。
- 远程监看：RTSP 原图传输，支持共享或独立摄像头；图传启动失败不关闭识别控制。

小车补偿采用内部阶段计时，本代码包不包含小车底盘驱动及实际加速度反馈。

## 目录与文档

| 目录 | 内容 |
| --- | --- |
| `taishan/ball_balance/` | Linux 视觉、通信、显示与图传应用 |
| `mspm0/` | CCS / SysConfig 电机控制工程 |
| `models/` | 模型接口与接入说明 |
| `config.example.json` | 单摄像头配置 |
| `config.dual-camera.example.json` | 双视角配置 |
| `tools/` | 模型转换与源码检查工具 |
| `tests/` | 主机自动化测试 |

- [系统设计](docs/design.md)
- [模块职责与阅读顺序](docs/modules.md)
- [部署与接线](docs/deployment.md)
- [通信与控制约定](docs/protocol.md)
- [功能检查清单](docs/feature-checklist.md)
- [验证记录](docs/validation.md)
- [第三方说明](THIRD_PARTY.md)

## 快速开始

先按部署文档安装匹配的 Linux、OpenCV、GStreamer 和 RKNNLite 环境。

```bash
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install -e .
cp config.example.json config.local.json
# 按实际硬件修改摄像头、串口及显示配置
ball-balance --config config.local.json --preview-only --check
ball-balance --config config.local.json --preview-only
```

预览模式不加载模型、不打开控制串口。放入匹配的 `models/steel_ball.rknn` 后：

```bash
ball-balance --config config.local.json --check
ball-balance --config config.local.json
```

RTSP 地址为 `rtsp://<泰山派IP>:8554/test`，默认配置为 320×240、15fps、400kbps；这些是配置目标，不是实测指标。无桌面环境时设置 `display=false`。

## 主机检查

```bash
PYTHONPATH=taishan python3 -m unittest discover -s tests -v
python3 tools/check_source_integrity.py  # 需先补齐外部电机依赖
```

当前 28 项测试通过。主机测试不代替 TI 编译、RKNN 推理与整机联调。
