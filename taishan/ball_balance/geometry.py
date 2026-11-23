"""ROI、模型输入及原始图像之间的坐标转换与目标筛选。"""
from dataclasses import dataclass
import math
from .protocol import INVALID_COORDINATE, COORDINATE_WIDTH

@dataclass(frozen=True)
class Letterbox:
    roi: tuple
    size: tuple
    resized: tuple
    left: int
    top: int

    @classmethod
    def create(cls, roi, size):
        x, y, w, h = roi
        tw, th = size
        if min(w, h, tw, th) <= 0 or min(x, y) < 0:
            raise ValueError('invalid ROI or input size')
        scale = min(tw / w, th / h)
        rw, rh = max(1, round(w * scale)), max(1, round(h * scale))
        return cls(tuple(roi), tuple(size), (rw, rh), (tw - rw) // 2, (th - rh) // 2)

    def to_source(self, box):
        x, y, w, h = self.roi
        rw, rh = self.resized
        a, b, c, d = box
        return ((a - self.left) * w / rw + x, (b - self.top) * h / rh + y,
                (c - self.left) * w / rw + x, (d - self.top) * h / rh + y)

    def to_model(self, box):
        x, y, w, h = self.roi
        rw, rh = self.resized
        a, b, c, d = box
        return ((a - x) * rw / w + self.left, (b - y) * rh / h + self.top,
                (c - x) * rw / w + self.left, (d - y) * rh / h + self.top)


def select_coordinate(detections, source_width, captured_at, now, max_age, threshold, target_class=0):
    if source_width <= 0 or not 0 <= now - captured_at <= max_age:
        return INVALID_COORDINATE
    valid = []
    for detection in detections:
        a, b, c, d = detection.box
        if (detection.class_id == target_class and math.isfinite(detection.confidence)
                and detection.confidence >= threshold
                and all(math.isfinite(v) for v in detection.box)
                and 0 <= a < c <= source_width and b < d):
            valid.append(detection)
    if not valid:
        return INVALID_COORDINATE
    # 沿用原工程：多目标时选择置信度最高的钢珠，不改变控制目标选择策略。
    best = max(valid, key=lambda item: item.confidence)
    # MCU 参数以 800 宽坐标标定，与实际摄像头分辨率解耦。
    center = (best.box[0] + best.box[2]) / 2
    return max(0, min(COORDINATE_WIDTH - 1, round(center * COORDINATE_WIDTH / source_width)))
