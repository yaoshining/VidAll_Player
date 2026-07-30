#ifndef VIDALL_EVENT_DISPATCHER_H
#define VIDALL_EVENT_DISPATCHER_H
#include <cstdint>
#include <string>
namespace vidall {
struct QueuedEvent { std::string type; std::uint64_t sequence = 0; std::uint64_t epoch = 0; std::uint64_t surfaceGeneration = 0; bool valid = false; };
class EventDispatcher {
public:
  QueuedEvent enqueue(const std::string& type, std::uint64_t surfaceGeneration = 0);
  bool accept(const QueuedEvent& event);
  void advanceEpoch();
  void close();
private:
  std::uint64_t sequence_ = 0;
  std::uint64_t epoch_ = 1;
  std::uint64_t lastAcceptedSequence_ = 0;
  bool closed_ = false;
};
} // namespace vidall
#endif
