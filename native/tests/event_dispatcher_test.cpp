#include <iostream>
#include "event_dispatcher.h"

namespace { bool check(bool ok, const char* msg) { if (!ok) std::cerr << "FAILED: " << msg << '\n'; return ok; } }

int main() {
  vidall::EventDispatcher events;
  bool passed = true;
  const auto first = events.enqueue("state");
  const auto second = events.enqueue("firstFrame", 1);
  passed &= check(first.sequence == 1 && second.sequence == 2, "events are ordered per session");
  passed &= check(second.surfaceGeneration == 1, "surface generation is retained");
  // Reject out-of-order and duplicate sequences within the same epoch.
  passed &= check(events.accept(second), "in-order sequence 2 is accepted");
  vidall::QueuedEvent stale{second.type, second.sequence, second.epoch, second.surfaceGeneration, true};
  passed &= check(!events.accept(stale), "duplicate sequence 2 is rejected");
  vidall::QueuedEvent earlier{first.type, first.sequence, first.epoch, first.surfaceGeneration, true};
  passed &= check(!events.accept(earlier), "out-of-order sequence 1 after 2 is rejected");
  events.advanceEpoch();
  passed &= check(!events.accept(first), "old epoch event is rejected");
  const auto current = events.enqueue("state");
  passed &= check(events.accept(current), "current event is accepted");
  events.close();
  passed &= check(!events.enqueue("closed").valid && !events.accept(current), "closed dispatcher cannot deliver callbacks");
  return passed ? 0 : 1;
}
