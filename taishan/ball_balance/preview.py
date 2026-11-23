"""Original-style 800x480 preview, always pairing boxes with their image."""
from dataclasses import dataclass
from .geometry import select_coordinate
from .protocol import INVALID_COORDINATE

DISPLAY_SIZE = (800, 480)


@dataclass(frozen=True)
class PreviewLayout:
    source_bgr: object
    sequence: int
    boxes: list
    roi: tuple
    target: tuple


def preview_layout(frame, result, roi, now, max_age, threshold=.45, target_class=0):
    completed = None if result is None else result.completed_at
    result_time = None if result is None else (result.captured_at if completed is None else completed)
    paired = (result is not None and result.source_bgr is not None
              and 0 <= now - result_time <= max_age)
    image = result.source_bgr if paired else frame.bgr
    sequence = result.sequence if paired else frame.sequence
    height, width = image.shape[:2]
    sx, sy = DISPLAY_SIZE[0] / width, DISPLAY_SIZE[1] / height
    boxes, selected = [], []
    if paired:
        for detection in result.detections:
            if select_coordinate([detection], width, now, now, max_age, threshold, target_class) == INVALID_COORDINATE:
                continue
            a, b, c, d = detection.box
            boxes.append((a * sx, b * sy, c * sx, d * sy))
            selected.append(detection)
    target = None
    if selected:
        best = max(selected, key=lambda item: item.confidence)
        a, b, c, d = best.box
        target = (max(0, min(799, round((a+c) * .5 * sx))),
                  max(0, min(479, round((b+d) * .5 * sy))))
    roi_box = None
    if roi is not None:
        x, y, w, h = roi
        roi_box = (x * sx, y * sy, (x+w) * sx, (y+h) * sy)
    return PreviewLayout(image, sequence, boxes, roi_box, target)


def draw_preview(layout, cv2):
    image = cv2.resize(layout.source_bgr, DISPLAY_SIZE)
    if layout.roi:
        a, b, c, d = map(round, layout.roi)
        cv2.rectangle(image, (a, b), (c, d), (0, 255, 255), 2)
    for box in layout.boxes:
        a, b, c, d = map(round, box)
        cv2.rectangle(image, (a, b), (c, d), (0, 255, 0), 2)
    text = 'Ball: none' if layout.target is None else f'Ball: ({layout.target[0]}, {layout.target[1]})'
    if layout.target:
        cv2.circle(image, layout.target, 4, (0, 255, 255), -1)
    cv2.putText(image, text, (490, 455), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2)
    return image
