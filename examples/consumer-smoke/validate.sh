#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
candidate_har="${CANDIDATE_HAR:-$root/candidate/vidall-player.har}"

[ -f "$root/oh-package.json5" ] || { echo '错误: oh-package.json5 不存在' >&2; exit 1; }
[ -f "$root/entry/oh-package.json5" ] || { echo '错误: entry/oh-package.json5 不存在' >&2; exit 1; }
[ -f "$candidate_har" ] || { echo "错误: 必须提供候选 HAR: $candidate_har" >&2; exit 1; }

# Consumer must not reach into SDK source or private implementation through source or package inputs.
if rg -n "(@vidall/player/(src|native|internal|xcomponent)|requireNativeModule|VidAll_TV|from[[:space:]]+['\"][^'\"]*(native|internal))" "$root/entry/src" "$root/test"; then
  echo '错误: consumer-smoke 包含私有 SDK 导入或 NAPI 访问' >&2
  exit 1
fi
if rg -n 'file:.*packages/vidall-player' "$root/oh-package.json5" "$root/package.json5" "$root/entry/oh-package.json5" "$root/test/oh-package.json5"; then
  echo '错误: consumer-smoke 不能依赖仓库 SDK 源码' >&2
  exit 1
fi

for manifest_and_path in \
  "$root/package.json5:file:./candidate/vidall-player.har" \
  "$root/oh-package.json5:file:./candidate/vidall-player.har" \
  "$root/entry/oh-package.json5:file:../candidate/vidall-player.har" \
  "$root/test/oh-package.json5:file:../candidate/vidall-player.har"; do
  manifest="${manifest_and_path%%:*}"
  expected="${manifest_and_path#*:}"
  if ! python3 - "$manifest" "$expected" <<'PY'
import json
import pathlib
import sys

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
if manifest.get('dependencies', {}).get('@vidall/player') != sys.argv[2]:
    raise SystemExit(1)
PY
  then
    echo "错误: manifest 必须精确引用候选 HAR: $manifest" >&2
    exit 1
  fi
done

python3 - "$candidate_har" <<'PY'
import pathlib
import sys
import zipfile
path = pathlib.Path(sys.argv[1])
if path.stat().st_size == 0 or not zipfile.is_zipfile(path):
    raise SystemExit('错误: 候选 HAR 不是有效归档')
PY

echo '验证通过：consumer-smoke 仅使用候选 HAR 的公开 API。'
