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
//
// 设计融合：
// - 复用 MediaLoader/PlayerErrorMapper 进行 URI 校验与错误映射
// - 提供 segment 时间线跟踪（精准寻址、缓存命中、推进指针）
// - 提供断网上报与重试专用方法
// - 生成 mpv 缓存/demuxer 选项供原生桥接层使用

enum class AdaptiveStreamState {
    Idle,
    ManifestLoaded,
    Playing,
    Buffering,
    SeekPending,
    Recovering,
    Failed,
    Released,
};

// 分段获取结果：调用方（native bridge）上报每条 segment 的获取结局。
enum class SegmentFetchOutcome {
    Fetched,           // 成功获取并解码，推进到下一条 segment
    TransientFailure,  // 瞬时失败（5xx、超时、连接重置），可重试
    PermanentFailure,  // 永久失败（404、解析错误、格式不支持），不可重试
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

struct AdaptiveSegment {
    uint64_t sequence;
    uint64_t startMs;
    uint64_t durationMs;
};

struct AdaptiveStreamError {
    std::string domain;
    std::string code;
    std::string message;
    bool retryable = false;
};

struct SeekTarget {
    enum Type { Relative, Percent, AbsoluteMs };
    Type type = Relative;
    double value = 0.0;
};

class AdaptiveStreaming {
public:
    explicit AdaptiveStreaming(const AdaptiveStreamConfig& config = AdaptiveStreamConfig{});

    // ===== Manifest 装载 =====

    // 加载自适应清单：校验 kind 必须为 Hls 或 Dash，验证 URI 格式，
    // 存储 segment 时间线，计算 mpv 缓存选项。
    AdaptiveStreamError loadManifest(MediaKind kind, const std::string& uri,
        const std::vector<AdaptiveSegment>& segments,
        const std::vector<HeaderEntry>& headers = {});

    // 返回 loadManifest 成功后应传递给 mpv 的选项键值对。
    const std::vector<std::pair<std::string, std::string>>& mpvOptions() const;

    // ===== Segment 时间线与精准寻址 =====

    // 跳转到指定毫秒位置：定位包含该位置的 segment，更新当前指针并返回该 segment。
    // 超出末尾返回 nullptr 且不改变状态；空时间线返回 nullptr。
    const AdaptiveSegment* seekTo(uint64_t positionMs);

    // 兼容接口：通用跳转（记录跳转目标并更新状态）。
    bool beginSeek(const SeekTarget& target);
    void endSeek();

    // ===== 分段获取上报 =====

    // 上报 segment 获取结果：Fetched 推进当前指针并缓存该 segment；
    // TransientFailure 进入 Recovering 并记录可重试错误；
    // PermanentFailure 进入 Failed 并记录不可重试错误。
    // 返回实际生效的结果（无 manifest 或未知 sequence 时归一为 PermanentFailure）。
    SegmentFetchOutcome reportSegment(uint64_t sequence, SegmentFetchOutcome outcome);

    // 兼容接口：根据 mpv 错误码分类分段失败。
    AdaptiveStreamError handleSegmentError(int mpvErrorCode, const std::string& context);

    // ===== 断网与重试 =====

    // 断网上报：进入 Recovering 并记录 NETWORK_DISCONNECTED 可重试错误；
    // 仅在已装载 manifest 且未处于终态时生效。
    void reportNetworkDisconnected();

    // 重试当前 segment：仅在 Recovering 且错误可重试时恢复为 Buffering 并返回 true；
    // 终态或不可重试返回 false 且不改变状态。
    bool retryCurrentSegment();

    // 网络中断恢复延迟（毫秒）：根据连续失败计数和配置计算线性退避。
    int64_t networkRecoveryDelay(int consecutiveFailures) const;

    // ===== 状态查询 =====
    AdaptiveStreamState state() const;
    uint64_t currentSequence() const;
    size_t bufferedCount() const;
    const std::vector<uint64_t>& bufferedSequences() const;
    AdaptiveStreamError lastError() const;
    bool isSeekPending() const;
    const std::string& currentUri() const;
    MediaKind currentKind() const;
    int retryCount() const;

    // ===== 生命周期 =====
    void reset();
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
    std::vector<AdaptiveSegment> segments_;
    std::vector<uint64_t> buffered_;
    uint64_t currentSequence_ = 0;
    bool seekPending_ = false;
    int retryCount_ = 0;
    int consecutiveFailures_ = 0;
    AdaptiveStreamError lastError_;

    const AdaptiveSegment* findSegment(uint64_t sequence) const;
    void fail(const std::string& domain, const std::string& code,
        const std::string& message, bool retryable);
    void buildMpvOptions();
    void clearManifestState();
};

} // namespace vidall
#endif