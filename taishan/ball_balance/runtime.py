"""兼容原运行模块导入路径；各功能实现已拆分到独立模块。"""
from .data_types import Frame, InferenceResult
from .capture import capture_loop
from .inference import inference_loop
from .serial_link import SerialSender
