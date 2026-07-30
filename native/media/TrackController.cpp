#include "TrackController.h"

#include <algorithm>
#include <cctype>

namespace {

std::string toLower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(),
        [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return value;
}

} // namespace

namespace vidall {

void TrackController::updateTrackList(const std::vector<PlayerTrackEntry>& nativeTracks)
{
    tracks_ = nativeTracks;
    // 外挂轨道 ID 从现有最大 ID + 1 起始
    nextExternalId_ = 1000;
    for (const auto& t : tracks_) {
        if (t.id >= nextExternalId_) {
            nextExternalId_ = t.id + 1;
        }
    }
}

TrackCommandResult TrackController::selectTrack(TrackKind kind, int64_t id)
{
    auto candidates = std::vector<PlayerTrackEntry*>{};
    for (auto& t : tracks_) {
        if (t.kind == kind) {
            candidates.push_back(&t);
        }
    }
    // 查找指定 ID
    bool found = false;
    for (auto* t : candidates) {
        if (t->id == id) {
            found = true;
            break;
        }
    }
    if (!found) {
        setError("lifecycle", "TRACK_NOT_FOUND",
                 "指定的音轨或字幕轨道不存在 (The requested track does not exist).", false);
        return TrackCommandResult::RejectedTrackNotFound;
    }
    // 更新选择状态：同类型内互斥
    for (auto* t : candidates) {
        t->selected = (t->id == id);
    }
    return TrackCommandResult::Accepted;
}

TrackCommandResult TrackController::deselectTrack(TrackKind kind)
{
    for (auto& t : tracks_) {
        if (t.kind == kind) {
            t.selected = false;
        }
    }
    return TrackCommandResult::Accepted;
}

TrackCommandResult TrackController::addExternalAudio(const ExternalAudioRequest& audio)
{
    if (!isHttpOrHttps(audio.uri)) {
        setError("input", "UNSUPPORTED_EXTERNAL_AUDIO_PROTOCOL",
                 "外挂音频仅支持 HTTP/HTTPS (External audio only supports HTTP/HTTPS).", false);
        return TrackCommandResult::RejectedInaccessibleUrl;
    }
    PlayerTrackEntry entry;
    entry.id = nextTrackId();
    entry.kind = TrackKind::Audio;
    entry.title = audio.title;
    entry.language = audio.language;
    entry.selected = false;
    entry.recognitionStatus = RecognitionStatus::Recognized;
    tracks_.push_back(entry);
    return TrackCommandResult::Accepted;
}

TrackCommandResult TrackController::addExternalSubtitle(const ExternalSubtitleRequest& subtitle)
{
    // 协议校验：HTTP/HTTPS 或本地缓存 file URI
    if (!isHttpOrHttps(subtitle.uri) && !isLocalFileUri(subtitle.uri)) {
        setError("input", "UNSUPPORTED_SUBTITLE_PROTOCOL",
                 "外挂字幕仅支持 HTTP/HTTPS 或本地缓存文件协议 (External subtitle only supports HTTP/HTTPS or cached file URIs).", false);
        return TrackCommandResult::RejectedInaccessibleUrl;
    }
    // 格式校验
    if (!subtitle.format.empty() && !isSupportedSubtitleFormat(subtitle.format)) {
        setError("input", "UNSUPPORTED_SUBTITLE_FORMAT",
                 "不支持的外挂字幕格式 (Unsupported external subtitle format).", false);
        return TrackCommandResult::RejectedFeatureUnsupported;
    }
    PlayerTrackEntry entry;
    entry.id = nextTrackId();
    entry.kind = TrackKind::Subtitle;
    entry.title = subtitle.title;
    entry.language = ""; // ExternalSubtitleRequest 无 language 字段
    entry.selected = false;
    entry.recognitionStatus = inferSubtitleRecognitionStatus(subtitle.format);
    tracks_.push_back(entry);
    return TrackCommandResult::Accepted;
}

TrackCommandResult TrackController::setSubtitleDelay(int64_t delayMs)
{
    // 当前仅接受有限值；实际映射到 mpv sub-delay 在 bridge 层处理
    (void)delayMs;
    return TrackCommandResult::Accepted;
}

TrackCommandResult TrackController::requestCache()
{
    // 首期缓存请求稳定返回 FEATURE_UNSUPPORTED
    setError("lifecycle", "FEATURE_UNSUPPORTED",
             "缓存请求尚未实现 (Cache request is not implemented in the first release).", false);
    return TrackCommandResult::RejectedFeatureUnsupported;
}

void TrackController::clear()
{
    tracks_.clear();
    nextExternalId_ = 1000;
}

int64_t TrackController::nextTrackId() const
{
    return nextExternalId_;
}

RecognitionStatus TrackController::inferSubtitleRecognitionStatus(const std::string& format)
{
    // 图形字幕：识别但不经 libass 渲染
    const auto lower = toLower(format);
    if (lower == "pgs" || lower == "vobsub") {
        return RecognitionStatus::Recognized;
    }
    // 文本字幕：可经 libass 渲染
    if (lower == "srt" || lower == "ass" || lower == "ssa" || lower == "webvtt" || lower.empty()) {
        return RecognitionStatus::Renderable;
    }
    // 不支持格式
    return RecognitionStatus::Unsupported;
}

bool TrackController::isHttpOrHttps(const std::string& uri)
{
    const auto lower = toLower(uri.substr(0, 8));
    return lower.find("https://") == 0 || lower.find("http://") == 0;
}

bool TrackController::isLocalFileUri(const std::string& uri)
{
    return toLower(uri.substr(0, 7)) == "file://";
}

bool TrackController::isSupportedSubtitleFormat(const std::string& format)
{
    const auto lower = toLower(format);
    static const std::vector<std::string> supported = {
        "srt", "ass", "ssa", "webvtt", "pgs", "vobsub"
    };
    return std::find(supported.begin(), supported.end(), lower) != supported.end();
}

void TrackController::setError(const std::string& domain, const std::string& code,
                               const std::string& message, bool retryable)
{
    lastError_ = {domain, code, message, retryable};
}

} // namespace vidall