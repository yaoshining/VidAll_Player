#pragma once
#include <atomic>
#include <memory>

namespace vidall::runtime {
// 名额附着在原生对象上，移除 JS handle 或进入隔离都不释放名额。
class SessionBudget {
    inline static std::atomic<unsigned> standard_{0};
    inline static std::atomic<unsigned> compatible_{0};
    inline static std::atomic<unsigned> recovery_{0};
    std::atomic<unsigned>& pool_;
    explicit SessionBudget(std::atomic<unsigned>& pool) : pool_(pool) {}
public:
    SessionBudget(const SessionBudget&) = delete;
    SessionBudget& operator=(const SessionBudget&) = delete;
    ~SessionBudget() { --pool_; }
    static std::shared_ptr<SessionBudget> Acquire(bool compatible, bool recovery = false) {
        auto& pool = compatible ? (recovery ? recovery_ : compatible_) : standard_;
        const unsigned limit = compatible ? 2 : 6;
        unsigned used = pool.load();
        do { if (used >= limit) return {}; }
        while (!pool.compare_exchange_weak(used, used + 1));
        // 分开 new 与控制块分配：控制块失败会 delete 已建对象，不能再扣一次。
        SessionBudget* lease = nullptr;
        try { lease = new SessionBudget(pool); }
        catch (...) { --pool; throw; }
        return std::shared_ptr<SessionBudget>(lease);
    }
};
}
