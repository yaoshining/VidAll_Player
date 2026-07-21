#!/usr/bin/env bash
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly LOCK_FILE="$ROOT_DIR/native/config/sources.lock.json"
readonly BUILD_REPOSITORY='https://github.com/mpv-ohos/libmpv-ohos-build.git'
readonly BUILD_COMMIT='1bab837e662ffa47ce51efd0720d3ed7c4988944'
readonly MESON_VERSION='1.7.0'
readonly CACHE_ROOT="${VIDALL_PLAYER_CACHE_DIR:-${HOME:-$ROOT_DIR}/.cache/vidall-player}"
readonly WORK_DIR="$CACHE_ROOT/libmpv-ohos-build"
readonly OUTPUT_DIR="$ROOT_DIR/dist/libmpv/arm64-v8a"
readonly MESON_MARKER="$WORK_DIR/.vidall-player-meson-version"

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

# Meson 或上游补丁更新时使已有中间构建失效，避免缓存污染。
if [ ! -f "$MESON_MARKER" ] || [ "$(cat "$MESON_MARKER")" != "$MESON_VERSION" ]; then
  rm -rf "$WORK_DIR/libmpv"/*/.build
  printf '%s\n' "$MESON_VERSION" > "$MESON_MARKER"
fi
# 该脚本从受控提交获取源码构建流程，不下载或使用预编译 libmpv。
cd "$WORK_DIR"
chmod +x ./*.sh ./download/*.sh ./scripts/*.sh
./download.sh
./patch.sh
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
