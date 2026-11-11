#!/usr/bin/env python3
"""只在三个真实工具均为可执行 LLVM 18 时选择预装目录；失败不改 GITHUB_PATH。"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def select(directory: Path, github_path: Path) -> dict:
    directory = directory.resolve(strict=True)
    if not directory.is_dir() or any(char in str(directory) for char in '\r\n'):
        raise ValueError('LLVM 目录无效')
    records = []
    for name in ('clang', 'clang++', 'llvm-nm'):
        command = directory / name
        if not command.is_file() or not os.access(command, os.X_OK):
            raise ValueError(name + ' 缺失或不可执行')
        result = subprocess.run([str(command), '--version'], capture_output=True, text=True,
                                errors='replace', timeout=10)
        if result.returncode != 0:
            raise ValueError(name + ' --version 失败：' + str(result.returncode))
        version = (result.stdout + '\n' + result.stderr).strip()
        label = 'LLVM' if name == 'llvm-nm' else 'clang'
        matches = re.findall(r'^\s*(?:(?:Ubuntu|Debian) )?' + label + r' version ([0-9]+)\.[0-9]+',
                             version, flags=re.MULTILINE)
        if not matches or any(int(value) != 18 for value in matches):
            raise ValueError(name + ' 必须明确报告 LLVM 主版本 18')
        records.append({'tool': name, 'realPath': str(command.resolve(strict=True)), 'version': version})
    # 所有检查结束后才追加一次，不能因最后一个工具失败而遗留部分 PATH。
    with github_path.open('a', encoding='utf-8') as output:
        output.write(str(directory) + '\n')
    return {'selected': True, 'major': 18, 'directory': str(directory), 'tools': records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool-dir', type=Path, default=Path('/usr/lib/llvm-18/bin'))
    args = parser.parse_args()
    github_path = os.environ.get('GITHUB_PATH')
    if not github_path:
        raise ValueError('缺少 GITHUB_PATH')
    print(json.dumps(select(args.tool_dir, Path(github_path)), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('预装 LLVM 18 选择失败：' + str(error), file=sys.stderr)
        raise SystemExit(1)
