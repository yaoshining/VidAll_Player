#!/usr/bin/env bash
# issue #66：libmpv 桥接必须显式下发 HDR tone mapping 配置，使 HDR10/HLG/BT.2020 内容
# 在目标电视上按 bt.2390 确定性 tone map 到 SDR，而不是依赖 mpv 平台默认猜测。
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly SOURCE="$ROOT/packages/vidall-player/src/main/cpp/napi_init.cpp"
readonly TYPES="$ROOT/packages/vidall-player/src/main/cpp/types/libvidall_player_native/index.d.ts"
readonly BRIDGE="$ROOT/packages/vidall-player/src/native/nativeBridge.ets"

fail() { echo "测试失败：$*" >&2; exit 1; }
require_contains() { rg -q --fixed-strings "$2" "$1" || fail "$1 缺少：$2"; }

# 原生层必须在 mpv_initialize 之前下发 tone-mapping 与 hdr-compute-peak 选项。
require_contains "$SOURCE" '"tone-mapping"'
require_contains "$SOURCE" '"hdr-compute-peak"'
# 缺省曲线必须是 vo_gpu（渲染 API 后端）确定性支持且 auto 解析为 bt.2390 的曲线。
require_contains "$SOURCE" '"bt.2390"'
# Initialize 必须接收并转发这两个新参数，而不是硬编码。
require_contains "$SOURCE" 'toneMapping'
require_contains "$SOURCE" 'hdrComputePeak'

# NAPI 导出签名必须把两个新参数暴露给 ArkTS 侧。
require_contains "$TYPES" 'toneMapping'
require_contains "$TYPES" 'hdrComputePeak'

# ArkTS 桥接层必须有解析器把枚举值映射为 mpv 选项字符串并转发。
require_contains "$BRIDGE" 'resolveHdrToneMapping'
require_contains "$BRIDGE" 'resolveHdrComputePeak'
