#ifndef VIDALL_ADAPTIVE_STREAMING_H
#define VIDALL_ADAPTIVE_STREAMING_H

#include "MediaLoader.h"
#include <cstdint>
#include <string>
#include <vector>

namespace vidall {

// 自适应流加载策略：根据清单类型（HLS/DASH）决定缓存、跳转和错误恢复行为。
// libmpv 内部处理 HLS/DASH 协议；本模块控制 mpv 选项、缓存配置、
// 分段失败分类和网络中断恢复策略。

enum class AdaptiveStreamState {
    Idle,
    Loading,
    Playing,
    Buffering,
    SeekPending,
    Error,
    Released,
};

struct AdaptiveStreamConfig {
    // 前向缓存时长（秒）；0 表示禁用。
    int64_t cacheDurationSec = 60;
    // 最小前向缓存时长（秒）；低于此阈值触发 buffering 事件。
    int64_t cacheMinSec = 5;
    // 最大后退缓存（秒）。
    int64_t cacheBackSec = 30;
    // 分段请求超时（秒）。
    int64_t segmentTimeoutSec = 15;
    // 网络重试最大次数（0 = 不重试）。
    int maxRetries = 2;
    // 重试间隔基准（毫秒）；实际间隔 = base * attempt（线性退避）。
    int64_t retryBaseMs = 1000;
};

struct AdaptiveStreamError {
    std::string domain;
    std::string code;
    std::string message;
    bool retryable = false;
};

struct SeekTarget {
    enum Type { Relative, Percent };
    Type type = Relative;
    double value = 0.0;
};

class AdaptiveStreaming {
public:
    explicit AdaptiveStreaming(const AdaptiveStreamConfig& config = AdaptiveStreamConfig{});

    // 加载自适应清单。验证 kind 必须为 Hls 或 Dash，然后计算 mpv 缓存选项。
    MediaLoadResult prepareLoad(MediaKind kind, const std::string& uri,
        const std::vector<HeaderEntry>& headers);

    // 返回 prepareLoad 成功后应传递给 mpv 的选项键值对。
    const std::vector<std::pair<std::string, std::string>>& mpvOptions() const;

    // 跳转：记录跳转目标并更新状态；libmpv 实际执行跳转，
    // 本模块负责状态跟踪和跳转期间的缓存守卫。
    bool beginSeek(const SeekTarget& target);
    void endSeek();

    // 分段失败处理：根据错误码判断瞬时/永久失败，
    // 返回是否建议重试。瞬时错误（超时/断连）标记为 retryable，
    // 永久错误（格式/认证）标记为不可重试。
    AdaptiveStreamError handleSegmentError(int mpvErrorCode, const std::string& context);

    // 网络中断恢复：根据连续失败计数和错误类型决定是否可重试，
    // 返回建议的恢复延迟（毫秒）；0 表示不可重试。
    int64_t networkRecoveryDelay(int consecutiveFailures) const;

    // 状态查询
    AdaptiveStreamState state() const;
    bool isSeekPending() const;
    const std::string& currentUri() const;
    MediaKind currentKind() const;
    int retryCount() const;

    // 重置内部状态（切源或 stop 时调用）。
    void reset();

    // 释放资源。
    void release();

    // 测试辅助：模拟原生层状态回调以设置内部状态。
    // 生产代码中不应调用；状态只应由真实事件驱动。
    void simulateStateChange(AdaptiveStreamState newState);

private:
    AdaptiveStreamConfig config_;
    AdaptiveStreamState state_ = AdaptiveStreamState::Idle;
    std::string currentUri_;
    MediaKind currentKind_ = MediaKind::Hls;
    std::vector<std::pair<std::string, std::string>> mpvOptions_;
    bool seekPending_ = false;
    int retryCount_ = 0;
    int consecutiveFailures_ = 0;

    void buildMpvOptions();
};

} // namespace vidall
#endif