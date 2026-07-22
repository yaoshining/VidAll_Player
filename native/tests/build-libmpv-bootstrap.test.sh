#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly BOOTSTRAP_SCRIPT="$PROJECT_ROOT/native/scripts/build-libmpv-bootstrap.sh"

fail() {
  echo "测试失败：$*" >&2
  exit 1
}

assert_missing() {
  [ ! -e "$1" ] || fail "应已删除：$1"
}

assert_file_content() {
  [ "$(cat "$1")" = "$2" ] || fail "文件内容不符合预期：$1"
}

main() {
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT

  local work_dir="$temp_dir/libmpv-ohos-build"
  mkdir -p "$work_dir/libmpv/ffmpeg" "$work_dir/libmpv/arm64-build"
  printf '%s\n' 'release/9.0' > "$work_dir/libmpv/ffmpeg/version"
  printf '%s\n' 'old-build-commit' > "$work_dir/.vidall-player-build-commit"

  # 旧构建来源必须移除全部依赖，而不是仅清理 Meson 中间目录。
  source "$BOOTSTRAP_SCRIPT"
  invalidate_dependency_cache_if_build_source_changed "$work_dir" 'new-build-commit'

  assert_missing "$work_dir/libmpv/ffmpeg"
  assert_missing "$work_dir/libmpv/arm64-build"
  assert_file_content "$work_dir/.vidall-player-build-commit" 'new-build-commit'

  mkdir -p "$work_dir/libmpv/ffmpeg"
  invalidate_dependency_cache_if_build_source_changed "$work_dir" 'new-build-commit'
  [ -d "$work_dir/libmpv/ffmpeg" ] || fail '相同构建来源不应清除依赖缓存'

  rm "$work_dir/.vidall-player-build-commit"
  invalidate_dependency_cache_if_build_source_changed "$work_dir" 'new-build-commit'
  assert_missing "$work_dir/libmpv/ffmpeg"
  assert_file_content "$work_dir/.vidall-player-build-commit" 'new-build-commit'
}

main "$@"
