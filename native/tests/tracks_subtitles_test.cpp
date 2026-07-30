// T043 原生轨道/外挂音频/字幕测试：track-list、aid/sid、audio-add、sub-add、
// 延迟、不可访问 URL、缓存请求 FEATURE_UNSUPPORTED。
//
// TDD 红阶段：测试先编写，TrackController 实现后应通过。

#include <iostream>
#include <string>
#include <vector>

#include "TrackController.h"

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

vidall::PlayerTrackEntry makeTrack(int64_t id, vidall::TrackKind kind,
                                   const std::string& lang,
                                   const std::string& title,
                                   bool selected,
                                   vidall::RecognitionStatus status)
{
    vidall::PlayerTrackEntry t;
    t.id = id;
    t.kind = kind;
    t.language = lang;
    t.title = title;
    t.selected = selected;
    t.recognitionStatus = status;
    return t;
}

} // namespace

int main()
{
    bool passed = true;

    // ═══ 1. track-list 枚举：updateTrackList 更新内部轨道 ═══
    {
        vidall::TrackController ctrl;
        auto nativeTracks = std::vector<vidall::PlayerTrackEntry>{
            makeTrack(1, vidall::TrackKind::Audio, "eng", "English", true, vidall::RecognitionStatus::Recognized),
            makeTrack(2, vidall::TrackKind::Audio, "jpn", "日本語", false, vidall::RecognitionStatus::Recognized),
            makeTrack(3, vidall::TrackKind::Subtitle, "zho", "简体中文", true, vidall::RecognitionStatus::Renderable),
        };
        ctrl.updateTrackList(nativeTracks);
        passed &= check(ctrl.tracks().size() == 3,
            "updateTrackList stores 3 tracks");
        passed &= check(ctrl.tracks()[0].id == 1 && ctrl.tracks()[0].kind == vidall::TrackKind::Audio,
            "first track is audio id=1");
        passed &= check(ctrl.tracks()[2].kind == vidall::TrackKind::Subtitle,
            "third track is subtitle");
    }

    // ═══ 2. selectTrack 正常选择与互斥 ═══
    {
        vidall::TrackController ctrl;
        ctrl.updateTrackList({
            makeTrack(1, vidall::TrackKind::Audio, "eng", "English", true, vidall::RecognitionStatus::Recognized),
            makeTrack(2, vidall::TrackKind::Audio, "jpn", "日本語", false, vidall::RecognitionStatus::Recognized),
        });
        auto result = ctrl.selectTrack(vidall::TrackKind::Audio, 2);
        passed &= check(result == vidall::TrackCommandResult::Accepted,
            "selectTrack audio id=2 accepted");
        passed &= check(ctrl.tracks()[0].selected == false,
            "after select id=2, id=1 is deselected");
        passed &= check(ctrl.tracks()[1].selected == true,
            "after select id=2, id=2 is selected");
    }

    // ═══ 3. deselectTrack 取消选择 ═══
    {
        vidall::TrackController ctrl;
        ctrl.updateTrackList({
            makeTrack(1, vidall::TrackKind::Audio, "eng", "English", true, vidall::RecognitionStatus::Recognized),
        });
        auto result = ctrl.deselectTrack(vidall::TrackKind::Audio);
        passed &= check(result == vidall::TrackCommandResult::Accepted,
            "deselectTrack accepted");
        passed &= check(ctrl.tracks()[0].selected == false,
            "after deselect, track is not selected");
    }

    // ═══ 4. selectTrack 非法 ID 拒绝 ═══
    {
        vidall::TrackController ctrl;
        ctrl.updateTrackList({
            makeTrack(1, vidall::TrackKind::Audio, "eng", "English", true, vidall::RecognitionStatus::Recognized),
        });
        auto result = ctrl.selectTrack(vidall::TrackKind::Audio, 9999);
        passed &= check(result == vidall::TrackCommandResult::RejectedTrackNotFound,
            "selectTrack with non-existent id returns TRACK_NOT_FOUND");
        passed &= checkContains(ctrl.lastError().code, "TRACK_NOT_FOUND",
            "error code is TRACK_NOT_FOUND");
    }

    // ═══ 5. 连续切换音轨 ═══
    {
        vidall::TrackController ctrl;
        ctrl.updateTrackList({
            makeTrack(1, vidall::TrackKind::Audio, "eng", "English", true, vidall::RecognitionStatus::Recognized),
            makeTrack(2, vidall::TrackKind::Audio, "jpn", "日本語", false, vidall::RecognitionStatus::Recognized),
            makeTrack(3, vidall::TrackKind::Audio, "zho", "中文", false, vidall::RecognitionStatus::Recognized),
        });
        ctrl.selectTrack(vidall::TrackKind::Audio, 2);
        ctrl.selectTrack(vidall::TrackKind::Audio, 3);
        ctrl.selectTrack(vidall::TrackKind::Audio, 1);
        passed &= check(ctrl.tracks()[0].selected == true,
            "after switching back, id=1 is selected");
        passed &= check(ctrl.tracks()[1].selected == false,
            "id=2 is deselected");
        passed &= check(ctrl.tracks()[2].selected == false,
            "id=3 is deselected");
    }

    // ═══ 6. addExternalAudio HTTP/HTTPS 接受 ═══
    {
        vidall::TrackController ctrl;
        vidall::ExternalAudioRequest audio;
        audio.uri = "https://fixture.invalid/audio-eng.aac";
        audio.title = "English";
        audio.language = "eng";
        auto result = ctrl.addExternalAudio(audio);
        passed &= check(result == vidall::TrackCommandResult::Accepted,
            "addExternalAudio with HTTPS accepted");
        passed &= check(ctrl.tracks().size() == 1,
            "one external audio track added");
        passed &= check(ctrl.tracks()[0].kind == vidall::TrackKind::Audio,
            "external track kind is audio");
        passed &= check(ctrl.tracks()[0].recognitionStatus == vidall::RecognitionStatus::Recognized,
            "external audio recognitionStatus is Recognized");
    }

    // ═══ 7. addExternalAudio 非 HTTP/HTTPS 拒绝 ═══
    {
        vidall::TrackController ctrl;
        vidall::ExternalAudioRequest audio;
        audio.uri = "ftp://fixture.invalid/audio.aac";
        auto result = ctrl.addExternalAudio(audio);
        passed &= check(result == vidall::TrackCommandResult::RejectedInaccessibleUrl,
            "addExternalAudio with FTP rejected");
        passed &= checkContains(ctrl.lastError().code, "UNSUPPORTED_EXTERNAL_AUDIO_PROTOCOL",
            "error code is UNSUPPORTED_EXTERNAL_AUDIO_PROTOCOL");
    }

    // ═══ 8. addExternalSubtitle 文本格式为 Renderable ═══
    {
        vidall::TrackController ctrl;
        vidall::ExternalSubtitleRequest sub;
        sub.uri = "https://fixture.invalid/sub.srt";
        sub.title = "简体中文";
        sub.format = "srt";
        auto result = ctrl.addExternalSubtitle(sub);
        passed &= check(result == vidall::TrackCommandResult::Accepted,
            "addExternalSubtitle SRT accepted");
        passed &= check(ctrl.tracks()[0].recognitionStatus == vidall::RecognitionStatus::Renderable,
            "SRT subtitle recognitionStatus is Renderable");
    }

    // ═══ 9. addExternalSubtitle 图形格式为 Recognized ═══
    {
        vidall::TrackController ctrl;
        vidall::ExternalSubtitleRequest sub;
        sub.uri = "https://fixture.invalid/sub.pgs";
        sub.format = "pgs";
        auto result = ctrl.addExternalSubtitle(sub);
        passed &= check(result == vidall::TrackCommandResult::Accepted,
            "addExternalSubtitle PGS accepted");
        passed &= check(ctrl.tracks()[0].recognitionStatus == vidall::RecognitionStatus::Recognized,
            "PGS subtitle recognitionStatus is Recognized");
    }

    // ═══ 10. addExternalSubtitle 不支持格式拒绝 ═══
    {
        vidall::TrackController ctrl;
        vidall::ExternalSubtitleRequest sub;
        sub.uri = "https://fixture.invalid/sub.dvb";
        sub.format = "dvb";
        auto result = ctrl.addExternalSubtitle(sub);
        passed &= check(result == vidall::TrackCommandResult::RejectedFeatureUnsupported,
            "addExternalSubtitle with DVB format rejected");
        passed &= checkContains(ctrl.lastError().code, "UNSUPPORTED_SUBTITLE_FORMAT",
            "error code is UNSUPPORTED_SUBTITLE_FORMAT");
    }

    // ═══ 11. addExternalSubtitle 非 HTTP/HTTPS/file URI 拒绝 ═══
    {
        vidall::TrackController ctrl;
        vidall::ExternalSubtitleRequest sub;
        sub.uri = "ftp://fixture.invalid/sub.srt";
        sub.format = "srt";
        auto result = ctrl.addExternalSubtitle(sub);
        passed &= check(result == vidall::TrackCommandResult::RejectedInaccessibleUrl,
            "addExternalSubtitle with FTP rejected");
    }

    // ═══ 12. addExternalSubtitle 本地缓存 file URI 接受 ═══
    {
        vidall::TrackController ctrl;
        vidall::ExternalSubtitleRequest sub;
        sub.uri = "file:///data/local/cache/sub.srt";
        sub.format = "srt";
        auto result = ctrl.addExternalSubtitle(sub);
        passed &= check(result == vidall::TrackCommandResult::Accepted,
            "addExternalSubtitle with local file URI accepted");
    }

    // ═══ 13. setSubtitleDelay 正常 ═══
    {
        vidall::TrackController ctrl;
        auto result = ctrl.setSubtitleDelay(500);
        passed &= check(result == vidall::TrackCommandResult::Accepted,
            "setSubtitleDelay 500ms accepted");
        result = ctrl.setSubtitleDelay(-200);
        passed &= check(result == vidall::TrackCommandResult::Accepted,
            "setSubtitleDelay -200ms accepted");
    }

    // ═══ 14. requestCache 稳定返回 FEATURE_UNSUPPORTED ═══
    {
        vidall::TrackController ctrl;
        auto result = ctrl.requestCache();
        passed &= check(result == vidall::TrackCommandResult::RejectedFeatureUnsupported,
            "requestCache returns FEATURE_UNSUPPORTED");
        passed &= checkContains(ctrl.lastError().code, "FEATURE_UNSUPPORTED",
            "cache request error code is FEATURE_UNSUPPORTED");
    }

    // ═══ 15. clear 重置轨道 ═══
    {
        vidall::TrackController ctrl;
        ctrl.updateTrackList({
            makeTrack(1, vidall::TrackKind::Audio, "eng", "English", true, vidall::RecognitionStatus::Recognized),
        });
        ctrl.clear();
        passed &= check(ctrl.tracks().empty(),
            "after clear, tracks are empty");
    }

    // ═══ 16. inferSubtitleRecognitionStatus 覆盖全部格式 ═══
    {
        passed &= check(vidall::TrackController::inferSubtitleRecognitionStatus("srt") == vidall::RecognitionStatus::Renderable,
            "SRT is Renderable");
        passed &= check(vidall::TrackController::inferSubtitleRecognitionStatus("ass") == vidall::RecognitionStatus::Renderable,
            "ASS is Renderable");
        passed &= check(vidall::TrackController::inferSubtitleRecognitionStatus("ssa") == vidall::RecognitionStatus::Renderable,
            "SSA is Renderable");
        passed &= check(vidall::TrackController::inferSubtitleRecognitionStatus("webvtt") == vidall::RecognitionStatus::Renderable,
            "WebVTT is Renderable");
        passed &= check(vidall::TrackController::inferSubtitleRecognitionStatus("pgs") == vidall::RecognitionStatus::Recognized,
            "PGS is Recognized");
        passed &= check(vidall::TrackController::inferSubtitleRecognitionStatus("vobsub") == vidall::RecognitionStatus::Recognized,
            "VOBsub is Recognized");
        passed &= check(vidall::TrackController::inferSubtitleRecognitionStatus("") == vidall::RecognitionStatus::Renderable,
            "empty format defaults to Renderable");
        passed &= check(vidall::TrackController::inferSubtitleRecognitionStatus("dvb") == vidall::RecognitionStatus::Unsupported,
            "DVB is Unsupported");
    }

    // ═══ 17. 外挂轨道 ID 不与 native 轨道冲突 ═══
    {
        vidall::TrackController ctrl;
        ctrl.updateTrackList({
            makeTrack(1, vidall::TrackKind::Audio, "eng", "English", true, vidall::RecognitionStatus::Recognized),
            makeTrack(2, vidall::TrackKind::Audio, "jpn", "日本語", false, vidall::RecognitionStatus::Recognized),
        });
        vidall::ExternalAudioRequest audio;
        audio.uri = "https://fixture.invalid/audio-extra.aac";
        auto result = ctrl.addExternalAudio(audio);
        passed &= check(result == vidall::TrackCommandResult::Accepted,
            "external audio added after native tracks");
        // 外挂 ID 应大于 native ID
        const auto& lastTrack = ctrl.tracks().back();
        passed &= check(lastTrack.id > 2,
            "external track id > native track ids");
    }

    // ═══ 18. selectTrack 仅影响同类型轨道 ═══
    {
        vidall::TrackController ctrl;
        ctrl.updateTrackList({
            makeTrack(1, vidall::TrackKind::Audio, "eng", "English", true, vidall::RecognitionStatus::Recognized),
            makeTrack(2, vidall::TrackKind::Subtitle, "zho", "简体中文", true, vidall::RecognitionStatus::Renderable),
        });
        ctrl.selectTrack(vidall::TrackKind::Audio, 1);
        // 字幕轨道不受影响
        passed &= check(ctrl.tracks()[1].selected == true,
            "subtitle track selection unchanged after audio select");
    }

    // ═══ 19. 连续添加外挂轨道 ID 唯一递增 ═══
    {
        vidall::TrackController ctrl;
        vidall::ExternalAudioRequest audio1, audio2;
        audio1.uri = "https://fixture.invalid/a1.aac";
        audio1.title = "Audio 1";
        audio2.uri = "https://fixture.invalid/a2.aac";
        audio2.title = "Audio 2";
        ctrl.addExternalAudio(audio1);
        ctrl.addExternalAudio(audio2);
        const auto id1 = ctrl.tracks()[0].id;
        const auto id2 = ctrl.tracks()[1].id;
        passed &= check(id1 != id2,
            "two external tracks have distinct IDs");
        passed &= check(id2 > id1,
            "second external track ID is greater than first");
    }

    // ═══ 20. file URI 仅接受绝对路径和 localhost ═══
    {
        vidall::TrackController ctrl;
        // file:/// 绝对路径 — 接受
        vidall::ExternalSubtitleRequest sub1;
        sub1.uri = "file:///data/local/cache/sub.srt";
        sub1.format = "srt";
        passed &= check(ctrl.addExternalSubtitle(sub1) == vidall::TrackCommandResult::Accepted,
            "file:/// absolute path accepted");
        ctrl.clear();

        // file://localhost/ 绝对路径 — 接受
        vidall::ExternalSubtitleRequest sub2;
        sub2.uri = "file://localhost/data/local/cache/sub.srt";
        sub2.format = "srt";
        passed &= check(ctrl.addExternalSubtitle(sub2) == vidall::TrackCommandResult::Accepted,
            "file://localhost/ absolute path accepted");
        ctrl.clear();

        // file://evilhost/ — 拒绝
        vidall::ExternalSubtitleRequest sub3;
        sub3.uri = "file://evilhost/data/sub.srt";
        sub3.format = "srt";
        passed &= check(ctrl.addExternalSubtitle(sub3) == vidall::TrackCommandResult::RejectedInaccessibleUrl,
            "file://evilhost/ rejected");
    }

    return passed ? 0 : 1;
}