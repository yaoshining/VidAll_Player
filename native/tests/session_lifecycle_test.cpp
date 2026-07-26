#include <cassert>
#include <string>

#include "session_lifecycle.h"

int main()
{
    vidall::SessionLifecycle lifecycle;
    assert(lifecycle.state() == vidall::SessionState::Idle);
    assert(lifecycle.attach(1, 1920, 1080) == vidall::LifecycleResult::Accepted);
    assert(lifecycle.detach(0) == vidall::LifecycleResult::IgnoredStaleGeneration);
    assert(lifecycle.detach(1) == vidall::LifecycleResult::Accepted);
    assert(lifecycle.release() == vidall::LifecycleResult::Accepted);
    assert(lifecycle.release() == vidall::LifecycleResult::IgnoredReleased);
    assert(lifecycle.state() == vidall::SessionState::Released);
    assert(lifecycle.attach(2, 1920, 1080) == vidall::LifecycleResult::RejectedReleased);
    return 0;
}
