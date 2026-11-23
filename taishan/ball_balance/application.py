"""应用生命周期：协调工作线程、独立图传、界面显示及退出清理。"""
import importlib.util
import logging
import queue
import signal
import threading
import time
from .latest_slot import LatestSlot
from .detector import RknnYoloV8, require_model
from .serial_link import SerialSender
from .capture import capture_loop
from .inference import inference_loop
from .preview import preview_layout, draw_preview

LOG = logging.getLogger('ball_balance')


def run(config, preview_only=False):
    import cv2
    stop, errors = threading.Event(), queue.Queue()
    stream_stop = threading.Event()
    frames, results, stream_frames = LatestSlot(), LatestSlot(), None
    threads, port, detector, stream = [], None, None, None

    def worker(name, function, *args, fatal=True):
        def guarded():
            try:
                function(*args)
            except BaseException as error:
                LOG.exception('%s worker failed', name)
                if fatal:
                    errors.put(error)
                    stop.set()
                else:
                    stream_stop.set()
                    LOG.warning('Streaming role unavailable; vision/control continues')
        thread = threading.Thread(target=guarded, name=name, daemon=True)
        threads.append(thread)
        thread.start()
        return thread

    old_handlers = {}
    inference_thread = None
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            old_handlers[signum] = signal.signal(signum, lambda *_: stop.set())
        if not preview_only:
            # 先加载模型，失败时不打开运动控制串口，避免系统部分启动。
            detector = RknnYoloV8(config['model'])
        worker('capture', capture_loop, config['camera'], frames, stop)
        deadline = time.monotonic() + 5
        while frames.read()[1] is None and not stop.is_set() and time.monotonic() < deadline:
            frames.wait_after(0, timeout=.1)
        if frames.read()[1] is None:
            raise RuntimeError('No recognition camera frame within startup timeout')
        stream_frames = frames
        if config['rtsp']['enabled']:
            # 图传与识别控制故障隔离：第二摄像头、编码器或端口失败只关闭图传。
            try:
                if config['stream_camera'] is not None:
                    stream_frames = LatestSlot()
                    worker('stream-camera', capture_loop, config['stream_camera'], stream_frames,
                           stream_stop, fatal=False)
                    deadline = time.monotonic() + 5
                    while (stream_frames.read()[1] is None and not stop.is_set()
                           and not stream_stop.is_set() and time.monotonic() < deadline):
                        stream_frames.wait_after(0, timeout=.1)
                    if stream_frames.read()[1] is None:
                        raise RuntimeError('No streaming camera frame within startup timeout')
                from .rtsp import RtspServer
                stream = RtspServer(config['rtsp'], stream_frames, stream_stop)
                stream.start()
            except Exception:
                stream_stop.set()
                if stream:
                    stream.close()
                    stream = None
                LOG.exception('RTSP unavailable; keeping recognition and UART independent')
        if not preview_only:
            import serial
            serial_cfg, model_cfg = config['serial'], config['model']
            port = serial.Serial(serial_cfg['device'], serial_cfg['baudrate'], timeout=.1, write_timeout=.1)
            sender = SerialSender(port, results, stop, serial_cfg['rate_hz'], serial_cfg['max_age_s'],
                                  model_cfg['confidence'], model_cfg['target_class'],
                                  serial_cfg.get('loss_policy', 'legacy_silent'))
            worker('uart', sender.run)
            inference_thread = worker('inference', inference_loop, detector, frames, results, stop)
        else:
            LOG.warning('PREVIEW ONLY: no model, no UART, no motion commands')
        last_report = time.monotonic()
        while not stop.is_set():
            if config['display']:
                _, frame = frames.read()
                _, result = results.read()
                if frame:
                    layout = preview_layout(frame, result, config['model']['roi'], time.monotonic(),
                                            config['serial']['max_age_s'], config['model']['confidence'],
                                            config['model']['target_class'])
                    image = draw_preview(layout, cv2)
                    cv2.imshow('Ball balance (q: quit)', image)
                    if cv2.waitKey(1) & 255 in (ord('q'), 27):
                        stop.set()
            if time.monotonic() - last_report >= 5:
                _, frame = frames.read()
                _, result = results.read()
                LOG.info('capture_seq=%s inference_seq=%s', frame.sequence if frame else 0,
                         result.sequence if result else 0)
                last_report = time.monotonic()
            stop.wait(.02)
        if not errors.empty():
            raise RuntimeError('Worker failed') from errors.get()
    finally:
        stop.set()
        stream_stop.set()
        # 唤醒等待结果的串口线程；None 只用于退出，不伪造检测结果。
        results.publish(None)
        if stream:
            stream.close()
        # 先等待工作线程退出，再释放其使用的串口与 NPU，避免跨线程释放。
        for thread in threads:
            thread.join(timeout=2)
            if thread.is_alive():
                LOG.warning('%s has not returned; no cross-thread SDK release is attempted', thread.name)
        if port:
            port.close()
        if detector and (inference_thread is None or not inference_thread.is_alive()):
            detector.close()
        if config['display']:
            cv2.destroyAllWindows()
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
