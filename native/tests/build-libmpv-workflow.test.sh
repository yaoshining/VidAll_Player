#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly WORKFLOW="$PROJECT_ROOT/specs/010-cloud-build-device-execution/history/build-libmpv.pre-cloud.yml"
readonly ACTIVE="$PROJECT_ROOT/.github/workflows/build-libmpv.yml"

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

# 历史配方只作追溯，云端仍保留来源与交付契约。
! grep -Eq '^  (build-libmpv-external-ffmpeg|cross-build-prerequisites):' "$ACTIVE" || fail '旧生产入口未退役'
grep -Fq 'cloud-build/producer-input.py' "$ACTIVE" || fail '缺少精确producer输入门禁'
for job in native-contracts clean-environment; do grep -Fq "  $job:" "$ACTIVE" || fail '独有来源契约检查丢失'; done
