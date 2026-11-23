"""兼容原导入路径；实际实现按数据、线程交换和坐标计算分别维护。"""
from .data_types import Detection
from .latest_slot import LatestSlot
from .geometry import Letterbox, select_coordinate
