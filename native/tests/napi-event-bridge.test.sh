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
  assert_contains "$BRIDGE" "napi_tsfn_abort"
  assert_contains "$BRIDGE" "EventCallbackContext"
  assert_contains "$BRIDGE" "callbackContext->closed.load()"
  assert_contains "$BRIDGE" "eventCallbackContext_->closed.store(true)"
  assert_contains "$BRIDGE" "FinalizeEventCallback"
  assert_contains "$BRIDGE" "resourceName, 0, 1"
  assert_contains "$BRIDGE" "MPV_EVENT_END_FILE"
  assert_contains "$BRIDGE" "MPV_END_FILE_REASON_ERROR"
  assert_contains "$BRIDGE" "MPV_EVENT_LOG_MESSAGE"
  assert_contains "$BRIDGE" "MPV_EVENT_PROPERTY_CHANGE"
  assert_contains "$BRIDGE" "mpv_request_log_messages"
  assert_contains "$BRIDGE" "mpv_observe_property"
  assert_contains "$BRIDGE" "setEventCallback"
  assert_contains "$BRIDGE" 'DispatchEvent("firstFrame", "当前 Surface 已提交首帧")'
  assert_contains "$BRIDGE" "eglSwapBuffers(display_, surface_) == EGL_TRUE"
  assert_contains "$BRIDGE" "OH_NativeWindow_NativeWindowFlushBuffer(window_, buffer, fenceFd, region) == 0"
  assert_contains "$BRIDGE" "firstFrameDelivered_.store(false)"
  assert_contains "$BRIDGE" "if (useNativeWindow && frameSubmitted && !firstFrameDelivered_.exchange(true))"
  assert_contains "$BRIDGE" "if (released_.load() || eventTsfn_ == nullptr)"
  assert_contains "$BRIDGE" "eventSequence_"
  assert_contains "$TYPES" "sequence: number;"
  assert_contains "$TYPES" "'firstFrame'"
  assert_contains "$TYPES" "setEventCallback(handle: number, callback: NativeEventCallback): string;"
  assert_contains "$PAGE" "libentry.setEventCallback(handle"
  if rg -q --fixed-strings "gNativeWindow" "$BRIDGE"; then
    fail "NativeWindow 不能作为进程全局状态保存"
  fi
  assert_contains "$BRIDGE" "const std::string& smbUsername, const std::string& smbPassword"
  assert_contains "$BRIDGE" "kind == \"smb\""
  assert_contains "$BRIDGE" "isSmb ? \"\" : authorization.c_str()"
  assert_contains "$BRIDGE" "demuxer-lavf-o"
  assert_contains "$BRIDGE" "stream-lavf-o"
  assert_contains "$BRIDGE" "EscapeMpvOptionValue"
  assert_contains "$BRIDGE" '",pass" "word=" + EscapeMpvOptionValue(smbPassword)'
  if rg -q --fixed-strings '",******"' "$BRIDGE"; then
    fail "SMB 密码不能被掩码后传给 FFmpeg"
  fi
  assert_contains "$BRIDGE" "smbUsernameCopy.clear()"
  assert_contains "$BRIDGE" "smbPasswordCopy.clear()"
  assert_contains "$TYPES" "smbUsername: string, smbPassword: string"
  assert_contains "$PAGE" "this.smbUsername"
  assert_contains "$PAGE" "this.smbPassword"
  assert_contains "$PAGE" "this.loadVideo()"
  assert_contains "$PAGE" "@State smbConfigStatus: string = ''"
  assert_contains "$PAGE" "正在验证 SMB 配置..."
  assert_contains "$PAGE" "smb-config-status"
  assert_contains "$PAGE" "save-smb-config-button"
  assert_contains "$PAGE" "SMB 配置已保存，密码未保存。"
  assert_contains "$PAGE" "libentry.loadMedia(this.playerHandle, kind, targetUrl, authorization, proxyLeaseId, smbUsername, smbPassword)"
  assert_contains "$PAGE" "if (!this.createPlayer())"
}

main "$@"
