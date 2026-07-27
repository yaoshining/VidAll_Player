#!/usr/bin/env bash
# HAR 内部 native packaging 的静态回归门禁；运行时装入另由 consumer 构建和设备日志取证。
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fail() { echo "测试失败：$*" >&2; exit 1; }
require_file() { [ -f "$1" ] || fail "缺少 $1"; }
require_contains() { rg -q --fixed-strings "$2" "$1" || fail "$1 缺少：$2"; }

CMAKE="$ROOT/packages/vidall-player/src/main/cpp/CMakeLists.txt"
SOURCE="$ROOT/packages/vidall-player/src/main/cpp/napi_init.cpp"
TYPES="$ROOT/packages/vidall-player/src/main/cpp/types/libvidall_player_native/index.d.ts"
MANIFEST="$ROOT/packages/vidall-player/src/main/cpp/types/libvidall_player_native/oh-package.json5"
BRIDGE="$ROOT/packages/vidall-player/src/native/harNativePackagingProbe.ets"
ENTRY="$ROOT/packages/vidall-player/Index.ets"
BUILD_PROFILE="$ROOT/packages/vidall-player/build-profile.json5"

require_file "$CMAKE"
require_file "$SOURCE"
require_file "$TYPES"
require_file "$MANIFEST"
require_file "$BRIDGE"
require_contains "$BUILD_PROFILE" '"externalNativeOptions"'
require_contains "$CMAKE" 'add_library(vidall_player_native SHARED napi_init.cpp)'
require_contains "$CMAKE" 'libace_napi.z.so'
require_contains "$SOURCE" 'NAPI_MODULE(vidall_player_native, Init)'
require_contains "$SOURCE" 'napi_call_function'
require_contains "$MANIFEST" '"name": "libvidall_player_native.so"'
require_contains "$TYPES" 'ping(): string;'
require_contains "$TYPES" 'setCallback(callback: ProbeCallback): string;'
require_contains "$BRIDGE" "from 'libvidall_player_native.so'"
require_contains "$BRIDGE" 'runHarNativePackagingProbe'
for forbidden in 'libvidall_player_native' 'NativePackagingProbe' 'napi'; do
  ! rg -q --fixed-strings "$forbidden" "$ENTRY" || fail "公开入口泄露内部符号：$forbidden"
done

if [ "${1:-}" = "--artifacts" ]; then
  HAR="$ROOT/packages/vidall-player/build/default/outputs/default/vidall_player.har"
  HAP="$ROOT/entry/build/default/outputs/default/entry-default-unsigned.hap"
  require_file "$HAR"
  require_file "$HAP"
  for abi in arm64-v8a x86_64; do
    tar -tzf "$HAR" | rg -q "^package/libs/$abi/libvidall_player_native\\.so$" || fail "HAR 缺少 $abi native 库"
    unzip -Z1 "$HAP" | rg -q "^libs/$abi/libvidall_player_native\\.so$" || fail "consumer HAP 缺少 $abi native 库"
  done
fi
