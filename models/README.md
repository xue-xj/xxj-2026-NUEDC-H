# 模型接口

本代码包不包含训练权重，模型通过以下接口独立接入。`config.example.json` 约定 `models/steel_ball.rknn`，可修改路径。

## 接入点

- `taishan/ball_balance/detector.py`：`Detector.detect(bgr) -> list[Detection]`。
- 默认实现 `RknnYoloV8` 使用 `rknnlite.api.RKNNLite`。
- 输入是完整源图 BGR；检测器完成 ROI、缩放补边、RGB 转换。
- 返回框必须是 **完整源图像素坐标** `(left, top, right, bottom)`，并携带置信度和类别；不要返回 ROI 局部坐标或直接的 800 尺度坐标。
- UART 层统一完成 `x_center * 800 / source_width`，避免重复缩放。

## 默认模型契约

| 项目 | 约定 |
| --- | --- |
| 平台 | RK3566，RKNN-Toolkit2 转换，与板端驱动/runtime 兼容 |
| 输入 | batch=1、NHWC、RGB uint8，默认 `[1,320,320,3]` |
| 归一化 | 由转换配置嵌入，默认 mean=0、std=255；应用不再次除255 |
| 补边 | 配置 `pad_value=128`，必须与训练/导出预处理核对 |
| 类别 | 默认 `steel_ball` 类别编号0，可配置 `target_class` |
| 输出 | Rockchip 优化导出的 YOLOv8 DFL，3个不同网格分支，每分支2或3个输出 |
| 输出顺序 | `(DFL logits, activated class probabilities[, score_sum])`，分支连续排列，共6或9张量 |
| 张量 | batch1、NCHW，DFL通道为 `4 * reg_max`，结果是 RKNNLite 已反量化的浮点数 |

现有解码器**不支持直接把普通 Ultralytics 单输出 `(1,4+nc,N)` 当作上述格式**，也不猜测 INT8 scale/zero-point。布局不符会明确报错，应针对新模型修改 `yolov8.py`，并用已标注图片验证。

## 后续补齐顺序

1. 准备钢珠检测 `.pt` / `.onnx` 权重，或采集数据后训练模型。
2. 参考瑞芯微官方优化导出流程得到 ONNX，核对输出数量/布局/激活方式及输入尺寸。
3. 在合适的 x86 Linux 环境安装 RKNN-Toolkit2，准备真实摆杆/钢珠标定图像列表；不将其上传仓库。
4. 执行转换入口，不能以随机图像代替量化标定：

```bash
python tools/convert_model.py --onnx steel_ball.onnx \
  --dataset calibration.txt --output models/steel_ball.rknn
```

也可加 `--float` 先做未量化对照；这不保证速度或精度。

5. 核对 PC 与板端的框坐标/置信度，确认 ROI、颜色、补边、归一化和量化误差。
6. 再接串口和执行机构。不要先通电运动再猜模型输出。

官方参考：https://github.com/airockchip/rknn_model_zoo/tree/main/examples/yolov8
