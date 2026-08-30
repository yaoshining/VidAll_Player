#pragma once

namespace vidall::render {

enum class RenderBackend {
    Vulkan,
    OpenGles,
    Software,
    Unavailable,
};

struct BackendCapabilities {
    bool vulkanSafe = false;
    bool openGlesAvailable = false;
    bool softwareAvailable = false;
};

RenderBackend SelectRenderBackend(const BackendCapabilities& capabilities);

} // namespace vidall::render
