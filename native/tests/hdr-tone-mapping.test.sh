#!/usr/bin/env bash
# issue #66：libmpv 桥接必须显式下发 HDR tone mapping 配置，使 HDR10/HLG/BT.2020 内容
# 在目标电视上按 bt.2390 确定性 tone map 到 SDR，而不是依赖 mpv 平台默认猜测。
set -euo pipefail

# 先完成路径解析与普通变量赋值，再单独声明只读：若 cd 在命令替换内失败，
# 普通赋值的退出状态会随命令替换传播给 set -e，而 readonly/declare 内置的
# 退出状态不反映命令替换失败，会把定位失败静默吞掉。
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
readonly SOURCE="$ROOT/packages/vidall-player/src/main/cpp/napi_init.cpp"
readonly TYPES="$ROOT/packages/vidall-player/src/main/cpp/types/libvidall_player_native/index.d.ts"
readonly BRIDGE="$ROOT/packages/vidall-player/src/main/ets/native/nativeBridge.ets"

fail() { echo "测试失败：$*" >&2; exit 1; }
require_contains() { rg -q --fixed-strings "$2" "$1" || fail "$1 缺少：$2"; }

# 原生层必须下发 tone-mapping 与 hdr-compute-peak 选项。
require_contains "$SOURCE" '"tone-mapping"'
require_contains "$SOURCE" '"hdr-compute-peak"'
# 缺省曲线必须是 vo_gpu（渲染 API 后端）确定性支持且 auto 解析为 bt.2390 的曲线。
require_contains "$SOURCE" '"bt.2390"'
# Initialize 必须接收并转发这两个新参数，而不是硬编码。
require_contains "$SOURCE" 'toneMapping'
require_contains "$SOURCE" 'hdrComputePeak'

# 关键：两个 set_option 必须早于 mpv_initialize，否则 mpv 初始化后这些 vo 选项
# 会被忽略，HDR 兜底配置静默失效。用行号断言顺序，而非仅断言字符串存在。
initialize_line="$(rg -n -F 'mpv_initialize(player_.get())' "$SOURCE" | head -n1 | cut -d: -f1)"
tone_mapping_line="$(rg -n -F 'mpv_set_option_string(player_.get(), "tone-mapping"' "$SOURCE" | head -n1 | cut -d: -f1)"
compute_peak_line="$(rg -n -F 'mpv_set_option_string(player_.get(), "hdr-compute-peak"' "$SOURCE" | head -n1 | cut -d: -f1)"
[ -n "$initialize_line" ] || fail "$SOURCE 缺少 mpv_initialize 调用"
[ -n "$tone_mapping_line" ] || fail "$SOURCE 缺少 tone-mapping 的 set_option 调用"
[ -n "$compute_peak_line" ] || fail "$SOURCE 缺少 hdr-compute-peak 的 set_option 调用"
[ "$tone_mapping_line" -lt "$initialize_line" ] || fail "tone-mapping 必须在 mpv_initialize 前设置"
[ "$compute_peak_line" -lt "$initialize_line" ] || fail "hdr-compute-peak 必须在 mpv_initialize 前设置"

# NAPI 导出签名必须把两个新参数暴露给 ArkTS 侧。
require_contains "$TYPES" 'toneMapping'
require_contains "$TYPES" 'hdrComputePeak'

# ArkTS 桥接层必须有解析器把枚举值映射为 mpv 选项字符串并转发。
require_contains "$BRIDGE" 'resolveHdrToneMapping'
require_contains "$BRIDGE" 'resolveHdrComputePeak'
