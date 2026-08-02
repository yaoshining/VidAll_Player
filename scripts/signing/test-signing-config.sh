#!/usr/bin/env bash
set -euo pipefail

readonly PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly VALIDATOR="$PROJECT_ROOT/scripts/signing/validate-signing-config.py"
readonly CONFIG="$PROJECT_ROOT/build-profile.json5"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

python3 "$VALIDATOR" "$CONFIG"

# 开发签名密码必须保留 DevEco Studio 生成的密文，才能在本机构建并安装。
python3 - "$CONFIG" <<'PY'
import json
import re
import sys
import pathlib
source = re.sub(r",\s*([}\]])", r"\1", open(sys.argv[1], encoding="utf-8").read())
config = json.loads(source)
material = next(item["material"] for item in config["app"]["signingConfigs"] if item["name"] == "development")
assert material["keyPassword"]
assert material["storePassword"]
assert (pathlib.Path(sys.argv[1]).parent / "signing/development/material").is_dir()
PY

# CI 暂时使用开发环境的等价签名材料，密码必须可供受控环境直接构建。
python3 - "$CONFIG" <<'PY'
import json
import pathlib
import re
import sys
source = re.sub(r",\s*([}\]])", r"\1", pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
config = json.loads(source)
materials = {item["name"]: item["material"] for item in config["app"]["signingConfigs"]}
assert set(materials) == {"development", "ci"}
assert materials["ci"]["keyPassword"]
assert materials["ci"]["storePassword"]
assert (pathlib.Path(sys.argv[1]).parent / "signing/ci/material").is_dir()
PY

# default product 代表开发环境，必须映射至 development 签名。
python3 - "$CONFIG" "$tmp_dir/default-mapping.json5" <<'PY'
import pathlib
import sys
source = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
pathlib.Path(sys.argv[2]).write_text(source.replace('"signingConfig": "development",', '"signingConfig": "default",', 1), encoding='utf-8')
PY
if python3 "$VALIDATOR" "$tmp_dir/default-mapping.json5"; then
  echo '测试失败：default product 未映射到 development 签名时不应通过' >&2
  exit 1
fi

# CI 签名材料必须位于独立目录，不能直接指向开发目录。
python3 - "$CONFIG" "$tmp_dir/shared-development-material.json5" <<'PY'
import pathlib
import sys
source = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
pathlib.Path(sys.argv[2]).write_text(source.replace('signing/ci/app.cer', 'signing/development/app.cer', 1), encoding='utf-8')
PY
if python3 "$VALIDATOR" "$tmp_dir/shared-development-material.json5"; then
  echo '测试失败：CI 未使用独立签名材料目录时不应通过' >&2
  exit 1
fi

echo '签名环境配置测试通过'

# CI 必须选择 ci product；当前暂时使用与开发环境等价的独立材料副本。
workflow="$PROJECT_ROOT/.github/workflows/test-player.yml"
for expected in \
  'devecocli build --product ci --modules entry@ohosTest'; do
  if ! grep -Fq "$expected" "$workflow"; then
    echo "测试失败：CI 工作流缺少 $expected" >&2
    exit 1
  fi
done

# 签名脚本或说明变更必须触发 CI，避免仅靠人工发现配置回归。
for expected in "'scripts/signing/**'" "'signing/README.md'"; do
  if ! grep -Fq "$expected" "$workflow"; then
    echo "测试失败：CI 触发路径缺少 $expected" >&2
    exit 1
  fi
done
