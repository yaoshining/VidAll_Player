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
  printf '%s\n' 'new-build-commit' > "$work_dir/.vidall-player-build-commit"

  # 无版本的旧标记必须失效，避免复用在旧脚本中留下的不完整缓存。
  source "$BOOTSTRAP_SCRIPT"
  invalidate_dependency_cache_if_build_source_changed "$work_dir" 'new-build-commit:2'

  assert_missing "$work_dir/libmpv/ffmpeg"
  assert_missing "$work_dir/libmpv/arm64-build"
  assert_missing "$work_dir/.vidall-player-build-commit"

  mkdir -p "$work_dir/libmpv/ffmpeg"
  invalidate_dependency_cache_if_build_source_changed "$work_dir" 'new-build-commit:2'
  assert_missing "$work_dir/libmpv/ffmpeg"

  mkdir -p "$work_dir/libmpv/ffmpeg"
  mark_dependency_cache_prepared "$work_dir" 'new-build-commit:2'
  assert_file_content "$work_dir/.vidall-player-build-commit" 'new-build-commit:2'
  invalidate_dependency_cache_if_build_source_changed "$work_dir" 'new-build-commit:2'
  [ -d "$work_dir/libmpv/ffmpeg" ] || fail '相同构建来源不应清除依赖缓存'

  rm "$work_dir/.vidall-player-build-commit"
  invalidate_dependency_cache_if_build_source_changed "$work_dir" 'new-build-commit:2'
  assert_missing "$work_dir/libmpv/ffmpeg"
  assert_missing "$work_dir/.vidall-player-build-commit"
}

main "$@"
