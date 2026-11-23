"""V4L2 图像采集；摄像头资源由采集线程创建并在退出时释放。"""
import time
from .data_types import Frame

def capture_loop(config, frames, stop):
    import cv2
    capture = cv2.VideoCapture(config['device'], cv2.CAP_V4L2)
    try:
        if not capture.isOpened():
            raise RuntimeError(f'Cannot open V4L2 camera {config["device"]}')
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, config['width'])
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config['height'])
        capture.set(cv2.CAP_PROP_FPS, config['fps'])
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        sequence = 0
        while not stop.is_set():
            ok, bgr = capture.read()
            captured = time.monotonic()
            if not ok:
                raise RuntimeError('Camera read failed')
            if bgr.shape[:2] != (config['height'], config['width']):
                raise RuntimeError(f'Camera ignored resolution: actual={bgr.shape[:2]}, requested={config["height"]}x{config["width"]}')
            sequence += 1
            frames.publish(Frame(sequence, captured, bgr))
    finally:
        capture.release()
