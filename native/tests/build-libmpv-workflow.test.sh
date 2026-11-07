#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly WORKFLOW="$PROJECT_ROOT/.github/workflows/build-libmpv.yml"

fail() {
  echo "测试失败：$*" >&2
  exit 1
}

# cargo install 的普通版本要求会按 SemVer 漂移到同一兼容范围内的新版。
grep -Fq 'cargo install cargo-c --version "=$CARGO_C_VERSION"' "$WORKFLOW" || \
  fail 'cargo-c 必须使用精确版本要求安装'

grep -Fq 'CARGO_C_EXPECTED_VERSION: 0.10.13+cargo-0.88.0' "$WORKFLOW" || \
  fail '必须记录与 Rust 1.85.1 兼容的完整 cargo-c 版本'

grep -Fq 'test "$(cargo-cbuild --version)" = "cargo-c $CARGO_C_EXPECTED_VERSION"' "$WORKFLOW" || \
  fail '安装后必须验证 cargo-c 的完整版本'

grep -Fq 'os: [macos-15, ubuntu-22.04]' "$WORKFLOW" || \
  fail '元数据检查须同时覆盖可用的 macOS 与 Ubuntu 运行器'

expected_condition="(github.event_name != 'pull_request' || github.base_ref != 'codex/legacy-vulkan-size-83') && (needs.detect-build-changes.outputs.build-needed == 'true' || inputs.force_build)"
actual_condition=$(sed -n '/^  build-libmpv-external-ffmpeg:/,/^    runs-on:/p' "$WORKFLOW" |
  sed -n '/^    if: >-$/,/^    runs-on:/{ /^      /s/^      //p; }' | paste -sd ' ' -)
test "$actual_condition" = "$expected_condition" || fail '外部构建条件必须排除兼容基线 PR 并检查构建输入或显式强制构建'
