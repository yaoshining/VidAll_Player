#ifndef VIDALL_ADAPTIVE_STREAMING_H
#define VIDALL_ADAPTIVE_STREAMING_H

#include <cstdint>
#include <string>
#include <vector>

namespace vidall {

// T048/T049：HLS/DASH 自适应流控制器契约。
// 本模块只建模 manifest 装载、segment 时间线、跳转、分段失败与断网重试的
// 确定性状态机；真实网络 IO 与 libmpv demux 由调用方在 native bridge 注入，
// 此处不伪造播放或首帧。所有错误须脱敏（无凭据、完整路径或敏感查询）。

enum class AdaptiveKind {
    Hls,
    Dash,
};

enum class AdaptiveState {
    Idle,
    ManifestLoaded,
    Buffering,
    Playing,
    Recovering,
    Failed,
};

// 分段获取结果：调用方（native bridge）上报每条 segment 的获取结局。
enum class SegmentFetchOutcome {
    Fetched,           // 成功获取并解码，推进到下一条 segment
    TransientFailure,  // 瞬时失败（5xx、超时、连接重置），可重试
    PermanentFailure,  // 永久失败（404、解析错误、格式不支持），不可重试
};

struct AdaptiveSegment {
    std::uint64_t sequence;
    std::uint64_t startMs;
    std::uint64_t durationMs;
};

struct AdaptiveError {
    std::string domain;
    std::string code;
    std::string message;
    bool retryable = false;
};

class AdaptiveStreaming {
public:
    // 装载 manifest：校验 URI（http/https、无 userinfo）并存储已解析的 segment 时间线。
    // 成功返回空错误并将状态置为 ManifestLoaded；失败返回结构化错误且状态保持 Idle/Failed。
    AdaptiveError loadManifest(AdaptiveKind kind, const std::string& uri,
        const std::vector<AdaptiveSegment>& segments);

    // 跳转到指定毫秒位置：定位包含该位置的 segment，更新当前指针并返回该 segment。
    // 超出末尾返回 nullptr 且不改变状态；空时间线返回 nullptr。
    const AdaptiveSegment* seekTo(std::uint64_t positionMs);

    // 上报 segment 获取结果：Fetched 推进当前指针并缓存该 segment；
    // TransientFailure 进入 Recovering 并记录可重试错误；
    // PermanentFailure 进入 Failed 并记录不可重试错误。
    // 返回实际生效的结果（无 manifest 或未知 sequence 时归一为 PermanentFailure）。
    SegmentFetchOutcome reportSegment(std::uint64_t sequence, SegmentFetchOutcome outcome);

    // 断网上报：进入 Recovering 并记录 NETWORK_DISCONNECTED 可重试错误；
    // 仅在已装载 manifest 且未处于终态时生效。
    void reportNetworkDisconnected();

    // 重试当前 segment：仅在 Recovering 且错误可重试时恢复为 Buffering 并返回 true；
    // 终态或不可重试返回 false 且不改变状态。
    bool retryCurrentSegment();

    AdaptiveState state() const;
    std::uint64_t currentSequence() const;
    std::size_t bufferedCount() const;
    const std::vector<std::uint64_t>& bufferedSequences() const;
    AdaptiveError lastError() const;

private:
    AdaptiveState state_ = AdaptiveState::Idle;
    std::uint64_t currentSequence_ = 0;
    std::vector<AdaptiveSegment> segments_;
    std::vector<std::uint64_t> buffered_;
    AdaptiveError lastError_;

    const AdaptiveSegment* findSegment(std::uint64_t sequence) const;
    void fail(const std::string& code, const std::string& message, bool retryable);
    static bool isHttpUri(const std::string& uri);
    static bool hasUserinfo(const std::string& uri);
};

} // namespace vidall
#endif
