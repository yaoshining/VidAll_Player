#include "player_session.h"

namespace vidall {
PlayerSession::PlayerSession(std::uint64_t id) : id_(id) {}
std::uint64_t PlayerSession::id() const { return id_; }
std::uint64_t PlayerSession::commandSequence() const { return commandSequence_; }
SessionCommandResult PlayerSession::acceptCommand()
{
  if (closing_) return SessionCommandResult::RejectedClosing;
  ++commandSequence_;
  return SessionCommandResult::Accepted;
}
ReleaseResult PlayerSession::release()
{
  if (closing_) return ReleaseResult::AlreadyReleased;
  closing_ = true;
  eventLoopStopped_ = true;
  rendererDrained_ = true;
  return ReleaseResult::Released;
}
bool PlayerSession::releaseStagesComplete() const
{
  return closing_ && eventLoopStopped_ && rendererDrained_;
}
} // namespace vidall
