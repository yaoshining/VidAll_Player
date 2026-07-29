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
  events.advanceEpoch();
  passed &= check(!events.accept(first), "old epoch event is rejected");
  const auto current = events.enqueue("state");
  passed &= check(events.accept(current), "current event is accepted");
  events.close();
  passed &= check(!events.enqueue("closed").valid && !events.accept(current), "closed dispatcher cannot deliver callbacks");
  return passed ? 0 : 1;
}
