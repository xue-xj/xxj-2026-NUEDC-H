"""推理工作线程：只处理最新图像，并将检测结果与对应原图一起发布。"""
import time
from .data_types import InferenceResult

def inference_loop(detector, frames, results, stop):
    version = 0
    while not stop.is_set():
        new_version, frame = frames.wait_after(version)
        if frame is None or new_version == version:
            continue
        version = new_version
        # 结果携带对应原图，显示时避免把旧检测框画到新帧上。
        detections = detector.detect(frame.bgr)
        results.publish(InferenceResult(frame.sequence, frame.captured_at, frame.bgr.shape[1],
                                        detections, frame.bgr, time.monotonic()))
