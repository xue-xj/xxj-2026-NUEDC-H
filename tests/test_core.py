import math
import unittest
import numpy as np

from ball_balance.protocol import encode_coordinate, CoordinateParser, INVALID_COORDINATE
from ball_balance.core import LatestSlot, Detection, select_coordinate, Letterbox
from ball_balance.yolov8 import decode_outputs


class ProtocolTests(unittest.TestCase):
    def test_original_firmware_wire_format(self):
        self.assertEqual(encode_coordinate(400), bytes.fromhex('AA 55 01 90 91 55 FF'))
        self.assertEqual(encode_coordinate(INVALID_COORDINATE), bytes.fromhex('AA 55 FF FF FE 55 FF'))

    def test_reject_invalid_inputs(self):
        for value in [-1, 65536, 1.5, True]:
            with self.assertRaises((ValueError, TypeError)):
                encode_coordinate(value)

    def test_fragment_noise_corruption_and_coalesced_frames(self):
        parser = CoordinateParser()
        bad = bytearray(encode_coordinate(100))
        bad[4] ^= 1
        self.assertEqual(parser.feed(b'noise\xaa' + bad + encode_coordinate(325)[:3]), [])
        self.assertEqual(parser.feed(encode_coordinate(325)[3:] + encode_coordinate(565)), [325, 565])


class ControlDataTests(unittest.TestCase):
    def test_latest_slot_drops_old_frames(self):
        slot = LatestSlot()
        slot.publish('old')
        version = slot.publish('new')
        self.assertEqual(slot.read(), (version, 'new'))
        self.assertEqual(slot.wait_after(version, timeout=0.001), (version, 'new'))

    def test_letterbox_maps_crop_back_to_original(self):
        transform = Letterbox.create((13, 72, 614, 216), (320, 320))
        model_box = transform.to_model((300, 150, 340, 190))
        np.testing.assert_allclose(transform.to_source(model_box), (300, 150, 340, 190), atol=1e-5)

    def test_coordinate_scale_staleness_and_low_confidence(self):
        det = Detection((300, 100, 340, 140), .9, 0)
        self.assertEqual(select_coordinate([det], 640, 10, 10.1, .3, .45), 400)
        self.assertEqual(select_coordinate([det], 640, 10, 11, .3, .45), INVALID_COORDINATE)
        self.assertEqual(select_coordinate([], 640, 10, 10.1, .3, .45), INVALID_COORDINATE)
        self.assertEqual(select_coordinate([Detection(det.box, .1, 0)], 640, 10, 10.1, .3, .45), INVALID_COORDINATE)

    def test_only_target_class_and_finite_in_bounds_box(self):
        invalid = [Detection((0, 0, math.nan, 1), .99, 0), Detection((0, 0, 10, 10), .99, 1)]
        self.assertEqual(select_coordinate(invalid, 640, 1, 1.1, .3, .45), INVALID_COORDINATE)
        self.assertEqual(select_coordinate([Detection((630, 0, 640, 10), .9, 0)], 640, 1, 1.1, .3, .45), 794)


class YoloTests(unittest.TestCase):
    @staticmethod
    def outputs():
        out = []
        for size in [4, 2, 1]:
            logits = np.full((1, 16, size, size), -20., dtype=np.float32)
            for side in range(4):
                logits[:, side * 4 + 1, :, :] = 20
            scores = np.zeros((1, 1, size, size), dtype=np.float32)
            out.extend([logits, scores, scores.copy()])
        return out

    def test_dfl_single_class_geometry(self):
        outputs = self.outputs()
        outputs[1][0, 0, 1, 1] = .9
        boxes = decode_outputs(outputs, (32, 32), .45, .45, 0)
        self.assertEqual(len(boxes), 1)
        np.testing.assert_allclose(boxes[0].box, (4, 4, 20, 20), atol=1e-4)

    def test_empty_results_and_wrong_contract(self):
        self.assertEqual(decode_outputs(self.outputs(), (32, 32), .45, .45, 0), [])
        with self.assertRaises(ValueError):
            decode_outputs([np.zeros((1, 5, 21))], (32, 32), .45, .45, 0)
        raw = self.outputs()
        raw[0] = raw[0].astype(np.int8)
        with self.assertRaises(ValueError):
            decode_outputs(raw, (32, 32), .45, .45, 0)


if __name__ == '__main__':
    unittest.main()
