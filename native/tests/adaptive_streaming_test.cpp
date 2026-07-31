// T048/T049：HLS/DASH 自适应流测试
// 覆盖：有效清单、分段失败（瞬时/永久）、跳转定位、断网后重试、结构化脱敏错误。
// TDD 红阶段：先写测试，T049 实现使之通过。

#include <iostream>
#include <string>
#include <vector>

#include "AdaptiveStreaming.h"

namespace {

bool check(bool condition, const char* message)
{
    if (!condition) {
        std::cerr << "FAILED: " << message << '\n';
        return false;
    }
    return true;
}

bool checkEqual(std::uint64_t actual, std::uint64_t expected, const char* message)
{
    if (actual != expected) {
        std::cerr << "FAILED: " << message << " (expected " << expected
                  << ", got " << actual << ")\n";
        return false;
    }
    return true;
}

std::vector<vidall::AdaptiveSegment> makeTimeline()
{
    return {
        {1, 0, 6000},
        {2, 6000, 6000},
        {3, 12000, 6000},
        {4, 18000, 6000},
        {5, 24000, 6000},
    };
}

} // namespace

int main()
{
    bool passed = true;

    // ===== 1. 有效清单：装载成功，状态为 ManifestLoaded =====
    {
        vidall::AdaptiveStreaming stream;
        const auto err = stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://fixture.invalid/stream.m3u8", makeTimeline());
        passed &= check(err.code.empty(), "valid manifest produces no error");
        passed &= check(stream.state() == vidall::AdaptiveState::ManifestLoaded,
            "valid manifest transitions to ManifestLoaded");
        passed &= checkEqual(stream.currentSequence(), 1, "current sequence is first segment");
        passed &= checkEqual(stream.bufferedCount(), 0, "no segments buffered yet");
    }

    // ===== 2. 空清单：结构化错误，状态保持 Idle =====
    {
        vidall::AdaptiveStreaming stream;
        const auto err = stream.loadManifest(vidall::AdaptiveKind::Dash,
            "https://fixture.invalid/stream.mpd", {});
        passed &= check(!err.code.empty(), "empty manifest produces error");
        passed &= check(err.domain == "media", "empty manifest error domain is media");
        passed &= check(!err.retryable, "empty manifest error is not retryable");
        passed &= check(stream.state() == vidall::AdaptiveState::Idle,
            "empty manifest leaves state Idle");
    }

    // ===== 3. 无效 URI：userinfo / 非 http(s) 拒绝 =====
    {
        vidall::AdaptiveStreaming stream;
        const auto err = stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://user:pass@fixture.invalid/stream.m3u8", makeTimeline());
        passed &= check(err.code == "URL_USERINFO_FORBIDDEN",
            "manifest URI with userinfo is rejected");
        passed &= check(stream.state() == vidall::AdaptiveState::Idle,
            "userinfo URI leaves state Idle");
    }
    {
        vidall::AdaptiveStreaming stream;
        const auto err = stream.loadManifest(vidall::AdaptiveKind::Dash,
            "ftp://fixture.invalid/stream.mpd", makeTimeline());
        passed &= check(err.code == "INVALID_URI",
            "non-http(s) manifest URI is rejected");
    }

    // ===== 4. 分段成功获取：推进指针并缓存 =====
    {
        vidall::AdaptiveStreaming stream;
        stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://fixture.invalid/stream.m3u8", makeTimeline());
        const auto r1 = stream.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(r1 == vidall::SegmentFetchOutcome::Fetched,
            "fetched segment reports Fetched");
        passed &= checkEqual(stream.currentSequence(), 2, "fetched advances to next segment");
        passed &= checkEqual(stream.bufferedCount(), 1, "fetched segment is buffered");
        passed &= check(stream.state() == vidall::AdaptiveState::Playing,
            "fetched segment transitions to Playing");
        // 连续获取
        stream.reportSegment(2, vidall::SegmentFetchOutcome::Fetched);
        stream.reportSegment(3, vidall::SegmentFetchOutcome::Fetched);
        passed &= checkEqual(stream.currentSequence(), 4, "three segments advance to fourth");
        passed &= checkEqual(stream.bufferedCount(), 3, "three segments buffered");
    }

    // ===== 5. 瞬时分段失败：进入 Recovering，可重试 =====
    {
        vidall::AdaptiveStreaming stream;
        stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://fixture.invalid/stream.m3u8", makeTimeline());
        stream.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        const auto r = stream.reportSegment(2, vidall::SegmentFetchOutcome::TransientFailure);
        passed &= check(r == vidall::SegmentFetchOutcome::TransientFailure,
            "transient failure reports TransientFailure");
        passed &= check(stream.state() == vidall::AdaptiveState::Recovering,
            "transient failure enters Recovering");
        const auto err = stream.lastError();
        passed &= check(err.retryable, "transient failure error is retryable");
        passed &= check(err.domain == "network", "transient failure domain is network");
        passed &= check(!err.code.empty(), "transient failure has stable code");
    }

    // ===== 6. 永久分段失败：进入 Failed，不可重试 =====
    {
        vidall::AdaptiveStreaming stream;
        stream.loadManifest(vidall::AdaptiveKind::Dash,
            "https://fixture.invalid/stream.mpd", makeTimeline());
        const auto r = stream.reportSegment(1, vidall::SegmentFetchOutcome::PermanentFailure);
        passed &= check(r == vidall::SegmentFetchOutcome::PermanentFailure,
            "permanent failure reports PermanentFailure");
        passed &= check(stream.state() == vidall::AdaptiveState::Failed,
            "permanent failure enters Failed");
        const auto err = stream.lastError();
        passed &= check(!err.retryable, "permanent failure error is not retryable");
        passed &= check(err.domain == "media", "permanent failure domain is media");
    }

    // ===== 7. 跳转定位：返回包含位置的 segment =====
    {
        vidall::AdaptiveStreaming stream;
        stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://fixture.invalid/stream.m3u8", makeTimeline());
        const auto seg = stream.seekTo(13000);
        passed &= check(seg != nullptr, "seek within timeline returns a segment");
        passed &= check(seg != nullptr && seg->sequence == 3, "seek to 13s lands on segment 3");
        passed &= checkEqual(stream.currentSequence(), 3, "seek updates current sequence");
        // 跳转后获取，推进
        stream.reportSegment(3, vidall::SegmentFetchOutcome::Fetched);
        passed &= checkEqual(stream.currentSequence(), 4, "post-seek fetch advances to 4");
    }

    // ===== 8. 跳转超出末尾：返回 nullptr，状态不变 =====
    {
        vidall::AdaptiveStreaming stream;
        stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://fixture.invalid/stream.m3u8", makeTimeline());
        const auto seg = stream.seekTo(60000);
        passed &= check(seg == nullptr, "seek beyond end returns nullptr");
        passed &= checkEqual(stream.currentSequence(), 1, "seek beyond end keeps current at 1");
    }

    // ===== 9. 断网后重试：Recovering → retry → Buffering =====
    {
        vidall::AdaptiveStreaming stream;
        stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://fixture.invalid/stream.m3u8", makeTimeline());
        stream.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        stream.reportNetworkDisconnected();
        passed &= check(stream.state() == vidall::AdaptiveState::Recovering,
            "network disconnect enters Recovering");
        const auto err = stream.lastError();
        passed &= check(err.code == "NETWORK_DISCONNECTED",
            "network disconnect error code is NETWORK_DISCONNECTED");
        passed &= check(err.retryable, "network disconnect is retryable");
        const bool retried = stream.retryCurrentSegment();
        passed &= check(retried, "retry after disconnect is allowed");
        passed &= check(stream.state() == vidall::AdaptiveState::Buffering,
            "retry transitions to Buffering");
        // 重试后再次获取成功，推进
        stream.reportSegment(2, vidall::SegmentFetchOutcome::Fetched);
        passed &= checkEqual(stream.currentSequence(), 3, "post-retry fetch advances to 3");
        passed &= check(stream.state() == vidall::AdaptiveState::Playing,
            "post-retry fetch transitions to Playing");
    }

    // ===== 10. 永久失败后重试被拒绝 =====
    {
        vidall::AdaptiveStreaming stream;
        stream.loadManifest(vidall::AdaptiveKind::Dash,
            "https://fixture.invalid/stream.mpd", makeTimeline());
        stream.reportSegment(1, vidall::SegmentFetchOutcome::PermanentFailure);
        const bool retried = stream.retryCurrentSegment();
        passed &= check(!retried, "retry after permanent failure is rejected");
        passed &= check(stream.state() == vidall::AdaptiveState::Failed,
            "permanent failure remains Failed after rejected retry");
    }

    // ===== 11. 缓存命中：跳转回已获取的 segment 可重播 =====
    {
        vidall::AdaptiveStreaming stream;
        stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://fixture.invalid/stream.m3u8", makeTimeline());
        stream.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        stream.reportSegment(2, vidall::SegmentFetchOutcome::Fetched);
        const auto buffered = stream.bufferedSequences();
        passed &= check(std::find(buffered.begin(), buffered.end(), 1) != buffered.end(),
            "segment 1 is buffered after fetch");
        // 跳回 segment 1
        const auto seg = stream.seekTo(0);
        passed &= check(seg != nullptr && seg->sequence == 1, "seek to 0 lands on segment 1");
        passed &= checkEqual(stream.currentSequence(), 1, "seek back updates current to 1");
        // 已缓存，可重新获取推进
        stream.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        passed &= checkEqual(stream.currentSequence(), 2, "replay advances to 2");
    }

    // ===== 12. 结构化错误脱敏：不含凭据、完整路径或 URI =====
    {
        vidall::AdaptiveStreaming stream;
        // 即使上游传入带凭据的 URI，错误消息也不应回显凭据
        stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://user:pass@fixture.invalid/stream.m3u8", makeTimeline());
        const auto err = stream.lastError();
        passed &= check(err.message.find("user:pass") == std::string::npos,
            "error message must not echo userinfo credentials");
        passed &= check(err.message.find("pass") == std::string::npos,
            "error message must not echo password token");
    }

    // ===== 13. 未知 sequence 上报：归一为永久失败 =====
    {
        vidall::AdaptiveStreaming stream;
        stream.loadManifest(vidall::AdaptiveKind::Hls,
            "https://fixture.invalid/stream.m3u8", makeTimeline());
        const auto r = stream.reportSegment(999, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(r == vidall::SegmentFetchOutcome::PermanentFailure,
            "unknown sequence is normalized to PermanentFailure");
        passed &= check(stream.state() == vidall::AdaptiveState::Failed,
            "unknown sequence enters Failed");
    }

    // ===== 14. 未装载 manifest 即上报：归一为永久失败 =====
    {
        vidall::AdaptiveStreaming stream;
        const auto r = stream.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(r == vidall::SegmentFetchOutcome::PermanentFailure,
            "report without manifest is PermanentFailure");
        passed &= check(stream.state() == vidall::AdaptiveState::Failed,
            "report without manifest enters Failed");
    }

    // ===== 15. 断网在未装载时不生效 =====
    {
        vidall::AdaptiveStreaming stream;
        stream.reportNetworkDisconnected();
        passed &= check(stream.state() == vidall::AdaptiveState::Idle,
            "network disconnect without manifest leaves Idle");
    }

    return passed ? 0 : 1;
}
