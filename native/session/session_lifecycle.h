#ifndef VIDALL_SESSION_LIFECYCLE_H
#define VIDALL_SESSION_LIFECYCLE_H

#include <cstdint>

namespace vidall {

enum class SessionState { Idle, Released };
enum class LifecycleResult { Accepted, IgnoredStaleGeneration, IgnoredReleased, RejectedReleased, RejectedInvalidSurface };

class SessionLifecycle {
public:
    LifecycleResult attach(std::uint64_t generation, int width, int height);
    LifecycleResult detach(std::uint64_t generation);
    LifecycleResult release();
    SessionState state() const;

private:
    SessionState state_ = SessionState::Idle;
    std::uint64_t generation_ = 0;
};

} // namespace vidall
#endif
