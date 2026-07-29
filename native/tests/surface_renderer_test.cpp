#include <iostream>
#include "surface_renderer.h"

namespace { bool check(bool ok, const char* msg) { if (!ok) std::cerr << "FAILED: " << msg << '\n'; return ok; } }

int main() {
  vidall::SurfaceRenderer renderer;
  bool passed = true;
  passed &= check(renderer.attach(1, 1920, 1080) == vidall::SurfaceResult::Accepted, "valid surface attaches");
  passed &= check(renderer.submitFrame(1) == vidall::SurfaceResult::FrameSubmitted, "current generation submits frame");
  passed &= check(renderer.attach(2, 1280, 720) == vidall::SurfaceResult::Accepted, "new generation replaces old");
  passed &= check(renderer.submitFrame(1) == vidall::SurfaceResult::IgnoredStaleGeneration, "old render job is dropped");
  passed &= check(renderer.detach(1) == vidall::SurfaceResult::IgnoredStaleGeneration, "old detach is dropped");
  passed &= check(renderer.detach(2) == vidall::SurfaceResult::Accepted, "current generation detaches");
  passed &= check(renderer.submitFrame(2) == vidall::SurfaceResult::IgnoredDetached, "detached renderer drops work");
  passed &= check(renderer.attach(3, 0, 720) == vidall::SurfaceResult::RejectedInvalidSurface, "zero size is rejected");
  return passed ? 0 : 1;
}
