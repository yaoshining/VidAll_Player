#include "session_lifecycle.h"

namespace vidall {

LifecycleResult SessionLifecycle::attach(std::uint64_t generation, int width, int height)
{
    if (state_ == SessionState::Released) {
        return LifecycleResult::RejectedReleased;
    }
    if (generation == 0 || width <= 0 || height <= 0) {
        return LifecycleResult::RejectedInvalidSurface;
    }
    if (generation < generation_) {
        return LifecycleResult::IgnoredStaleGeneration;
    }
    generation_ = generation;
    return LifecycleResult::Accepted;
}

LifecycleResult SessionLifecycle::detach(std::uint64_t generation)
{
    if (state_ == SessionState::Released) {
        return LifecycleResult::IgnoredReleased;
    }
    if (generation < generation_) {
        return LifecycleResult::IgnoredStaleGeneration;
    }
    if (generation == generation_) {
        generation_ = 0;
    }
    return LifecycleResult::Accepted;
}

LifecycleResult SessionLifecycle::release()
{
    if (state_ == SessionState::Released) {
        return LifecycleResult::IgnoredReleased;
    }
    state_ = SessionState::Released;
    generation_ = 0;
    return LifecycleResult::Accepted;
}

SessionState SessionLifecycle::state() const
{
    return state_;
}

} // namespace vidall
