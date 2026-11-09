// 执行真实会话线程，用独立条件变量模拟阻塞的 GPU 操作。
#include "session_isolation.h"
#include <cassert>
#include <future>
using vidall::runtime::SessionIsolation;
using namespace std::chrono_literals;

int main() {
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
    assert(!first->Run([] { assert(false); }, 100ms, true));

    auto next = SessionIsolation::Acquire();
    assert(next && next->Run([] {}, 1s));
    bool caught = false;
    try { next->Run([] { throw 42; }, 1s); } catch (int err) { caught = err == 42; }
    assert(caught && !next->IsQuarantined());
    first->FinishedRelease();  // 已明确失效的 GPU 所有权不能凭迟到回调释放名额。
    assert(!SessionIsolation::Acquire());

    std::promise<void> slow, closed;
    auto wait = slow.get_future().share();
    assert(!next->Run([wait] { wait.wait(); }, 100ms));
    assert(!next->IsQuarantined());
    // 退出列表的调用及时返回。真实关闭任务仍由旧实例持有，等待在途操作完成。
    assert(!next->Run([&] { next->FinishedRelease(); closed.set_value(); }, 100ms, true));
    assert(!SessionIsolation::Acquire());
    assert(!next->Run([] { assert(false); }, 100ms));
    slow.set_value();
    assert(closed.get_future().wait_for(1s) == std::future_status::ready);
    auto recovered = SessionIsolation::Acquire();
    assert(recovered && recovered->Run([] {}, 1s));
    finish.set_value();
}
