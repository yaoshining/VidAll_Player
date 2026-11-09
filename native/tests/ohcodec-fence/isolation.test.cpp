// 执行真实会话隔离器；阻塞的操作使用独立条件变量模拟仍在使用的 GPU。
#include "session_isolation.h"
#include <cassert>
#include <future>

using vidall::runtime::SessionIsolation;
using namespace std::chrono_literals;

int main() {
    auto healthy = SessionIsolation::Acquire();
    assert(healthy && healthy->Run([] {}, 1s));
    healthy->FinishedRelease();
    auto first = SessionIsolation::Acquire();
    assert(first);
    std::promise<void> entered, finish;
    auto gate = finish.get_future().share();
    auto pending = std::async(std::launch::async, [&] {
        return first->Run([&] { entered.set_value(); gate.wait(); }, 1s);
    });
    entered.get_future().wait();
    first->Quarantine();
    assert(pending.wait_for(250ms) == std::future_status::ready && !pending.get());
    assert(!first->Run([] { assert(false); }, 100ms));
    auto next = SessionIsolation::Acquire();
    assert(next && next->Run([] {}, 1s));
    bool caught = false;
    try { next->Run([] { throw 42; }, 1s); } catch (int err) { caught = err == 42; }
    assert(caught && !next->IsQuarantined());
    assert(!SessionIsolation::Acquire());
    finish.set_value();

    std::promise<void> unblock;
    auto wait = unblock.get_future().share();
    assert(!next->Run([wait] { wait.wait(); }, 100ms));
    assert(next->IsQuarantined());
    assert(!SessionIsolation::Acquire());
    unblock.set_value();
}
