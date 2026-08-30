#include "../render/render_backend_policy.h"

#include <cassert>

using vidall::render::BackendCapabilities;
using vidall::render::RenderBackend;
using vidall::render::SelectRenderBackend;

int main()
{
    assert(SelectRenderBackend({true, true, true}) == RenderBackend::Vulkan);
    assert(SelectRenderBackend({false, true, true}) == RenderBackend::OpenGles);
    assert(SelectRenderBackend({false, false, true}) == RenderBackend::Software);
    assert(SelectRenderBackend({false, false, false}) == RenderBackend::Unavailable);

    // GLES must remain a safe fallback when Vulkan evidence is incomplete.
    assert(SelectRenderBackend({false, true, false}) == RenderBackend::OpenGles);
    return 0;
}
