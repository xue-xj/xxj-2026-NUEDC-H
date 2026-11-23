"""Strict, explicit configuration; model paths are relative to this file."""
import json
import math
from pathlib import Path


FIELDS = {
    'camera': {'device', 'width', 'height', 'fps'},
    'model': {'path', 'input_size', 'roi', 'confidence', 'nms', 'target_class', 'pad_value'},
    'serial': {'device', 'baudrate', 'rate_hz', 'max_age_s'},
    'rtsp': {'enabled', 'bind', 'port', 'mount', 'width', 'height', 'fps', 'bitrate_kbps', 'encoder'},
}


def _keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f'{name}: required keys are {sorted(expected)} (no extra keys)')


def _number(value, lower, upper, name, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not lower <= value <= upper
            or (integer and not isinstance(value, int))):
        raise ValueError(f'{name}: expected {"integer" if integer else "number"} in [{lower}, {upper}]')


def _camera(camera, name):
    _keys(camera, FIELDS['camera'], name)
    device = camera['device']
    if isinstance(device, bool) or not isinstance(device, (int, str)) or (isinstance(device, int) and device < 0) or device == '':
        raise ValueError(f'{name}.device must be a camera index or /dev/video path')
    for key in ('width', 'height'):
        _number(camera[key], 16, 4096, f'{name}.{key}', True)
    _number(camera['fps'], 1, 120, f'{name}.fps', True)


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    _keys(config, set(FIELDS) | {'stream_camera', 'display'}, 'config')
    for key in FIELDS:
        if key == 'serial':
            fields = set(config[key]) if isinstance(config[key], dict) else set()
            if fields not in (FIELDS[key], FIELDS[key] | {'loss_policy'}):
                raise ValueError('serial: unexpected or missing keys')
        else:
            _keys(config[key], FIELDS[key], key)
    _camera(config['camera'], 'camera')
    if config['stream_camera'] is not None:
        _camera(config['stream_camera'], 'stream_camera')
        if config['stream_camera']['device'] == config['camera']['device']:
            raise ValueError('use stream_camera=null to share one capture; do not open it twice')
    if not isinstance(config['display'], bool) or not isinstance(config['rtsp']['enabled'], bool):
        raise ValueError('display and rtsp.enabled must be boolean')
    model = config['model']
    if not isinstance(model['path'], str) or not model['path']:
        raise ValueError('model.path is required')
    model['path'] = str((path.parent / model['path']).resolve())
    size, roi = model['input_size'], model['roi']
    if not isinstance(size, list) or len(size) != 2:
        raise ValueError('input_size must be [width,height]')
    for value in size:
        _number(value, 32, 2048, 'input_size', True)
        if value % 32:
            raise ValueError('model input dimensions must be multiples of 32')
    if roi is not None:
        if not isinstance(roi, list) or len(roi) != 4:
            raise ValueError('roi must be null or [x,y,width,height]')
        for value in roi:
            _number(value, 0, 4096, 'roi', True)
        x, y, w, h = roi
        if w <= 0 or h <= 0 or x + w > config['camera']['width'] or y + h > config['camera']['height']:
            raise ValueError('roi is outside the configured camera frame')
    for key in ('confidence', 'nms'):
        _number(model[key], .01, 1, key)
    _number(model['target_class'], 0, 9999, 'target_class', True)
    _number(model['pad_value'], 0, 255, 'pad_value', True)
    serial = config['serial']
    serial.setdefault('loss_policy', 'legacy_silent')
    if serial['loss_policy'] not in ('legacy_silent', 'stop'):
        raise ValueError('loss_policy must be legacy_silent or stop')
    if not isinstance(serial['device'], str) or not serial['device']:
        raise ValueError('serial.device is required')
    _number(serial['baudrate'], 1200, 3000000, 'baudrate', True)
    _number(serial['rate_hz'], 1, 100, 'rate_hz')
    _number(serial['max_age_s'], .01, 10, 'max_age_s')
    rtsp = config['rtsp']
    for key, low, high in [('port', 1024, 65535), ('width', 16, 4096), ('height', 16, 4096),
                           ('fps', 1, 60), ('bitrate_kbps', 64, 20000)]:
        _number(rtsp[key], low, high, f'rtsp.{key}', True)
    # BGR appsrc uses tightly packed rows, while Gst raw video aligns stride to
    # 4 bytes. Width divisible by 4 makes both agree; I420 also needs even height.
    if rtsp['width'] % 4 or rtsp['height'] % 2:
        raise ValueError('RTSP width must be divisible by 4 and height must be even')
    if not isinstance(rtsp['bind'], str) or not rtsp['bind']:
        raise ValueError('rtsp.bind must be a nonempty address')
    if not isinstance(rtsp['mount'], str) or not rtsp['mount'].startswith('/') or any(c.isspace() for c in rtsp['mount']):
        raise ValueError('rtsp.mount must start with / and have no spaces')
    if rtsp['encoder'] not in ('x264enc', 'mpph264enc'):
        raise ValueError('encoder must be x264enc or mpph264enc')
    return config

