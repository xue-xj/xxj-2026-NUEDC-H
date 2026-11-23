"""Optional PC conversion entry point, not an absent-model substitute.

Requires a Rockchip-optimized YOLOv8 ONNX with 6/9 outputs and an RKNN-Toolkit2
version compatible with the board runtime/driver. The user's lost weights must
be recovered or retrained. Run with --help for usage.
"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Convert a compatible YOLOv8 ONNX to RK3566 RKNN')
    parser.add_argument('--onnx', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, help='real calibration image list; required for INT8')
    parser.add_argument('--float', action='store_true', help='disable INT8 quantization for comparison')
    args = parser.parse_args()
    if not args.onnx.is_file():
        parser.error('ONNX model does not exist')
    if not args.float and (not args.dataset or not args.dataset.is_file()):
        parser.error('INT8 requires a real calibration dataset list')
    if args.output.exists():
        parser.error('output exists; choose a new name to keep the previous model')
    from rknn.api import RKNN
    rknn = RKNN(verbose=True)
    try:
        rknn.config(target_platform='rk3566', mean_values=[[0, 0, 0]], std_values=[[255, 255, 255]])
        if rknn.load_onnx(model=str(args.onnx)) != 0:
            raise RuntimeError('load_onnx failed')
        if rknn.build(do_quantization=not args.float, dataset=str(args.dataset) if args.dataset else None) != 0:
            raise RuntimeError('build failed')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if rknn.export_rknn(str(args.output)) != 0:
            raise RuntimeError('export failed')
        print(f'Exported {args.output}; check preprocessing/output tensors before enabling control')
    finally:
        rknn.release()


if __name__ == '__main__':
    main()
