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

test -x "$VALIDATOR" || fail '缺少能力证据校验脚本'
test -f "$TEMPLATE" || fail '缺少 ARM64 TV 能力证据模板'
"$VALIDATOR" --input "$TEMPLATE"

temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
python3 - "$TEMPLATE" "$temp_dir/invalid.json" <<'PY'
import json
import sys
source, output = sys.argv[1:]
data = json.load(open(source, encoding='utf-8'))
data['performance']['firstFrame']['status'] = '已支持'
json.dump(data, open(output, 'w', encoding='utf-8'), ensure_ascii=False)
PY
if "$VALIDATOR" --input "$temp_dir/invalid.json"; then
  fail '校验器必须拒绝非三态结论'
fi
