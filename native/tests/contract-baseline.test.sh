#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fail() { echo "测试失败：$*" >&2; exit 1; }

# 根导出是唯一 SDK 消费边界；内部实现和原生术语不得由此暴露。
python3 - "$ROOT" <<'PY'
from pathlib import Path
import json
import sys
root = Path(sys.argv[1])
package = json.loads((root / 'packages/vidall-player/oh-package.json5').read_text())
assert package['name'] == '@vidall/player'
assert package['version'] == '0.1.0'
exports = (root / 'packages/vidall-player/Index.ets').read_text()
for symbol in ('createPlayer', 'VidAllPlayer', 'ExternalAudio', 'PlayerEventType', 'VideoParams', 'AudioParams', 'PlayerLog', 'ProxyLeaseStatus'):
    assert symbol in exports, f'缺少公开导出：{symbol}'
for forbidden in ('NativePlayerBridge', 'NativeWindow', 'EGL', 'GLES', 'libmpv', 'napi'):
    assert forbidden not in exports, f'泄露内部符号：{forbidden}'
contract = (root / 'packages/vidall-player/test/contract/public-api.test.ets').read_text()
assert "from '@vidall/player'" in contract
for forbidden in ('/src/internal/', '/src/native/', 'NativeWindow', 'EGL', 'libmpv', 'napi'):
    assert forbidden not in contract, f'契约测试引用受限符号：{forbidden}'
review = json.loads((root / 'native/config/api-review.json').read_text())
assert [review['installationCompatibilityApi'], review['sensitiveApiReviewLevel'], review['certificationTargetApi']] == [15, 19, 22]
assert review['candidateStatus'] == 'blocked-until-evidence'
spike = json.loads((root / 'release/audits/har-native-packaging-spike.json').read_text())
assert spike['status'] == 'blocked'
assert spike['realBridgeAllowed'] is False
PY

build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT
cmake -S "$ROOT/native/tests" -B "$build_dir" >/dev/null
cmake --build "$build_dir" >/dev/null
ctest --test-dir "$build_dir" --output-on-failure
"$ROOT/scripts/evidence/validate-evidence.sh" --input "$ROOT/release/audits/har-native-packaging-spike.json"
