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

  # macOS 自带 Bash 3.2 不支持 mapfile；发布归档必须使用可移植的循环收集。
  if grep -q 'mapfile' "$BOOTSTRAP_SCRIPT"; then
    fail '引导脚本不得依赖 macOS Bash 3.2 不支持的 mapfile'
  fi

  # macOS 不提供 sha256sum；发布摘要必须回退到随系统提供的 shasum。
  local hash_input="$temp_dir/libmpv.so"
  local hash_output="$temp_dir/libmpv.so.sha256"
  printf 'libmpv artifact\n' > "$hash_input"
  write_sha256 "$hash_input" "$hash_output"
  grep -Eq '^[0-9a-f]{64}[[:space:]]+' "$hash_output" || fail 'libmpv SHA-256 摘要格式无效'

  # external prefix 必须携带 FFmpeg 8 shared libraries、pkg-config、许可证及播放能力证明。
  local ffmpeg_prefix="$temp_dir/ffmpeg-prefix"
  local ffmpeg_dest="$temp_dir/ffmpeg-dest"
  mkdir -p "$ffmpeg_prefix/include/libavcodec" "$ffmpeg_prefix/include/libavformat" \
    "$ffmpeg_prefix/include/libavutil" "$ffmpeg_prefix/include/libavfilter" \
    "$ffmpeg_prefix/include/libswresample" "$ffmpeg_prefix/include/libswscale" \
    "$ffmpeg_prefix/lib/pkgconfig" "$ffmpeg_prefix/licenses"
  local component soname version
  for component in avcodec avformat avutil avfilter swresample swscale; do
    case "$component" in
      avcodec) soname=62; version=62.11.100 ;;
      avformat) soname=62; version=62.3.100 ;;
      avutil) soname=60; version=60.8.100 ;;
      avfilter) soname=11; version=11.4.100 ;;
      swresample) soname=6; version=6.1.100 ;;
      swscale) soname=9; version=9.1.100 ;;
    esac
    printf 'header\n' > "$ffmpeg_prefix/include/lib$component/$component.h"
    printf 'shared-%s\n' "$component" > "$ffmpeg_prefix/lib/lib$component.so.$version"
    ln -s "lib$component.so.$version" "$ffmpeg_prefix/lib/lib$component.so.$soname"
    ln -s "lib$component.so.$soname" "$ffmpeg_prefix/lib/lib$component.so"
    cat > "$ffmpeg_prefix/lib/pkgconfig/lib$component.pc" <<EOF
prefix=/producer/absolute/path
exec_prefix=\${prefix}
libdir=\${exec_prefix}/lib
includedir=\${prefix}/include
Name: lib$component
Version: $version
Libs: -L\${libdir} -l$component
Libs.private: -L/home/runner/work/ohos_ijkplayer/smb-sysroot/lib -lsmbclient
Cflags: -I\${includedir}
EOF
  done
  printf 'GPL license\n' > "$ffmpeg_prefix/licenses/GPL-3.0-or-later.txt"
  printf 'FFmpeg license\n' > "$ffmpeg_prefix/licenses/FFmpeg-LGPL-2.1-or-later.txt"
  cat > "$ffmpeg_prefix/VERSION" <<'EOF'
ffmpeg_version=8.0
source_tag=n8.0
source_commit=140fd653aed8cad774f991ba083e2d01e86420c7
libsmbclient=enabled
libsmbclient_linkage=static-closure
smb_patch=patches/0001-libsmbclient-private-credentials.patch
target=aarch64-unknown-linux-ohos
architecture=arm64-v8a
elf_machine=AArch64
EOF
  cat > "$ffmpeg_prefix/configure-options.txt" <<'EOF'
--disable-static
--enable-shared
--enable-gpl
--enable-version3
--enable-libsmbclient
--enable-network
--enable-libdav1d
--enable-mbedtls
--enable-libxml2
--enable-demuxer=dash
--enable-ohcodec
--enable-encoder=png,mjpeg
EOF
  printf 'manifest\n' > "$ffmpeg_prefix/MANIFEST.tsv"
  printf 'elf report\n' > "$ffmpeg_prefix/ELF-REPORT.txt"
  prepare_ffmpeg_shared_prefix "$ffmpeg_prefix" "$ffmpeg_dest"
  assert_file_content "$ffmpeg_dest/lib/libavcodec.so.62.11.100" 'shared-avcodec'
  [ -L "$ffmpeg_dest/lib/libavcodec.so" ] || fail 'staging 必须保留共享库符号链接'
  grep -Fxq "prefix=$ffmpeg_dest" "$ffmpeg_dest/lib/pkgconfig/libavformat.pc" || fail 'FFmpeg .pc 必须重写 staging prefix'
  ! rg -q '/producer/absolute/path|/home/runner/' "$ffmpeg_dest/lib/pkgconfig" || fail 'FFmpeg .pc 不得泄露 producer 绝对路径'

  cp -R "$ffmpeg_prefix" "$temp_dir/invalid-static"
  printf 'archive\n' > "$temp_dir/invalid-static/lib/libavcodec.a"
  if prepare_ffmpeg_shared_prefix "$temp_dir/invalid-static" "$temp_dir/rejected-static"; then
    fail '包含 FFmpeg 静态归档的 prefix 必须被拒绝'
  fi
  cp -R "$ffmpeg_prefix" "$temp_dir/invalid-features"
  sed -i.bak '/--enable-demuxer=dash/d' "$temp_dir/invalid-features/configure-options.txt"
  if prepare_ffmpeg_shared_prefix "$temp_dir/invalid-features" "$temp_dir/rejected-features"; then
    fail '缺少历史播放能力的 prefix 必须被拒绝'
  fi
  cp -R "$ffmpeg_prefix" "$temp_dir/invalid-license"
  rm "$temp_dir/invalid-license/licenses/GPL-3.0-or-later.txt"
  if prepare_ffmpeg_shared_prefix "$temp_dir/invalid-license" "$temp_dir/rejected-license"; then
    fail '缺少 GPL 许可证的 prefix 必须被拒绝'
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
