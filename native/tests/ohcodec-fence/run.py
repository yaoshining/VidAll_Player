"""在非 Vulkan 宿主上编译所选 mpv 源树的释放函数，验证句柄和缓冲区所有权。"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
CASES = ('drain-ok', 'release-error', 'hold-error', 'signal-error', 'wait-error',
         'history-error', 'frame-ok', 'frame-hold-error', 'frame-signal-error')


def definition(source, name):
    pattern = rf'^static (?:void|int) {name}\([^;{{]+\)\s*\{{.*?^\}}'
    match = re.search(pattern, source, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f'缺少生产函数 {name}')
    return match.group()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mpv', type=Path)
    parser.add_argument('--case', choices=CASES, action='append')
    args = parser.parse_args()
    source = (args.mpv / 'video/out/hwdec/hwdec_ohcodec_pl.c').read_text()
    functions = '\n'.join(definition(source, fn) for fn in ('mapper_release', 'ohcodec_drain'))
    template = (HERE / 'harness.c').read_text()
    failed = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / 'test.c').write_text(template.replace('/* PRODUCTION */', functions))
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Werror',
                        str(root / 'test.c'), '-o', str(root / 'test')], check=True)
        for case in args.case or CASES:
            result = subprocess.run([str(root / 'test'), case], timeout=5)
            if result.returncode:
                failed.append(case)
            print(case, 'FAIL' if result.returncode else 'PASS', flush=True)
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
