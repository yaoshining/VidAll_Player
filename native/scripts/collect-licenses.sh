#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo '用法：collect-licenses.sh --lock <sources.lock.json> --output <NOTICE 文件>' >&2
  exit 2
}

lock_file=''
output_file=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --lock) lock_file="$2"; shift 2 ;;
    --output) output_file="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -f "$lock_file" ] && [ -n "$output_file" ] || usage
mkdir -p "$(dirname "$output_file")"

python3 - "$lock_file" "$output_file" <<'PY'
import json
import pathlib
import sys
lock = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
lines = [
    'VidAll_Player libmpv 第三方组件 NOTICE',
    '',
    '此文件记录受控构建来源、许可证标识和对应源码定位。发布包必须同时提供每个上游项目的完整许可证文本与适用的源码获取方式。',
    '',
]
for name, source in lock['sources'].items():
    lines.extend([
        name,
        '  许可证：' + source['license'],
        '  来源：' + source['repository'],
        '  提交：' + source['commit'],
        '',
    ])
pathlib.Path(sys.argv[2]).write_text('\n'.join(lines), encoding='utf-8')
PY
