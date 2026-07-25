#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo '用法：audit-licenses.sh --lock <sources.lock.json> --output <文件>' >&2
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
review = []
for name, source in lock['sources'].items():
    license_id = source['license']
    if license_id.startswith(('GPL-', 'LGPL-')):
        review.append({
            'component': name,
            'license': license_id,
            'reason': '该组件可能改变发布制品的再许可与提供对应源码义务；发布前须由法务确认实际链接方式、启用编解码器及 NOTICE。',
        })
report = {
    'schemaVersion': 1,
    'status': 'review-required' if review else 'passed',
    'policy': '静态或动态组合均不得绕过许可证义务；不得仅依赖预编译第三方 release。',
    'reviewRequired': review,
}
pathlib.Path(sys.argv[2]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
