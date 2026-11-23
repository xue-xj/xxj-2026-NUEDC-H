"""坐标发送：保持原七字节协议，每个有效视觉结果仅发送一次。"""
import logging
import time
from .geometry import select_coordinate
from .protocol import encode_coordinate, INVALID_COORDINATE

LOG = logging.getLogger(__name__)

class SerialSender:
    """Event-driven valid coordinates, with explicit loss policy.

    This cannot protect against Linux power loss / physical UART disconnection.
    The unchanged firmware has no independent communication-loss watchdog.
    """

    def __init__(self, port, results, stop, rate_hz, max_age, threshold, target_class,
                 loss_policy='legacy_silent'):
        self.port, self.results, self.stop = port, results, stop
        self.period, self.max_age = 1 / rate_hz, max_age
        self.threshold, self.target_class = threshold, target_class
        self._last_sent_sequence = None
        if loss_policy not in ('legacy_silent', 'stop'):
            raise ValueError('unknown loss policy')
        self.loss_policy = loss_policy

    def _write(self, coordinate):
        packet = encode_coordinate(coordinate)
        if self.port.write(packet) != len(packet):
            raise IOError('partial serial write')

    def send_once(self, now=None):
        now = time.monotonic() if now is None else now
        _, result = self.results.read()
        coordinate = INVALID_COORDINATE if result is None else select_coordinate(
            result.detections, result.width, result.captured_at, now,
            self.max_age if self.loss_policy == 'stop' else float('inf'),
            self.threshold, self.target_class)
        # 默认沿用原 K230 行为：未检测到目标时静默；stop 模式才发送无效坐标。
        if coordinate == INVALID_COORDINATE and self.loss_policy == 'legacy_silent':
            return None
        # MCU 每收到一帧就更新 PID 与到位计数，因此同一推理结果不能重复发送。
        if coordinate != INVALID_COORDINATE and result.sequence == self._last_sent_sequence:
            return None
        self._write(coordinate)
        if result is not None:
            self._last_sent_sequence = result.sequence
        return coordinate

    def run(self):
        version = -1
        try:
            while not self.stop.is_set():
                # 推理完成立即唤醒；rate_hz 仅用于无新结果时轮询，不限制有效帧发送率。
                version, _ = self.results.wait_after(version, timeout=self.period)
                if not self.stop.is_set():
                    self.send_once()
        finally:
            # Best effort on software shutdown, never reported as hardware protection.
            if self.loss_policy == 'stop':
                try:
                    self._write(INVALID_COORDINATE)
                except Exception:
                    LOG.exception('Could not send final invalid coordinate')
