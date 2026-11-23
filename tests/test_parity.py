"""Behavior checks against the roles of the two original K230 programs."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import numpy as np

from ball_balance import application as app
from ball_balance.core import Detection, LatestSlot
from ball_balance.protocol import CoordinateParser
from ball_balance.runtime import Frame, InferenceResult, SerialSender
from test_runtime import CONFIG, MemorySerial


class OriginalParityTests(unittest.TestCase):
    def test_legacy_no_target_is_silent_and_does_not_reset_firmware_pid(self):
        slot, port, stop = LatestSlot(), MemorySerial(), threading.Event()
        sender = SerialSender(port, slot, stop, 20, .1, .45, 0)
        sender.send_once(now=10)
        slot.publish(InferenceResult(1, 10, 640, []))
        sender.send_once(now=10.01)
        self.assertEqual(port.frames, [])
        # Original script emits a detected result after inference, even if inference
        # was slower than the previous migration's arbitrary 350ms freshness bound.
        slot.publish(InferenceResult(2, 10, 640, [Detection((300, 100, 340, 140), .9)]))
        self.assertEqual(sender.send_once(now=10.5), 400)

    def test_legacy_software_exit_does_not_inject_a_new_stop_command(self):
        port, stop = MemorySerial(), threading.Event()
        stop.set()
        SerialSender(port, LatestSlot(), stop, 20, .1, .45, 0).run()
        self.assertEqual(port.frames, [])

    def test_new_result_wakes_serial_without_waiting_for_heartbeat_period(self):
        slot, port, stop = LatestSlot(), MemorySerial(), threading.Event()
        seen = threading.Event()
        class ObservablePort(MemorySerial):
            def write(self, data):
                result = super().write(data)
                if CoordinateParser().feed(data) == [400]:
                    seen.set()
                return result
        port = ObservablePort()
        sender = SerialSender(port, slot, stop, 1, .5, .45, 0)
        worker = threading.Thread(target=sender.run, daemon=True)
        worker.start()
        try:
            time.sleep(.02)
            slot.publish(InferenceResult(1, time.monotonic(), 640, [Detection((300, 100, 340, 140), .9)]))
            self.assertTrue(seen.wait(.3), 'fresh coordinates waited for the one-second polling interval')
        finally:
            stop.set()
            slot.publish(None)
            worker.join(timeout=2)

    def test_rtsp_defaults_match_old_stream_url_and_resolution(self):
        path = Path(__file__).resolve().parents[1] / 'config.example.json'
        config = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((config['rtsp']['mount'], config['rtsp']['width'], config['rtsp']['height'],
                          config['rtsp']['bitrate_kbps']), ('/test', 320, 240, 400))


class PreviewParityTests(unittest.TestCase):
    def test_display_uses_completed_frame_and_original_800x480_coordinates(self):
        from ball_balance.preview import preview_layout
        image = np.zeros((360, 640, 3), dtype=np.uint8)
        result = InferenceResult(1, 10, 640, [Detection((300, 100, 340, 140), .9)], source_bgr=image)
        newest = Frame(2, 10.1, np.ones_like(image))
        layout = preview_layout(newest, result, [13, 72, 614, 216], now=10.1, max_age=.35)
        self.assertIs(layout.source_bgr, image)
        self.assertEqual(layout.sequence, 1)
        self.assertEqual(layout.target, (400, 160))
        np.testing.assert_allclose(layout.boxes[0], (375, 100 * 480 / 360, 425, 140 * 480 / 360))
        np.testing.assert_allclose(layout.roi, (16.25, 96, 783.75, 384))

    def test_outdated_inference_boxes_are_not_painted_over_a_new_frame(self):
        from ball_balance.preview import preview_layout
        old = np.zeros((360, 640, 3), dtype=np.uint8)
        new = np.ones_like(old)
        result = InferenceResult(1, 1, 640, [Detection((300, 100, 340, 140), .9)], source_bgr=old)
        layout = preview_layout(Frame(2, 10, new), result, None, now=10, max_age=.35)
        self.assertIs(layout.source_bgr, new)
        self.assertEqual(layout.boxes, [])
        self.assertIsNone(layout.target)


class IndependentRoleTests(unittest.TestCase):
    def test_second_camera_failure_does_not_stop_recognition(self):
        config = copy.deepcopy(CONFIG)
        config['rtsp']['enabled'] = True
        config['stream_camera'] = {'device': 2, 'width': 320, 'height': 240, 'fps': 30}
        seen = threading.Event()
        control_stop = []
        def capture(camera, frames, stop):
            if camera['device'] == 2:
                raise RuntimeError('second camera disconnected')
            control_stop.append(stop)
            frames.publish(Frame(1, time.monotonic(), np.zeros((360, 640, 3), dtype=np.uint8)))
            stop.wait(2)
        def inference(detector, frames, results, stop):
            self.assertFalse(stop.is_set())
            seen.set()
            stop.set()
        fake_serial = types.ModuleType('serial')
        port = MemorySerial()
        port.close = lambda: None
        fake_serial.Serial = lambda *args, **kwargs: port
        with patch.dict('sys.modules', {'cv2': types.ModuleType('cv2'), 'serial': fake_serial}), \
                patch.object(app, 'capture_loop', capture), \
                patch.object(app, 'inference_loop', inference), \
                patch.object(app, 'RknnYoloV8'):
            app.run(config)
        self.assertTrue(seen.is_set())

    def test_stream_initialization_failure_keeps_inference_and_uart_running(self):
        config = copy.deepcopy(CONFIG)
        config['rtsp']['enabled'] = True
        calls = threading.Event()
        port = MemorySerial()
        port.close = lambda: None
        def capture(config, frames, stop):
            frames.publish(Frame(1, time.monotonic(), np.zeros((360, 640, 3), dtype=np.uint8)))
            stop.wait(.06)
            stop.set()
        def inference(detector, frames, results, stop):
            calls.set()
        fake_serial = types.ModuleType('serial')
        fake_serial.Serial = lambda *args, **kwargs: port
        fake_rtsp = types.ModuleType('ball_balance.rtsp')
        def failed_rtsp(*args, **kwargs):
            raise RuntimeError('missing encoder')
        fake_rtsp.RtspServer = failed_rtsp
        with patch.dict('sys.modules', {'cv2': types.ModuleType('cv2'), 'serial': fake_serial,
                                       'ball_balance.rtsp': fake_rtsp}), \
                patch.object(app, 'capture_loop', capture), \
                patch.object(app, 'inference_loop', inference), \
                patch.object(app, 'RknnYoloV8'):
            app.run(config)
        self.assertTrue(calls.is_set())


if __name__ == '__main__':
    unittest.main()
