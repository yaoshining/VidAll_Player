#include "render_backend_policy.h"

namespace vidall::render {

RenderBackend SelectRenderBackend(const BackendCapabilities& capabilities)
{
    if (capabilities.gpuBuildAvailable && capabilities.vulkanSafe) {
        return RenderBackend::Vulkan;
    }
    if (capabilities.gpuBuildAvailable && capabilities.openGlesAvailable) {
        return RenderBackend::OpenGles;
    }
    if (capabilities.softwareAvailable) {
        return RenderBackend::Software;
    }
    return RenderBackend::Unavailable;
}

} // namespace vidall::render
