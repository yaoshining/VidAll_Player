#include <napi/native_api.h>
#include <hilog/log.h>

#include <atomic>
#include <chrono>
#include <cstring>
#include <unistd.h>
#include <sys/mman.h>
#include <condition_variable>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

#if VIDALL_MPV_AVAILABLE
#include <ace/xcomponent/native_interface_xcomponent.h>
#include <mpv/client.h>
#include <mpv/render.h>
#include <native_window/external_window.h>
#include <native_buffer/native_buffer.h>
#endif

#undef LOG_TAG
#define LOG_TAG "VidAllPlayerNative"
#undef LOG_DOMAIN
#define LOG_DOMAIN 0xD001

namespace {

struct NativeResult {
    bool ok;
    std::uint64_t handle;
    const char* code;
};

bool Check(napi_env env, napi_status status, const char* operation)
{
    if (status == napi_ok) return true;
    napi_throw_error(env, nullptr, operation);
    return false;
}

napi_value CreateString(napi_env env, const std::string& value)
{
    napi_value result = nullptr;
    napi_create_string_utf8(env, value.c_str(), NAPI_AUTO_LENGTH, &result);
    return result;
}

napi_value CreateResult(napi_env env, NativeResult nativeResult)
{
    napi_value result = nullptr;
    napi_value ok = nullptr;
    napi_value handle = nullptr;
    napi_value code = nullptr;
    if (!Check(env, napi_create_object(env, &result), "Failed to create native result.") ||
        !Check(env, napi_get_boolean(env, nativeResult.ok, &ok), "Failed to create result flag.") ||
        !Check(env, napi_create_int64(env, static_cast<int64_t>(nativeResult.handle), &handle), "Failed to create session handle.") ||
        !Check(env, napi_create_string_utf8(env, nativeResult.code, NAPI_AUTO_LENGTH, &code), "Failed to create result code.") ||
        !Check(env, napi_set_named_property(env, result, "ok", ok), "Failed to set result flag.") ||
        !Check(env, napi_set_named_property(env, result, "handle", handle), "Failed to set session handle.") ||
        !Check(env, napi_set_named_property(env, result, "code", code), "Failed to set result code.")) {
        return nullptr;
    }
    return result;
}

bool ReadString(napi_env env, napi_value value, std::string& output)
{
    size_t length = 0;
    if (value == nullptr || napi_get_value_string_utf8(env, value, nullptr, 0, &length) != napi_ok) return false;
    output.assign(length + 1, '\0');
    if (napi_get_value_string_utf8(env, value, output.data(), output.size(), &length) != napi_ok) return false;
    output.resize(length);
    return true;
}

bool GetArguments(napi_env env, napi_callback_info info, size_t requested, napi_value* args, size_t& argc)
{
    argc = requested;
    return Check(env, napi_get_cb_info(env, info, &argc, args, nullptr, nullptr), "Failed to read native arguments.");
}

bool ReadHandle(napi_env env, napi_value value, std::uint64_t& output)
{
    int64_t handle = 0;
    return value != nullptr && napi_get_value_int64(env, value, &handle) == napi_ok && handle > 0 &&
        ((output = static_cast<std::uint64_t>(handle)), true);
}

#if VIDALL_MPV_AVAILABLE
// mpv 的 demuxer-lavf-o/stream-lavf-o 选项以逗号分隔 key=value 对；转义用户名/密码中的
// 反斜杠、逗号与等号，避免凭据本身破坏选项解析（与旧版 entry/src/main/cpp/napi_bridge.cpp
// 的实现保持一致，迁移到 @vidall/player HAR 时该转发逻辑此前被遗漏）。
std::string EscapeMpvOptionValue(const std::string& value)
{
    std::string escaped;
    escaped.reserve(value.size());
    for (const char character : value) {
        if (character == '\\' || character == ',' || character == '=') {
            escaped.push_back('\\');
        }
        escaped.push_back(character);
    }
    return escaped;
}

// 将 mpv "track-list" 属性（MPV_FORMAT_NODE_ARRAY，元素为 MPV_FORMAT_NODE_MAP）编码为
// 纯字符串上报给 ArkTS 层（原生 Event 结构体未新增字段，沿用 videoParams 的编码思路）。
// 记录间以 \x1e（record separator）分隔，字段间以 \x1f（unit separator）分隔——这两个
// ASCII 控制字符几乎不可能出现在 mpv 上报的语言/标题字符串中，无需额外转义。
// 只保留 audio/sub 类型（视频轨不参与 ArkTS 层音轨/字幕选择 UI）。
std::string EncodeTrackList(const mpv_node* node)
{
    if (node == nullptr || node->format != MPV_FORMAT_NODE_ARRAY || node->u.list == nullptr) return "";
    std::string encoded;
    const mpv_node_list* list = node->u.list;
    for (int i = 0; i < list->num; ++i) {
        const mpv_node& entry = list->values[i];
        if (entry.format != MPV_FORMAT_NODE_MAP || entry.u.list == nullptr) continue;
        const mpv_node_list* map = entry.u.list;
        int64_t id = -1;
        std::string type;
        std::string lang;
        std::string title;
        int selected = 0;
        for (int j = 0; j < map->num; ++j) {
            if (map->keys[j] == nullptr) continue;
            const std::string key = map->keys[j];
            const mpv_node& value = map->values[j];
            if (key == "id" && value.format == MPV_FORMAT_INT64) {
                id = value.u.int64;
            } else if (key == "type" && value.format == MPV_FORMAT_STRING && value.u.string != nullptr) {
                type = value.u.string;
            } else if (key == "lang" && value.format == MPV_FORMAT_STRING && value.u.string != nullptr) {
                lang = value.u.string;
            } else if (key == "title" && value.format == MPV_FORMAT_STRING && value.u.string != nullptr) {
                title = value.u.string;
            } else if (key == "selected" && value.format == MPV_FORMAT_FLAG) {
                selected = value.u.flag;
            }
        }
        if (id < 0 || (type != "audio" && type != "sub")) continue;
        if (!encoded.empty()) encoded.push_back('\x1e');
        encoded += std::to_string(id) + "\x1f" + (type == "sub" ? "subtitle" : "audio") + "\x1f" + lang + "\x1f" + title +
            "\x1f" + (selected ? "1" : "0");
    }
    return encoded;
}

class NativeSession {
public:
    struct Event {
        std::string type;
        std::string message;
        std::uint64_t epoch;
        std::uint64_t sequence;
        std::uint64_t generation;
    };

    NativeSession()
        : player_(mpv_create(), mpv_terminate_destroy)
    {
    }

    ~NativeSession() { Release(); }

    bool Initialize(const std::string& fontsDir)
    {
        if (!player_) return false;
        mpv_set_option_string(player_.get(), "terminal", "no");
        mpv_set_option_string(player_.get(), "config", "no");
        mpv_set_option_string(player_.get(), "vo", "libmpv");
        // 临时诊断：显式提升所有模块（含 libass 的 "ass" 模块）的日志级别，
        // 仅调用 mpv_request_log_messages 不足以让某些模块打印到 trace/debug 级别的内部细节。
        mpv_set_option_string(player_.get(), "msg-level", "all=trace");
        if (!fontsDir.empty()) {
            // HarmonyOS 沙箱内没有系统 fontconfig，libass 的 fontconfig provider 探测不到
            // 任何字体，导致字幕轨道被正确选中但完全不可见（无渲染文字）。改用 "none"
            // provider 并显式指定应用侧解包好的字体目录，让 libass 直接按目录匹配字体。
            mpv_set_option_string(player_.get(), "sub-font-provider", "none");
            mpv_set_option_string(player_.get(), "sub-fonts-dir", fontsDir.c_str());
            mpv_set_option_string(player_.get(), "osd-fonts-dir", fontsDir.c_str());
        }
        if (mpv_initialize(player_.get()) < 0) return false;
        // 临时诊断：转发 mpv/libass 内部日志到 hilog，用于排查字幕不渲染问题。
        mpv_request_log_messages(player_.get(), "trace");
        // 观察 dwidth/dheight（已包含旋转与像素宽高比修正后的显示尺寸），
        // 用于向 ArkTS 层上报真实视频宽高比，避免画面被拉伸。
        mpv_observe_property(player_.get(), 0, "dwidth", MPV_FORMAT_INT64);
        mpv_observe_property(player_.get(), 0, "dheight", MPV_FORMAT_INT64);
        // 观察 pause 属性变化，用于在暂停/恢复播放时向 ArkTS 层上报状态，
        // 使 playerSession 状态机能正确在 playing <-> paused 间迁移。
        mpv_observe_property(player_.get(), 0, "pause", MPV_FORMAT_FLAG);
        // 观察 track-list，用于向 ArkTS 层上报媒体内嵌的音轨/字幕轨道元数据
        // （之前的最小 libmpv bridge 从未枚举过内嵌轨道，导致音轨/字幕选择功能形同虚设）。
        mpv_observe_property(player_.get(), 0, "track-list", MPV_FORMAT_NODE);
        // 观察 sub-text：mpv 内部按当前播放位置解析出的当前字幕行纯文本
        // （与 libass 渲染到视频帧内是否可见完全无关），用于向 ArkTS/消费方
        // 提供一条不依赖软件渲染合成管线的字幕文本通道，供上层自行展示
        // （例如 entry 调试页面的字幕条，或 vidall-tv 等消费方的自绘字幕 UI）。
        mpv_observe_property(player_.get(), 0, "sub-text", MPV_FORMAT_STRING);
        eventThread_ = std::thread(&NativeSession::EventLoop, this, player_.get());
        return true;
    }

    NativeResult Attach(const std::string& surfaceId, std::uint64_t generation, int width, int height, std::uint64_t handle)
    {
        if (surfaceId.empty() || generation == 0 || width <= 0 || height <= 0) return {false, handle, "INPUT_INVALID"};
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        StopRendererLocked();
        surfaceId_ = surfaceId;
        generation_ = generation;
        width_ = width;
        height_ = height;
        rendererReady_ = false;
        rendererFailed_ = false;
        stopRenderer_ = false;
        renderThread_ = std::thread(&NativeSession::RenderLoop, this);
        std::unique_lock<std::mutex> readyLock(rendererMutex_);
        rendererReadyCv_.wait_for(readyLock, std::chrono::seconds(3), [this] { return rendererReady_ || rendererFailed_; });
        return rendererReady_ ? NativeResult{true, handle, "OK"} : NativeResult{false, handle, "SURFACE_UNAVAILABLE"};
    }

    NativeResult Resize(std::uint64_t generation, int width, int height, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (generation != generation_ || width <= 0 || height <= 0 || !rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        width_ = width;
        height_ = height;
        geometryDirty_ = true;
        renderRequested_ = true;
        renderCondition_.notify_one();
        return {true, handle, "OK"};
    }

    NativeResult Detach(std::uint64_t generation, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (generation != generation_) return {false, handle, "SURFACE_UNAVAILABLE"};
        StopRendererLocked();
        generation_ = 0;
        return {true, handle, "OK"};
    }

    NativeResult Load(const std::string& uri, const std::string& headerFields,
                       const std::string& smbUsername, const std::string& smbPassword, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        if (uri.empty()) return {false, handle, "INPUT_INVALID"};
        // direct smb:// 走 FFmpeg 的 demuxer-lavf-o/stream-lavf-o username=/password= 选项
        // 认证（libsmbclient 已静态链接进 libmpv.so），不走 HTTP header；其余来源仍使用
        // http-header-fields 转发 WebDAV/HTTP(S) 鉴权头。每次 load 都重设两类选项，避免
        // 上一次加载的凭据残留到下一次无凭据/不同协议的加载。
        const bool isSmb = !smbUsername.empty() || !smbPassword.empty();
        mpv_set_option_string(player_.get(), "http-header-fields", isSmb ? "" : headerFields.c_str());
        const std::string smbOptions = isSmb
            ? "username=" + EscapeMpvOptionValue(smbUsername) + ",password=" + EscapeMpvOptionValue(smbPassword)
            : "";
        mpv_set_option_string(player_.get(), "demuxer-lavf-o", smbOptions.c_str());
        mpv_set_option_string(player_.get(), "stream-lavf-o", smbOptions.c_str());
        const char* command[] = {"loadfile", uri.c_str(), "replace", nullptr};
        if (mpv_command_async(player_.get(), 0, command) < 0) return {false, handle, "NATIVE_PLAYBACK_FAILED"};
        ++eventEpoch_;
        eventSequence_ = 0;
        firstFrameSent_ = false;
        Dispatch("state", "preparing");
        return {true, handle, "OK"};
    }

    NativeResult Play(std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        if (mpv_set_property_string(player_.get(), "pause", "no") < 0) return {false, handle, "NATIVE_PLAYBACK_FAILED"};
        return {true, handle, "OK"};
    }

    NativeResult Pause(std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        if (mpv_set_property_string(player_.get(), "pause", "yes") < 0) return {false, handle, "NATIVE_PLAYBACK_FAILED"};
        return {true, handle, "OK"};
    }

    NativeResult SeekRelative(double seconds, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        const std::string secondsStr = std::to_string(seconds);
        const char* command[] = {"seek", secondsStr.c_str(), "relative", nullptr};
        return mpv_command_async(player_.get(), 0, command) >= 0
            ? NativeResult{true, handle, "OK"} : NativeResult{false, handle, "NATIVE_PLAYBACK_FAILED"};
    }

    NativeResult SeekPercent(double percent, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        const std::string percentStr = std::to_string(percent);
        const char* command[] = {"seek", percentStr.c_str(), "absolute-percent", nullptr};
        return mpv_command_async(player_.get(), 0, command) >= 0
            ? NativeResult{true, handle, "OK"} : NativeResult{false, handle, "NATIVE_PLAYBACK_FAILED"};
    }

    NativeResult SetRate(double rate, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        const std::string rateStr = std::to_string(rate);
        return mpv_set_property_string(player_.get(), "speed", rateStr.c_str()) >= 0
            ? NativeResult{true, handle, "OK"} : NativeResult{false, handle, "NATIVE_PLAYBACK_FAILED"};
    }

    // kind: "audio" -> mpv "aid"；"subtitle" -> mpv "sid"。trackId < 0 表示取消选择（"no"）。
    NativeResult SelectTrack(const std::string& kind, int64_t trackId, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        const char* property = kind == "subtitle" ? "sid" : "aid";
        const std::string value = trackId < 0 ? "no" : std::to_string(trackId);
        return mpv_set_property_string(player_.get(), property, value.c_str()) >= 0
            ? NativeResult{true, handle, "OK"} : NativeResult{false, handle, "NATIVE_PLAYBACK_FAILED"};
    }

    // kind: "audio" -> mpv "audio-add"；"subtitle" -> mpv "sub-add"。
    NativeResult AddExternalTrack(const std::string& kind, const std::string& uri, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        if (uri.empty()) return {false, handle, "INPUT_INVALID"};
        const char* command[] = {kind == "subtitle" ? "sub-add" : "audio-add", uri.c_str(), nullptr};
        return mpv_command_async(player_.get(), 0, command) >= 0
            ? NativeResult{true, handle, "OK"} : NativeResult{false, handle, "NATIVE_PLAYBACK_FAILED"};
    }

    NativeResult Stop(std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        const char* command[] = {"stop", nullptr};
        return mpv_command_async(player_.get(), 0, command) >= 0 ? NativeResult{true, handle, "OK"} : NativeResult{false, handle, "NATIVE_PLAYBACK_FAILED"};
    }

    NativeResult SetEventCallback(napi_env env, napi_value callback, std::uint64_t handle)
    {
        napi_valuetype type = napi_undefined;
        if (callback == nullptr || napi_typeof(env, callback, &type) != napi_ok || type != napi_function) return {false, handle, "INPUT_INVALID"};
        std::lock_guard<std::mutex> lock(callbackMutex_);
        CloseCallbackLocked();
        napi_value name = CreateString(env, "VidAllHarEvent");
        if (napi_create_threadsafe_function(env, callback, nullptr, name, 0, 1, nullptr, FinalizeCallback, this, CallCallback, &eventTsfn_) != napi_ok) {
            return {false, handle, "NATIVE_PLAYBACK_FAILED"};
        }
        return {true, handle, "OK"};
    }

    void Release()
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return;
        released_ = true;
        StopRendererLocked();
        stopEvents_ = true;
        // mpv_wakeup only interrupts a wait; keep the handle alive until the waiter exits.
        if (player_) mpv_wakeup(player_.get());
        if (eventThread_.joinable()) eventThread_.join();
        {
            std::lock_guard<std::mutex> callbackLock(callbackMutex_);
            CloseCallbackLocked();
        }
        player_.reset();
    }

private:
    static void NotifyRender(void* context)
    {
        auto* session = static_cast<NativeSession*>(context);
        { std::lock_guard<std::mutex> lock(session->rendererMutex_); session->renderRequested_ = true; }
        session->renderCondition_.notify_one();
    }

    static void FinalizeCallback(napi_env, void*, void*) {}

    static void CallCallback(napi_env env, napi_value callback, void*, void* data)
    {
        std::unique_ptr<Event> event(static_cast<Event*>(data));
        if (env == nullptr || callback == nullptr || !event) return;
        napi_value payload = nullptr;
        napi_create_object(env, &payload);
        napi_set_named_property(env, payload, "type", CreateString(env, event->type));
        napi_set_named_property(env, payload, "message", CreateString(env, event->message));
        napi_value value = nullptr;
        napi_create_int64(env, static_cast<int64_t>(event->epoch), &value); napi_set_named_property(env, payload, "eventEpoch", value);
        napi_create_int64(env, static_cast<int64_t>(event->sequence), &value); napi_set_named_property(env, payload, "sequence", value);
        napi_create_int64(env, static_cast<int64_t>(event->generation), &value); napi_set_named_property(env, payload, "surfaceGeneration", value);
        napi_value ignored = nullptr;
        napi_call_function(env, nullptr, callback, 1, &payload, &ignored);
    }

    void Dispatch(const std::string& type, const std::string& message)
    {
        std::lock_guard<std::mutex> lock(callbackMutex_);
        if (released_ || eventTsfn_ == nullptr) {
            OH_LOG_Print(LOG_APP, LOG_WARN, LOG_DOMAIN, LOG_TAG,
                "Dispatch: dropped type=%{public}s message=%{public}s released=%{public}d tsfnNull=%{public}d",
                type.c_str(), message.c_str(), released_, eventTsfn_ == nullptr);
            return;
        }
        auto* event = new Event{type, message, eventEpoch_, ++eventSequence_, generation_};
        if (napi_call_threadsafe_function(eventTsfn_, event, napi_tsfn_nonblocking) != napi_ok) delete event;
    }

    void EventLoop(mpv_handle* player)
    {
        // dwidth_/dheight_/pause 相关本地变量只在事件线程读写，无需原子操作。
        int lastDispatchedWidth = 0;
        int lastDispatchedHeight = 0;
        int lastDispatchedPause = -1; // -1 表示尚未收到过第一次通知（用作基线，不上报）
        std::string lastDispatchedTracks;
        std::string lastDispatchedSubtitleText;
        while (!stopEvents_) {
            mpv_event* event = mpv_wait_event(player, 0.1);
            if (event->event_id == MPV_EVENT_SHUTDOWN) break;
            if (event->event_id == MPV_EVENT_LOG_MESSAGE) {
                // 临时诊断：把 mpv/libass 日志打到 hilog，用于排查字幕不渲染问题。
                const auto* msg = static_cast<mpv_event_log_message*>(event->data);
                if (msg != nullptr && msg->text != nullptr) {
                    OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG, "mpv[%{public}s/%{public}s] %{public}s",
                        msg->prefix ? msg->prefix : "", msg->level ? msg->level : "", msg->text);
                }
            }
            if (event->event_id == MPV_EVENT_END_FILE) {
                const auto* end = static_cast<mpv_event_end_file*>(event->data);
                if (end != nullptr && end->reason == MPV_END_FILE_REASON_ERROR) Dispatch("error", "libmpv playback failed");
            }
            if (event->event_id == MPV_EVENT_PROPERTY_CHANGE) {
                const auto* prop = static_cast<mpv_event_property*>(event->data);
                if (prop != nullptr && prop->format == MPV_FORMAT_INT64 && prop->data != nullptr) {
                    const int64_t value = *static_cast<int64_t*>(prop->data);
                    if (std::strcmp(prop->name, "dwidth") == 0) videoWidth_ = static_cast<int>(value);
                    if (std::strcmp(prop->name, "dheight") == 0) videoHeight_ = static_cast<int>(value);
                    const int width = videoWidth_;
                    const int height = videoHeight_;
                    if (width > 0 && height > 0 && (width != lastDispatchedWidth || height != lastDispatchedHeight)) {
                        lastDispatchedWidth = width;
                        lastDispatchedHeight = height;
                        Dispatch("videoParams", std::to_string(width) + "x" + std::to_string(height));
                    }
                }
                if (prop != nullptr && prop->format == MPV_FORMAT_FLAG && prop->data != nullptr &&
                    std::strcmp(prop->name, "pause") == 0) {
                    const int value = *static_cast<int*>(prop->data);
                    if (lastDispatchedPause == -1) {
                        // 首次通知只作为基线记录，避免在尚未真正暂停/恢复过时误报状态。
                        lastDispatchedPause = value;
                    } else if (value != lastDispatchedPause) {
                        lastDispatchedPause = value;
                        Dispatch("state", value ? "paused" : "resumed");
                    }
                }
                if (prop != nullptr && prop->format == MPV_FORMAT_NODE && prop->data != nullptr &&
                    std::strcmp(prop->name, "track-list") == 0) {
                    const std::string encoded = EncodeTrackList(static_cast<mpv_node*>(prop->data));
                    if (encoded != lastDispatchedTracks) {
                        lastDispatchedTracks = encoded;
                        Dispatch("tracks", encoded);
                    }
                }
                if (prop != nullptr && std::strcmp(prop->name, "sub-text") == 0) {
                    // MPV_FORMAT_STRING 属性变化事件里 prop->data 是 char**；无字幕命中时
                    // mpv 上报空字符串（而非属性不存在），据此可以上报"当前无字幕"。
                    const std::string text = (prop->format == MPV_FORMAT_STRING && prop->data != nullptr)
                        ? std::string(*static_cast<char**>(prop->data)) : std::string();
                    if (text != lastDispatchedSubtitleText) {
                        lastDispatchedSubtitleText = text;
                        Dispatch("subtitleText", text);
                    }
                }
            }
        }
    }


    void RenderLoop()
    {
        std::uint64_t id = 0;
        try { id = std::stoull(surfaceId_); } catch (...) { MarkRendererFailed(); return; }
        OHNativeWindow* window = nullptr;
        int createRc = OH_NativeWindow_CreateNativeWindowFromSurfaceId(id, &window);
        if (createRc != 0 || window == nullptr) {
            OH_LOG_Print(LOG_APP, LOG_ERROR, LOG_DOMAIN, LOG_TAG, "CreateNativeWindowFromSurfaceId failed rc=%{public}d window=%{public}d", createRc, window != nullptr);
            MarkRendererFailed(); return;
        }
        window_ = window;
        // mpv 软件渲染输出 RGBA8888（每像素 4 字节），Surface 缓冲区格式必须匹配，
        // 否则显示 HDI 层会拒绝分配缓冲区（"format X can not support"）。
        int32_t format = NATIVEBUFFER_PIXEL_FMT_RGBA_8888;
        OH_NativeWindow_NativeWindowHandleOpt(window_, SET_FORMAT, format);
        OH_NativeWindow_NativeWindowHandleOpt(window_, SET_BUFFER_GEOMETRY, width_.load(), height_.load());
        // 软件渲染需要 CPU 直接写入缓冲区，必须显式声明 CPU 读写 usage，
        // 否则分配到的 BufferHandle::virAddr 为空（仅 GPU 可访问），导致每帧都被丢弃。
        uint64_t usage = NATIVEBUFFER_USAGE_CPU_READ | NATIVEBUFFER_USAGE_CPU_WRITE;
        OH_NativeWindow_NativeWindowHandleOpt(window_, SET_USAGE, usage);
        const char* api = MPV_RENDER_API_TYPE_SW;
        mpv_render_param params[] = {{MPV_RENDER_PARAM_API_TYPE, const_cast<char*>(api)}, {MPV_RENDER_PARAM_INVALID, nullptr}};
        int renderCreateRc = mpv_render_context_create(&renderer_, player_.get(), params);
        if (renderCreateRc < 0) {
            OH_LOG_Print(LOG_APP, LOG_ERROR, LOG_DOMAIN, LOG_TAG, "mpv_render_context_create failed rc=%{public}d", renderCreateRc);
            MarkRendererFailed(); DestroyRenderer(); return;
        }
        OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG, "renderer created, entering loop width=%{public}d height=%{public}d", width_.load(), height_.load());
        mpv_render_context_set_update_callback(renderer_, NotifyRender, this);
        { std::lock_guard<std::mutex> lock(rendererMutex_); rendererReady_ = true; rendererReadyCv_.notify_one(); }

        std::vector<uint8_t> pixels;
        while (true) {
            bool geometryDirty = false;
            { std::unique_lock<std::mutex> lock(rendererMutex_); renderCondition_.wait_for(lock, std::chrono::milliseconds(16), [this] { return stopRenderer_ || renderRequested_ || geometryDirty_; }); if (stopRenderer_) break; renderRequested_ = false; geometryDirty = geometryDirty_.exchange(false); }
            int width = width_; int height = height_;
            if (geometryDirty) OH_NativeWindow_NativeWindowHandleOpt(window_, SET_BUFFER_GEOMETRY, width, height);
            uint64_t updateFlags = mpv_render_context_update(renderer_);
            if ((updateFlags & MPV_RENDER_UPDATE_FRAME) == 0) continue;
            if (width <= 0 || height <= 0) continue;
            size_t stride = static_cast<size_t>(width) * 4;
            pixels.resize(stride * static_cast<size_t>(height));
            int size[] = {width, height}; char* rgba = const_cast<char*>("rgba");
            mpv_render_param frame[] = {{MPV_RENDER_PARAM_SW_SIZE, size}, {MPV_RENDER_PARAM_SW_FORMAT, rgba}, {MPV_RENDER_PARAM_SW_STRIDE, &stride}, {MPV_RENDER_PARAM_SW_POINTER, pixels.data()}, {MPV_RENDER_PARAM_INVALID, nullptr}};
            int renderResult = mpv_render_context_render(renderer_, frame);
            if (renderResult < 0) {
                OH_LOG_Print(LOG_APP, LOG_ERROR, LOG_DOMAIN, LOG_TAG, "mpv_render_context_render failed rc=%{public}d", renderResult);
                continue;
            }
            OHNativeWindowBuffer* buffer = nullptr;
            int fence = -1;
            int requestRc = OH_NativeWindow_NativeWindowRequestBuffer(window_, &buffer, &fence);
            if (requestRc != 0 || buffer == nullptr) {
                OH_LOG_Print(LOG_APP, LOG_ERROR, LOG_DOMAIN, LOG_TAG, "RequestBuffer failed rc=%{public}d buffer=%{public}d", requestRc, buffer != nullptr);
                continue;
            }
            BufferHandle* target = OH_NativeWindow_GetBufferHandleFromNative(buffer);
            void* mappedAddr = nullptr;
            bool ownsMapping = false;
            if (target != nullptr && target->virAddr == nullptr && target->fd >= 0 && target->size > 0) {
                // 部分设备/模拟器上 HDI 不会自动为 BufferHandle 填充 virAddr（CPU 可访问的映射地址），
                // 需要应用侧通过 fd 自行 mmap，这是软件渲染路径写入像素数据的常见回退方案。
                mappedAddr = mmap(nullptr, static_cast<size_t>(target->size), PROT_READ | PROT_WRITE, MAP_SHARED, target->fd, 0);
                if (mappedAddr != MAP_FAILED && mappedAddr != nullptr) {
                    ownsMapping = true;
                } else {
                    mappedAddr = nullptr;
                }
            }
            void* virAddr = (target != nullptr && target->virAddr != nullptr) ? target->virAddr : mappedAddr;
            if (target == nullptr || virAddr == nullptr || target->stride < width * 4 || target->height < height) {
                OH_LOG_Print(LOG_APP, LOG_ERROR, LOG_DOMAIN, LOG_TAG,
                    "target invalid target=%{public}d virAddr=%{public}d fd=%{public}d size=%{public}d stride=%{public}d needStride=%{public}d bufHeight=%{public}d needHeight=%{public}d",
                    target != nullptr, virAddr != nullptr, target != nullptr ? target->fd : -1, target != nullptr ? target->size : -1,
                    target != nullptr ? target->stride : -1, width * 4, target != nullptr ? target->height : -1, height);
                Region empty{};
                OH_NativeWindow_NativeWindowFlushBuffer(window_, buffer, fence, empty);
                if (ownsMapping) munmap(mappedAddr, static_cast<size_t>(target->size));
                continue;
            }
            for (int row = 0; row < height; ++row) {
                memcpy(static_cast<uint8_t*>(virAddr) + static_cast<size_t>(row) * target->stride, pixels.data() + static_cast<size_t>(row) * stride, stride);
            }
            if (ownsMapping) munmap(mappedAddr, static_cast<size_t>(target->size));
            Region region{};
            Region::Rect rect = {0, 0, static_cast<uint32_t>(width), static_cast<uint32_t>(height)};
            region.rects = &rect;
            region.rectNumber = 1;
            OH_NativeWindow_NativeWindowFlushBuffer(window_, buffer, fence, region);
            // 只在真正成功提交过一次真实解码帧到 NativeWindow 后才上报 playing，
            // 避免把 attach/load 命令成功等间接信号伪造成首帧证据。
            if (!firstFrameSent_.exchange(true)) {
                Dispatch("state", "playing");
            }
        }
        DestroyRenderer();
    }

    void MarkRendererFailed()
    {
        std::lock_guard<std::mutex> lock(rendererMutex_);
        rendererFailed_ = true;
        rendererReadyCv_.notify_one();
    }

    void StopRendererLocked()
    {
        { std::lock_guard<std::mutex> lock(rendererMutex_); stopRenderer_ = true; renderCondition_.notify_one(); }
        if (renderThread_.joinable()) renderThread_.join();
        rendererReady_ = false;
    }

    void DestroyRenderer()
    {
        if (renderer_ != nullptr) { mpv_render_context_set_update_callback(renderer_, nullptr, nullptr); mpv_render_context_free(renderer_); renderer_ = nullptr; }
        if (window_ != nullptr) { OH_NativeWindow_DestroyNativeWindow(window_); window_ = nullptr; }
    }

    void CloseCallbackLocked()
    {
        if (eventTsfn_ != nullptr) { napi_release_threadsafe_function(eventTsfn_, napi_tsfn_release); eventTsfn_ = nullptr; }
    }

    std::unique_ptr<mpv_handle, decltype(&mpv_terminate_destroy)> player_{nullptr, mpv_terminate_destroy};
    std::mutex lifecycleMutex_;
    std::mutex rendererMutex_;
    std::condition_variable rendererReadyCv_;
    std::condition_variable renderCondition_;
    std::thread eventThread_;
    std::thread renderThread_;
    std::atomic<bool> stopEvents_{false};
    bool stopRenderer_ = false;
    bool renderRequested_ = false;
    std::atomic<bool> geometryDirty_{false};
    bool rendererReady_ = false;
    bool rendererFailed_ = false;
    bool released_ = false;
    std::string surfaceId_;
    std::atomic<std::uint64_t> generation_{0};
    std::atomic<std::uint64_t> eventEpoch_{0};
    std::atomic<std::uint64_t> eventSequence_{0};
    std::atomic<int> width_{0};
    std::atomic<int> height_{0};
    // videoWidth_/videoHeight_ 只在 EventLoop 所在的事件线程读写，无需原子操作。
    int videoWidth_ = 0;
    int videoHeight_ = 0;
    std::atomic<bool> firstFrameSent_{false};
    OHNativeWindow* window_ = nullptr;
    mpv_render_context* renderer_ = nullptr;
    std::mutex callbackMutex_;
    napi_threadsafe_function eventTsfn_ = nullptr;
};
#endif

std::mutex gSessionsMutex;
#if VIDALL_MPV_AVAILABLE
std::unordered_map<std::uint64_t, std::shared_ptr<NativeSession>> gSessions;
#endif
std::uint64_t gNextSessionId = 1;

#if VIDALL_MPV_AVAILABLE
std::shared_ptr<NativeSession> FindSession(std::uint64_t handle)
{
    std::lock_guard<std::mutex> lock(gSessionsMutex);
    const auto session = gSessions.find(handle);
    return session == gSessions.end() ? nullptr : session->second;
}
#endif

napi_value CreateSession(napi_env env, napi_callback_info info)
{
    napi_value args[1] = {nullptr}; size_t argc = 1;
    std::string fontsDir;
    if (napi_get_cb_info(env, info, &argc, args, nullptr, nullptr) == napi_ok && argc >= 1) {
        ReadString(env, args[0], fontsDir);
    }
#if VIDALL_MPV_AVAILABLE
    auto session = std::make_shared<NativeSession>();
    if (!session->Initialize(fontsDir)) return CreateResult(env, {false, 0, "NATIVE_PLAYBACK_FAILED"});
    std::lock_guard<std::mutex> lock(gSessionsMutex);
    const std::uint64_t handle = gNextSessionId++;
    gSessions.emplace(handle, std::move(session));
    return CreateResult(env, {true, handle, "OK"});
#else
    return CreateResult(env, {false, 0, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value ReleaseSession(napi_env env, napi_callback_info info)
{
    napi_value args[1] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0;
    if (!GetArguments(env, info, 1, args, argc) || argc != 1 || !ReadHandle(env, args[0], handle)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session;
    { std::lock_guard<std::mutex> lock(gSessionsMutex); const auto found = gSessions.find(handle); if (found == gSessions.end()) return CreateResult(env, {true, handle, "ALREADY_RELEASED"}); session = std::move(found->second); gSessions.erase(found); }
    session->Release();
    return CreateResult(env, {true, handle, "RELEASED"});
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value WithSurface(napi_env env, napi_callback_info info, int operation)
{
    napi_value args[5] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; std::string component;
    int64_t generation = 0, width = 0, height = 0;
    if (!GetArguments(env, info, 5, args, argc) || argc != 5 || !ReadHandle(env, args[0], handle) || !ReadString(env, args[1], component) ||
        napi_get_value_int64(env, args[2], &generation) != napi_ok || napi_get_value_int64(env, args[3], &width) != napi_ok || napi_get_value_int64(env, args[4], &height) != napi_ok) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    if (session == nullptr) return CreateResult(env, {false, handle, "RELEASED"});
    return CreateResult(env, operation == 0 ? session->Attach(component, generation, width, height, handle) : session->Resize(generation, width, height, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}
napi_value AttachSurface(napi_env env, napi_callback_info info) { return WithSurface(env, info, 0); }
napi_value ResizeSurface(napi_env env, napi_callback_info info) { return WithSurface(env, info, 1); }

napi_value DetachSurface(napi_env env, napi_callback_info info)
{
    napi_value args[2] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; int64_t generation = 0;
    if (!GetArguments(env, info, 2, args, argc) || argc != 2 || !ReadHandle(env, args[0], handle) || napi_get_value_int64(env, args[1], &generation) != napi_ok) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle); return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->Detach(generation, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value Load(napi_env env, napi_callback_info info)
{
    napi_value args[5] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0;
    std::string uri; std::string headerFields; std::string smbUsername; std::string smbPassword;
    if (!GetArguments(env, info, 5, args, argc) || argc != 5 || !ReadHandle(env, args[0], handle) ||
        !ReadString(env, args[1], uri) || !ReadString(env, args[2], headerFields) ||
        !ReadString(env, args[3], smbUsername) || !ReadString(env, args[4], smbPassword)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    if (session != nullptr) {
        NativeResult result = session->Load(uri, headerFields, smbUsername, smbPassword, handle);
        smbUsername.assign(smbUsername.size(), '\0');
        smbPassword.assign(smbPassword.size(), '\0');
        return CreateResult(env, result);
    }
    return CreateResult(env, {false, handle, "RELEASED"});
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value Control(napi_env env, napi_callback_info info, int action)
{
    napi_value args[1] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0;
    if (!GetArguments(env, info, 1, args, argc) || argc != 1 || !ReadHandle(env, args[0], handle)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    if (session == nullptr) return CreateResult(env, {false, handle, "RELEASED"});
    NativeResult result = action == 1 ? session->Play(handle) : (action == 2 ? session->Pause(handle) : session->Stop(handle));
    return CreateResult(env, result);
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}
napi_value Play(napi_env env, napi_callback_info info) { return Control(env, info, 1); }
napi_value Pause(napi_env env, napi_callback_info info) { return Control(env, info, 2); }
napi_value Stop(napi_env env, napi_callback_info info) { return Control(env, info, 0); }

napi_value SeekRelative(napi_env env, napi_callback_info info)
{
    napi_value args[2] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; double seconds = 0;
    if (!GetArguments(env, info, 2, args, argc) || argc != 2 || !ReadHandle(env, args[0], handle) ||
        napi_get_value_double(env, args[1], &seconds) != napi_ok) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->SeekRelative(seconds, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value SeekPercent(napi_env env, napi_callback_info info)
{
    napi_value args[2] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; double percent = 0;
    if (!GetArguments(env, info, 2, args, argc) || argc != 2 || !ReadHandle(env, args[0], handle) ||
        napi_get_value_double(env, args[1], &percent) != napi_ok) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->SeekPercent(percent, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value SetRate(napi_env env, napi_callback_info info)
{
    napi_value args[2] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; double rate = 0;
    if (!GetArguments(env, info, 2, args, argc) || argc != 2 || !ReadHandle(env, args[0], handle) ||
        napi_get_value_double(env, args[1], &rate) != napi_ok) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->SetRate(rate, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value SelectTrack(napi_env env, napi_callback_info info)
{
    napi_value args[3] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; std::string kind; int64_t trackId = 0;
    if (!GetArguments(env, info, 3, args, argc) || argc != 3 || !ReadHandle(env, args[0], handle) ||
        !ReadString(env, args[1], kind) || napi_get_value_int64(env, args[2], &trackId) != napi_ok) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->SelectTrack(kind, trackId, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value AddExternalTrack(napi_env env, napi_callback_info info, const char* kind)
{
    napi_value args[2] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; std::string uri;
    if (!GetArguments(env, info, 2, args, argc) || argc != 2 || !ReadHandle(env, args[0], handle) ||
        !ReadString(env, args[1], uri)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->AddExternalTrack(kind, uri, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}
napi_value AddExternalAudio(napi_env env, napi_callback_info info) { return AddExternalTrack(env, info, "audio"); }
napi_value AddExternalSubtitle(napi_env env, napi_callback_info info) { return AddExternalTrack(env, info, "subtitle"); }

napi_value SetEventCallback(napi_env env, napi_callback_info info)
{
    napi_value args[2] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0;
    if (!GetArguments(env, info, 2, args, argc) || argc != 2 || !ReadHandle(env, args[0], handle)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle); return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->SetEventCallback(env, args[1], handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

void CleanupSessions(void*)
{
#if VIDALL_MPV_AVAILABLE
    std::unordered_map<std::uint64_t, std::shared_ptr<NativeSession>> sessions;
    { std::lock_guard<std::mutex> lock(gSessionsMutex); sessions.swap(gSessions); }
#endif
}

napi_value Init(napi_env env, napi_value exports)
{
    napi_property_descriptor descriptors[] = {
        {"createSession", nullptr, CreateSession, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"releaseSession", nullptr, ReleaseSession, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"attachSurface", nullptr, AttachSurface, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"resizeSurface", nullptr, ResizeSurface, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"detachSurface", nullptr, DetachSurface, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"load", nullptr, Load, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"play", nullptr, Play, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"pause", nullptr, Pause, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"stop", nullptr, Stop, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"seekRelative", nullptr, SeekRelative, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"seekPercent", nullptr, SeekPercent, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setRate", nullptr, SetRate, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"selectTrack", nullptr, SelectTrack, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"addExternalAudio", nullptr, AddExternalAudio, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"addExternalSubtitle", nullptr, AddExternalSubtitle, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setEventCallback", nullptr, SetEventCallback, nullptr, nullptr, nullptr, napi_default, nullptr},
    };
    if (!Check(env, napi_define_properties(env, exports, sizeof(descriptors) / sizeof(descriptors[0]), descriptors), "Failed to define native bridge exports.") ||
        !Check(env, napi_add_env_cleanup_hook(env, CleanupSessions, nullptr), "Failed to register cleanup hook.")) return nullptr;
    return exports;
}
} // namespace

NAPI_MODULE(vidall_player_native, Init)
