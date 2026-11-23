"""Wire contract shared with the existing MSPM0 coord_receiver.c."""

INVALID_COORDINATE = 0xFFFF
COORDINATE_WIDTH = 800


def encode_coordinate(x):
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError('coordinate must be an integer')
    if not 0 <= x <= 0xFFFF:
        raise ValueError('coordinate must fit in uint16')
    high, low = x >> 8, x & 255
    return bytes((0xAA, 0x55, high, low, (high + low) & 255, 0x55, 0xFF))


class CoordinateParser:
    """Host diagnostic decoder; firmware parser remains the C implementation."""

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        result = []
        while True:
            start = self.buffer.find(b'\xaa\x55')
            if start < 0:
                self.buffer[:] = b'\xaa' if self.buffer.endswith(b'\xaa') else b''
                break
            del self.buffer[:start]
            if len(self.buffer) < 7:
                break
            frame = self.buffer[:7]
            if frame[5:] == b'\x55\xff' and frame[4] == (frame[2] + frame[3]) & 255:
                result.append(frame[2] << 8 | frame[3])
                del self.buffer[:7]
            else:
                del self.buffer[0]
        return result

