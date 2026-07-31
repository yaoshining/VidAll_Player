// T048: HLS/DASH 自适应流测试
// 覆盖：有效清单、分段失败、跳转、断网后重试和结构化错误
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

} // namespace

int main()
{
    bool passed = true;

    // ===== 正常路径：HLS 清单加载 =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::Hls,
            "https://example.com/live/stream.m3u8",
            {});
        passed &= check(result == vidall::MediaLoadResult::Accepted,
            "HLS manifest with HTTPS URI is accepted");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Loading,
            "HLS state is Loading after prepareLoad");
        passed &= check(streamer.currentUri() == "https://example.com/live/stream.m3u8",
            "HLS current URI is recorded");
        passed &= check(streamer.currentKind() == vidall::MediaKind::Hls,
            "HLS current kind is Hls");
    }

    // ===== 正常路径：DASH 清单加载 =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::Dash,
            "https://example.com/vod/manifest.mpd",
            {});
        passed &= check(result == vidall::MediaLoadResult::Accepted,
            "DASH manifest with HTTPS URI is accepted");
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Loading,
            "DASH state is Loading after prepareLoad");
        passed &= check(streamer.currentKind() == vidall::MediaKind::Dash,
            "DASH current kind is Dash");
    }

    // ===== 正常路径：HLS HTTP URI =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::Hls,
            "http://example.com/stream.m3u8",
            {});
        passed &= check(result == vidall::MediaLoadResult::Accepted,
            "HLS with HTTP URI is accepted");
    }

    // ===== 失败路径：非自适应 kind =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::Http,
            "http://example.com/media.mp4",
            {});
        passed &= check(result == vidall::MediaLoadResult::RejectedKindMismatch,
            "HTTP kind is rejected for adaptive streaming");
    }

    // ===== 失败路径：LocalFile kind =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::LocalFile,
            "file:///data/media/video.mp4",
            {});
        passed &= check(result == vidall::MediaLoadResult::RejectedKindMismatch,
            "LocalFile kind is rejected for adaptive streaming");
    }

    // ===== 失败路径：空 URI =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::Hls,
            "",
            {});
        passed &= check(result == vidall::MediaLoadResult::RejectedInvalidUri,
            "Empty URI is rejected for adaptive streaming");
    }

    // ===== 失败路径：URI 含 userinfo =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::Hls,
            "https://user:pass@example.com/stream.m3u8",
            {});
        passed &= check(result == vidall::MediaLoadResult::RejectedUrlUserinfoForbidden,
            "HLS URI with userinfo is rejected");
    }

    // ===== MPV 缓存选项：HLS =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
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

    // ===== MPV 缓存选项：DASH =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Dash, "https://example.com/manifest.mpd", {});
        const auto& opts = streamer.mpvOptions();
        bool hasCache = false;
        for (const auto& kv : opts) {
            if (kv.first == "cache") { hasCache = true; break; }
        }
        passed &= check(hasCache,
            "DASH load produces cache option for mpv");
    }

    // ===== 自定义缓存配置 =====
    {
        vidall::AdaptiveStreamConfig config;
        config.cacheDurationSec = 120;
        config.cacheMinSec = 10;
        config.cacheBackSec = 60;
        vidall::AdaptiveStreaming streamer(config);
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        const auto& opts = streamer.mpvOptions();
        // 验证缓存选项包含自定义值
        bool foundCacheValue = false;
        for (const auto& kv : opts) {
            if (kv.first == "cache" && kv.second.find("120") != std::string::npos) {
                foundCacheValue = true;
            }
        }
        passed &= check(foundCacheValue,
            "Custom cache duration is reflected in mpv options");
    }

    // ===== 跳转：正常跳转 =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        streamer.simulateStateChange(vidall::AdaptiveStreamState::Playing);
        vidall::SeekTarget target;
        target.type = vidall::SeekTarget::Percent;
        target.value = 50.0;
        const auto ok = streamer.beginSeek(target);
        passed &= check(ok, "Seek is accepted in Playing state");
        passed &= check(streamer.isSeekPending(), "Seek is pending after beginSeek");
        streamer.endSeek();
        passed &= check(!streamer.isSeekPending(), "Seek is no longer pending after endSeek");
    }

    // ===== 跳转：Idle 状态拒绝 =====
    {
        vidall::AdaptiveStreaming streamer;
        vidall::SeekTarget target;
        target.type = vidall::SeekTarget::Relative;
        target.value = 10.0;
        const auto ok = streamer.beginSeek(target);
        passed &= check(!ok, "Seek is rejected in Idle state");
        passed &= check(!streamer.isSeekPending(), "Seek is not pending after rejected seek");
    }

    // ===== 跳转：Error 状态拒绝 =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        streamer.simulateStateChange(vidall::AdaptiveStreamState::Error);
        vidall::SeekTarget target;
        target.type = vidall::SeekTarget::Percent;
        target.value = 30.0;
        const auto ok = streamer.beginSeek(target);
        passed &= check(!ok, "Seek is rejected in Error state");
    }

    // ===== 跳转：已释放状态拒绝 =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        streamer.release();
        vidall::SeekTarget target;
        target.type = vidall::SeekTarget::Percent;
        target.value = 50.0;
        const auto ok = streamer.beginSeek(target);
        passed &= check(!ok, "Seek is rejected after release");
    }

    // ===== 分段失败：瞬时错误（超时） =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        const auto err = streamer.handleSegmentError(-7, "network timeout");
        passed &= check(err.retryable, "Segment timeout is retryable");
        passed &= check(err.domain == "media", "Segment timeout domain is media");
    }

    // ===== 分段失败：永久错误（格式不支持） =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        const auto err = streamer.handleSegmentError(-4, "unsupported format");
        passed &= check(!err.retryable, "Unsupported format is not retryable");
        passed &= check(err.domain == "media", "Unsupported format domain is media");
    }

    // ===== 分段失败：脱敏检查 =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        const auto err = streamer.handleSegmentError(-7,
            "******host.example.com/segment.ts");
        passed &= checkNotContains(err.message, "secret",
            "Segment error message must not contain userinfo credentials");
        passed &= checkNotContains(err.message, "user:",
            "Segment error message must not contain userinfo prefix");
    }

    // ===== 网络恢复：首次失败建议重试 =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto delay = streamer.networkRecoveryDelay(1);
        passed &= check(delay > 0, "First network failure suggests positive retry delay");
    }

    // ===== 网络恢复：连续失败退避 =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto delay1 = streamer.networkRecoveryDelay(1);
        const auto delay2 = streamer.networkRecoveryDelay(2);
        passed &= check(delay2 > delay1,
            "Second failure delay is longer than first (linear backoff)");
    }

    // ===== 网络恢复：超过最大重试次数不重试 =====
    {
        vidall::AdaptiveStreamConfig config;
        config.maxRetries = 2;
        vidall::AdaptiveStreaming streamer(config);
        const auto delay = streamer.networkRecoveryDelay(3);
        passed &= check(delay == 0,
            "Beyond max retries, network recovery delay is 0 (no retry)");
    }

    // ===== 网络恢复：maxRetries=0 不重试 =====
    {
        vidall::AdaptiveStreamConfig config;
        config.maxRetries = 0;
        vidall::AdaptiveStreaming streamer(config);
        const auto delay = streamer.networkRecoveryDelay(1);
        passed &= check(delay == 0,
            "With maxRetries=0, no retry is suggested");
    }

    // ===== 切源重置 =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        streamer.simulateStateChange(vidall::AdaptiveStreamState::Playing);
        vidall::SeekTarget target;
        target.type = vidall::SeekTarget::Percent;
        target.value = 50.0;
        streamer.beginSeek(target);
        // 模拟分段失败以增加重试计数
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
    }

    // ===== 释放 =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        streamer.release();
        passed &= check(streamer.state() == vidall::AdaptiveStreamState::Released,
            "State is Released after release");
    }

    // ===== 释放后操作拒绝 =====
    {
        vidall::AdaptiveStreaming streamer;
        streamer.prepareLoad(vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        streamer.release();
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::Hls, "https://example.com/stream.m3u8", {});
        passed &= check(result == vidall::MediaLoadResult::RejectedInvalidUri,
            "prepareLoad is rejected after release");
    }

    // ===== 带 headers 的 HLS 加载 =====
    {
        vidall::AdaptiveStreaming streamer;
        std::vector<vidall::HeaderEntry> headers;
        headers.push_back({"authorization", "Bearer test-token"});
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::Hls,
            "https://example.com/stream.m3u8",
            headers);
        passed &= check(result == vidall::MediaLoadResult::Accepted,
            "HLS with authorization header is accepted");
        // 验证 mpv 选项包含 http-header 字段
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

    // ===== DASH 非 HTTP(S) URI 拒绝 =====
    {
        vidall::AdaptiveStreaming streamer;
        const auto result = streamer.prepareLoad(
            vidall::MediaKind::Dash,
            "ftp://example.com/manifest.mpd",
            {});
        passed &= check(result == vidall::MediaLoadResult::RejectedKindMismatch,
            "DASH with FTP URI is rejected");
    }

    return passed ? 0 : 1;
}