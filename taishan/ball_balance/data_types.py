"""采集帧与推理结果的数据契约；图像共享只读，绘图前必须复制。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Detection:
    box: tuple  # source-frame (left, top, right, bottom)
    confidence: float
    class_id: int = 0


@dataclass(frozen=True)
class Frame:
    sequence: int
    captured_at: float
    bgr: object  # immutable by convention; consumers copy before annotating


@dataclass(frozen=True)
class InferenceResult:
    sequence: int
    captured_at: float
    width: int
    detections: list
    source_bgr: object = None
    completed_at: float = None
