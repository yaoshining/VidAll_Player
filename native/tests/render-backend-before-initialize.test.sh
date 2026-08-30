#!/usr/bin/env bash
# issue #75：不兼容设备必须在 mpv_initialize 前绕开 Vulkan，不得用危险初始化路径试探能力。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
readonly SOURCE="$ROOT/packages/vidall-player/src/main/cpp/napi_init.cpp"

fail() { echo "测试失败：$*" >&2; exit 1; }
require_contains() { grep -Fq -- "$2" "$1" || fail "$1 缺少：$2"; }

require_contains "$SOURCE" 'SelectRenderBackend'
require_contains "$SOURCE" 'libEGL_impl.so'
require_contains "$SOURCE" 'RenderBackend::Vulkan'
require_contains "$SOURCE" 'mpv_set_option_string(player_.get(), "vo", "libmpv")'

policy_line="$(grep -nF 'SelectRenderBackend' "$SOURCE" | head -n1 | cut -d: -f1)"
initialize_line="$(grep -nF 'mpv_initialize(player_.get())' "$SOURCE" | head -n1 | cut -d: -f1)"
[ "$policy_line" -lt "$initialize_line" ] || fail "渲染后端必须在 mpv_initialize 前选择"

# Vulkan 选项只能位于 Vulkan 分支；安全降级必须显式选择 libmpv render API。
python3 - "$SOURCE" <<'PY'
import pathlib, sys
source = pathlib.Path(sys.argv[1]).read_text()
start = source.index('if (renderBackend_ == vidall::render::RenderBackend::Vulkan)')
end = source.index('// HDR tone mapping', start)
block = source[start:end]
assert '"gpu-api", "vulkan"' in block
assert '} else {' in block and '"vo", "libmpv"' in block
PY

echo "render-backend-before-initialize 测试通过"
