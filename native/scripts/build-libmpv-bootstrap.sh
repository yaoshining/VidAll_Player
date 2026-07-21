#!/usr/bin/env bash
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly LOCK_FILE="$ROOT_DIR/native/config/sources.lock.json"
readonly BUILD_REPOSITORY='https://github.com/mpv-ohos/libmpv-ohos-build.git'
readonly BUILD_COMMIT='1bab837e662ffa47ce51efd0720d3ed7c4988944'
readonly WORK_DIR="${RUNNER_TEMP:-$ROOT_DIR/.cache}/libmpv-ohos-build"
readonly OUTPUT_DIR="$ROOT_DIR/dist/libmpv/arm64-v8a"

if [ ! -f "$LOCK_FILE" ]; then
  echo "未找到来源锁定文件：$LOCK_FILE" >&2
  exit 1
fi

git clone --no-checkout "$BUILD_REPOSITORY" "$WORK_DIR"
git -C "$WORK_DIR" checkout --detach "$BUILD_COMMIT"
actual_commit="$(git -C "$WORK_DIR" rev-parse HEAD)"
if [ "$actual_commit" != "$BUILD_COMMIT" ]; then
  echo "引导构建来源提交不匹配：$actual_commit" >&2
  exit 1
fi

# 该脚本从受控提交获取源码构建流程，不下载或使用预编译 libmpv。
cd "$WORK_DIR"
chmod +x ./*.sh ./download/*.sh ./scripts/*.sh
./bundle.sh

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
