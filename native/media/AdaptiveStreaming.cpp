#include "AdaptiveStreaming.h"
#include "PlayerErrorMapper.h"

#include <algorithm>
#include <sstream>

namespace vidall {

AdaptiveStreaming::AdaptiveStreaming(const AdaptiveStreamConfig& config)
    : config_(config)
{
}

MediaLoadResult AdaptiveStreaming::prepareLoad(MediaKind kind, const std::string& uri,
    const std::vector<HeaderEntry>& headers)
{
    if (state_ == AdaptiveStreamState::Released) {
        return MediaLoadResult::RejectedInvalidUri;
    }

    if (uri.empty()) {
        return MediaLoadResult::RejectedInvalidUri;
    }

    // 仅接受 HLS 和 DASH kind
    if (kind != MediaKind::Hls && kind != MediaKind::Dash) {
        return MediaLoadResult::RejectedKindMismatch;
    }

    // 使用 MediaLoader 校验 URI 格式
    MediaLoadRequest req;
    req.kind = kind;
    req.uri = uri;
    req.headers = headers;

    MediaLoader loader;
    const auto loadResult = loader.load(req);
    if (loadResult != MediaLoadResult::Accepted) {
        return loadResult;
    }

    // 记录当前加载源
    currentUri_ = uri;
    currentKind_ = kind;
    retryCount_ = 0;
    consecutiveFailures_ = 0;
    seekPending_ = false;
    state_ = AdaptiveStreamState::Loading;

    // 构建 mpv 选项
    buildMpvOptions();

    // 附加 HTTP headers 为 mpv 选项
    for (const auto& h : headers) {
        // 跳过可能包含凭据的敏感头部在日志中的暴露；
        // mpv 需要完整 header 值来执行 HTTP 请求。
        std::string headerOpt = h.name + ": " + h.value;
        mpvOptions_.push_back({"http-header-fields", headerOpt});
    }

    return MediaLoadResult::Accepted;
}

const std::vector<std::pair<std::string, std::string>>& AdaptiveStreaming::mpvOptions() const
{
    return mpvOptions_;
}

bool AdaptiveStreaming::beginSeek(const SeekTarget& target)
{
    if (state_ == AdaptiveStreamState::Released ||
        state_ == AdaptiveStreamState::Idle ||
        state_ == AdaptiveStreamState::Error) {
        return false;
    }
    if (seekPending_) {
        return false;
    }
    seekPending_ = true;
    state_ = AdaptiveStreamState::SeekPending;
    (void)target; // 跳转目标供上层使用
    return true;
}

void AdaptiveStreaming::endSeek()
{
    if (!seekPending_) {
        return;
    }
    seekPending_ = false;
    state_ = AdaptiveStreamState::Playing;
}

AdaptiveStreamError AdaptiveStreaming::handleSegmentError(int mpvErrorCode, const std::string& context)
{
    if (state_ == AdaptiveStreamState::Released) {
        return {"lifecycle", "SESSION_RELEASED", "Session has been released.", false};
    }

    const auto mapped = PlayerErrorMapper::mapMpvError(mpvErrorCode, context);
    consecutiveFailures_++;
    if (mapped.retryable) {
        retryCount_++;
    }
    // 瞬时错误：超时、网络断连、连接拒绝等 — 标记为可重试
    // 永久错误：格式不支持、无效参数 — 标记为不可重试
    return {mapped.domain, mapped.code, mapped.message, mapped.retryable};
}

int64_t AdaptiveStreaming::networkRecoveryDelay(int consecutiveFailures) const
{
    if (config_.maxRetries <= 0) {
        return 0;
    }
    if (consecutiveFailures > config_.maxRetries) {
        return 0;
    }
    // 线性退避：delay = baseMs * failureCount
    return config_.retryBaseMs * consecutiveFailures;
}

AdaptiveStreamState AdaptiveStreaming::state() const
{
    return state_;
}

bool AdaptiveStreaming::isSeekPending() const
{
    return seekPending_;
}

const std::string& AdaptiveStreaming::currentUri() const
{
    return currentUri_;
}

MediaKind AdaptiveStreaming::currentKind() const
{
    return currentKind_;
}

int AdaptiveStreaming::retryCount() const
{
    return retryCount_;
}

void AdaptiveStreaming::reset()
{
    state_ = AdaptiveStreamState::Idle;
    currentUri_.clear();
    seekPending_ = false;
    retryCount_ = 0;
    consecutiveFailures_ = 0;
    mpvOptions_.clear();
}

void AdaptiveStreaming::release()
{
    state_ = AdaptiveStreamState::Released;
    currentUri_.clear();
    seekPending_ = false;
    retryCount_ = 0;
    consecutiveFailures_ = 0;
    mpvOptions_.clear();
}

void AdaptiveStreaming::simulateStateChange(AdaptiveStreamState newState)
{
    if (state_ == AdaptiveStreamState::Released) {
        return;
    }
    state_ = newState;
}

void AdaptiveStreaming::buildMpvOptions()
{
    mpvOptions_.clear();

    // 缓存配置：cache=yes,duration=<sec>,min=<sec>,back=<sec>
    std::ostringstream cacheVal;
    cacheVal << "yes,"
             << config_.cacheDurationSec << ","
             << config_.cacheMinSec << ","
             << config_.cacheBackSec;
    mpvOptions_.push_back({"cache", cacheVal.str()});

    // 分段请求超时
    std::ostringstream timeoutVal;
    timeoutVal << config_.segmentTimeoutSec;
    mpvOptions_.push_back({"demuxer-lavf-o", "timeout=" + timeoutVal.str()});

    // 流层超时
    mpvOptions_.push_back({"stream-lavf-o", "timeout=" + timeoutVal.str()});
}

} // namespace vidall