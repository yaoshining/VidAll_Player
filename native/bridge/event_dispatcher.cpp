#include "event_dispatcher.h"

namespace vidall {
QueuedEvent EventDispatcher::enqueue(const std::string& type, std::uint64_t surfaceGeneration)
{
  if (closed_) return {};
  return {type, ++sequence_, epoch_, surfaceGeneration, true};
}
bool EventDispatcher::accept(const QueuedEvent& event) const
{
  return !closed_ && event.valid && event.epoch == epoch_;
}
void EventDispatcher::advanceEpoch() { if (!closed_) ++epoch_; }
void EventDispatcher::close() { closed_ = true; }
} // namespace vidall
