#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo '用法：validate-capability-evidence.sh --input <arm64-tv-capability-evidence.json>' >&2
  exit 2
}

input=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --input) input="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -f "$input" ] || usage

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 - "$input" "$project_root" <<'PY'
import json
import os
import re
import sys

path, project_root = sys.argv[1:]
with open(path, encoding='utf-8') as handle:
    data = json.load(handle)

states = {'已通过真机样本', '已构建待验证', '不支持或暂缓'}
required_capabilities = {
    'containersVideo', 'audio', 'subtitles', 'network', 'hdrColor', 'ijkCompatibility'
}
required_performance = {
    'firstFrame', 'seek', 'bufferRecovery', 'resourceUsage', 'longPlayback'
}

def fail(message):
    raise SystemExit(f'能力证据校验失败：{message}')

def validate_row(row, location):
    if not isinstance(row, dict):
        fail(f'{location} 必须是对象')
    status = row.get('status')
    if status not in states:
        fail(f'{location} 的 status 必须为三态结论')
    if not row.get('knownLimitations'):
        fail(f'{location} 缺少 knownLimitations')
    if status == '已通过真机样本':
        for field in ('device', 'sampleId', 'executedAt', 'evidenceFile', 'metrics'):
            if not row.get(field):
                fail(f'{location} 标为真机通过时缺少 {field}')
        if not re.fullmatch(r'ARM64-TV-[A-Za-z0-9_-]+', row['device']):
            fail(f'{location} 的 device 必须为匿名 ARM64 TV 标识')
        if not re.fullmatch(r'ARM64-TV-SAMPLE-[A-Za-z0-9_-]+', row['sampleId']):
            fail(f'{location} 的 sampleId 必须为匿名样本标识')
        evidence_file = row['evidenceFile']
        if not isinstance(evidence_file, str) or not re.fullmatch(r'release/capabilities/evidence/[A-Za-z0-9][A-Za-z0-9._/-]*', evidence_file):
            fail(f'{location} 的 evidenceFile 必须位于 release/capabilities/evidence/')
        evidence_path = os.path.realpath(os.path.join(project_root, evidence_file))
        evidence_root = os.path.realpath(os.path.join(project_root, 'release/capabilities/evidence'))
        if not evidence_path.startswith(evidence_root + os.sep) or not os.path.isfile(evidence_path):
            fail(f'{location} 的 evidenceFile 必须引用已提交的能力证据文件')
    elif any(row.get(field) for field in ('device', 'sampleId', 'executedAt', 'evidenceFile', 'metrics')):
        fail(f'{location} 未经真机验证时不得填写设备、样本、指标或证据')

if data.get('schemaVersion') != 1:
    fail('schemaVersion 必须为 1')
metadata = data.get('metadata')
if not isinstance(metadata, dict):
    fail('缺少 metadata')
for field in ('sdkVersion', 'sourceCommit', 'lockDigest', 'targetAbi', 'apiCompatibility'):
    if not metadata.get(field):
        fail(f'metadata 缺少 {field}')
if metadata['targetAbi'] != 'aarch64-linux-ohos':
    fail('targetAbi 必须为 aarch64-linux-ohos')
if sorted(metadata['apiCompatibility']) != [15, 19, 22]:
    fail('apiCompatibility 必须记录 API 15、19、22')

performance = data.get('performance')
if not isinstance(performance, dict) or set(performance) != required_performance:
    fail('performance 必须完整覆盖首帧、跳转、缓冲恢复、资源占用和长播')
for name, row in performance.items():
    validate_row(row, f'performance.{name}')
    if not row.get('threshold'):
        fail(f'performance.{name} 缺少 threshold')

capabilities = data.get('capabilities')
if not isinstance(capabilities, dict) or set(capabilities) != required_capabilities:
    fail('capabilities 必须完整覆盖六类能力矩阵')
for group, rows in capabilities.items():
    if not isinstance(rows, list) or not rows:
        fail(f'capabilities.{group} 必须包含至少一行')
    for index, row in enumerate(rows):
        validate_row(row, f'capabilities.{group}[{index}]')
        if not row.get('feature'):
            fail(f'capabilities.{group}[{index}] 缺少 feature')

print(f'能力证据校验通过：{path}')
PY
