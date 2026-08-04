#include "surface_renderer.h"

namespace vidall {
SurfaceResult SurfaceRenderer::attach(std::uint64_t generation, int width, int height)
{
  if (released_) return SurfaceResult::IgnoredDetached;
  if (generation == 0 || width <= 0 || height <= 0) return SurfaceResult::RejectedInvalidSurface;
  if (generation < generation_) return SurfaceResult::IgnoredStaleGeneration;
  generation_ = generation;
  attached_ = true;
  return SurfaceResult::Accepted;
}
SurfaceResult SurfaceRenderer::resize(std::uint64_t generation, int width, int height)
{
  if (released_) return SurfaceResult::IgnoredDetached;
  if (width <= 0 || height <= 0) return SurfaceResult::RejectedInvalidSurface;
  if (!attached_ || generation != generation_) return SurfaceResult::IgnoredStaleGeneration;
  return SurfaceResult::Accepted;
}
SurfaceResult SurfaceRenderer::detach(std::uint64_t generation)
{
  if (released_) return SurfaceResult::IgnoredDetached;
  if (generation < generation_) return SurfaceResult::IgnoredStaleGeneration;
  if (generation > generation_) {
    // A future generation has never been attached; detaching it must not claim
    // success, or the caller may believe the surface was released while the
    // current generation remains able to submit frames.
    return SurfaceResult::IgnoredStaleGeneration;
  }
  attached_ = false;
  return SurfaceResult::Accepted;
}
SurfaceResult SurfaceRenderer::submitFrame(std::uint64_t generation)
{
  if (released_ || !attached_) return SurfaceResult::IgnoredDetached;
  if (generation != generation_) return SurfaceResult::IgnoredStaleGeneration;
  return SurfaceResult::FrameSubmitted;
}
void SurfaceRenderer::release()
{
  attached_ = false;
  released_ = true;
}
} // namespace vidall
