// T048: HLS/DASH 自适应流测试
// 覆盖：有效清单、分段失败、跳转、断网后重试和结构化错误
// 合并设计：segment 时间线 + mpv 选项 + 断网/重试 + 错误脱敏
// TDD 红阶段：先写失败测试，T049 实现后全部通过。

#include <iostream>
#include <string>
#include <vector>

#include "AdaptiveStreaming.h"
#include "MediaLoader.h"

namespace {

bool check(bool condition, const char* message)
{
    if (!condition) {
        std::cerr << "FAILED: " << message << '\n';
        return false;
    }
    return true;
}

bool checkContains(const std::string& haystack, const std::string& needle, const char* message)
{
    if (haystack.find(needle) == std::string::npos) {
        std::cerr << "FAILED: " << message << " (expected '" << needle
                  << "' in '" << haystack << "')\n";
        return false;
    }
    return true;
}

bool checkNotContains(const std::string& haystack, const std::string& needle, const char* message)
{
    if (haystack.find(needle) != std::string::npos) {
        std::cerr << "FAILED: " << message << " (unexpected '" << needle
                  << "' in '" << haystack << "')\n";
        return false;
    }
    return true;
}

// 辅助：构造 3-segment 时间线
std::vector<vidall::AdaptiveSegment> makeTimeline()
{
    return {
        {1, 0, 10000},     // segment 1: 0-10s
        {2, 10000, 10000}, // segment 2: 10-20s
        {3, 20000, 10000}, // segment 3: 20-30s
    };
}

} // namespace

int main()
{
    bool passed = true;

    // =============================================
    // 1. 正常路径：HLS 清单加载 + segment 时间线
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Hls,
            "https://example.com/live/stream.m3u8",
            makeTimeline(),
            {});
        passed &= check(result.code.empty(),
            "HLS manifest load succeeds with no error");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::ManifestLoaded,
            "HLS state is ManifestLoaded after loadManifest");
        passed &= check(streamer.currentUri() == "https://example.com/live/stream.m3u8",
            "HLS current URI is recorded");
        passed &= check(streamer.currentKind() == vidall::MediaKind::Hls,
            "HLS current kind is Hls");
        passed &= check(streamer.currentSequence() == 1,
            "HLS current sequence starts at first segment");
        passed &= check(streamer.bufferedCount() == 0,
            "No segments buffered initially");
    }

    // =============================================
    // 2. 正常路径：DASH 清单加载
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Dash,
            "https://example.com/vod/manifest.mpd",
            makeTimeline(),
            {});
        passed &= check(result.code.empty(),
            "DASH manifest load succeeds with no error");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::ManifestLoaded,
            "DASH state is ManifestLoaded after loadManifest");
        passed &= check(streamer.currentKind() == vidall::MediaKind::Dash,
            "DASH current kind is Dash");
    }

    // =============================================
    // 3. 正常路径：HLS HTTP URI
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Hls,
            "http://example.com/stream.m3u8",
            makeTimeline(),
            {});
        passed &= check(result.code.empty(),
            "HLS with HTTP URI is accepted");
    }

    // =============================================
    // 4. 失败路径：非自适应 kind
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Http,
            "http://example.com/media.mp4",
            makeTimeline(),
            {});
        passed &= check(!result.code.empty(),
            "HTTP kind is rejected for adaptive streaming");
        passed &= check(result.domain == "input",
            "HTTP kind rejection domain is input");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Idle,
            "State returns to Idle after kind mismatch");
    }

    // =============================================
    // 5. 失败路径：LocalFile kind
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.loadManifest(
            vidall::MediaKind::LocalFile,
            "file:///data/media/video.mp4",
            makeTimeline(),
            {});
        passed &= check(!result.code.empty(),
            "LocalFile kind is rejected for adaptive streaming");
    }

    // =============================================
    // 6. 失败路径：空 URI
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Hls,
            "",
            makeTimeline(),
            {});
        passed &= check(!result.code.empty(),
            "Empty URI is rejected for adaptive streaming");
        passed &= check(result.domain == "input",
            "Empty URI rejection domain is input");
    }

    // =============================================
    // 7. 失败路径：URI 含 userinfo
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Hls,
            "https://user:secret@example.com/stream.m3u8",
            makeTimeline(),
            {});
        passed &= check(!result.code.empty(),
            "HLS URI with userinfo is rejected");
        passed &= check(result.domain == "input",
            "Userinfo URI rejection domain is input");
        passed &= check(result.code == "URL_USERINFO_FORBIDDEN",
            "Userinfo URI rejection code is URL_USERINFO_FORBIDDEN (via PlayerErrorMapper)");
    }

    // =============================================
    // 8. 失败路径：空 segment 时间线
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Hls,
            "https://example.com/stream.m3u8",
            {}, // 空时间线
            {});
        passed &= check(!result.code.empty(),
            "Empty segment timeline is rejected");
        passed &= check(result.domain == "media",
            "Empty timeline rejection domain is media");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Idle,
            "State returns to Idle after empty timeline");
    }

    // =============================================
    // 9. DASH 非 HTTP(S) URI 拒绝
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Dash,
            "ftp://example.com/manifest.mpd",
            makeTimeline(),
            {});
        passed &= check(!result.code.empty(),
            "DASH with FTP URI is rejected");
        passed &= check(result.domain == "input",
            "FTP URI rejection domain is input");
    }

    // =============================================
    // 10. MPV 缓存选项：HLS
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        const auto& opts = streamer.mpvOptions();
        bool hasCache = false;
        for (const auto& kv : opts) {
            if (kv.first == "cache") { hasCache = true; break; }
        }
        passed &= check(hasCache,
            "HLS load produces cache option for mpv");
        passed &= check(opts.size() >= 3,
            "HLS load produces at least cache, demuxer-lavf-o and stream-lavf-o options");
    }

    // =============================================
    // 11. 自定义缓存配置
    // =============================================
    {
        vidall::AdaptiveStreamConfig config;
        config.cacheDurationSec = 120;
        config.cacheMinSec = 10;
        config.cacheBackSec = 60;
        vidall::AdaptiveStreaming streamer(config);
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        const auto& opts = streamer.mpvOptions();
        bool foundCacheValue = false;
        for (const auto& kv : opts) {
            if (kv.first == "cache" && kv.second.find("120") != std::string::npos) {
                foundCacheValue = true;
            }
        }
        passed &= check(foundCacheValue,
            "Custom cache duration is reflected in mpv options");
    }

    // =============================================
    // 12. Segment 获取：成功获取 + 缓存 + 推进
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        const auto r1 = streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(r1 == vidall::SegmentFetchOutcome::Fetched,
            "Segment 1 fetch returns Fetched");
        passed &= check(streamer.bufferedCount() == 1,
            "One segment buffered after first fetch");
        passed &= check(streamer.currentSequence() == 2,
            "Current sequence advances to 2 after first fetch");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Playing,
            "State is Playing after successful fetch");

        const auto r2 = streamer.reportSegment(2, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(r2 == vidall::SegmentFetchOutcome::Fetched,
            "Segment 2 fetch returns Fetched");
        passed &= check(streamer.bufferedCount() == 2,
            "Two segments buffered after second fetch");
        passed &= check(streamer.currentSequence() == 3,
            "Current sequence advances to 3 after second fetch");

        const auto r3 = streamer.reportSegment(3, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(r3 == vidall::SegmentFetchOutcome::Fetched,
            "Segment 3 fetch returns Fetched");
        passed &= check(streamer.bufferedCount() == 3,
            "Three segments buffered after third fetch");
        passed &= check(streamer.currentSequence() == 3,
            "Current sequence stays at 3 after last segment fetch");
    }

    // =============================================
    // 13. Segment 获取：重复 segment 不重复缓存
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(streamer.bufferedCount() == 1,
            "Duplicate segment 1 does not duplicate in buffer");
    }

    // =============================================
    // 14. Segment 获取：瞬时失败 → Recovering
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);

        const auto r = streamer.reportSegment(2, vidall::SegmentFetchOutcome::TransientFailure);
        passed &= check(r == vidall::SegmentFetchOutcome::TransientFailure,
            "Transient failure returns TransientFailure");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Recovering,
            "State is Recovering after transient failure");
        passed &= check(streamer.lastError().retryable,
            "Transient failure error is retryable");
        passed &= check(streamer.lastError().domain == "network",
            "Transient failure domain is network");
        passed &= check(streamer.retryCount() == 1,
            "Retry count is 1 after transient failure");
    }

    // =============================================
    // 15. Segment 获取：永久失败 → Failed
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);

        const auto r = streamer.reportSegment(2, vidall::SegmentFetchOutcome::PermanentFailure);
        passed &= check(r == vidall::SegmentFetchOutcome::PermanentFailure,
            "Permanent failure returns PermanentFailure");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Failed,
            "State is Failed after permanent failure");
        passed &= check(!streamer.lastError().retryable,
            "Permanent failure error is not retryable");
        passed &= check(streamer.lastError().domain == "media",
            "Permanent failure domain is media");
    }

    // =============================================
    // 16. Segment 获取：未知 sequence 归一为永久失败
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);

        const auto r = streamer.reportSegment(99, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(r == vidall::SegmentFetchOutcome::PermanentFailure,
            "Unknown sequence is normalized to PermanentFailure");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Failed,
            "State is Failed after unknown sequence");
    }

    // =============================================
    // 17. Segment 获取：无 manifest 时上报归一为永久失败
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto r = streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(r == vidall::SegmentFetchOutcome::PermanentFailure,
            "Segment report without manifest is PermanentFailure");
    }

    // =============================================
    // 18. 精准跳转：seekTo 按毫秒定位 segment
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        const auto* seg1 = streamer.seekTo(5000);
        passed &= check(seg1 != nullptr, "seekTo 5s finds a segment");
        passed &= check(seg1->sequence == 1, "seekTo 5s lands on segment 1");
        passed &= check(streamer.currentSequence() == 1,
            "Current sequence updated to 1 after seekTo");

        const auto* seg2 = streamer.seekTo(15000);
        passed &= check(seg2 != nullptr, "seekTo 15s finds a segment");
        passed &= check(seg2->sequence == 2, "seekTo 15s lands on segment 2");

        const auto* seg3 = streamer.seekTo(25000);
        passed &= check(seg3 != nullptr, "seekTo 25s finds a segment");
        passed &= check(seg3->sequence == 3, "seekTo 25s lands on segment 3");
    }

    // =============================================
    // 19. 精准跳转：seekTo 超出末尾
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        const auto* seg = streamer.seekTo(35000);
        passed &= check(seg == nullptr,
            "seekTo beyond end returns nullptr");
    }

    // =============================================
    // 20. 精准跳转：边界测试
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        const auto* seg = streamer.seekTo(0);
        passed &= check(seg != nullptr && seg->sequence == 1,
            "seekTo 0ms lands on segment 1");

        const auto* seg2 = streamer.seekTo(10000);
        passed &= check(seg2 != nullptr && seg2->sequence == 2,
            "seekTo 10000ms lands on segment 2 (boundary)");
    }

    // =============================================
    // 21. 通用跳转：beginSeek / endSeek
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.simulateStateChange(vidall::AdaptiveStreamState::Playing);

        vidall::SeekTarget target;
        target.type = vidall::SeekTarget::Percent;
        target.value = 50.0;
        const auto ok = streamer.beginSeek(target);
        passed &= check(ok, "Seek is accepted in Playing state");
        passed &= check(streamer.isSeekPending(), "Seek is pending after beginSeek");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::SeekPending,
            "State is SeekPending after beginSeek");

        streamer.endSeek();
        passed &= check(!streamer.isSeekPending(), "Seek is not pending after endSeek");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Playing,
            "State returns to Playing after endSeek");
    }

    // =============================================
    // 22. 通用跳转：Idle 状态拒绝
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        vidall::SeekTarget target;
        target.type = vidall::SeekTarget::Relative;
        target.value = 10.0;
        const auto ok = streamer.beginSeek(target);
        passed &= check(!ok, "Seek is rejected in Idle state");
        passed &= check(!streamer.isSeekPending(), "Seek is not pending after rejected seek");
    }

    // =============================================
    // 23. 通用跳转：Failed 状态拒绝
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        streamer.reportSegment(2, vidall::SegmentFetchOutcome::PermanentFailure);

        vidall::SeekTarget target;
        target.type = vidall::SeekTarget::Percent;
        target.value = 30.0;
        const auto ok = streamer.beginSeek(target);
        passed &= check(!ok, "Seek is rejected in Failed state");
    }

    // =============================================
    // 24. 通用跳转：已释放状态拒绝
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.release();
        vidall::SeekTarget target;
        target.type = vidall::SeekTarget::Percent;
        target.value = 50.0;
        const auto ok = streamer.beginSeek(target);
        passed &= check(!ok, "Seek is rejected after release");
    }

    // =============================================
    // 25. 断网上报：进入 Recovering
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        streamer.simulateStateChange(vidall::AdaptiveStreamState::Playing);

        streamer.reportNetworkDisconnected();
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Recovering,
            "State is Recovering after network disconnect");
        passed &= check(streamer.lastError().domain == "network",
            "Network disconnect error domain is network");
        passed &= check(streamer.lastError().retryable,
            "Network disconnect error is retryable");
        passed &= check(streamer.retryCount() == 1,
            "Retry count incremented after network disconnect");
    }

    // =============================================
    // 26. 断网后重试：Recovering → Buffering
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        streamer.simulateStateChange(vidall::AdaptiveStreamState::Playing);
        streamer.reportNetworkDisconnected();

        const auto ok = streamer.retryCurrentSegment();
        passed &= check(ok, "Retry is accepted in Recovering state with retryable error");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Buffering,
            "State transitions to Buffering after retry");
    }

    // =============================================
    // 27. 重试拒绝：Failed 状态不可重试
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        streamer.reportSegment(2, vidall::SegmentFetchOutcome::PermanentFailure);

        const auto ok = streamer.retryCurrentSegment();
        passed &= check(!ok, "Retry is rejected in Failed state with non-retryable error");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Failed,
            "State remains Failed after rejected retry");
    }

    // =============================================
    // 28. 断网上报：无 manifest 时无效
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.reportNetworkDisconnected();
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Idle,
            "Network disconnect without manifest does not change state");
    }

    // =============================================
    // 29. 缓存序列查询
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        streamer.reportSegment(2, vidall::SegmentFetchOutcome::Fetched);

        const auto& buf = streamer.bufferedSequences();
        passed &= check(buf.size() == 2, "Buffered sequences has 2 entries");
        passed &= check(buf[0] == 1, "First buffered sequence is 1");
        passed &= check(buf[1] == 2, "Second buffered sequence is 2");
    }

    // =============================================
    // 30. 缓存命中回放：已缓存的 segment 再次 seekTo
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        streamer.reportSegment(2, vidall::SegmentFetchOutcome::Fetched);

        const auto* seg = streamer.seekTo(5000);
        passed &= check(seg != nullptr && seg->sequence == 1,
            "SeekTo cached segment 1 succeeds");
        passed &= check(streamer.bufferedCount() == 2,
            "Buffered count unchanged after seeking to cached segment");
    }

    // =============================================
    // 31. handleSegmentError：瞬时错误（超时 -7）
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        const auto err = streamer.handleSegmentError(-7, "network timeout");
        passed &= check(err.retryable, "Segment timeout is retryable");
        passed &= check(err.domain == "media", "Segment timeout domain is media (via PlayerErrorMapper)");
    }

    // =============================================
    // 32. handleSegmentError：永久错误（-4）
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        const auto err = streamer.handleSegmentError(-4, "unsupported format");
        passed &= check(!err.retryable, "Unsupported format is not retryable");
        passed &= check(err.domain == "media", "Unsupported format domain is media");
    }

    // =============================================
    // 33. handleSegmentError：错误消息脱敏
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        const auto err = streamer.handleSegmentError(-7,
            "******host.example.com/segment.ts");
        passed &= checkNotContains(err.message, "secret",
            "Segment error message must not contain userinfo credentials");
        passed &= checkNotContains(err.message, "user:",
            "Segment error message must not contain userinfo prefix");
    }

    // =============================================
    // 34. 网络恢复延迟：首次失败
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto delay = streamer.networkRecoveryDelay(1);
        passed &= check(delay > 0, "First network failure suggests positive retry delay");
    }

    // =============================================
    // 35. 网络恢复延迟：线性退避
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        const auto delay1 = streamer.networkRecoveryDelay(1);
        const auto delay2 = streamer.networkRecoveryDelay(2);
        passed &= check(delay2 > delay1,
            "Second failure delay is longer than first (linear backoff)");
    }

    // =============================================
    // 36. 网络恢复延迟：超过最大重试次数
    // =============================================
    {
        vidall::AdaptiveStreamConfig config;
        config.maxRetries = 2;
        vidall::AdaptiveStreaming streamer(config);
        const auto delay = streamer.networkRecoveryDelay(3);
        passed &= check(delay == 0,
            "Beyond max retries, network recovery delay is 0 (no retry)");
    }

    // =============================================
    // 37. 网络恢复延迟：maxRetries=0
    // =============================================
    {
        vidall::AdaptiveStreamConfig config;
        config.maxRetries = 0;
        vidall::AdaptiveStreaming streamer(config);
        const auto delay = streamer.networkRecoveryDelay(1);
        passed &= check(delay == 0,
            "With maxRetries=0, no retry is suggested");
    }

    // =============================================
    // 38. 切源重置
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        streamer.simulateStateChange(vidall::AdaptiveStreamState::Playing);
        streamer.handleSegmentError(-7, "timeout");
        streamer.reset();
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Idle,
            "State is Idle after reset");
        passed &= check(!streamer.isSeekPending(),
            "No seek pending after reset");
        passed &= check(streamer.retryCount() == 0,
            "Retry count is 0 after reset");
        passed &= check(streamer.currentUri().empty(),
            "Current URI is empty after reset");
        passed &= check(streamer.bufferedCount() == 0,
            "Buffered count is 0 after reset");
        passed &= check(streamer.currentSequence() == 0,
            "Current sequence is 0 after reset");
    }

    // =============================================
    // 39. 释放
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.release();
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Released,
            "State is Released after release");
        passed &= check(streamer.currentUri().empty(),
            "Current URI is empty after release");
        passed &= check(streamer.bufferedCount() == 0,
            "Buffered count is 0 after release");
    }

    // =============================================
    // 40. 释放后操作拒绝
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.release();
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        passed &= check(!result.code.empty(),
            "loadManifest is rejected after release");
        passed &= check(result.domain == "lifecycle",
            "Post-release rejection domain is lifecycle");
    }

    // =============================================
    // 41. 带 headers 的 HLS 加载
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        std::vector<vidall::HeaderEntry> headers;
        headers.push_back({"authorization", "Bearer test-token-123"});
        const auto result = streamer.loadManifest(
            vidall::MediaKind::Hls,
            "https://example.com/stream.m3u8",
            makeTimeline(),
            headers);
        passed &= check(result.code.empty(),
            "HLS with authorization header is accepted");
        const auto& opts = streamer.mpvOptions();
        bool hasHeader = false;
        for (const auto& kv : opts) {
            if (kv.first == "http-header-fields" &&
                kv.second.find("authorization") != std::string::npos) {
                hasHeader = true;
            }
        }
        passed &= check(hasHeader,
            "Authorization header is forwarded to mpv options");
    }

    // =============================================
    // 42. 完整断网→恢复→播放生命周期
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Playing,
            "Playing after segment 1");

        streamer.reportNetworkDisconnected();
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Recovering,
            "Recovering after network disconnect");

        streamer.retryCurrentSegment();
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Buffering,
            "Buffering after retry");

        streamer.reportSegment(2, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Playing,
            "Playing after recovery");
        passed &= check(streamer.bufferedCount() == 2,
            "Both segments buffered after recovery");
    }

    // =============================================
    // 43. simulateStateChange：Released 状态下无效
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.release();
        streamer.simulateStateChange(vidall::AdaptiveStreamState::Playing);
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Released,
            "simulateStateChange is ignored in Released state");
    }

    // =============================================
    // 44. reportSegment 在 Released 状态下不改变终态
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        streamer.release();
        const auto r = streamer.reportSegment(1, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(r == vidall::SegmentFetchOutcome::PermanentFailure,
            "reportSegment after release returns PermanentFailure");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Released,
            "State remains Released after reportSegment on released session");
    }

    // =============================================
    // 45. 加载失败后旧状态清除
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        // 先成功加载一次
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::ManifestLoaded,
            "First load succeeds");

        // 再用空 URI 加载失败：旧 manifest 数据应被清除
        const auto result = streamer.loadManifest(vidall::MediaKind::Hls, "", makeTimeline(), {});
        passed &= check(!result.code.empty(), "Empty URI is rejected on second load");
        passed &= check(streamer.currentUri().empty(), "URI cleared after failed load");
        passed &= check(streamer.bufferedCount() == 0, "Buffered cleared after failed load");
        passed &= check(streamer.currentSequence() == 0, "Sequence reset after failed load");
        passed &= check(streamer.mpvOptions().empty(), "mpvOptions cleared after failed load");
    }

    // =============================================
    // 46. 多条 header 合并为单个 http-header-fields
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        std::vector<vidall::HeaderEntry> headers = {
            {"Authorization", "Bearer token123"},
            {"X-Custom", "value1"}
        };
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), headers);

        const auto& opts = streamer.mpvOptions();
        int headerFieldCount = 0;
        for (const auto& opt : opts) {
            if (opt.first == "http-header-fields") {
                headerFieldCount++;
                // 两条 header 应合并在同一个值中
                passed &= check(opt.second.find(",") != std::string::npos,
                    "Multiple headers are joined with comma");
                passed &= check(opt.second.find("Authorization") != std::string::npos,
                    "Joined value contains first header");
                passed &= check(opt.second.find("X-Custom") != std::string::npos,
                    "Joined value contains second header");
            }
        }
        passed &= check(headerFieldCount == 1,
            "Only one http-header-fields entry for multiple headers");
    }

    // =============================================
    // 47. header value 特殊字符转义
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        std::vector<vidall::HeaderEntry> headers = {
            {"Cookie", "session=abc,123; lang=en:zh"},
            {"X-Path", "C:\\test\\file"}
        };
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), headers);

        const auto& opts = streamer.mpvOptions();
        for (const auto& opt : opts) {
            if (opt.first == "http-header-fields") {
                // 逗号与反斜杠需转义以避免破坏 mpv 列表解析；冒号无需转义
                passed &= check(opt.second.find("session=abc\\,123; lang=en:zh") != std::string::npos,
                    "Comma in Cookie value is escaped, colon preserved");
                passed &= check(opt.second.find("C:\\\\test\\\\file") != std::string::npos,
                    "Backslashes in path value are escaped");
            }
        }
    }

    // =============================================
    // 48. reportSegment 在 Failed 状态下保留之前的失败原因
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        // 先触发一个永久错误使状态进入 Failed
        streamer.handleSegmentError(-4, "unsupported format");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Failed,
            "State is Failed after permanent error");
        const auto firstError = streamer.lastError();
        passed &= check(firstError.code == "PERMANENT_SEGMENT_FAILURE" || !firstError.retryable,
            "First error is recorded");

        // 再次上报 segment 不应覆盖之前的失败原因
        const auto outcome = streamer.reportSegment(0, vidall::SegmentFetchOutcome::Fetched);
        passed &= check(outcome == vidall::SegmentFetchOutcome::PermanentFailure,
            "reportSegment on Failed returns PermanentFailure");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Failed,
            "State remains Failed after reportSegment");
        passed &= check(streamer.lastError().code == firstError.code,
            "lastError is preserved (not overwritten) after reportSegment on Failed");
    }

    // =============================================
    // 49. endSeek 在 Recovering 状态下保留原状态
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        streamer.beginSeek(vidall::SeekTarget{vidall::SeekTarget::AbsoluteMs, 5000.0});
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::SeekPending,
            "State is SeekPending after beginSeek");

        // seek 期间断网
        streamer.reportNetworkDisconnected();
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Recovering,
            "State is Recovering after disconnect during seek");

        streamer.endSeek();
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Recovering,
            "endSeek preserves Recovering state instead of overwriting to Playing");
    }

    // =============================================
    // 50. retryCurrentSegment 超过最大重试次数时拒绝
    // =============================================
    {
        vidall::AdaptiveStreamConfig config;
        config.maxRetries = 2;
        vidall::AdaptiveStreaming streamer(config);
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        // 触发 3 次瞬时失败（超过 maxRetries=2）
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::TransientFailure);
        streamer.retryCurrentSegment();
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::TransientFailure);
        streamer.retryCurrentSegment();
        streamer.reportSegment(1, vidall::SegmentFetchOutcome::TransientFailure);

        // 第 3 次重试应被拒绝
        const bool result = streamer.retryCurrentSegment();
        passed &= check(!result, "retryCurrentSegment rejected when retryCount exceeds maxRetries");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Failed,
            "State is Failed after exceeding max retries");
        passed &= check(streamer.lastError().code == "RETRY_LIMIT_EXCEEDED",
            "Error code is RETRY_LIMIT_EXCEEDED after exceeding max retries");
    }

    // =============================================
    // 51. handleSegmentError 更新状态为 Recovering（可重试错误）
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        const auto err = streamer.handleSegmentError(-7, "network timeout");
        passed &= check(err.retryable, "Segment timeout is retryable via handleSegmentError");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Recovering,
            "State is Recovering after retryable handleSegmentError");
        passed &= check(streamer.lastError().retryable,
            "lastError is retryable after handleSegmentError");

        // 可以立即调用 retryCurrentSegment
        const bool retried = streamer.retryCurrentSegment();
        passed &= check(retried, "retryCurrentSegment succeeds after handleSegmentError set Recovering");
    }

    // =============================================
    // 52. handleSegmentError 更新状态为 Failed（永久错误）
    // =============================================
    {
        vidall::AdaptiveStreaming streamer;
        streamer.loadManifest(vidall::MediaKind::Hls, "https://example.com/stream.m3u8",
            makeTimeline(), {});

        streamer.handleSegmentError(-4, "unsupported format");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Failed,
            "State is Failed after permanent handleSegmentError");
        passed &= check(!streamer.lastError().retryable,
            "lastError is not retryable after permanent handleSegmentError");
    }

    // ===== 结果汇总 =====
    if (passed) {
        std::cout << "All adaptive streaming tests passed.\n";
    } else {
        std::cout << "Some adaptive streaming tests FAILED.\n";
    }

    return passed ? 0 : 1;
}