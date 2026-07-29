#include "event_dispatcher.h"

namespace vidall {
QueuedEvent EventDispatcher::enqueue(const std::string& type, std::uint64_t surfaceGeneration)
{
  if (closed_) return {};
  return {type, ++sequence_, epoch_, surfaceGeneration, true};
}
bool EventDispatcher::accept(const QueuedEvent& event)
{
  if (closed_ || !event.valid || event.epoch != epoch_) {
    return false;
  }
  // Per-session events are strictly ordered; reject out-of-order or duplicate
  // sequences so a reordered or replayed event can never overtake a fresher one.
  if (event.sequence <= lastAcceptedSequence_) {
    return false;
  }
  lastAcceptedSequence_ = event.sequence;
  return true;
}
void EventDispatcher::advanceEpoch() { if (!closed_) { ++epoch_; lastAcceptedSequence_ = 0; } }
void EventDispatcher::close() { closed_ = true; }
} // namespace vidall
