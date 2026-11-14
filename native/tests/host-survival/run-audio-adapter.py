#!/usr/bin/env python3
"""S37实验适配器：独立进程隔离永久挂起场景，不把替身当设备验收。"""
import argparse, json, pathlib, subprocess, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[3]
CASES = ['normal', 'focus', 'pending-pause', 'unknown-stop', 'flush-error', 'release-hang', 'formats', 'clock', 'pause-clock', 'release-hang-formats', 'async-reset', 'reset-focus', 'reset-detach', 'all-slots-held']
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=pathlib.Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='vidall-audio-adapter-') as tmp:
        binary = str(pathlib.Path(tmp) / 'test')
        subprocess.run(['clang', '-std=gnu11', '-pthread', '-Wall', '-Wextra', '-Werror',
            '-fsanitize=address,undefined', str(ROOT / 'native/tests/host-survival/audio-adapter.test.c'),
            str(ROOT / 'native/experimental/audio_output_adapter.c'), '-o', binary], check=True)
        results = []
        for case in CASES:
            run = subprocess.run([binary, case], timeout=15, capture_output=True, text=True)
            results.append(dict(case=case, exit=run.returncode, output=run.stdout + run.stderr))
        args.out.write_text(json.dumps(dict(layer='host-platform-fake', cases=results), ensure_ascii=False, indent=2) + '\n')
        if any(row['exit'] for row in results):
            raise SystemExit(1)
if __name__ == '__main__': main()
