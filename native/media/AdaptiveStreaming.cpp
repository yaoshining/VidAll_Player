#include "AdaptiveStreaming.h"
#include "PlayerErrorMapper.h"

#include <algorithm>
#include <sstream>

namespace vidall {

AdaptiveStreaming::AdaptiveStreaming(const AdaptiveStreamConfig& config)
    : config_(config)
{
}

AdaptiveStreamError AdaptiveStreaming::loadManifest(MediaKind kind, const std::string& uri,
    const std::vector<AdaptiveSegment>& segments,
    const std::vector<HeaderEntry>& headers)
{
    if (state_ == AdaptiveStreamState::Released) {
        fail("lifecycle", "SESSION_RELEASED", "Session has been released.", false);
        return lastError_;
    }

    // 仅接受 HLS 和 DASH kind
    if (kind != MediaKind::Hls && kind != MediaKind::Dash) {
        fail("input", "KIND_MISMATCH", "Adaptive streaming only accepts HLS or DASH kind.", false);
        state_ = AdaptiveStreamState::Idle;
        return lastError_;
    }

    // 使用 MediaLoader 校验 URI 格式
    if (uri.empty()) {
        fail("input", "INVALID_URI", "Media URI must not be empty.", false);
        state_ = AdaptiveStreamState::Idle;
        return lastError_;
    }

    MediaLoadRequest req;
    req.kind = kind;
    req.uri = uri;
    req.headers = headers;

    MediaLoader loader;
    const auto loadResult = loader.load(req);
    if (loadResult != MediaLoadResult::Accepted) {
        // 将 MediaLoader 的结果映射到结构化错误
        if (loadResult == MediaLoadResult::RejectedInvalidUri) {
            fail("input", "INVALID_URI", "Adaptive manifest URI validation failed.", false);
        } else if (loadResult == MediaLoadResult::RejectedKindMismatch) {
            fail("input", "URI_KIND_MISMATCH", "Adaptive media source requires an HTTP or HTTPS URI.", false);
        } else {
            fail("input", "REJECTED", "Manifest loading was rejected.", false);
        }
        state_ = AdaptiveStreamState::Idle;
        return lastError_;
    }

    // 空时间线拒绝
    if (segments.empty()) {
        fail("media", "INVALID_MANIFEST", "Adaptive manifest must contain at least one segment.", false);
        state_ = AdaptiveStreamState::Idle;
        return lastError_;
    }

    // 记录当前加载源
    currentUri_ = uri;
    currentKind_ = kind;
    segments_ = segments;
    currentSequence_ = segments_.front().sequence;
    buffered_.clear();
    retryCount_ = 0;
    consecutiveFailures_ = 0;
    seekPending_ = false;
    lastError_ = {};
    state_ = AdaptiveStreamState::ManifestLoaded;

    // 构建 mpv 选项
    buildMpvOptions();

    // 附加 HTTP headers 为 mpv 选项
    for (const auto& h : headers) {
        std::string headerOpt = h.name + ": " + h.value;
        mpvOptions_.push_back({"http-header-fields", headerOpt});
    }

    return {};
}

const std::vector<std::pair<std::string, std::string>>& AdaptiveStreaming::mpvOptions() const
{
    return mpvOptions_;
}

const AdaptiveSegment* AdaptiveStreaming::seekTo(uint64_t positionMs)
{
    if (segments_.empty()) {
        return nullptr;
    }
    for (const auto& seg : segments_) {
        if (positionMs >= seg.startMs && positionMs < seg.startMs + seg.durationMs) {
            currentSequence_ = seg.sequence;
            return &seg;
        }
    }
    // 超出末尾：不改变状态与当前指针
    return nullptr;
}

bool AdaptiveStreaming::beginSeek(const SeekTarget& target)
{
    if (state_ == AdaptiveStreamState::Released ||
        state_ == AdaptiveStreamState::Idle ||
        state_ == AdaptiveStreamState::Failed) {
        return false;
    }
    if (seekPending_) {
        return false;
    }
    seekPending_ = true;
    state_ = AdaptiveStreamState::SeekPending;
    (void)target;
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

SegmentFetchOutcome AdaptiveStreaming::reportSegment(uint64_t sequence, SegmentFetchOutcome outcome)
{
    if (state_ == AdaptiveStreamState::Idle || state_ == AdaptiveStreamState::Failed ||
        state_ == AdaptiveStreamState::Released) {
        fail("media", "PERMANENT_SEGMENT_FAILURE", "Segment reported without a loaded manifest.", false);
        state_ = AdaptiveStreamState::Failed;
        return SegmentFetchOutcome::PermanentFailure;
    }
    const auto* seg = findSegment(sequence);
    if (seg == nullptr) {
        fail("media", "PERMANENT_SEGMENT_FAILURE", "Segment sequence is not part of the manifest.", false);
        state_ = AdaptiveStreamState::Failed;
        return SegmentFetchOutcome::PermanentFailure;
    }
    if (outcome == SegmentFetchOutcome::Fetched) {
        // 缓存已获取 segment（去重），推进到下一条 segment
        if (std::find(buffered_.begin(), buffered_.end(), sequence) == buffered_.end()) {
            buffered_.push_back(sequence);
        }
        const auto it = std::find_if(segments_.begin(), segments_.end(),
            [sequence](const AdaptiveSegment& s) { return s.sequence == sequence; });
        const auto next = std::next(it);
        if (next != segments_.end()) {
            currentSequence_ = next->sequence;
        }
        state_ = AdaptiveStreamState::Playing;
        return SegmentFetchOutcome::Fetched;
    }
    if (outcome == SegmentFetchOutcome::TransientFailure) {
        fail("network", "TRANSIENT_SEGMENT_FAILURE",
            "Adaptive segment fetch failed transiently; retryable.", true);
        consecutiveFailures_++;
        retryCount_++;
        state_ = AdaptiveStreamState::Recovering;
        return SegmentFetchOutcome::TransientFailure;
    }
    fail("media", "PERMANENT_SEGMENT_FAILURE",
        "Adaptive segment fetch failed permanently.", false);
    state_ = AdaptiveStreamState::Failed;
    return SegmentFetchOutcome::PermanentFailure;
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
    return {mapped.domain, mapped.code, mapped.message, mapped.retryable};
}

void AdaptiveStreaming::reportNetworkDisconnected()
{
    if (segments_.empty() || state_ == AdaptiveStreamState::Idle ||
        state_ == AdaptiveStreamState::Failed || state_ == AdaptiveStreamState::Released) {
        return;
    }
    fail("network", "NETWORK_DISCONNECTED",
        "Network disconnected during adaptive streaming; retryable.", true);
    consecutiveFailures_++;
    retryCount_++;
    state_ = AdaptiveStreamState::Recovering;
}

bool AdaptiveStreaming::retryCurrentSegment()
{
    if (state_ != AdaptiveStreamState::Recovering || !lastError_.retryable) {
        return false;
    }
    state_ = AdaptiveStreamState::Buffering;
    return true;
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

uint64_t AdaptiveStreaming::currentSequence() const
{
    return currentSequence_;
}

size_t AdaptiveStreaming::bufferedCount() const
{
    return buffered_.size();
}

const std::vector<uint64_t>& AdaptiveStreaming::bufferedSequences() const
{
    return buffered_;
}

AdaptiveStreamError AdaptiveStreaming::lastError() const
{
    return lastError_;
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
    segments_.clear();
    buffered_.clear();
    currentSequence_ = 0;
    seekPending_ = false;
    retryCount_ = 0;
    consecutiveFailures_ = 0;
    mpvOptions_.clear();
    lastError_ = {};
}

void AdaptiveStreaming::release()
{
    state_ = AdaptiveStreamState::Released;
    currentUri_.clear();
    segments_.clear();
    buffered_.clear();
    currentSequence_ = 0;
    seekPending_ = false;
    retryCount_ = 0;
    consecutiveFailures_ = 0;
    mpvOptions_.clear();
    lastError_ = {};
}

void AdaptiveStreaming::simulateStateChange(AdaptiveStreamState newState)
{
    if (state_ == AdaptiveStreamState::Released) {
        return;
    }
    state_ = newState;
}

const AdaptiveSegment* AdaptiveStreaming::findSegment(uint64_t sequence) const
{
    for (const auto& seg : segments_) {
        if (seg.sequence == sequence) {
            return &seg;
        }
    }
    return nullptr;
}

void AdaptiveStreaming::fail(const std::string& domain, const std::string& code,
    const std::string& message, bool retryable)
{
    lastError_ = {domain, code, message, retryable};
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