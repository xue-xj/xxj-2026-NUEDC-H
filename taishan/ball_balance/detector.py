"""Model replacement boundary: implement Detector.detect(bgr) -> list[Detection]."""
from pathlib import Path
from .data_types import Detection
from .geometry import Letterbox
from .yolov8 import decode_outputs


def require_model(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'No RKNN model: {path}. Supply your trained model or explicitly use --preview-only.')
    if path.suffix.lower() != '.rknn':
        raise ValueError('expected .rknn; K230 .kmodel cannot run on RK3566')
    return path


class Detector:
    def detect(self, bgr):
        raise NotImplementedError

    def close(self):
        pass


class RknnYoloV8(Detector):
    """RKNNLite + Rockchip optimized 6/9-output YOLOv8 DFL model.

    Model is absent by design. Configure preprocessing to match its conversion.
    A different export must replace the decoder rather than guessing tensors.
    """

    def __init__(self, config):
        model = require_model(config['path'])
        import cv2
        from rknnlite.api import RKNNLite
        self.cv2, self.config, self.rknn = cv2, config, RKNNLite()
        try:
            if self.rknn.load_rknn(str(model)) != 0:
                raise RuntimeError('RKNN model loading failed')
            if self.rknn.init_runtime() != 0:
                raise RuntimeError('RKNN runtime initialization failed; check NPU driver/runtime compatibility')
        except BaseException:
            self.rknn.release()
            raise

    def detect(self, bgr):
        import numpy as np
        cv2, config = self.cv2, self.config
        height, width = bgr.shape[:2]
        roi = config['roi'] or [0, 0, width, height]
        x, y, w, h = roi
        if x + w > width or y + h > height:
            raise ValueError('ROI outside actual camera frame')
        # ROI 等比例缩放并补边；逆变换必须使用相同的实际缩放尺寸与边距。
        transform = Letterbox.create(roi, config['input_size'])
        tw, th = transform.size
        rw, rh = transform.resized
        resized = cv2.resize(bgr[y:y+h, x:x+w], (rw, rh))
        tensor = np.full((th, tw, 3), config['pad_value'], dtype=np.uint8)
        tensor[transform.top:transform.top+rh, transform.left:transform.left+rw] = resized
        tensor = np.ascontiguousarray(cv2.cvtColor(tensor, cv2.COLOR_BGR2RGB)[None, ...])
        # 输入契约为 RGB / uint8 / NHWC；模型转换配置必须与此一致。
        outputs = self.rknn.inference(inputs=[tensor], data_format=['nhwc'])
        if outputs is None:
            raise RuntimeError('RKNN inference returned no outputs')
        decoded = decode_outputs(outputs, transform.size, config['confidence'], config['nms'], config['target_class'])
        result = []
        for detection in decoded:
            # 将模型坐标还原为摄像头原图坐标，后续再统一映射到 0~799。
            a, b, c, d = transform.to_source(detection.box)
            a, b, c, d = max(x, a), max(y, b), min(x+w, c), min(y+h, d)
            if a < c and b < d:
                result.append(Detection((a, b, c, d), detection.confidence, detection.class_id))
        return result

    def close(self):
        self.rknn.release()

