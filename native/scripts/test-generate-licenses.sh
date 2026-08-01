#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; script="$root/native/scripts/generate-licenses.sh"; temp="$(mktemp -d)"; trap 'rm -rf "$temp"' EXIT
cat > "$temp/lock.json" <<'JSON'
{"sources":{"ok":{"license":"MIT","repository":"https://example.test/ok","tag":"v1","commit":"1111111111111111111111111111111111111111"},"review":{"license":"GPL-2.0-or-later","repository":"https://example.test/review","tag":"v2","commit":"2222222222222222222222222222222222222222"}},"licensePolicy":{"releaseRequiresReview":["GPL-2.0-or-later"],"noticeRequired":true,"sourceOfferRequired":true}}
JSON
"$script" --lock "$temp/lock.json" --output "$temp/out.json" --notice "$temp/NOTICE"
python3 - "$temp/out.json" "$temp/NOTICE" <<'PY'
import json, pathlib, sys
assert json.load(open(sys.argv[1]))['complianceStatus'] == 'requires-review'
notice=pathlib.Path(sys.argv[2]).read_text(); assert '来源:' in notice and notice.endswith('\n') and '源码获取' in notice
PY
echo '许可证结论门禁测试通过。'
