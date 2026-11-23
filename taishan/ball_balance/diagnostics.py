"""启动前依赖检查：不打开摄像头、控制串口或 NPU。"""
import importlib.util
import threading
from .latest_slot import LatestSlot
from .detector import require_model

def check(config, preview_only):
    missing = []
    for module in ['numpy', 'cv2'] + ([] if preview_only else ['serial', 'rknnlite']):
        found = importlib.util.find_spec(module) is not None
        print(f'{module}: {"installed" if found else "MISSING"}')
        if not found:
            missing.append(module)
    if config['rtsp']['enabled']:
        try:
            from .rtsp import RtspServer
            server = RtspServer(config['rtsp'], LatestSlot(), threading.Event())
            server.close()
            print('RTSP GI and encoder plugins: available (port not opened)')
        except Exception as error:
            missing.append('RTSP')
            print(f'RTSP: {error}')
    if not preview_only:
        try:
            require_model(config['model']['path'])
            print('model: file exists (inference not verified)')
        except (ValueError, FileNotFoundError) as error:
            missing.append('model')
            print(error)
    print('Check only: camera/UART/NPU not opened. Physical mapping and tensor contract still need board validation.')
    return 1 if missing else 0
