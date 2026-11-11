#pragma once
#include <atomic>
#include <cstddef>
#include <deque>
#include <memory>
#include <mutex>
#include <string>
#include <utility>

namespace vidall::runtime {
// 每个回调代有独立邮箱；额度直到会话、TSFN finalize 和旧票据全部结束才归还。
template<class Event> class EventMailbox {
    inline static std::atomic<unsigned> instances_[2]{};
    const unsigned pool_;
    std::mutex mutex_;
    std::deque<Event> pending_;
    size_t bytes_ = 0;
    bool scheduled_ = false;
    bool closed_ = false;
    bool failed_ = false;
    explicit EventMailbox(unsigned pool) : pool_(pool) {}
    static size_t Bytes(const Event& event) { return event.type.size() + event.message.size(); }
    static bool Snapshot(const std::string& type) {
        return type == "position" || type == "subtitleText" || type == "videoParams" ||
               type == "audioParams" || type == "tracks";
    }
public:
    static constexpr size_t MaxEvents = 64;
    static constexpr size_t MaxBytes = 256 * 1024;
    static constexpr size_t MaxEventBytes = 64 * 1024;
    struct Result { bool wake; bool failed; };
    static std::shared_ptr<EventMailbox> Acquire(bool recovery = false) {
        const unsigned pool = recovery ? 1 : 0;
        const unsigned limit = recovery ? 8 : 32;
        auto& counter = instances_[pool];
        unsigned used = counter.load();
        do { if (used >= limit) return {}; }
        while (!counter.compare_exchange_weak(used, used + 1));
        EventMailbox* mailbox;
        try { mailbox = new EventMailbox(pool); }
        catch (...) { --counter; throw; }
        return std::shared_ptr<EventMailbox>(mailbox);
    }
    ~EventMailbox() { --instances_[pool_]; }
    // 替换快照时移到队尾；新 sequence 不能占据旧队列位置，导致中间状态被丢弃。
    Result Push(Event event, const std::string& type, const std::string& message) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (closed_ || failed_) return {false, failed_};
        if (Snapshot(type)) {
            for (auto it = pending_.begin(); it != pending_.end(); ++it) {
                if (it->type == type) {
                    bytes_ -= Bytes(*it); pending_.erase(it); break;
                }
            }
        }
        const bool oversized = type.size() > MaxEventBytes || message.size() > MaxEventBytes - type.size();
        const size_t size = oversized ? 0 : type.size() + message.size();
        if (oversized || pending_.size() >= MaxEvents || size > MaxBytes - bytes_) {
            // 不能静默漏关键事件；无法保证次序时明确结束当前会话的事件交付。
            pending_.clear(); bytes_ = 0; failed_ = true;
            event.type = "error"; event.message = "PLAYER_EVENT_QUEUE_FULL";
        } else {
            // 检查额度之后再复制；临时插入值也占本批次的有效载荷预算。
            event.type = type; event.message = message;
        }
        bytes_ += Bytes(event);
        pending_.push_back(std::move(event));
        const bool wake = !scheduled_; scheduled_ = true;
        return {wake, failed_};
    }
    std::deque<Event> Take() {
        std::lock_guard<std::mutex> lock(mutex_);
        std::deque<Event> batch;
        batch.swap(pending_); bytes_ = 0; scheduled_ = false;
        return batch;
    }
    void Close() {
        std::lock_guard<std::mutex> lock(mutex_);
        closed_ = true; pending_.clear(); bytes_ = 0;
    }
};
}
