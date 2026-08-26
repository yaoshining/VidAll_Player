#!/usr/bin/env bash
# issue #73：会话复用场景 vo_gpu_next 窗口(wid) 必须在 mpv_initialize 前注入。
# vo_gpu_next 的 VO（vo_ohos_init）创建时读 --wid 建 OHNativeWindow + Vulkan surface；若在
# Attach/RenderLoop 才 mpv_set_property（运行时），会话复用「跳过冗余重建」时 VO 可能早已按
# 旧窗口创建（或注入晚于 VO 创建），导致 vo_gpu_next 拿不到最新窗口。故将 mpv_initialize
# 推迟到首次 Attach，并在 init 前把 XComponent surfaceId 以 wid 选项注入（native 内闭环，
# 不依赖 ArkTS 提前重排 surfaceId 传参、不破坏 createSession 公开签名）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
readonly SOURCE="$ROOT/packages/vidall-player/src/main/cpp/napi_init.cpp"

fail() { echo "测试失败：$*" >&2; exit 1; }
require_contains() { rg -q --fixed-strings "$2" "$1" || fail "$1 缺少：$2"; }

# 1) 原生层必须以 wid 选项注入（而非仅运行时 mpv_set_property 兜底）。
require_contains "$SOURCE" 'mpv_set_option_string(player_.get(), "wid"'
# 2) 首次 init 后须有 mpvInitialized_ 门闩，避免同一句柄重复 mpv_initialize。
require_contains "$SOURCE" 'mpvInitialized_'

# 3) 关键顺序：wid 的 set_option 必须早于 mpv_initialize，否则初始化后 vo_gpu_next 的 VO
#    读不到最新窗口。用行号断言顺序。
initialize_line="$(rg -n -F 'mpv_initialize(player_.get())' "$SOURCE" | head -n1 | cut -d: -f1)"
wid_line="$(rg -n -F 'mpv_set_option_string(player_.get(), "wid"' "$SOURCE" | head -n1 | cut -d: -f1)"
[ -n "$initialize_line" ] || fail "$SOURCE 缺少 mpv_initialize 调用"
[ -n "$wid_line" ] || fail "$SOURCE 缺少 wid 的 set_option 调用"
[ "$wid_line" -lt "$initialize_line" ] || fail "wid 必须在 mpv_initialize 前设置"

# 4) mpv_initialize 必须从 Initialize() 移出（推迟到首次 Attach）：Initialize 函数体
#    （bool Initialize( 起到 NativeResult Attach( 之前）不应再出现 mpv_initialize 调用
#    （注释文本中的单词不计数，故只匹配实际函数调用 mpv_initialize(player_.get())）。
initialize_body="$(awk '/bool Initialize\(/,/NativeResult Attach\(/' "$SOURCE")"
if echo "$initialize_body" | rg -q 'mpv_initialize\(player_\.get\(\)\)'; then
  fail "Initialize() 不得直接调用 mpv_initialize（应推迟到首次 Attach 前注入 wid）"
fi

# 5) wid 选项注入必须出现在 Attach()（surfaceId 就绪、mpv 尚未 init 的分支内）。
attach_body="$(awk '/NativeResult Attach\(/,/NativeResult Resize\(/' "$SOURCE")"
if ! echo "$attach_body" | rg -q 'mpv_set_option_string\(player_\.get\(\), "wid"'; then
  fail "wid 选项注入应位于 Attach()（拿到 surfaceId 后、mpv_initialize 前）"
fi
if ! echo "$attach_body" | rg -q 'mpv_initialize'; then
  fail "Attach() 应调用 mpv_initialize（推迟后的首次 init）"
fi

echo "wid-before-initialize 测试通过"
