#include "AdaptiveStreaming.h"

#include <algorithm>
#include <cctype>

namespace vidall {

namespace {

std::string toLower(const std::string& value)
{
    std::string out = value;
    std::transform(out.begin(), out.end(), out.begin(),
        [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return out;
}

} // namespace

AdaptiveError AdaptiveStreaming::loadManifest(AdaptiveKind, const std::string& uri,
    const std::vector<AdaptiveSegment>& segments)
{
    // URI 校验：必须 http/https 且不含 userinfo。错误消息不回显凭据。
    if (!isHttpUri(uri)) {
        fail("INVALID_URI", "Adaptive manifest URI must be HTTP or HTTPS.", false);
        state_ = AdaptiveState::Idle;
        return lastError_;
    }
    if (hasUserinfo(uri)) {
        fail("URL_USERINFO_FORBIDDEN", "Media URI must not contain user information.", false);
        state_ = AdaptiveState::Idle;
        return lastError_;
    }
    if (segments.empty()) {
        fail("INVALID_MANIFEST", "Adaptive manifest must contain at least one segment.", false);
        state_ = AdaptiveState::Idle;
        return lastError_;
    }
    segments_ = segments;
    currentSequence_ = segments_.front().sequence;
    buffered_.clear();
    lastError_ = {};
    state_ = AdaptiveState::ManifestLoaded;
    return {};
}

const AdaptiveSegment* AdaptiveStreaming::seekTo(std::uint64_t positionMs)
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
    // 超出末尾：不改变状态与当前指针。
    return nullptr;
}

SegmentFetchOutcome AdaptiveStreaming::reportSegment(std::uint64_t sequence, SegmentFetchOutcome outcome)
{
    if (state_ == AdaptiveState::Idle || state_ == AdaptiveState::Failed) {
        fail("PERMANENT_SEGMENT_FAILURE", "Segment reported without a loaded manifest.", false);
        state_ = AdaptiveState::Failed;
        return SegmentFetchOutcome::PermanentFailure;
    }
    const auto* seg = findSegment(sequence);
    if (seg == nullptr) {
        fail("PERMANENT_SEGMENT_FAILURE", "Segment sequence is not part of the manifest.", false);
        state_ = AdaptiveState::Failed;
        return SegmentFetchOutcome::PermanentFailure;
    }
    if (outcome == SegmentFetchOutcome::Fetched) {
        // 缓存已获取 segment（去重），推进到下一条 segment。
        if (std::find(buffered_.begin(), buffered_.end(), sequence) == buffered_.end()) {
            buffered_.push_back(sequence);
        }
        const auto it = std::find_if(segments_.begin(), segments_.end(),
            [sequence](const AdaptiveSegment& s) { return s.sequence == sequence; });
        const auto next = std::next(it);
        if (next != segments_.end()) {
            currentSequence_ = next->sequence;
        }
        // 首次获取或重试后恢复进入 Playing；后续获取保持 Playing。
        state_ = AdaptiveState::Playing;
        return SegmentFetchOutcome::Fetched;
    }
    if (outcome == SegmentFetchOutcome::TransientFailure) {
        fail("TRANSIENT_SEGMENT_FAILURE", "Adaptive segment fetch failed transiently; retryable.", true);
        state_ = AdaptiveState::Recovering;
        return SegmentFetchOutcome::TransientFailure;
    }
    fail("PERMANENT_SEGMENT_FAILURE", "Adaptive segment fetch failed permanently.", false);
    state_ = AdaptiveState::Failed;
    return SegmentFetchOutcome::PermanentFailure;
}

void AdaptiveStreaming::reportNetworkDisconnected()
{
    if (segments_.empty() || state_ == AdaptiveState::Idle || state_ == AdaptiveState::Failed) {
        return;
    }
    fail("NETWORK_DISCONNECTED", "Network disconnected during adaptive streaming; retryable.", true);
    state_ = AdaptiveState::Recovering;
}

bool AdaptiveStreaming::retryCurrentSegment()
{
    if (state_ != AdaptiveState::Recovering || !lastError_.retryable) {
        return false;
    }
    state_ = AdaptiveState::Buffering;
    return true;
}

AdaptiveState AdaptiveStreaming::state() const { return state_; }
std::uint64_t AdaptiveStreaming::currentSequence() const { return currentSequence_; }
std::size_t AdaptiveStreaming::bufferedCount() const { return buffered_.size(); }
const std::vector<std::uint64_t>& AdaptiveStreaming::bufferedSequences() const { return buffered_; }
AdaptiveError AdaptiveStreaming::lastError() const { return lastError_; }

const AdaptiveSegment* AdaptiveStreaming::findSegment(std::uint64_t sequence) const
{
    for (const auto& seg : segments_) {
        if (seg.sequence == sequence) {
            return &seg;
        }
    }
    return nullptr;
}

void AdaptiveStreaming::fail(const std::string& code, const std::string& message, bool retryable)
{
    std::string domain;
    if (code == "INVALID_URI" || code == "URL_USERINFO_FORBIDDEN") {
        domain = "input";
    } else if (code == "INVALID_MANIFEST" || code == "PERMANENT_SEGMENT_FAILURE") {
        domain = "media";
    } else {
        domain = "network";
    }
    lastError_ = {domain, code, message, retryable};
}

bool AdaptiveStreaming::isHttpUri(const std::string& uri)
{
    const std::string lowered = toLower(uri);
    return lowered.rfind("http://", 0) == 0 || lowered.rfind("https://", 0) == 0;
}

bool AdaptiveStreaming::hasUserinfo(const std::string& uri)
{
    const std::size_t schemeEnd = uri.find("://");
    if (schemeEnd == std::string::npos) {
        return false;
    }
    const std::size_t authorityStart = schemeEnd + 3;
    const std::size_t authorityEnd = uri.find_first_of("/?#", authorityStart);
    const std::string authority = (authorityEnd == std::string::npos)
        ? uri.substr(authorityStart)
        : uri.substr(authorityStart, authorityEnd - authorityStart);
    return authority.find('@') != std::string::npos;
}

} // namespace vidall
