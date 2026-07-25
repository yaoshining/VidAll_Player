#!/usr/bin/env bash
# 回归 issue #22：mpv EventLoop 必须通过 TSFN 将失败与诊断日志交给 ArkTS。
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly BRIDGE="$PROJECT_ROOT/entry/src/main/cpp/napi_bridge.cpp"
readonly TYPES="$PROJECT_ROOT/entry/src/main/cpp/types/libentry/index.d.ts"
readonly PAGE="$PROJECT_ROOT/entry/src/main/ets/pages/Index.ets"

fail() {
  echo "测试失败：$*" >&2
  exit 1
}

assert_contains() {
  local file="$1"
  local pattern="$2"
  rg -q --fixed-strings "$pattern" "$file" || fail "$file 缺少：$pattern"
}

main() {
  assert_contains "$BRIDGE" "napi_create_threadsafe_function"
  assert_contains "$BRIDGE" "napi_call_threadsafe_function"
  assert_contains "$BRIDGE" "napi_release_threadsafe_function"
  assert_contains "$BRIDGE" "MPV_EVENT_END_FILE"
  assert_contains "$BRIDGE" "MPV_END_FILE_REASON_ERROR"
  assert_contains "$BRIDGE" "MPV_EVENT_LOG_MESSAGE"
  assert_contains "$BRIDGE" "MPV_EVENT_PROPERTY_CHANGE"
  assert_contains "$BRIDGE" "mpv_request_log_messages"
  assert_contains "$BRIDGE" "mpv_observe_property"
  assert_contains "$BRIDGE" "setEventCallback"
  assert_contains "$TYPES" "setEventCallback(handle: number, callback: NativeEventCallback): string;"
  assert_contains "$PAGE" "libentry.setEventCallback(handle"
}

main "$@"
