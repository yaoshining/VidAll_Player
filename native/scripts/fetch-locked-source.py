#!/usr/bin/env python3
"""有界重试浅获取固定 Git 提交；超时终止整个 Git 子进程组。"""
import argparse
import os
from pathlib import Path
import re
import signal
import subprocess
import time


def run(command, timeout):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, command)
    return output.strip()


def fetch(repository, commit, destination, timeout=300, attempts=3):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('源码必须固定为 40 位 commit，不能使用分支或 tag')
    if timeout <= 0 or attempts < 1:
        raise ValueError('超时和尝试次数必须为正数')
    destination.mkdir(parents=True, exist_ok=True)
    run(['git', 'init', str(destination)], timeout=30)
    git = ['git', '-C', str(destination)]
    for attempt in range(1, attempts + 1):
        print(f'浅获取锁定源码 {commit}：{attempt}/{attempts}，单次限时 {timeout}s', flush=True)
        try:
            run(git + ['-c', 'http.lowSpeedLimit=1024', '-c', 'http.lowSpeedTime=30',
                       'fetch', '--progress', '--no-tags', '--depth=1', repository, commit], timeout=timeout)
            break
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)
    actual = run(git + ['rev-parse', 'FETCH_HEAD'], timeout=30)
    if actual != commit:
        raise ValueError(f'源码提交不匹配：期望 {commit}，实际 {actual}')
    run(git + ['checkout', '--detach', commit], timeout=30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--attempts', type=int, default=3)
    args = parser.parse_args()
    fetch(args.repository, args.commit, args.destination, args.timeout, args.attempts)
