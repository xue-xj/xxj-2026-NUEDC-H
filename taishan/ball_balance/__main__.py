"""命令行入口：解析配置、预检查并启动应用。"""
import argparse
import logging
import sys
from .config import load_config
from .detector import require_model
from .application import run
from .diagnostics import check

LOG = logging.getLogger("ball_balance")

def main(argv=None):
    parser = argparse.ArgumentParser(description='RK3566 Linux vision + RTSP + MSPM0 coordinate bridge')
    parser.add_argument('--config', default='config.example.json', help='JSON configuration path')
    parser.add_argument('--preview-only', action='store_true', help='camera/RTSP only, never opens control UART')
    parser.add_argument('--check', action='store_true', help='check files/dependencies without opening camera/UART/NPU')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    try:
        config = load_config(args.config)
        if args.check:
            return check(config, args.preview_only)
        if not args.preview_only:
            require_model(config['model']['path'])
        run(config, args.preview_only)
        return 0
    except Exception as error:
        LOG.error('%s', error)
        return 1


if __name__ == '__main__':
    sys.exit(main())
