#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fail() { echo "测试失败：$*" >&2; exit 1; }

# 根导出是唯一 SDK 消费边界；内部实现和原生术语不得由此暴露。
python3 - "$ROOT" <<'PY'
from pathlib import Path
import json
import sys

# oh-package.json5 / build-profile.json5 等 HarmonyOS 配置使用 JSON5 语法，
# 允许 // 注释（独立行或行尾）与尾逗号。stdlib json 不识别这些语法，这里用
# 字符串感知的方式剔除 // 注释（保留字符串字面量内的 //，例如 URL 的
# https://...），再去掉 } ] 前的尾逗号。不沿用 signing 校验脚本的 //.*$ 正则，
# 因为它会把 URL 内的 // 截断（oh-package.json5 含 homepage/repository URL）。
def _strip_json5_comments(text: str) -> str:
    out = []
    in_str = False
    escaped = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
        elif ch == '"':
            in_str = True
            out.append(ch)
            i += 1
        elif ch == '/' and i + 1 < n and text[i + 1] == '/':
            while i < n and text[i] != '\n':
                i += 1
        else:
            out.append(ch)
            i += 1
    no_comments = ''.join(out)
    # 去尾逗号同样需要字符串感知：直接对整段文本做 re.sub(r',\s*([}\]])', ...)
    # 会误删字符串字面量内恰好形如 ",}" 的文本（例如 note 字段写 "foo ,}"），
    # 因此复用同样的逐字符扫描，只在字符串外部识别 `, <空白> } 或 ]` 才剔除逗号。
    result = []
    in_str = False
    escaped = False
    i, n = 0, len(no_comments)
    while i < n:
        ch = no_comments[i]
        if in_str:
            result.append(ch)
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            result.append(ch)
            i += 1
            continue
        if ch == ',':
            j = i + 1
            while j < n and no_comments[j] in ' \t\r\n':
                j += 1
            if j < n and no_comments[j] in '}]':
                i += 1
                continue
        result.append(ch)
        i += 1
    return ''.join(result)

def load_json5(path: Path):
    return json.loads(_strip_json5_comments(path.read_text(encoding='utf-8')))

# 回归：确认 _strip_json5_comments 覆盖独立注释、行尾注释、尾逗号，
# 且不破坏字符串字面量内的 //（如 URL）。
assert json.loads(_strip_json5_comments('// 独立注释\n{"a": 1}')) == {'a': 1}
assert json.loads(_strip_json5_comments('{"a": 1 // 行尾注释\n}')) == {'a': 1}
assert json.loads(_strip_json5_comments('{"b": 2,}')) == {'b': 2}
assert json.loads(_strip_json5_comments('{"url": "https://github.com/x"}')) == {'url': 'https://github.com/x'}
# 回归：去尾逗号必须字符串感知，不能破坏字符串字面量内恰好形如 ",}" / ",]" 的文本。
assert json.loads(_strip_json5_comments('{"note": "trailing text ,}"}')) == {'note': 'trailing text ,}'}
assert json.loads(_strip_json5_comments('{"note": "a ,] b", "c": 1,}')) == {'note': 'a ,] b', 'c': 1}

root = Path(sys.argv[1])
package = load_json5(root / 'packages/vidall-player/oh-package.json5')
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
assert spike['status'] == 'passed'
assert spike['realBridgeAllowed'] is False
tdd = json.loads((root / 'release/audits/tdd-baseline.json').read_text())
assert tdd['status'] == 'recorded'
assert tdd['t008']['redPhase']['result'] == 'failed-as-expected'
assert tdd['t008']['greenPhase']['result'] == 'passed'
assert tdd['t006']['realBridgeAllowed'] is False
PY

build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT
cmake -S "$ROOT/native/tests" -B "$build_dir" >/dev/null
cmake --build "$build_dir" >/dev/null
ctest --test-dir "$build_dir" --output-on-failure
"$ROOT/scripts/evidence/validate-evidence.sh" --input "$ROOT/release/audits/har-native-packaging-spike.json"
