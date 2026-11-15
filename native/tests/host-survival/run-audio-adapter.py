#!/usr/bin/env python3
"""S37实验适配器：独立进程隔离永久挂起场景，不把替身当设备验收。"""
import argparse, json, pathlib, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[3]
CASES = ['normal', 'focus', 'pending-pause', 'unknown-stop', 'flush-error', 'release-hang', 'formats', 'clock', 'pause-clock', 'release-hang-formats', 'async-reset', 'reset-focus', 'reset-detach', 'all-slots-held']
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=pathlib.Path, required=True)
    args = parser.parse_args()
    subprocess.run([sys.executable, '-B', str(ROOT / 'native/tests/host-survival/audio-adapter-contention.test.py')], check=True)
    with tempfile.TemporaryDirectory(prefix='vidall-audio-adapter-') as tmp:
        binary = str(pathlib.Path(tmp) / 'test')
        subprocess.run(['clang', '-std=gnu11', '-pthread', '-Wall', '-Wextra', '-Werror',
            '-fsanitize=address,undefined', str(ROOT / 'native/tests/host-survival/audio-adapter.test.c'),
            str(ROOT / 'native/experimental/audio_output_adapter.c'), '-o', binary], check=True)
        results = []
        for case in CASES:
            timed_out = False
            try:
                run = subprocess.run([binary, case], timeout=15, capture_output=True, text=True)
            except subprocess.TimeoutExpired as error:
                # 即使text=True，TimeoutExpired携带的输出也可能仍为bytes。
                def decode(value):
                    return value.decode(errors='replace') if isinstance(value, bytes) else (value or '')
                timed_out = True
                run = subprocess.CompletedProcess([binary, case], 124, decode(error.stdout),
                                                   decode(error.stderr) + '\nTIMEOUT after 15 seconds\n')
            results.append(dict(case=case, exit=run.returncode, output=run.stdout + run.stderr, timedOut=timed_out))
            print(f'{case}: {"FAIL" if run.returncode else "PASS"} (exit={run.returncode})', flush=True)
            if run.returncode:
                print(run.stdout + run.stderr, flush=True)
        args.out.write_text(json.dumps(dict(layer='host-platform-fake', cases=results), ensure_ascii=False, indent=2) + '\n')
        if any(row['exit'] for row in results):
            raise SystemExit(1)
if __name__ == '__main__': main()
