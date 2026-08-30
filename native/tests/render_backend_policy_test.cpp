#include "../render/render_backend_policy.h"

#include <iostream>

using vidall::render::BackendCapabilities;
using vidall::render::RenderBackend;
using vidall::render::SelectRenderBackend;

namespace {

bool check(bool condition, const char* message)
{
    if (!condition) {
        std::cerr << "FAILED: " << message << '\n';
        return false;
    }
    return true;
}

} // namespace

int main()
{
    bool passed = true;
    // 断言在 NDEBUG 下会被编译掉，故用显式检查，确保 Release 构建仍真正校验回归行为。
    passed &= check(SelectRenderBackend({true, true, true}) == RenderBackend::Vulkan,
        "vendor GPU stack present selects Vulkan");
    passed &= check(SelectRenderBackend({false, true, true}) == RenderBackend::OpenGles,
        "GLES available without Vulkan selects OpenGles");
    passed &= check(SelectRenderBackend({false, false, true}) == RenderBackend::Software,
        "software available without GPU selects Software");
    passed &= check(SelectRenderBackend({false, false, false}) == RenderBackend::Unavailable,
        "no backend available selects Unavailable");

    // GLES must remain a safe fallback when Vulkan evidence is incomplete.
    passed &= check(SelectRenderBackend({false, true, false}) == RenderBackend::OpenGles,
        "GLES fallback is selected when Vulkan evidence is incomplete");
    return passed ? 0 : 1;
}
