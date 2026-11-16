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
    // 构建能力优先于设备文件探测；纯软件构建不能选中 GPU。
    bool gpuBuildAvailable = true;
};

RenderBackend SelectRenderBackend(const BackendCapabilities& capabilities);

} // namespace vidall::render
