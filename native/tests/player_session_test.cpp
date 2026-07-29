#include <iostream>
#include "player_session.h"

namespace { bool check(bool ok, const char* msg) { if (!ok) std::cerr << "FAILED: " << msg << '\n'; return ok; } }

int main() {
  vidall::PlayerSession first(1), second(2);
  bool passed = true;
  passed &= check(first.id() != second.id(), "sessions use distinct identities");
  passed &= check(first.acceptCommand() == vidall::SessionCommandResult::Accepted, "first accepts commands");
  passed &= check(second.acceptCommand() == vidall::SessionCommandResult::Accepted, "second accepts commands");
  passed &= check(first.commandSequence() == 1 && second.commandSequence() == 1, "command sequences are per session");
  passed &= check(first.release() == vidall::ReleaseResult::Released, "first release succeeds");
  passed &= check(first.acceptCommand() == vidall::SessionCommandResult::RejectedClosing, "released session rejects commands");
  passed &= check(second.acceptCommand() == vidall::SessionCommandResult::Accepted, "releasing first does not affect second");
  passed &= check(first.release() == vidall::ReleaseResult::AlreadyReleased, "release is idempotent");
  return passed ? 0 : 1;
}
