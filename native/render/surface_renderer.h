#ifndef VIDALL_SURFACE_RENDERER_H
#define VIDALL_SURFACE_RENDERER_H
#include <cstdint>
namespace vidall {
enum class SurfaceResult { Accepted, FrameSubmitted, IgnoredStaleGeneration, IgnoredDetached, RejectedInvalidSurface };
class SurfaceRenderer {
public:
  SurfaceResult attach(std::uint64_t generation, int width, int height);
  SurfaceResult resize(std::uint64_t generation, int width, int height);
  SurfaceResult detach(std::uint64_t generation);
  SurfaceResult submitFrame(std::uint64_t generation);
 void release();
private:
  std::uint64_t generation_ = 0;
  bool attached_ = false;
  bool released_ = false;
};
} // namespace vidall
#endif
