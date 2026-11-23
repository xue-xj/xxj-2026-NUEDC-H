# Linux 部署与实物接线

公开版未附带电机示例及集成依赖，MCU 构建前请按 [外部依赖说明](external-dependencies.md) 补齐文件。本地完整工程验证记录不代表公开目录可直接构建。

## 默认适配范围

RK3566 泰山派，Debian/Ubuntu 类 Linux、Python 3.9+、USB UVC 摄像头。板卡/系统/摄像头未实际确认，本项目不包含专用设备树 overlay 或 MIPI CSI 驱动。Buildroot 需要自行提供同等 OpenCV、GI 和 GStreamer 组件。

Python 3.13 的 Windows 主机只用于纯逻辑测试，不用于 RKNN wheel 部署。目标 Python 版本需与瑞芯微提供的 AArch64 wheel 匹配；常见发行版使用3.9/3.10，但不得盲目混装。

## 依赖

Debian/Ubuntu 示例（按自己的系统仓库调整）：

```bash
sudo apt update
sudo apt install python3-venv python3-numpy python3-opencv python3-gi \
  gir1.2-gst-rtsp-server-1.0 gstreamer1.0-tools gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
  v4l-utils
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install -e .
```

RKNNLite2 不使用随机 PyPI 同名包代替：从瑞芯微官方工具链选择匹配 **AArch64、Python ABI、板端 NPU 驱动**的 wheel，并按官方要求安装匹配依赖。NumPy 版本以 wheel 要求为准；仓库目标依赖限制为 NumPy 1.x，当前纯逻辑也在 NumPy 2.x 主机测试过。

```bash
python -m pip install /path/to/matching/rknn_toolkit_lite2-....whl
```

参考：https://github.com/airockchip/rknn-toolkit2

## 摄像头

```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

将支持的分辨率/帧率写进 `config.local.json`。应用会检查实际图像尺寸；相机忽略请求时退出，防止 ROI 和位置尺度悄悄变化。`CAP_PROP_BUFFERSIZE=1` 是请求，是否生效需测相机驱动；最新帧槽不等于已证明全链路低延迟。

需要独立监看视角时，在配置中设置第二个摄像头：

```json
"stream_camera": {"device": "/dev/video2", "width": 640, "height": 360, "fps": 30}
```

识别仍只读取 `camera`；`stream_camera` 只用于原图监看。不需要第二视角时保持 `null`，确保一台相机只打开一次。

## UART 与 MSPM0

| 连接 | 接法 |
| --- | --- |
| 泰山派选定UART TX | MSPM0 UART1 RX：PA9 |
| GND | MSPM0 GND |
| MSPM0 UART1 TX：PA8 | 可不接；当前视觉协议单向下发 |
| MSPM0 UART0 PA10/PA11 | 连接 Emm V5 电机驱动器，不接视觉端 |

均按实际模块确认3.3V TTL，不能接RS232电平。两板已分别供电时不互接电源脚。

`/dev/ttyS1` 只是例子，不代表泰山派某组固定排针。根据板卡文档选择 UART、核对 pinmux、串口控制台占用及设备节点，再配置 `serial.device`。没有实际板型，不能指定物理排针编号。

如需串口权限，按发行版配置 dialout 组并重新登录；不要使用永久 `chmod 777` 或以 root 运行整个应用作为默认方案。

## RTSP

默认软件 `x264enc` 是便于部署的兼容方案，不宣称硬编码性能。地址为 `rtsp://<board-ip>:8554/test`，用 VLC 打开。默认分辨率320×240，帧率目标15、码率400kbps。

图传保持原图。`display=true`（示例默认）显示800×480本地画面、ROI、检测框和钢珠中心坐标；识别有延迟时使用对应的已完成图像，确保检测框与对应图像配对。结果过期后回到最新预览并显示无目标。

本地显示采用 Linux 桌面 / OpenCV 窗口。使用外接屏时需确认屏幕驱动与桌面环境；无桌面时设 `display=false`。

两视角版本直接复制 `config.dual-camera.example.json` 为 `config.local.json`。第二相机或RTSP初始化失败会明确记录，但不停止识别与UART。识别或主控通信等关键线程失败时，应用整体退出并清理资源。

Wi-Fi由Linux网络服务连接，可用系统界面或 `nmcli --ask device wifi connect "<SSID>"` 交互配置；可由NetworkManager保存自动连接。仓库不保存热点密码。

RTSP宽度须为4的倍数、高度须为偶数，使BGR行跨度及I420编码对齐；配置加载会拒绝不匹配的尺寸。

```bash
gst-inspect-1.0 x264enc
gst-inspect-1.0 mpph264enc
```

板镜像提供并确认 `mpph264enc` 可用后，才将 `rtsp.encoder` 改为该值。MPP插件的码率属性/单位随镜像不同，当前代码不猜参数，`bitrate_kbps` 只应用于 x264enc。需要在板端调优并记录验证。

RTSP不含认证，默认监听局域网地址。只在可信局域网使用；需要限制访问时设置 `bind=127.0.0.1` 或按部署环境配置网络访问控制，不直接映射公网。WIFI连接由Linux系统网络管理处理，代码不保存热点密码。

## 启动顺序

1. 电机与摆杆先不联动，完成摄像头、RTSP预览。
2. 放入真模型，完成检测与坐标对照；运行 `--check`。
3. 用USB转TTL或逻辑分析仪确认7字节帧；默认漏检无输出，选择stop策略时再验证无效帧。
4. 将主控的现有工程导入CCS并按本地SDK构建。
5. 解决主控通信失联停机，再低速验证方向/限幅和 PID。
6. 最后测试识别、图传、UART及运动同时工作。

当前不自动安装系统服务、不自动烧录、不自动连接设备或上传GitHub。
