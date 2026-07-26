#include <iostream>

#include "session_lifecycle.h"

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
    vidall::SessionLifecycle lifecycle;
    bool passed = true;
    passed &= check(lifecycle.state() == vidall::SessionState::Idle, "initial state is idle");
    passed &= check(lifecycle.attach(0, 1920, 1080) == vidall::LifecycleResult::RejectedInvalidSurface,
        "zero generation is rejected");
    passed &= check(lifecycle.attach(1, 0, 1080) == vidall::LifecycleResult::RejectedInvalidSurface,
        "zero width is rejected");
    passed &= check(lifecycle.attach(1, 1920, -1) == vidall::LifecycleResult::RejectedInvalidSurface,
        "negative height is rejected");
    passed &= check(lifecycle.attach(1, 1920, 1080) == vidall::LifecycleResult::Accepted, "attach succeeds");
    passed &= check(lifecycle.detach(0) == vidall::LifecycleResult::IgnoredStaleGeneration,
        "stale detach is ignored");
    passed &= check(lifecycle.detach(1) == vidall::LifecycleResult::Accepted, "current detach succeeds");
    passed &= check(lifecycle.release() == vidall::LifecycleResult::Accepted, "release succeeds");
    passed &= check(lifecycle.release() == vidall::LifecycleResult::IgnoredReleased, "repeat release is ignored");
    passed &= check(lifecycle.state() == vidall::SessionState::Released, "released state persists");
    passed &= check(lifecycle.attach(2, 1920, 1080) == vidall::LifecycleResult::RejectedReleased,
        "attach after release is rejected");
    return passed ? 0 : 1;
}
