#pragma once

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <poll.h>
#include <unistd.h>

namespace vidall::render {

// 消费 RequestBuffer 返回的 release fence；成功后才允许 CPU 访问 buffer。
// 每个 fd 仅关闭一次，EINTR 不重新计时；FlushBuffer 另传 -1 表示 CPU 已写完。
inline bool WaitAndCloseReleaseFence(int& fence, int timeoutMs = 50)
{
    const int fd = fence;
    fence = -1;
    if (fd == -1) return true;
    if (fd < -1) return false;
    const auto until = std::chrono::steady_clock::now() +
        std::chrono::milliseconds(std::max(0, timeoutMs));
    bool ready = false;
    for (;;) {
        const auto remaining = until - std::chrono::steady_clock::now();
        if (remaining <= std::chrono::steady_clock::duration::zero()) break;
        const auto micros = std::chrono::duration_cast<std::chrono::microseconds>(remaining).count();
        const int waitMs = static_cast<int>((micros + 999) / 1000);
        pollfd descriptor{fd, POLLIN, 0};
        const int rc = poll(&descriptor, 1, waitMs);
        if (rc > 0) {
            ready = (descriptor.revents & POLLIN) &&
                !(descriptor.revents & (POLLERR | POLLNVAL | POLLHUP));
            break;
        }
        if (rc == 0 || (errno != EINTR && errno != EAGAIN)) break;
    }
    // close 的 EINTR 不重试，避免 fd 已被回收后误关其他线程复用的描述符。
    close(fd);
    return ready;
}

} // namespace vidall::render
