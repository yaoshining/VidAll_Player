#include "surface_renderer.h"

namespace vidall {
SurfaceResult SurfaceRenderer::attach(std::uint64_t generation, int width, int height)
{
  if (generation == 0 || width <= 0 || height <= 0) return SurfaceResult::RejectedInvalidSurface;
  if (generation < generation_) return SurfaceResult::IgnoredStaleGeneration;
  generation_ = generation;
  attached_ = true;
  return SurfaceResult::Accepted;
}
SurfaceResult SurfaceRenderer::detach(std::uint64_t generation)
{
  if (generation < generation_) return SurfaceResult::IgnoredStaleGeneration;
  if (generation == generation_) attached_ = false;
  return SurfaceResult::Accepted;
}
SurfaceResult SurfaceRenderer::submitFrame(std::uint64_t generation)
{
  if (!attached_) return SurfaceResult::IgnoredDetached;
  if (generation != generation_) return SurfaceResult::IgnoredStaleGeneration;
  return SurfaceResult::FrameSubmitted;
}
} // namespace vidall
