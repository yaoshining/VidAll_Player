#!/usr/bin/env bash
set -euo pipefail

input=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --input) input="$2"; shift 2 ;;
    *) echo '用法：validate-evidence.sh --input <evidence.json>' >&2; exit 2 ;;
  esac
done
[ -f "$input" ] || { echo '证据校验失败：缺少输入文件' >&2; exit 2; }

python3 - "$input" <<'PY'
import json
import sys

with open(sys.argv[1], encoding='utf-8') as handle:
    data = json.load(handle)
if data.get('schemaVersion') != 1:
    raise SystemExit('证据校验失败：schemaVersion 必须为 1')
if data.get('status') not in {'blocked', 'passed', 'failed'}:
    raise SystemExit('证据校验失败：status 必须为 blocked、passed 或 failed')
matrix = data.get('matrix')
if matrix is not None:
    allowed = {'已构建待验证', '不支持或暂缓', '已通过真机样本'}
    if not isinstance(matrix, dict) or not matrix:
        raise SystemExit('证据校验失败：matrix 必须为非空对象')
    for name, entry in matrix.items():
        if not isinstance(entry, dict) or entry.get('status') not in allowed:
            raise SystemExit(f'证据校验失败：{name} status 必须为三态结论')
        if not entry.get('knownLimitations'):
            raise SystemExit(f'证据校验失败：{name} 缺少 knownLimitations')
        verified = entry['status'] == '已通过真机样本'
        if verified and not all(entry.get(field) for field in ('device', 'sample', 'evidenceRef')):
            raise SystemExit(f'证据校验失败：{name} 真机通过缺少设备、样本或证据引用')
        if not verified and any(entry.get(field) for field in ('device', 'sample', 'evidenceRef')):
            raise SystemExit(f'证据校验失败：{name} 未验证时不得填写设备、样本或证据引用')
if data.get('status') == 'passed':
    for field in data.get('requiredEvidence', []):
        if not data.get(field):
            raise SystemExit(f'证据校验失败：通过状态缺少 {field}')
    if not data.get('recordedAt'):
        raise SystemExit('证据校验失败：通过状态缺少 recordedAt')
print(f'证据校验通过：{sys.argv[1]}（{data["status"]}）')
PY
