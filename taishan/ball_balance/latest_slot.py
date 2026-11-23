"""线程间的最新值交换：仅保存一帧，避免慢消费者积压旧图像。"""
import threading

class LatestSlot:
    """A bounded one-item exchange, never a growing video queue."""

    def __init__(self):
        self._condition = threading.Condition()
        self._version = 0
        self._value = None

    def publish(self, value):
        with self._condition:
            self._version += 1
            self._value = value
            self._condition.notify_all()
            return self._version

    def read(self):
        with self._condition:
            return self._version, self._value

    def wait_after(self, version, timeout=0.1):
        with self._condition:
            self._condition.wait_for(lambda: self._version != version, timeout)
            return self._version, self._value
