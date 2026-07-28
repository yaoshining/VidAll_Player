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

  # 当调用方提供已验证的 SMB sysroot 时，引导脚本必须将其注入 FFmpeg 使用的 DEST。
  local smb_sysroot="$temp_dir/smb-sysroot"
  mkdir -p "$smb_sysroot/lib/pkgconfig" "$smb_sysroot/include"
  printf 'archive\n' > "$smb_sysroot/lib/libsmbclient.a"
  printf 'transitive archive\n' > "$smb_sysroot/lib/libgnutls.a"
  printf 'pc\n' > "$smb_sysroot/lib/pkgconfig/smbclient.pc"
  printf 'header\n' > "$smb_sysroot/include/libsmbclient.h"
  printf 'transitive header\n' > "$smb_sysroot/include/gnutls.h"
  VIDALL_PLAYER_SMB_SYSROOT="$smb_sysroot" prepare_smb_sysroot "$work_dir/libmpv/arm64-build"
  assert_file_content "$work_dir/libmpv/arm64-build/lib/libsmbclient.a" 'archive'
  assert_file_content "$work_dir/libmpv/arm64-build/lib/libgnutls.a" 'transitive archive'
  assert_file_content "$work_dir/libmpv/arm64-build/lib/pkgconfig/smbclient.pc" 'pc'
  assert_file_content "$work_dir/libmpv/arm64-build/include/libsmbclient.h" 'header'
  assert_file_content "$work_dir/libmpv/arm64-build/include/gnutls.h" 'transitive header'

  if VIDALL_PLAYER_SMB_SYSROOT="$temp_dir/missing-smb-sysroot" prepare_smb_sysroot "$work_dir/libmpv/arm64-build"; then
    fail '不完整的 SMB sysroot 必须被拒绝'
  fi

  mkdir -p "$work_dir/libmpv/ffmpeg"
  mark_dependency_cache_prepared "$work_dir" 'new-build-commit:2'
  assert_file_content "$work_dir/.vidall-player-build-commit" 'new-build-commit:2'
  invalidate_dependency_cache_if_build_source_changed "$work_dir" 'new-build-commit:2'
  [ -d "$work_dir/libmpv/ffmpeg" ] || fail '相同构建来源不应清除依赖缓存'

  rm "$work_dir/.vidall-player-build-commit"
  invalidate_dependency_cache_if_build_source_changed "$work_dir" 'new-build-commit:2'
  assert_missing "$work_dir/libmpv/ffmpeg"
  assert_missing "$work_dir/.vidall-player-build-commit"

  # reset_dependency_sources 应还原 git 仓库依赖到干净状态（含 tracked 和 untracked 文件）
  local dep_dir="$work_dir/libmpv"
  mkdir -p "$work_dir/patches/ffmpeg"
  printf 'dummy\n' > "$work_dir/patches/ffmpeg/dummy.patch"
  mkdir -p "$dep_dir/ffmpeg"
  pushd "$dep_dir/ffmpeg" > /dev/null
  git init
  git config user.email 'test@test.com'
  git config user.name 'Test'
  printf 'original\n' > file.txt
  git add file.txt
  git commit -m 'initial'
  printf 'modified\n' > file.txt
  printf 'new-from-patch\n' > new_file_from_patch.txt
  popd > /dev/null

  reset_dependency_sources "$work_dir"
  [ "$(cat "$dep_dir/ffmpeg/file.txt")" = 'original' ] || fail 'reset_dependency_sources 应还原 tracked 文件到干净状态'
  assert_missing "$dep_dir/ffmpeg/new_file_from_patch.txt"

  # 无补丁的 git 依赖不应被还原，避免触发不必要的重新构建
  mkdir -p "$dep_dir/freetype"
  pushd "$dep_dir/freetype" > /dev/null
  git init
  git config user.email 'test@test.com'
  git config user.name 'Test'
  printf 'original\n' > file.txt
  git add file.txt
  git commit -m 'initial'
  printf 'modified\n' > file.txt
  popd > /dev/null
  reset_dependency_sources "$work_dir"
  [ "$(cat "$dep_dir/freetype/file.txt")" = 'modified' ] || fail '无补丁的 git 依赖不应被还原'

  # 非 git 仓库的依赖不应被还原
  mkdir -p "$dep_dir/mbedtls"
  printf 'unchanged\n' > "$dep_dir/mbedtls/file.txt"
  reset_dependency_sources "$work_dir"
  [ "$(cat "$dep_dir/mbedtls/file.txt")" = 'unchanged' ] || fail '非 git 仓库的依赖不应被还原'

  # .git 为文件的仓库（如 worktree）也应被还原
  rm -rf "$dep_dir/ffmpeg"
  local main_repo="$temp_dir/ffmpeg-main"
  mkdir -p "$main_repo"
  pushd "$main_repo" > /dev/null
  git init
  git config user.email 'test@test.com'
  git config user.name 'Test'
  printf 'original\n' > file.txt
  git add file.txt
  git commit -m 'initial'
  popd > /dev/null
  git -C "$main_repo" worktree add "$dep_dir/ffmpeg" HEAD 2>&1
  pushd "$dep_dir/ffmpeg" > /dev/null
  printf 'modified\n' > file.txt
  printf 'untracked\n' > untracked_file.txt
  popd > /dev/null
  reset_dependency_sources "$work_dir"
  [ "$(cat "$dep_dir/ffmpeg/file.txt")" = 'original' ] || fail '.git 文件形式的仓库也应被还原'
  assert_missing "$dep_dir/ffmpeg/untracked_file.txt"

  # patches 目录不存在时应正常退出
  rm -rf "$work_dir/patches"
  printf 'still-modified\n' > "$dep_dir/freetype/file.txt"
  reset_dependency_sources "$work_dir"
  [ "$(cat "$dep_dir/freetype/file.txt")" = 'still-modified' ] || fail 'patches 目录不存在时不应还原任何依赖'

  # libmpv 不存在时应正常退出
  rm -rf "$dep_dir"
  mkdir -p "$work_dir/patches/ffmpeg"
  reset_dependency_sources "$work_dir"
}

main "$@"
