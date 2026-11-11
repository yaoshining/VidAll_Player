#pragma once
#include <atomic>
#include <memory>
namespace vidall::runtime {
// 与后台任务共同持有；请求超时、NAPI complete 都不能提前归还实际在途名额。
class WorkBudget {
public:
    enum class Pool { Standard, Closing, Recovery };
private:
    inline static std::atomic<unsigned> used_[3]{};
    const unsigned pool_;
    explicit WorkBudget(unsigned pool) : pool_(pool) {}
public:
    WorkBudget(const WorkBudget&) = delete;
    WorkBudget& operator=(const WorkBudget&) = delete;
    ~WorkBudget() { --used_[pool_]; }
    static std::shared_ptr<WorkBudget> Acquire(Pool pool = Pool::Standard) {
        const unsigned index = static_cast<unsigned>(pool);
        if (index >= 3) return {};
        auto& counter = used_[index];
        const unsigned limit = pool == Pool::Standard ? 32 : 8;
        unsigned used = counter.load();
        do { if (used >= limit) return {}; }
        while (!counter.compare_exchange_weak(used, used + 1));
        WorkBudget* lease = nullptr;
        try { lease = new WorkBudget(index); }
        catch (...) { --counter; throw; }
        return std::shared_ptr<WorkBudget>(lease);
    }
};
}
