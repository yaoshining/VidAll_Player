#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
temp="$(mktemp -d)"
trap 'rm -rf "$temp"' EXIT
cp -R "$root" "$temp/consumer"
: > "$temp/candidate.har"
if CANDIDATE_HAR="$temp/candidate.har" "$temp/consumer/validate.sh" >/dev/null 2>&1; then
  echo '空候选 HAR 必须失败' >&2; exit 1
fi
printf 'candidate' > "$temp/candidate.har"
if CANDIDATE_HAR="$temp/candidate.har" "$temp/consumer/validate.sh" >/dev/null 2>&1; then
  echo '无效候选 HAR 必须失败' >&2; exit 1
fi
python3 - "$temp/candidate.har" <<'PY2'
import sys
import zipfile
with zipfile.ZipFile(sys.argv[1], 'w') as archive:
    archive.writestr('oh-package.json5', '{}')
PY2
CANDIDATE_HAR="$temp/candidate.har" "$temp/consumer/validate.sh" >/dev/null
printf "import x from '@vidall/player/internal/x';\n" > "$temp/consumer/entry/src/main/ets/Forbidden.ets"
if CANDIDATE_HAR="$temp/candidate.har" "$temp/consumer/validate.sh" >/dev/null 2>&1; then
  echo '私有 SDK 导入必须失败' >&2; exit 1
fi
rm "$temp/consumer/entry/src/main/ets/Forbidden.ets"
python3 - "$temp/consumer/entry/oh-package.json5" <<'PY2'
import json
import sys
path = sys.argv[1]
data = json.load(open(path))
data['dependencies']['@vidall/player'] = '@vidall/player@1.0.0'
open(path, 'w').write(json.dumps(data))
PY2
if CANDIDATE_HAR="$temp/candidate.har" "$temp/consumer/validate.sh" >/dev/null 2>&1; then
  echo 'entry 模块的 registry SDK 依赖必须失败' >&2; exit 1
fi
python3 - "$temp/consumer/entry/oh-package.json5" <<'PY2'
import json
import sys
path = sys.argv[1]
data = json.load(open(path))
data['dependencies']['@vidall/player'] = 'file:../candidate/vidall-player.har'
open(path, 'w').write(json.dumps(data))
PY2
python3 - "$temp/consumer/test/oh-package.json5" <<'PY2'
import json
import sys
path = sys.argv[1]
data = json.load(open(path))
data['dependencies']['@vidall/player'] = 'file:../../../packages/vidall-player'
open(path, 'w').write(json.dumps(data))
PY2
if CANDIDATE_HAR="$temp/candidate.har" "$temp/consumer/validate.sh" >/dev/null 2>&1; then
  echo '测试模块的源码 SDK 依赖必须失败' >&2; exit 1
fi
