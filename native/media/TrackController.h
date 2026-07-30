#ifndef VIDALL_TRACK_CONTROLLER_H
#define VIDALL_TRACK_CONTROLLER_H

#include <cstdint>
#include <string>
#include <vector>

namespace vidall {

enum class TrackKind {
    Audio,
    Video,
    Subtitle,
};

enum class RecognitionStatus {
    Recognized,
    Renderable,
    Degraded,
    Unsupported,
};

struct PlayerTrackEntry {
    int64_t id = 0;
    TrackKind kind = TrackKind::Audio;
    std::string language;
    std::string title;
    bool selected = false;
    RecognitionStatus recognitionStatus = RecognitionStatus::Recognized;
};

enum class TrackCommandResult {
    Accepted,
    RejectedTrackNotFound,
    RejectedInvalidTrackId,
    RejectedInvalidState,
    RejectedSessionReleased,
    RejectedFeatureUnsupported,
    RejectedInaccessibleUrl,
};

struct TrackCommandError {
    std::string domain;
    std::string code;
    std::string message;
    bool retryable = false;
};

struct ExternalAudioRequest {
    std::string uri;
    std::string title;
    std::string language;
};

struct ExternalSubtitleRequest {
    std::string uri;
    std::string title;
    std::string format; // "srt", "ass", "ssa", "webvtt", "pgs", "vobsub"
};

// TrackController 管理每会话的轨道枚举、选择/取消、外挂音频/字幕添加
// 和字幕延迟。它映射 libmpv 的 track-list 属性、aid/sid/vid 属性以及
// audio-add/sub-add 命令，但不直接持有 mpv_handle。
//
// 识别与渲染结论通过 recognitionStatus 四态分离：
// - Recognized：轨道被识别但不在 libass 管线渲染（如 PGS/VOBsub 图形字幕）
// - Renderable：文本字幕可经 libass 正确渲染
// - Degraded：识别但渲染降级（如字体缺失导致 CJK 回退）
// - Unsupported：轨道格式不支持（如首期未验证的 DVB 图文）
class TrackController {
public:
    TrackController() = default;

    // 从 libmpv track-list 事件更新内部轨道列表
    void updateTrackList(const std::vector<PlayerTrackEntry>& nativeTracks);

    // 选择/取消指定类型轨道
    TrackCommandResult selectTrack(TrackKind kind, int64_t id);
    TrackCommandResult deselectTrack(TrackKind kind);

    // 外挂音频：仅 HTTP/HTTPS
    TrackCommandResult addExternalAudio(const ExternalAudioRequest& audio);

    // 外挂字幕：HTTP/HTTPS 或本地缓存 file URI
    TrackCommandResult addExternalSubtitle(const ExternalSubtitleRequest& subtitle);

    // 字幕延迟（毫秒）
    TrackCommandResult setSubtitleDelay(int64_t delayMs);

    // 缓存请求：首期稳定返回 FEATURE_UNSUPPORTED
    TrackCommandResult requestCache();

    // 获取当前轨道快照
    const std::vector<PlayerTrackEntry>& tracks() const { return tracks_; }

    // 获取最近一次操作错误
    TrackCommandError lastError() const { return lastError_; }

    // 重置轨道（切源或停止时调用）
    void clear();

    // 下一可用轨道 ID（每次调用递增）
    int64_t nextTrackId();

    static RecognitionStatus inferSubtitleRecognitionStatus(const std::string& format);

private:
    std::vector<PlayerTrackEntry> tracks_;
    TrackCommandError lastError_{};
    int64_t nextExternalId_ = 1000; // 外挂轨道 ID 从 1000 开始

    static bool isHttpOrHttps(const std::string& uri);
    static bool isLocalFileUri(const std::string& uri);
    static bool isSupportedSubtitleFormat(const std::string& format);
    void setError(const std::string& domain, const std::string& code,
                  const std::string& message, bool retryable);
};

} // namespace vidall
#endif