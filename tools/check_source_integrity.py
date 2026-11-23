"""Check that the preserved MCU source still matches the migration baseline."""
from pathlib import Path
import hashlib
import json


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'docs/mspm0-source-sha256.json').read_text(encoding='utf-8'))
    errors = []
    for name, expected in manifest.items():
        if name == "main.c":  # 主函数已拆分，控制等价性由 test_modular 验证。
            continue
        path = root / 'mspm0' / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(name)
    if errors:
        raise SystemExit('Modified or missing original MCU files: ' + ', '.join(errors))
    print(f'MCU baseline verified: {len(manifest) - 1} files')


if __name__ == '__main__':
    main()
