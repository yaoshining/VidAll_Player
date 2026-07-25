#!/usr/bin/env bash
# 防止同一 ABI 的 libmpv.so 同时来自 CMake 与 entry/libs，导致 HAP 打包冲突。
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly CMAKE_FILE="$PROJECT_ROOT/entry/src/main/cpp/CMakeLists.txt"
readonly DUPLICATE_LIBRARY="$PROJECT_ROOT/entry/libs/arm64-v8a/libmpv.so"

grep -Fq 'IMPORTED_LOCATION ${LIBMPV_ROOT}/libmpv.so' "$CMAKE_FILE"
test ! -e "$DUPLICATE_LIBRARY" || {
  echo "重复打包输入存在：$DUPLICATE_LIBRARY" >&2
  exit 1
}
