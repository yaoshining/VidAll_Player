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
require_contains "$BUILD_PROFILE" '"librariesInfo"'
require_contains "$BUILD_PROFILE" '"name": "libvidall_player_native.so"'
require_contains "$BUILD_PROFILE" '"libmpv.so"'
require_contains "$CMAKE" 'add_library(vidall_player_native SHARED napi_init.cpp)'
require_contains "$CMAKE" 'libace_napi.z.so'
require_contains "$CMAKE" 'VIDALL_MPV_AVAILABLE=1'
require_contains "$SOURCE" 'NAPI_MODULE(vidall_player_native, Init)'
require_contains "$SOURCE" 'mpv_create()'
require_contains "$SOURCE" 'mpv_initialize'
require_contains "$SOURCE" 'CreateSession'
require_contains "$SOURCE" 'ReleaseSession'
require_contains "$MANIFEST" '"name": "libvidall_player_native.so"'
require_contains "$TYPES" 'createSession(fontsDir?: string, hwdec?: string, toneMapping?: string, hdrComputePeak?: string): NativeSessionResult;'
require_contains "$TYPES" 'releaseSession(handle: number): NativeSessionResult;'
require_contains "$BRIDGE" "from 'libvidall_player_native.so'"
NATIVE_BRIDGE="$ROOT/packages/vidall-player/src/native/nativeBridge.ets"
require_contains "$NATIVE_BRIDGE" 'createNativePlayerBridge'
require_contains "$NATIVE_BRIDGE" 'NativePlayerBridge'
require_contains "$NATIVE_BRIDGE" 'release(): Promise<void>'
for forbidden in 'libvidall_player_native' 'NativePackagingProbe' 'napi'; do
  ! rg -q --fixed-strings "$forbidden" "$ENTRY" || fail "公开入口泄露内部符号：$forbidden"
done

if [ "${1:-}" = "--artifacts" ]; then
  HAR="$ROOT/packages/vidall-player/build/default/outputs/default/vidall_player.har"
  HAP="$ROOT/entry/build/default/outputs/default/entry-default-unsigned.hap"
  READELF="${OHOS_NDK:-/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony}/native/llvm/bin/llvm-readelf"
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  require_file "$HAR"
  require_file "$HAP"
  require_file "$READELF"
  tar -xzf "$HAR" -C "$TMP_DIR"
  HAP_ENTRIES="$(unzip -Z1 "$HAP")"
  for abi in arm64-v8a x86_64; do
    tar -tzf "$HAR" | rg -q "^package/libs/$abi/libvidall_player_native\\.so$" || fail "HAR 缺少 $abi native 库"
    rg -qx "libs/$abi/libvidall_player_native\\.so" <<<"$HAP_ENTRIES" || fail "consumer HAP 缺少 $abi native 库"
    if tar -tzf "$HAR" | rg -q "^package/libs/$abi/lib(av(codec|format|util|filter)|sw(resample|scale))\\.so"; then
      fail "HAR 不得携带 FFmpeg runtime 副本：$abi"
    fi
  done
  ARM64_NATIVE="$TMP_DIR/package/libs/arm64-v8a/libvidall_player_native.so"
  ARM64_DYNAMIC="$($READELF -d "$ARM64_NATIVE")"
  rg -q 'Shared library: \[libmpv\.so\]' <<<"$ARM64_DYNAMIC" || fail "ARM64 native 缺少 libmpv.so DT_NEEDED"
  ! rg -q '\((RPATH|RUNPATH)\)' <<<"$ARM64_DYNAMIC" || fail "ARM64 native 不得携带 RPATH/RUNPATH"
  rg -q '"linkLibraries":\["libmpv.so"\]' "$TMP_DIR/package/oh-package.json5" || fail "HAR 未声明 libmpv.so 穿透依赖"
  for library in libmpv.so libavcodec.so.62 libavformat.so.62 libavutil.so.60 libavfilter.so.11 libswresample.so.6 libswscale.so.9; do
    rg -qx "libs/arm64-v8a/$library" <<<"$HAP_ENTRIES" || fail "最终宿主 HAP 缺少 ARM64 runtime：$library"
  done
fi
