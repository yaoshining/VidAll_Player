#ifndef VIDALL_SESSION_ISOLATION_H
#define VIDALL_SESSION_ISOLATION_H

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <exception>
#include <functional>
#include <memory>
#include <mutex>
#include <thread>

namespace vidall::runtime {

// 一个名额覆盖整个 mpv 实例及其工作线程，直到正常析构完成。
class SessionIsolation {
    struct Job {
        std::function<void()> work;
        bool done = false;
        std::exception_ptr error;
    };
    struct State {
        void ReleaseSlot() {
            if (ownsSlot.exchange(false)) --slots_;
        }
        ~State() { ReleaseSlot(); }
        std::atomic<bool> ownsSlot{true};
        std::mutex mutex;
        std::condition_variable changed;
        std::shared_ptr<Job> current;
        bool quarantined = false;
        bool stopping = false;
    };
    inline static std::atomic<unsigned> slots_{0};
    std::shared_ptr<State> state_;
    explicit SessionIsolation(std::shared_ptr<State> state) : state_(std::move(state)) {}

    static void Worker(std::shared_ptr<State> state) {
        std::unique_lock<std::mutex> lock(state->mutex);
        for (;;) {
            state->changed.wait(lock, [&] { return state->current || state->stopping || state->quarantined; });
            if (state->stopping || state->quarantined) break;
            auto job = state->current;
            lock.unlock();
            std::exception_ptr error;
            try { job->work(); } catch (...) { error = std::current_exception(); }
            job->work = nullptr;  // 不在状态锁内释放操作持有的最后一个会话引用。
            lock.lock();
            job->error = error;
            job->done = true;
            state->current.reset();
            state->changed.notify_all();
        }
        auto cancelled = std::move(state->current);
        lock.unlock();
    }
public:
    static std::shared_ptr<SessionIsolation> Acquire() {
        unsigned used = slots_.load();
        do {
            if (used >= 2) return {};
        } while (!slots_.compare_exchange_weak(used, used + 1));
        std::shared_ptr<State> state;
        try { state = std::make_shared<State>(); }
        catch (...) { --slots_; throw; }
        auto isolation = std::shared_ptr<SessionIsolation>(new SessionIsolation(state));
        std::thread(Worker, state).detach();
        return isolation;
    }
    ~SessionIsolation() {
        std::lock_guard<std::mutex> lock(state_->mutex);
        state_->stopping = true;
        state_->changed.notify_all();
    }
    bool IsQuarantined() const {
        std::lock_guard<std::mutex> lock(state_->mutex);
        return state_->quarantined;
    }
    // mpv 的正常 shutdown 已返回，后续建播放器不必等 UI 完成回调。
    void FinishedRelease() { state_->ReleaseSlot(); }
    bool Quarantine() {
        std::lock_guard<std::mutex> lock(state_->mutex);
        bool first = !state_->quarantined;
        state_->quarantined = true;
        state_->changed.notify_all();
        return first;
    }
    bool Run(std::function<void()> work, std::chrono::milliseconds timeout) {
        const auto until = std::chrono::steady_clock::now() + timeout;
        auto job = std::make_shared<Job>();
        job->work = std::move(work);
        std::unique_lock<std::mutex> lock(state_->mutex);
        auto wait = [&](auto ready) {
            if (!state_->changed.wait_until(lock, until, [&] { return state_->quarantined || ready(); })) {
                state_->quarantined = true;
                state_->changed.notify_all();
            }
            return !state_->quarantined;
        };
        if (!wait([&] { return !state_->current; })) return false;
        state_->current = job;
        state_->changed.notify_all();
        if (!wait([&] { return job->done; })) return false;
        if (job->error) std::rethrow_exception(job->error);
        return true;
    }
};
}
#endif
