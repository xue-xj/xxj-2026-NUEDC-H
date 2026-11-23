# 许可证范围与第三方依赖

## 项目许可

由 Xue Jiaxing（薛嘉兴）享有授权权利的代码与文档采用根目录 MIT License。
该许可不替代第三方许可，不覆盖商家示例、TI 版权部分、SDK、运行库或模型权重。

## 已随仓库提供的第三方版权部分

`mspm0/main.c` 与 `mspm0/ball_control.c` 包含 TI 模板版权部分，保留文件头的完整 BSD 三条款式声明；许可副本见 `LICENSES/TI-BSD-3-Clause.txt`。

## 未随公开仓库提供的电机依赖

Emm_V5、usart、fifo、delay 的 C/H 示例带有 ZHANGDATOU / 张大头来源信息，当前未确认其公开再分发许可。
gimbal.c/.h 的电机集成接口也先不纳入公开发布范围，待确认来源及再分发权限后再处理。
这些文件未重新授权，也不包含在公开仓库中。获取方式及所需文件见 `docs/external-dependencies.md`。

## 外部安装的运行依赖

| 组件 | 许可或核对入口 |
| --- | --- |
| NumPy | BSD-3-Clause：https://numpy.org/doc/stable/license.html |
| pySerial | BSD：https://pyserial.readthedocs.io/en/latest/appendix.html#license |
| OpenCV | 4.5+ Apache-2.0，较早版本 BSD：https://opencv.org/license/ |
| GStreamer / GI 与插件 | 按安装版本分别核对；GStreamer 为 LGPL，插件可能不同：https://gstreamer.freedesktop.org/documentation/application-development/appendix/licensing.html |
| RKNNLite / RKNN-Toolkit2 | Rockchip SDK 专用许可：https://github.com/airockchip/rknn-toolkit2/blob/master/LICENSE |

上述依赖的源码、wheel、动态库、SDK 和系统镜像均不随本仓库分发，安装后仍需遵守各自许可。
本项目不统一授权这些组件；分发含运行库的安装包或镜像时须单独核对。

## 模型与参考接口

本仓库不包含训练集、预训练权重或 Ultralytics 源码。RKNN YOLOv8 接口用于接入外部模型。
加入模型或第三方实现时，应核对其具体版本与来源；使用 Ultralytics 代码或相关模型须核对 AGPL-3.0 / Enterprise 条款：https://www.ultralytics.com/license 。
DFL 输出契约参考 Rockchip Model Zoo（仓库为 Apache-2.0）：https://github.com/airockchip/rknn_model_zoo 。
RTSP 使用 GStreamer 的公开 appsrc / media-factory 接口。

本说明不将第三方源码或模型重新授予 MIT 权利。
