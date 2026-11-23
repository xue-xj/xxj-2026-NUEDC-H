import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import types

from ball_balance.config import load_config
from ball_balance.detector import require_model
from ball_balance.core import Detection, LatestSlot
from ball_balance.runtime import InferenceResult, SerialSender
from ball_balance.protocol import CoordinateParser, INVALID_COORDINATE


CONFIG = {
    'camera': {'device': 0, 'width': 640, 'height': 360, 'fps': 30},
    'stream_camera': None,
    'model': {'path': 'models/steel_ball.rknn', 'input_size': [320, 320],
              'roi': [13, 72, 614, 216], 'confidence': .45, 'nms': .45,
              'target_class': 0, 'pad_value': 128},
    'serial': {'device': '/dev/ttyS1', 'baudrate': 115200, 'rate_hz': 20, 'max_age_s': .35},
    'rtsp': {'enabled': False, 'bind': '0.0.0.0', 'port': 8554, 'mount': '/ball',
             'width': 640, 'height': 360, 'fps': 15, 'bitrate_kbps': 800, 'encoder': 'x264enc'},
    'display': False,
}


class ConfigTests(unittest.TestCase):
    def load(self, config):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps(config), encoding='utf-8')
            return load_config(path)

    def test_relative_model_path_resolved_against_config(self):
        config = self.load(CONFIG)
        self.assertTrue(Path(config['model']['path']).is_absolute())
        self.assertEqual(Path(config['model']['path']).parts[-2:], ('models', 'steel_ball.rknn'))

    def test_typo_and_roi_must_not_be_silently_accepted(self):
        config = json.loads(json.dumps(CONFIG))
        config['serial']['baud_rate'] = config['serial'].pop('baudrate')
        with self.assertRaises(ValueError):
            self.load(config)
        config = json.loads(json.dumps(CONFIG))
        config['model']['roi'] = [600, 0, 100, 100]
        with self.assertRaises(ValueError):
            self.load(config)

    def test_missing_model_is_not_replaced_with_fake_results(self):
        with self.assertRaises(FileNotFoundError):
            require_model(Path('definitely_missing_model.rknn'))

    def test_packed_bgr_rtsp_rows_must_match_gstreamer_alignment(self):
        config = json.loads(json.dumps(CONFIG))
        config['rtsp']['width'] = 642  # 1926 bytes/row, Gst expects 1928
        with self.assertRaises(ValueError):
            self.load(config)


class MemorySerial:
    def __init__(self):
        self.frames = []

    def write(self, packet):
        self.frames.append(bytes(packet))
        return len(packet)

    def flush(self):
        pass


class SerialTests(unittest.TestCase):
    def test_same_detection_does_not_drive_pid_twice(self):
        slot, port, stop = LatestSlot(), MemorySerial(), threading.Event()
        sender = SerialSender(port, slot, stop, 20, .1, .45, 0, loss_policy="stop")
        slot.publish(InferenceResult(1, 10, 640, [Detection((300, 100, 340, 140), .9)]))
        sender.send_once(now=10.01)
        sender.send_once(now=10.02)
        self.assertEqual(len(port.frames), 1)
        sender.send_once(now=10.2)
        self.assertEqual(CoordinateParser().feed(port.frames[-1]), [65535])

    def test_stale_results_and_empty_results_emit_out_of_range_stop(self):
        slot, port = LatestSlot(), MemorySerial()
        stop = threading.Event()
        sender = SerialSender(port, slot, stop, 20, .1, .45, 0, loss_policy="stop")
        self.assertEqual(sender.send_once(now=10), INVALID_COORDINATE)
        slot.publish(InferenceResult(1, 10, 640, [Detection((300, 100, 340, 140), .9)]))
        self.assertEqual(sender.send_once(now=10.05), 400)
        self.assertEqual(sender.send_once(now=10.2), INVALID_COORDINATE)
        slot.publish(InferenceResult(2, 10.3, 640, []))
        self.assertEqual(sender.send_once(now=10.31), INVALID_COORDINATE)
        decoded = CoordinateParser().feed(b''.join(port.frames))
        self.assertEqual(decoded, [65535, 400, 65535, 65535])

    def test_exit_sends_stop_frame_and_short_write_fails(self):
        slot, port, stop = LatestSlot(), MemorySerial(), threading.Event()
        stop.set()
        sender = SerialSender(port, slot, stop, 20, .1, .45, 0, loss_policy="stop")
        sender.run()
        self.assertEqual(CoordinateParser().feed(port.frames[-1]), [65535])
        class ShortSerial(MemorySerial):
            def write(self, packet):
                return 1
        with self.assertRaises(IOError):
            SerialSender(ShortSerial(), slot, stop, 20, .1, .45, 0, loss_policy="stop").send_once(now=1)


class AppLifecycleTests(unittest.TestCase):
    def test_preview_only_never_loads_model_or_opens_uart(self):
        from ball_balance import application as app
        from ball_balance.runtime import Frame
        def capture(config, frames, stop):
            frames.publish(Frame(1, time.monotonic(), object()))
            stop.wait(.03)
            stop.set()
        fake_cv2 = types.ModuleType('cv2')
        with patch.dict('sys.modules', {'cv2': fake_cv2}), \
                patch.object(app, 'capture_loop', capture), \
                patch.object(app, 'RknnYoloV8') as detector:
            app.run(CONFIG, preview_only=True)
            detector.assert_not_called()

    def test_normal_mode_reports_missing_model_before_opencv_or_uart(self):
        from ball_balance import __main__ as app
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps(CONFIG), encoding='utf-8')
            with patch.object(app, 'run') as run:
                self.assertEqual(app.main(['--config', str(path)]), 1)
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()

