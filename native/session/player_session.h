#ifndef VIDALL_PLAYER_SESSION_H
#define VIDALL_PLAYER_SESSION_H

#include <cstdint>

namespace vidall {
enum class SessionCommandResult { Accepted, RejectedClosing };
enum class ReleaseResult { Released, AlreadyReleased };

class PlayerSession {
public:
  explicit PlayerSession(std::uint64_t id);
  std::uint64_t id() const;
  std::uint64_t commandSequence() const;
  SessionCommandResult acceptCommand();
  ReleaseResult release();
private:
  std::uint64_t id_;
  std::uint64_t commandSequence_ = 0;
  bool closing_ = false;
};
} // namespace vidall
#endif
