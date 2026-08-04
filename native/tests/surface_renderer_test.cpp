#include <iostream>
#include "surface_renderer.h"

namespace { bool check(bool ok, const char* msg) { if (!ok) std::cerr << "FAILED: " << msg << '\n'; return ok; } }

int main() {
  vidall::SurfaceRenderer renderer;
  bool passed = true;
  passed &= check(renderer.attach(1, 1920, 1080) == vidall::SurfaceResult::Accepted, "valid surface attaches");
  passed &= check(renderer.submitFrame(1) == vidall::SurfaceResult::FrameSubmitted, "current generation submits frame");
  passed &= check(renderer.attach(2, 1280, 720) == vidall::SurfaceResult::Accepted, "new generation replaces old");
  passed &= check(renderer.resize(2, 1024, 576) == vidall::SurfaceResult::Accepted, "current generation resize is accepted");
  passed &= check(renderer.resize(1, 1024, 576) == vidall::SurfaceResult::IgnoredStaleGeneration, "stale resize is dropped");
  passed &= check(renderer.resize(2, 0, 576) == vidall::SurfaceResult::RejectedInvalidSurface, "zero-sized resize is rejected");
  passed &= check(renderer.submitFrame(1) == vidall::SurfaceResult::IgnoredStaleGeneration, "old render job is dropped");
  passed &= check(renderer.detach(1) == vidall::SurfaceResult::IgnoredStaleGeneration, "old detach is dropped");
  passed &= check(renderer.detach(2) == vidall::SurfaceResult::Accepted, "current generation detaches");
  passed &= check(renderer.submitFrame(2) == vidall::SurfaceResult::IgnoredDetached, "detached renderer drops work");
  // detach on a future generation must not be reported as Accepted.
  vidall::SurfaceRenderer detached;
  passed &= check(detached.attach(1, 640, 480) == vidall::SurfaceResult::Accepted, "fresh surface attaches");
  passed &= check(detached.detach(2) == vidall::SurfaceResult::IgnoredStaleGeneration, "future generation detach is ignored");
  passed &= check(detached.submitFrame(1) == vidall::SurfaceResult::FrameSubmitted, "current generation still attached after ignored future detach");
  passed &= check(detached.detach(1) == vidall::SurfaceResult::Accepted, "current generation can still detach");
  passed &= check(detached.submitFrame(1) == vidall::SurfaceResult::IgnoredDetached, "detached renderer drops work");
  passed &= check(renderer.attach(3, 0, 720) == vidall::SurfaceResult::RejectedInvalidSurface, "zero size is rejected");
  vidall::SurfaceRenderer released;
  passed &= check(released.attach(1, 640, 480) == vidall::SurfaceResult::Accepted, "release target attaches");
  released.release();
  passed &= check(released.submitFrame(1) == vidall::SurfaceResult::IgnoredDetached, "released renderer drops queued frames");
  passed &= check(released.attach(2, 640, 480) == vidall::SurfaceResult::IgnoredDetached, "released renderer cannot accept a rebuilt surface");
  return passed ? 0 : 1;
}
