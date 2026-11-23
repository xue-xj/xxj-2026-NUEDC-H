"""NumPy DFL decoding for the Rockchip-optimized YOLOv8 export contract.

Not the standard Ultralytics (1, 4+classes, anchors) output contract.
Outputs must be dequantized floats, 3 branches with (box logits, scores[, sum]).
"""
import numpy as np
from .data_types import Detection


def _boxes(position, input_size):
    _, channels, height, width = position.shape
    if channels % 4 or channels < 8:
        raise ValueError('DFL channels must be 4 * reg_max, reg_max >= 2')
    bins = channels // 4
    logits = position.reshape(1, 4, bins, height, width)
    values = np.exp(logits - logits.max(axis=2, keepdims=True))
    values /= values.sum(axis=2, keepdims=True)
    distances = (values * np.arange(bins).reshape(1, 1, bins, 1, 1)).sum(axis=2)[0]
    xx, yy = np.meshgrid(np.arange(width) + .5, np.arange(height) + .5)
    sx, sy = input_size[0] / width, input_size[1] / height
    return np.stack(((xx - distances[0]) * sx, (yy - distances[1]) * sy,
                     (xx + distances[2]) * sx, (yy + distances[3]) * sy), axis=-1).reshape(-1, 4)


def _nms(boxes, scores, threshold):
    order = np.argsort(scores)[::-1]
    keep = []
    while order.size:
        current = int(order[0])
        keep.append(current)
        remaining = order[1:]
        lo = np.maximum(boxes[current, :2], boxes[remaining, :2])
        hi = np.minimum(boxes[current, 2:], boxes[remaining, 2:])
        inter = np.prod(np.maximum(0, hi - lo), axis=1)
        area0 = np.prod(np.maximum(0, boxes[current, 2:] - boxes[current, :2]))
        areas = np.prod(np.maximum(0, boxes[remaining, 2:] - boxes[remaining, :2]), axis=1)
        iou = inter / np.maximum(area0 + areas - inter, 1e-9)
        order = remaining[iou <= threshold]
    return keep


def decode_outputs(outputs, input_size, confidence, nms_threshold, target_class):
    if not isinstance(outputs, (list, tuple)) or len(outputs) not in (6, 9):
        raise ValueError('expected Rockchip YOLOv8 6/9 NCHW outputs; check model export')
    step = len(outputs) // 3
    boxes, scores = [], []
    classes_count = None
    grids = []
    for index in range(0, len(outputs), step):
        position, probabilities = np.asarray(outputs[index]), np.asarray(outputs[index + 1])
        if (position.ndim != 4 or probabilities.ndim != 4 or position.shape[0] != 1
                or probabilities.shape[0] != 1 or min(position.shape) <= 0
                or position.shape[2:] != probabilities.shape[2:]):
            raise ValueError('invalid YOLOv8 branch dimensions')
        if not np.issubdtype(position.dtype, np.floating) or not np.issubdtype(probabilities.dtype, np.floating):
            raise ValueError('outputs must be dequantized floats; raw INT8 requires scale/zero-point')
        if (not np.isfinite(position).all() or not np.isfinite(probabilities).all()
                or probabilities.min() < 0 or probabilities.max() > 1):
            raise ValueError('invalid scores/logits: expected finite values and activated scores in [0,1]')
        if not 0 <= target_class < probabilities.shape[1]:
            raise ValueError('target_class exceeds model classes')
        if classes_count is not None and classes_count != probabilities.shape[1]:
            raise ValueError('inconsistent class count')
        classes_count = probabilities.shape[1]
        grids.append(position.shape[2:])
        # Retain only the requested class when it wins the cell classification.
        flat = probabilities[0].transpose(1, 2, 0).reshape(-1, probabilities.shape[1])
        mask = (flat.argmax(axis=1) == target_class) & (flat[:, target_class] >= confidence)
        boxes.append(_boxes(position, input_size)[mask])
        scores.append(flat[mask, target_class])
    if len(set(grids)) != 3:
        raise ValueError('expected three distinct detection grids')
    boxes, scores = np.concatenate(boxes), np.concatenate(scores)
    if not len(boxes):
        return []
    return [Detection(tuple(map(float, boxes[i])), float(scores[i]), target_class)
            for i in _nms(boxes, scores, nms_threshold)]
