#!/usr/bin/env python3
"""统一执行音频验收工具的宿主回归，独立于生产94项门禁。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
TESTS = ['anchor.test.cjs', 'test_time_anchor.py', 'test_prepare_anchor.py', 'test_sync.py', 'test_prepare_sync.py', 'test_analyze.py', 'test_prepare.py', 'test_receive.py', 'chunks.test.cjs', 'manual.test.cjs', 'capture.test.cjs', 'page.test.cjs', 'baseline.test.cjs', 'seek.test.cjs', 'focus.test.cjs', 'alarm.test.cjs', 'evidence.test.cjs']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    locked = ROOT / 'scripts/test/normal-core/node_modules/typescript'
    if 'TYPESCRIPT_PATH' not in env and locked.is_dir():env['TYPESCRIPT_PATH'] = str(locked)
    results = []
    for name in TESTS:
        command = [sys.executable, '-B'] if name.endswith('.py') else ['node']
        command.append(str(Path(__file__).parent / name))
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
            code, log = result.returncode, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            code, log = 124, '测试超过60秒，不计为通过\n'
        (args.out / (name + '.log')).write_text(log)
        results.append({'test':name, 'exitCode':code})
        print(('PASS ' if code == 0 else 'FAIL ') + name, flush=True)
    passed = all(item['exitCode'] == 0 for item in results)
    (args.out / 'summary.json').write_text(json.dumps({'passed':passed, 'deviceAccepted':False, 'tests':results}, ensure_ascii=False, indent=2) + '\n')
    return 0 if passed else 1

if __name__ == '__main__':sys.exit(main())
