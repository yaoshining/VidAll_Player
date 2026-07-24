#!/usr/bin/env bash
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly LOCK_FILE="$ROOT_DIR/native/config/sources.lock.json"
readonly BUILD_REPOSITORY='https://github.com/mpv-ohos/libmpv-ohos-build.git'
readonly BUILD_COMMIT='1bab837e662ffa47ce51efd0720d3ed7c4988944'
readonly DEPENDENCY_CACHE_SCHEMA='4'
readonly MESON_VERSION='1.7.0'
readonly CACHE_ROOT="${VIDALL_PLAYER_CACHE_DIR:-${HOME:-$ROOT_DIR}/.cache/vidall-player}"
readonly WORK_DIR="$CACHE_ROOT/libmpv-ohos-build"
readonly OUTPUT_DIR="$ROOT_DIR/dist/libmpv/arm64-v8a"
readonly MESON_MARKER="$WORK_DIR/.vidall-player-meson-version"

invalidate_dependency_cache_if_build_source_changed() {
  local work_dir="$1"
  local expected_commit="$2"
  local commit_marker="$work_dir/.vidall-player-build-commit"

  if [ ! -f "$commit_marker" ] || [ "$(cat "$commit_marker")" != "$expected_commit" ]; then
    # 下载脚本会跳过已有依赖目录；来源变更时必须同时清除旧 FFmpeg 与构建目录。
    rm -rf -- "$work_dir/libmpv"
    rm -f -- "$commit_marker"
  fi
}

mark_dependency_cache_prepared() {
  local work_dir="$1"
  local expected_commit="$2"
  local commit_marker="$work_dir/.vidall-player-build-commit"
  local temporary_marker="$commit_marker.tmp"

  printf '%s\n' "$expected_commit" > "$temporary_marker"
  mv -- "$temporary_marker" "$commit_marker"
}

# 还原依赖源码到下载时的干净状态，确保补丁可以幂等应用。
# 缓存命中时 download.sh 会跳过已有目录，但 patch.sh 需要干净的工作树。
# 仅对 patches/<dep>/ 存在的依赖执行还原：重置无补丁的依赖（如 freetype）
# 会触发不必要的重新构建，可能因缓存中残留的 pkg-config 文件改变构建配置
# （例如 freetype 重新检测到 harfbuzz），最终导致链接错误。
reset_dependency_sources() {
  local work_dir="$1"
  local dep_dir="$work_dir/libmpv"
  local patches_dir="$work_dir/patches"

  if [ ! -d "$dep_dir" ] || [ ! -d "$patches_dir" ]; then
    return 0
  fi

  for patch_dep in "$patches_dir"/*/; do
    [ -d "$patch_dep" ] || continue
    local dep="$dep_dir/$(basename "$patch_dep")"
    if [ -e "$dep/.git" ]; then
      echo "还原 $dep 到干净状态..."
      git -C "$dep" reset --hard
      git -C "$dep" clean -fd
    fi
  done
}

# 供 shell 测试导入缓存失效逻辑，避免触发原生构建。
if [ "${BASH_SOURCE[0]}" != "$0" ]; then
  return 0
fi

if [ ! -f "$LOCK_FILE" ]; then
  echo "未找到来源锁定文件：$LOCK_FILE" >&2
  exit 1
fi

mkdir -p "$CACHE_ROOT"
if [ ! -d "$WORK_DIR/.git" ]; then
  git clone --no-checkout "$BUILD_REPOSITORY" "$WORK_DIR"
else
  git -C "$WORK_DIR" remote set-url origin "$BUILD_REPOSITORY"
  git -C "$WORK_DIR" fetch --depth 1 origin "$BUILD_COMMIT"
fi
git -C "$WORK_DIR" checkout --detach --force "$BUILD_COMMIT"
actual_commit="$(git -C "$WORK_DIR" rev-parse HEAD)"
if [ "$actual_commit" != "$BUILD_COMMIT" ]; then
  echo "引导构建来源提交不匹配：$actual_commit" >&2
  exit 1
fi

# 上游来源变更或缓存方案升级可能切换 FFmpeg 版本或补丁；清除会被 download.sh 跳过的旧依赖。
invalidate_dependency_cache_if_build_source_changed "$WORK_DIR" "$BUILD_COMMIT:$DEPENDENCY_CACHE_SCHEMA"

# Meson 或上游补丁更新时使已有中间构建失效，避免缓存污染。
if [ ! -f "$MESON_MARKER" ] || [ "$(cat "$MESON_MARKER")" != "$MESON_VERSION" ]; then
  rm -rf "$WORK_DIR/libmpv"/*/.build
  printf '%s\n' "$MESON_VERSION" > "$MESON_MARKER"
fi
# 该脚本从受控提交获取源码构建流程，不下载或使用预编译 libmpv。
cd "$WORK_DIR"
chmod +x ./*.sh ./download/*.sh ./scripts/*.sh
./download.sh
reset_dependency_sources "$WORK_DIR"
./patch.sh
mark_dependency_cache_prepared "$WORK_DIR" "$BUILD_COMMIT:$DEPENDENCY_CACHE_SCHEMA"
./build.sh
(
  cd libmpv/arm64-build
  zip -q libmpv_aarch64.zip libmpv.so
)

mkdir -p "$OUTPUT_DIR"
mapfile -t archives < <(find libmpv/arm64-build -maxdepth 1 -name '*.zip' -type f -print)
if [ "${#archives[@]}" -eq 0 ]; then
  echo '未生成 libmpv 发布压缩包。' >&2
  exit 1
fi

for archive in "${archives[@]}"; do
  unzip -oq "$archive" -d "$OUTPUT_DIR"
done

LIBMPV_PATH="$(find "$OUTPUT_DIR" -name libmpv.so -type f -print -quit)"
if [ -z "$LIBMPV_PATH" ]; then
  echo '构建输出中缺少 libmpv.so。' >&2
  exit 1
fi
sha256sum "$LIBMPV_PATH" | tee "$OUTPUT_DIR/libmpv.so.sha256"
echo "已生成：$LIBMPV_PATH"
