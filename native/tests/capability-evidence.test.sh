#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly VALIDATOR="$PROJECT_ROOT/native/scripts/validate-capability-evidence.sh"
readonly TEMPLATE="$PROJECT_ROOT/release/capabilities/arm64-tv-capability-evidence.json"

fail() {
  echo "测试失败：$*" >&2
  exit 1
}

assert_rejected() {
  local case_name="$1"
  local expected_message="$2"
  local output="$temp_dir/$case_name.json"
  python3 - "$TEMPLATE" "$output" "$case_name" <<'PYTHON'
import json
import sys
source, output, case_name = sys.argv[1:]
data = json.load(open(source, encoding='utf-8'))
row = data['performance']['firstFrame']
if case_name == 'invalid-status':
    row['status'] = '已支持'
elif case_name == 'non-anonymous-sample':
    row.update({
        'status': '已通过真机样本',
        'device': 'ARM64-TV-anonymous',
        'sampleId': 'customer-recording-42',
        'executedAt': '2026-07-26T00:00:00Z',
        'metrics': {'firstFrameMs': 100},
        'evidenceFile': 'release/capabilities/evidence/missing-evidence.json',
    })
elif case_name == 'unverified-metrics':
    row['metrics'] = {'firstFrameMs': 100}
elif case_name == 'missing-evidence':
    row.update({
        'status': '已通过真机样本',
        'device': 'ARM64-TV-anonymous',
        'sampleId': 'ARM64-TV-SAMPLE-anonymous',
        'executedAt': '2026-07-26T00:00:00Z',
        'metrics': {'firstFrameMs': 100},
        'evidenceFile': 'release/capabilities/evidence/missing-evidence.json',
    })
else:
    raise SystemExit(f'unknown case: {case_name}')
json.dump(data, open(output, 'w', encoding='utf-8'), ensure_ascii=False)
PYTHON
  if "$VALIDATOR" --input "$output" >"$temp_dir/$case_name.log" 2>&1; then
    fail "校验器必须拒绝 $case_name"
  fi
  grep -Fq "$expected_message" "$temp_dir/$case_name.log" || fail "$case_name 未报告预期错误"
}

test -x "$VALIDATOR" || fail '缺少能力证据校验脚本'
test -f "$TEMPLATE" || fail '缺少 ARM64 TV 能力证据模板'
"$VALIDATOR" --input "$TEMPLATE"

temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
assert_rejected 'invalid-status' 'status 必须为三态结论'
assert_rejected 'non-anonymous-sample' 'sampleId 必须为匿名样本标识'
assert_rejected 'unverified-metrics' '未经真机验证时不得填写设备、样本、指标或证据'
assert_rejected 'missing-evidence' 'evidenceFile 必须引用已提交的能力证据文件'
