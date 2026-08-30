#!/usr/bin/env bash
# issue #75：渲染上下文不可用必须返回可识别的 render domain 错误，而不是笼统的 surface 错误。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
readonly SOURCE="$ROOT/packages/vidall-player/src/main/cpp/napi_init.cpp"
readonly TYPES="$ROOT/packages/vidall-player/src/main/cpp/types/libvidall_player_native/index.d.ts"
readonly BRIDGE="$ROOT/packages/vidall-player/src/main/ets/native/nativeBridge.ets"

fail() { echo "测试失败：$*" >&2; exit 1; }
require_contains() { grep -Fq -- "$2" "$1" || fail "$1 缺少：$2"; }

require_contains "$SOURCE" 'RENDER_BACKEND_UNAVAILABLE'
require_contains "$TYPES" "'RENDER_BACKEND_UNAVAILABLE'"
require_contains "$BRIDGE" "result.code === 'RENDER_BACKEND_UNAVAILABLE'"
require_contains "$BRIDGE" "domain: renderFailure ? 'render'"

echo "render-backend-error 测试通过"
