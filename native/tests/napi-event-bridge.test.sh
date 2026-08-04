#!/usr/bin/env bash
# HAR native bridge must expose lifecycle, surface, playback, and asynchronous event boundaries.
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly SOURCE="$ROOT/packages/vidall-player/src/main/cpp/napi_init.cpp"
readonly TYPES="$ROOT/packages/vidall-player/src/main/cpp/types/libvidall_player_native/index.d.ts"
readonly CMAKE="$ROOT/packages/vidall-player/src/main/cpp/CMakeLists.txt"

fail() { echo "测试失败：$*" >&2; exit 1; }
require_contains() { rg -q --fixed-strings "$2" "$1" || fail "$1 缺少：$2"; }

for name in CreateSession ReleaseSession AttachSurface ResizeSurface DetachSurface Load Play Stop SetEventCallback; do
  require_contains "$SOURCE" "$name"
done
for name in createSession releaseSession attachSurface resizeSurface detachSurface load play stop setEventCallback; do
  require_contains "$TYPES" "$name"
done
require_contains "$SOURCE" "std::shared_ptr<NativeSession>"
require_contains "$SOURCE" "napi_create_threadsafe_function"
require_contains "$SOURCE" "napi_call_threadsafe_function"
require_contains "$SOURCE" "napi_release_threadsafe_function"
require_contains "$SOURCE" "mpv_wait_event"
require_contains "$SOURCE" "void EventLoop(mpv_handle* player)"
require_contains "$SOURCE" "std::thread(&NativeSession::EventLoop, this, player_.get())"
require_contains "$SOURCE" "MPV_EVENT_END_FILE"
require_contains "$SOURCE" "OH_NativeWindow_CreateNativeWindowFromSurfaceId"
require_contains "$CMAKE" "native_window"
require_contains "$CMAKE" "libace_ndk.z.so"
