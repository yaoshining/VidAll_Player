#pragma once
#include <atomic>
#include <memory>
#include <mutex>
#include <unordered_map>
namespace vidall::runtime {
// 不操作 NAPI，仅标识环境的这一轮生命周期；地址复用不等于身份复用。
class EnvironmentLifetime {
    inline static std::mutex mutex_;
    inline static std::unordered_map<void*, std::shared_ptr<EnvironmentLifetime>> registry_;
    const void* owner_;
    std::atomic<bool> open_{true};
    explicit EnvironmentLifetime(void* owner) : owner_(owner) {}
public:
    bool IsOpen() const { return open_.load(std::memory_order_acquire); }
    bool Matches(void* owner) const { return owner_ == owner && IsOpen(); }
    static std::shared_ptr<EnvironmentLifetime> Open(void* owner) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = registry_.find(owner);
        if (it != registry_.end() && it->second->IsOpen()) return it->second;
        if (it != registry_.end()) registry_.erase(it);
        auto state = std::shared_ptr<EnvironmentLifetime>(new EnvironmentLifetime(owner));
        registry_.emplace(owner, state);
        return state;
    }
    static std::shared_ptr<EnvironmentLifetime> Current(void* owner) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = registry_.find(owner);
        return it == registry_.end() ? nullptr : it->second;
    }
    static void Close(const std::shared_ptr<EnvironmentLifetime>& state) {
        if (!state) return;
        state->open_.store(false, std::memory_order_release);
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = registry_.find(const_cast<void*>(state->owner_));
        if (it != registry_.end() && it->second == state) registry_.erase(it);
    }
};
}
