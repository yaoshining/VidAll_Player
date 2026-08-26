#include <napi/native_api.h>
#include <hilog/log.h>

#include <atomic>
#include <chrono>
#include <cmath>
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
#include <mpv/render_gl.h>
#include <native_window/external_window.h>
#include <native_buffer/native_buffer.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
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

// JSON 字符串转义：处理反斜杠和双引号，防止破坏 JSON 结构。
std::string EscapeJsonString(const std::string& s)
{
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        if (c == '\\') { out += "\\\\"; }
        else if (c == '"') { out += "\\\""; }
        else if (c == '\n') { out += "\\n"; }
        else if (c == '\r') { out += "\\r"; }
        else if (c == '\t') { out += "\\t"; }
        else { out += c; }
    }
    return out;
}

// 将 mpv "track-list" 属性（MPV_FORMAT_NODE_ARRAY，元素为 MPV_FORMAT_NODE_MAP）编码为
// JSON 字符串上报给 ArkTS 层。每条轨道记录包含扩展元数据字段（codec/profile/level/
// bitrate/default/forced/demux-fps/demux-samplerate/demux-channels 等）。
// 记录间以 \x1e（record separator）分隔作为去重键，完整 JSON 数组作为消息体。
// 只保留 audio/sub 类型（视频轨不参与 ArkTS 层音轨/字幕选择 UI）。
std::string EncodeTrackList(const mpv_node* node)
{
    if (node == nullptr || node->format != MPV_FORMAT_NODE_ARRAY || node->u.list == nullptr) return "";
    std::string json = "[";
    std::string dedupKey;
    const mpv_node_list* list = node->u.list;
    bool first = true;
    for (int i = 0; i < list->num; ++i) {
        const mpv_node& entry = list->values[i];
        if (entry.format != MPV_FORMAT_NODE_MAP || entry.u.list == nullptr) continue;
        const mpv_node_list* map = entry.u.list;
        // 收集字段
        int64_t id = -1;
        std::string type;
        std::string lang;
        std::string title;
        int selected = 0;
        std::string codec;
        std::string profile;
        double level = 0;
        double bitrate = 0;
        int defaultTrack = 0;
        int forced = 0;
        double demuxFps = 0;
        double demuxSamplerate = 0;
        double demuxChannels = 0;
        int64_t demuxW = 0;
        int64_t demuxH = 0;
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
            } else if (key == "codec" && value.format == MPV_FORMAT_STRING && value.u.string != nullptr) {
                codec = value.u.string;
            } else if (key == "profile" && value.format == MPV_FORMAT_STRING && value.u.string != nullptr) {
                profile = value.u.string;
            } else if (key == "level" && value.format == MPV_FORMAT_DOUBLE) {
                level = value.u.double_;
            } else if (key == "demux-bitrate" && value.format == MPV_FORMAT_DOUBLE) {
                bitrate = value.u.double_;
            } else if (key == "default" && value.format == MPV_FORMAT_FLAG) {
                defaultTrack = value.u.flag;
            } else if (key == "forced" && value.format == MPV_FORMAT_FLAG) {
                forced = value.u.flag;
            } else if (key == "demux-fps" && value.format == MPV_FORMAT_DOUBLE) {
                demuxFps = value.u.double_;
            } else if (key == "demux-samplerate" && value.format == MPV_FORMAT_DOUBLE) {
                demuxSamplerate = value.u.double_;
            } else if (key == "demux-channels" && value.format == MPV_FORMAT_DOUBLE) {
                demuxChannels = value.u.double_;
            } else if (key == "demux-w" && value.format == MPV_FORMAT_INT64) {
                demuxW = value.u.int64;
            } else if (key == "demux-h" && value.format == MPV_FORMAT_INT64) {
                demuxH = value.u.int64;
            }
        }
        if (id < 0 || (type != "audio" && type != "sub" && type != "video")) continue;
        // 去重键
        if (!dedupKey.empty()) dedupKey.push_back('\x1e');
        dedupKey += std::to_string(id) + "\x1f" + type + "\x1f" + lang + "\x1f" + title +
            "\x1f" + (selected ? "1" : "0") + "\x1f" + codec + "\x1f" + std::to_string(bitrate);
        // JSON 条目
        if (!first) json += ",";
        first = false;
        json += "{\"id\":" + std::to_string(id) +
            ",\"type\":\"" + type + "\"" +
            ",\"lang\":\"" + EscapeJsonString(lang) + "\"" +
            ",\"title\":\"" + EscapeJsonString(title) + "\"" +
            ",\"selected\":" + (selected ? "1" : "0") +
            ",\"default\":" + (defaultTrack ? "1" : "0") +
            ",\"forced\":" + (forced ? "1" : "0");
        if (!codec.empty()) json += ",\"codec\":\"" + EscapeJsonString(codec) + "\"";
        if (!profile.empty()) json += ",\"profile\":\"" + EscapeJsonString(profile) + "\"";
        if (level > 0) json += ",\"level\":" + std::to_string(static_cast<int>(level));
        if (bitrate > 0) json += ",\"bitrate\":" + std::to_string(static_cast<int64_t>(bitrate));
        if (type == "audio") {
            if (demuxSamplerate > 0) json += ",\"demux_samplerate\":" + std::to_string(static_cast<int>(demuxSamplerate));
            if (demuxChannels > 0) json += ",\"demux_channels\":" + std::to_string(static_cast<int>(demuxChannels));
        }
        if (type == "video" && demuxFps > 0) {
            json += ",\"demux_fps\":" + std::to_string(demuxFps);
        }
        if (type == "video") {
            // 视频轨道分辨率与宽高比
            if (demuxW > 0 && demuxH > 0) {
                json += ",\"resolution\":\"" + std::to_string(demuxW) + "x" + std::to_string(demuxH) + "\"";
            }
        }
        json += "}";
    }
    json += "]";
    // 如果没有任何有效轨道，返回空字符串
    if (first) return "";
    // 拼接：去重键 + \x1f + JSON
    return dedupKey + "\x1f" + json;
}

// mpv GL 渲染所需的 GL 函数指针解析器：HarmonyOS EGL 的 eglGetProcAddress
// 能返回所有 ES3 扩展与核心函数指针，满足 mpv render_gl 的需求。
#if VIDALL_MPV_AVAILABLE
static void* MpvGlGetProcAddress(void* /*ctx*/, const char* name)
{
    return reinterpret_cast<void*>(eglGetProcAddress(name));
}
#endif

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

    bool Initialize(const std::string& fontsDir, const std::string& hwdec,
                    const std::string& toneMapping, const std::string& hdrComputePeak)
    {
        if (!player_) return false;
        mpv_set_option_string(player_.get(), "terminal", "no");
        mpv_set_option_string(player_.get(), "config", "no");
        // issue #71（DV Profile 5 渲染层迁移）：由 vo=libmpv(vo_gpu) 改为 vo_gpu_next，
        // 后者经 libplacebo pl_renderer 做 dovi RPU→显示 reshape。fork 复用 mpv --wid 传
        // XComponent Surface id（vo_ohos_init 读 WinID → OH_NativeWindow_CreateNativeWindowFromSurfaceId），
        // 并经 gpu-api=vulkan + ra_ctx_vulkan_ohos 建 Vulkan surface。需在 mpv_initialize 前设置。
        mpv_set_option_string(player_.get(), "vo", "gpu-next");
        mpv_set_option_string(player_.get(), "gpu-api", "vulkan");
        // 显式指定 ohos 上下文（可选：fork 在 OHOS 上可能按 gpu-api 自动选 ra_ctx_vulkan_ohos）。
        mpv_set_option_string(player_.get(), "gpu-context", "ohosvk");
        // HDR tone mapping（issue #66）：vo_gpu_next 也支持 tone-mapping/hdr-compute-peak。
        // 显式下发缺省 bt.2390 + auto，让 HDR10(PQ)/HLG/BT.2020/DV 内容确定性 tone map 到 SDR。
        mpv_set_option_string(player_.get(), "tone-mapping", toneMapping.empty() ? "bt.2390" : toneMapping.c_str());
        mpv_set_option_string(player_.get(), "hdr-compute-peak", hdrComputePeak.empty() ? "auto" : hdrComputePeak.c_str());
        // 硬件解码：libmpv 编译时 --enable-ohcodec，链接 libnative_media_vdec.so。
        // hwdec 为空时保留 mpv 默认（软件解码）；"auto-safe" 自动选择 ohcodec 硬解后端，
        // 失败时回退软件解码；"no" 强制软件解码。
        if (!hwdec.empty()) {
            mpv_set_option_string(player_.get(), "hwdec", hwdec.c_str());
            hardwareDecodingRequested_.store(hwdec != "no");
        }
        if (!fontsDir.empty()) {
            // HarmonyOS 沙箱内没有系统 fontconfig，libass 的 fontconfig provider 探测不到
            // 任何字体，导致字幕轨道被正确选中但完全不可见（无渲染文字）。改用 "none"
            // provider 并显式指定应用侧解包好的字体目录，让 libass 直接按目录匹配字体。
            mpv_set_option_string(player_.get(), "sub-font-provider", "none");
            mpv_set_option_string(player_.get(), "sub-fonts-dir", fontsDir.c_str());
            mpv_set_option_string(player_.get(), "osd-fonts-dir", fontsDir.c_str());
        }
        if (mpv_initialize(player_.get()) < 0) return false;
        // 诊断（issue #71）：请求 mpv 详细日志，经 MPV_EVENT_LOG_MESSAGE 转发到 hilog，
        // 便于真机查看 vo_gpu_next/ohosvk/Vulkan surface 初始化的真实结果或报错。
        mpv_request_log_messages(player_.get(), "v");
        // 输出当前 hwdec 设置，便于真机日志确认硬件解码策略已下发到 mpv。
        const char* hwdecValue = mpv_get_property_string(player_.get(), "hwdec");
        OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG, "hwdec configured: %{public}s", hwdecValue != nullptr ? hwdecValue : "(null)");
        // 输出生效的 HDR tone mapping 设置，便于真机日志确认 HDR 兜底配置已下发到 mpv。
        char* toneMappingValue = mpv_get_property_string(player_.get(), "tone-mapping");
        char* hdrComputePeakValue = mpv_get_property_string(player_.get(), "hdr-compute-peak");
        OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG,
            "hdr tone-mapping configured: tone-mapping=%{public}s hdr-compute-peak=%{public}s",
            toneMappingValue != nullptr ? toneMappingValue : "(null)",
            hdrComputePeakValue != nullptr ? hdrComputePeakValue : "(null)");
        if (toneMappingValue != nullptr) mpv_free(toneMappingValue);
        if (hdrComputePeakValue != nullptr) mpv_free(hdrComputePeakValue);
        // 观察 hwdec-current：mpv 在文件加载并选定解码器后会设置此属性，
        // 用于真机日志确认 ohcodec 硬件解码后端是否真正激活（空串=软解）。
        mpv_observe_property(player_.get(), 0, "hwdec-current", MPV_FORMAT_STRING);
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
        // 观察 video-params：mpv 上报的视频色彩与格式元数据（像素格式/位深度/
        // 基色/传输/色偏矩阵/视频范围/旋转/宽高比/隔行扫描），用于向 ArkTS 层
        // 暴露与系统 AVPlayer 对等的视频参数详情。
        mpv_observe_property(player_.get(), 0, "video-params", MPV_FORMAT_NODE);
        // 观察 container-fps：mpv 上报的容器帧率，用于 videoParams.fps 字段。
        mpv_observe_property(player_.get(), 0, "container-fps", MPV_FORMAT_DOUBLE);
        // 观察 audio-params：mpv 上报的音频输出格式（采样率/声道布局/声道数/采样格式），
        // 用于向 ArkTS 层暴露与系统 AVPlayer 对等的音频参数详情。声道布局字符串
        // （如 "stereo"/"5.1"）只存在于 audio-params，track-list 仅有数字声道数。
        mpv_observe_property(player_.get(), 0, "audio-params", MPV_FORMAT_NODE);
        // 观察 video-bitrate/audio-bitrate：实时解码码率，用于元数据弹层显示。
        // 某些容器（如 MKV）不报告 demux-bitrate（track-list 中为 0），需要用
        // 实时码率作为替代数据源。
        mpv_observe_property(player_.get(), 0, "video-bitrate", MPV_FORMAT_DOUBLE);
        mpv_observe_property(player_.get(), 0, "audio-bitrate", MPV_FORMAT_DOUBLE);
        // 观察 time-pos/duration：mpv 上报的当前播放位置与媒体总时长（秒），
        // 用于向 ArkTS 层周期性 emit 'position' 事件（VidAll_TV 进度条/续播依赖
        // 的 IPlayer.onTimeUpdate 契约）。ArkTS 侧再做 100ms 节流避免事件洪泛。
        mpv_observe_property(player_.get(), 0, "time-pos", MPV_FORMAT_DOUBLE);
        mpv_observe_property(player_.get(), 0, "duration", MPV_FORMAT_DOUBLE);
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
        // 认证（libsmbclient 已静态进入宿主统一打包的 libavformat.so），不走 HTTP header；其余来源仍使用
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
        // 抑制旧文件残留 time-pos：在新文件 FILE_LOADED 之前不派发 position，
        // 避免旧媒体进度携带新 eventEpoch_ 误报到 ArkTS。
        positionActive_ = false;
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

    // 通用 mpv 字符串属性设置接口，供上层动态控制 sid、sub-visibility 等属性。
    NativeResult SetPropertyString(const std::string& property, const std::string& value, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        if (property.empty()) return {false, handle, "INPUT_INVALID"};
        return mpv_set_property_string(player_.get(), property.c_str(), value.c_str()) >= 0
            ? NativeResult{true, handle, "OK"} : NativeResult{false, handle, "NATIVE_PLAYBACK_FAILED"};
    }

    NativeResult SetAudioFilter(const std::string& filter, std::uint64_t handle)
    {
        return SetPropertyString("af", filter, handle);
    }

    NativeResult SetVolume(double volume, std::uint64_t handle)
    {
        if (!std::isfinite(volume) || volume < 0 || volume > 100) return {false, handle, "INPUT_INVALID"};
        return SetPropertyString("volume", std::to_string(volume), handle);
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
                type.c_str(), message.c_str(), released_.load(), eventTsfn_ == nullptr);
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
        std::string lastDispatchedHwdec;
        // 构建完整的 videoParams 消息：宽x高|hwdec|pixfmt|bitDepth|primaries|transfer|matrix|videoRange|fps|rotation|aspectRatio|interlaced|colorLevels
        auto BuildVideoParamsMessage = [this, &lastDispatchedHwdec]() -> std::string {
            // pixelformat 在硬解时可能返回硬件名（如 "ohcodec"），此时用 hw-pixelformat
            // 作为 fallback（后者通常是标准格式如 "yuv420p"）。
            std::string displayPixfmt = vpPixfmt_;
            const bool isStdPixfmt = !displayPixfmt.empty() &&
                (displayPixfmt.find("yuv") == 0 || displayPixfmt.find("rgb") == 0 ||
                 displayPixfmt.find("nv") == 0 || displayPixfmt.find("p010") == 0 ||
                 displayPixfmt.find("gbrp") == 0 || displayPixfmt.find("gray") == 0 ||
                 displayPixfmt.find("ayuv") == 0 || displayPixfmt.find("ya8") == 0);
            if (!isStdPixfmt && !vpHwPixfmt_.empty()) {
                const bool isHwStd = vpHwPixfmt_.find("yuv") == 0 || vpHwPixfmt_.find("rgb") == 0 ||
                    vpHwPixfmt_.find("nv") == 0 || vpHwPixfmt_.find("p010") == 0 ||
                    vpHwPixfmt_.find("gbrp") == 0 || vpHwPixfmt_.find("gray") == 0;
                if (isHwStd) displayPixfmt = vpHwPixfmt_;
            }
            std::string msg = std::to_string(videoWidth_) + "x" + std::to_string(videoHeight_) + "|" + lastDispatchedHwdec;
            msg += "|" + displayPixfmt;
            msg += "|" + (vpBitDepth_ > 0 ? std::to_string(vpBitDepth_) : std::string());
            msg += "|" + vpPrimaries_;
            msg += "|" + vpTransfer_;
            msg += "|" + vpMatrix_;
            msg += "|" + vpVideoRange_;
            msg += "|" + (vpFps_ > 0 ? std::to_string(vpFps_) : std::string());
            msg += "|" + (vpRotate_ != 0 ? std::to_string(vpRotate_) : std::string("0"));
            msg += "|" + vpAspect_;
            msg += "|" + std::string(vpInterlaced_ ? "1" : "0");
            msg += "|" + vpColorLevels_;
            msg += "|" + (vpBitrate_ > 0 ? std::to_string(static_cast<int64_t>(vpBitrate_)) : std::string());
            return msg;
        };
        // 构建完整的 audioParams 消息：samplerate|channels|channelCount|format
        auto BuildAudioParamsMessage = [this]() -> std::string {
            std::string msg = std::to_string(apSamplerate_);
            msg += "|" + apChannels_;
            msg += "|" + std::to_string(apChannelCount_);
            msg += "|" + apFormat_;
            msg += "|" + (apBitrate_ > 0 ? std::to_string(static_cast<int64_t>(apBitrate_)) : std::string());
            return msg;
        };
        // 把当前缓存的 time-pos/duration（秒）转成毫秒并以 JSON 字符串派发给 ArkTS。
        // 仅当至少有一个有效值且与上次派发值不同时才发，避免 mpv 同值重复触发造成洪泛。
        // ArkTS 侧再叠加 100ms 节流（见 playerSession.ets 的 position 分支）。
        // time-pos < 0（mpv 初始化/无媒体）或 duration <= 0（直播/未知时长）按 0 上报，
        // 让消费方知道"位置未知"而非收到陈旧的旧值。
        auto DispatchPositionIfChanged = [this]() -> void {
            // 旧文件残留的 time-pos 在新文件 FILE_LOADED 之前不派发，避免携带新
            // eventEpoch_ 把旧媒体进度误报给 ArkTS（Load() 已置 positionActive_=false）。
            if (!positionActive_) return;
            const long long posMs = positionSeconds_ > 0 ? static_cast<long long>(positionSeconds_ * 1000.0 + 0.5) : 0;
            const long long durMs = durationSeconds_ > 0 ? static_cast<long long>(durationSeconds_ * 1000.0 + 0.5) : 0;
            if (positionSeconds_ < 0 && durationSeconds_ < 0) return;
            if (posMs == lastPositionMs_ && durMs == lastDurationMs_) return;
            lastPositionMs_ = posMs;
            lastDurationMs_ = durMs;
            std::string msg = "{\"positionMs\":";
            msg += std::to_string(posMs);
            msg += ",\"durationMs\":";
            msg += std::to_string(durMs);
            msg += "}";
            Dispatch("position", msg);
        };
        while (!stopEvents_) {
            mpv_event* event = mpv_wait_event(player, 0.1);
            if (event->event_id == MPV_EVENT_SHUTDOWN) break;
            // issue #71（vo_gpu_next 路径）：旧 vo_gpu 在 GlRenderLoop/SwRenderLoop 里首帧派发
            // "playing"；改为 vo_gpu_next 后这些循环被跳过，这里在视频输出重建（VO 出帧）时
            // 派发一次首帧 "playing"，保证消费方 _isPlaying 正确。firstFrameSent_ 只发一次。
            if (event->event_id == MPV_EVENT_VIDEO_RECONFIG) {
                if (!firstFrameSent_.exchange(true)) {
                    Dispatch("state", "playing");
                }
            }
            // 诊断（issue #71）：转发 mpv 日志消息到 hilog，便于真机定位 vo_gpu_next/ohosvk/Vulkan 初始化。
            if (event->event_id == MPV_EVENT_LOG_MESSAGE) {
                const auto* log = static_cast<mpv_event_log_message*>(event->data);
                if (log != nullptr && log->text != nullptr) {
                    OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG,
                        "mpv[%{public}s]: %{public}s", log->prefix != nullptr ? log->prefix : "", log->text);
                }
            }
            if (event->event_id == MPV_EVENT_END_FILE) {
                const auto* end = static_cast<mpv_event_end_file*>(event->data);
                if (end != nullptr && end->reason == MPV_END_FILE_REASON_ERROR) Dispatch("error", "libmpv playback failed");
                // 重置 video-params 缓存，避免跨文件残留旧属性
                vpPixfmt_.clear(); vpHwPixfmt_.clear(); vpBitDepth_ = 0; vpPrimaries_.clear();
                vpTransfer_.clear(); vpMatrix_.clear(); vpVideoRange_.clear();
                vpFps_ = 0; vpRotate_ = 0; vpAspect_.clear(); vpInterlaced_ = false;
                vpColorLevels_.clear();
                vpBitrate_ = 0;
                // 重置 audio-params 缓存
                apSamplerate_ = 0; apChannels_.clear(); apChannelCount_ = 0; apFormat_.clear();
                apBitrate_ = 0;
                // 重置 position 缓存，避免跨文件残留旧进度；下次新文件的 time-pos/duration
                // 属性变化会重新填充并触发派发。
                positionSeconds_ = -1.0;
                durationSeconds_ = -1.0;
                lastPositionMs_ = -1;
                lastDurationMs_ = -1;
                // 抑制旧文件残留 time-pos：END_FILE 后到新文件 FILE_LOADED 之间不派发 position。
                positionActive_ = false;
            }
            if (event->event_id == MPV_EVENT_FILE_LOADED) {
                // 新文件已加载就绪，激活 position 派发。在此之前 Load() 已把
                // positionActive_ 置 false，旧文件残留的 time-pos 会被丢弃，
                // 不会携带新 eventEpoch_ 误报旧媒体进度。
                positionActive_ = true;
            }
            if (event->event_id == MPV_EVENT_PROPERTY_CHANGE) {
                const auto* prop = static_cast<mpv_event_property*>(event->data);
                if (prop != nullptr && prop->format == MPV_FORMAT_STRING && prop->data != nullptr &&
                    std::strcmp(prop->name, "hwdec-current") == 0) {
                    const char* hwdecCurrent = *static_cast<char**>(prop->data);
                    const std::string hwdec = (hwdecCurrent != nullptr) ? hwdecCurrent : "";
                    OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG, "hwdec-current: %{public}s", hwdec.c_str());
                    if (hwdec != lastDispatchedHwdec) {
                        lastDispatchedHwdec = hwdec;
                        const int width = videoWidth_;
                        const int height = videoHeight_;
                        if (width > 0 && height > 0) {
                            Dispatch("videoParams", BuildVideoParamsMessage());
                        }
                    }
                }
                if (prop != nullptr && prop->format == MPV_FORMAT_INT64 && prop->data != nullptr) {
                    const int64_t value = *static_cast<int64_t*>(prop->data);
                    if (std::strcmp(prop->name, "dwidth") == 0) videoWidth_ = static_cast<int>(value);
                    if (std::strcmp(prop->name, "dheight") == 0) videoHeight_ = static_cast<int>(value);
                    const int width = videoWidth_;
                    const int height = videoHeight_;
                    if (width > 0 && height > 0 && (width != lastDispatchedWidth || height != lastDispatchedHeight)) {
                        lastDispatchedWidth = width;
                        lastDispatchedHeight = height;
                        // 附带当前已知的 hwdec 状态和 video-params 扩展字段。
                        Dispatch("videoParams", BuildVideoParamsMessage());
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
                // container-fps 属性变化：更新缓存并触发 videoParams 重新上报
                if (prop != nullptr && prop->format == MPV_FORMAT_DOUBLE && prop->data != nullptr &&
                    std::strcmp(prop->name, "container-fps") == 0) {
                    const double fps = *static_cast<double*>(prop->data);
                    if (vpFps_ != fps && fps > 0) {
                        vpFps_ = fps;
                        if (videoWidth_ > 0 && videoHeight_ > 0) {
                            Dispatch("videoParams", BuildVideoParamsMessage());
                        }
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
                // video-params 属性变化：更新扩展字段缓存并重新 Dispatch videoParams
                if (prop != nullptr && prop->format == MPV_FORMAT_NODE && prop->data != nullptr &&
                    std::strcmp(prop->name, "video-params") == 0) {
                    const mpv_node* vpNode = static_cast<mpv_node*>(prop->data);
                    if (vpNode != nullptr && vpNode->format == MPV_FORMAT_NODE_MAP && vpNode->u.list != nullptr) {
                        const mpv_node_list* map = vpNode->u.list;
                        bool changed = false;
                        for (int j = 0; j < map->num; ++j) {
                            if (map->keys[j] == nullptr) continue;
                            const std::string key = map->keys[j];
                            const mpv_node& val = map->values[j];
                            // mpv video-params 节点键名：pixelformat（不是 pixfmt）、
                            // aspect（DOUBLE 不是 STRING）、无 bits-per-component。
                            // 位深度从 pixelformat 字符串尾部数字推断（如 yuv420p10→10）。
                            if (key == "pixelformat" && val.format == MPV_FORMAT_STRING && val.u.string != nullptr) {
                                const std::string pf = val.u.string;
                                if (vpPixfmt_ != pf) {
                                    vpPixfmt_ = pf;
                                    // 从像素格式字符串推断位深度：yuv420p→8, yuv420p10→10, yuv420p12→12
                                    int bd = 8;
                                    auto pos = pf.find_last_not_of("0123456789");
                                    if (pos != std::string::npos && pos + 1 < pf.length()) {
                                        const std::string numPart = pf.substr(pos + 1);
                                        const int parsed = std::atoi(numPart.c_str());
                                        if (parsed > 0) bd = parsed;
                                    }
                                    if (vpBitDepth_ != bd) { vpBitDepth_ = bd; }
                                    changed = true;
                                }
                            } else if (key == "hw-pixelformat" && val.format == MPV_FORMAT_STRING && val.u.string != nullptr) {
                                // hw-pixelformat 是硬件解码器输出的像素格式，当 pixelformat
                                // 为硬件名（如 "ohcodec"）时作为 fallback。
                                const std::string hwpf = val.u.string;
                                if (vpHwPixfmt_ != hwpf) { vpHwPixfmt_ = hwpf; changed = true; }
                            } else if (key == "primaries" && val.format == MPV_FORMAT_STRING && val.u.string != nullptr) {
                                if (vpPrimaries_ != val.u.string) { vpPrimaries_ = val.u.string; changed = true; }
                            } else if (key == "gamma" && val.format == MPV_FORMAT_STRING && val.u.string != nullptr) {
                                // mpv video-params 节点用 "gamma" 表示传输函数（transfer function），
                                // 不是 "transfer"。旧代码用 "transfer" 导致始终读不到值。
                                if (vpTransfer_ != val.u.string) { vpTransfer_ = val.u.string; changed = true; }
                            } else if (key == "colormatrix" && val.format == MPV_FORMAT_STRING && val.u.string != nullptr) {
                                // mpv video-params 节点用 "colormatrix"，不是 "matrix"。
                                if (vpMatrix_ != val.u.string) { vpMatrix_ = val.u.string; changed = true; }
                            } else if (key == "colorlevels" && val.format == MPV_FORMAT_STRING && val.u.string != nullptr) {
                                if (vpColorLevels_ != val.u.string) { vpColorLevels_ = val.u.string; changed = true; }
                            } else if (key == "sig-peak" && val.format == MPV_FORMAT_DOUBLE) {
                                // 从 sig-peak 推断视频范围：>1.0→HDR，≈1.0→SDR
                                const std::string range = val.u.double_ > 1.01 ? "HDR" : "SDR";
                                if (vpVideoRange_ != range) { vpVideoRange_ = range; changed = true; }
                            } else if (key == "rotate" && val.format == MPV_FORMAT_INT64) {
                                const int rot = static_cast<int>(val.u.int64);
                                if (vpRotate_ != rot) { vpRotate_ = rot; changed = true; }
                            } else if (key == "aspect" && val.format == MPV_FORMAT_DOUBLE) {
                                // mpv video-params 的 aspect 是 DOUBLE（如 1.777778），不是 STRING。
                                // 格式化为简短字符串（保留 3 位小数）。
                                char buf[32];
                                snprintf(buf, sizeof(buf), "%.3f", val.u.double_);
                                const std::string aspectStr(buf);
                                if (vpAspect_ != aspectStr) { vpAspect_ = aspectStr; changed = true; }
                            } else if (key == "interlaced" && val.format == MPV_FORMAT_FLAG) {
                                const bool il = val.u.flag != 0;
                                if (vpInterlaced_ != il) { vpInterlaced_ = il; changed = true; }
                            }
                        }
                        // 诊断：全量 dump mpv video-params。其中 colormatrix 即色彩系统
                        // (repr.sys)：Dolby Vision 未被剥离时应为 "dolbyvision"；被 vo_gpu 的
                        // restore_dovi_mapping 剥离后为基础系统（如 bt2020nc）。结合 primaries/
                        // gamma/max-luma/light 可定位 DV Profile 5 是否被应用。仅日志，不改逻辑。
                        std::string diag;
                        diag.reserve(256);
                        for (int j = 0; j < map->num; ++j) {
                            if (map->keys[j] == nullptr) continue;
                            diag += map->keys[j];
                            diag += "=";
                            const mpv_node& v = map->values[j];
                            if (v.format == MPV_FORMAT_STRING && v.u.string) {
                                diag += v.u.string;
                            } else if (v.format == MPV_FORMAT_INT64) {
                                diag += std::to_string(v.u.int64);
                            } else if (v.format == MPV_FORMAT_DOUBLE) {
                                char db[32]; snprintf(db, sizeof(db), "%.3f", v.u.double_); diag += db;
                            } else if (v.format == MPV_FORMAT_FLAG) {
                                diag += v.u.flag ? "1" : "0";
                            } else {
                                continue;
                            }
                            diag += " ";
                        }
                        OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG,
                            "video-params diag: %{public}s", diag.c_str());
                        if (changed && videoWidth_ > 0 && videoHeight_ > 0) {
                            Dispatch("videoParams", BuildVideoParamsMessage());
                        }
                    }
                }
                // audio-params 属性变化：更新音频参数缓存并 Dispatch audioParams
                if (prop != nullptr && prop->format == MPV_FORMAT_NODE && prop->data != nullptr &&
                    std::strcmp(prop->name, "audio-params") == 0) {
                    const mpv_node* apNode = static_cast<mpv_node*>(prop->data);
                    if (apNode != nullptr && apNode->format == MPV_FORMAT_NODE_MAP && apNode->u.list != nullptr) {
                        const mpv_node_list* map = apNode->u.list;
                        bool changed = false;
                        for (int j = 0; j < map->num; ++j) {
                            if (map->keys[j] == nullptr) continue;
                            const std::string key = map->keys[j];
                            const mpv_node& val = map->values[j];
                            if (key == "samplerate" && val.format == MPV_FORMAT_INT64) {
                                const int sr = static_cast<int>(val.u.int64);
                                if (apSamplerate_ != sr) { apSamplerate_ = sr; changed = true; }
                            } else if (key == "channels" && val.format == MPV_FORMAT_STRING && val.u.string != nullptr) {
                                if (apChannels_ != val.u.string) { apChannels_ = val.u.string; changed = true; }
                            } else if (key == "channel-count" && val.format == MPV_FORMAT_INT64) {
                                const int cc = static_cast<int>(val.u.int64);
                                if (apChannelCount_ != cc) { apChannelCount_ = cc; changed = true; }
                            } else if (key == "format" && val.format == MPV_FORMAT_STRING && val.u.string != nullptr) {
                                if (apFormat_ != val.u.string) { apFormat_ = val.u.string; changed = true; }
                            }
                        }
                        if (changed) {
                            Dispatch("audioParams", BuildAudioParamsMessage());
                        }
                    }
                }
                // video-bitrate 属性变化：实时视频解码码率（bps），追加到 videoParams 消息。
                // 码率波动频繁，仅在变化超过 5% 时才 dispatch，避免 UI 刷屏。
                if (prop != nullptr && prop->format == MPV_FORMAT_DOUBLE && prop->data != nullptr &&
                    std::strcmp(prop->name, "video-bitrate") == 0) {
                    const double br = *static_cast<double*>(prop->data);
                    if (br > 0 && videoWidth_ > 0 && videoHeight_ > 0) {
                        const double threshold = vpBitrate_ > 0 ? vpBitrate_ * 0.05 : 1.0;
                        if (std::abs(br - vpBitrate_) > threshold) {
                            vpBitrate_ = br;
                            Dispatch("videoParams", BuildVideoParamsMessage());
                        }
                    }
                }
                // audio-bitrate 属性变化：实时音频解码码率（bps），追加到 audioParams 消息。
                if (prop != nullptr && prop->format == MPV_FORMAT_DOUBLE && prop->data != nullptr &&
                    std::strcmp(prop->name, "audio-bitrate") == 0) {
                    const double br = *static_cast<double*>(prop->data);
                    if (br > 0) {
                        const double threshold = apBitrate_ > 0 ? apBitrate_ * 0.05 : 1.0;
                        if (std::abs(br - apBitrate_) > threshold) {
                            apBitrate_ = br;
                            Dispatch("audioParams", BuildAudioParamsMessage());
                        }
                    }
                }
                if (prop != nullptr && prop->format == MPV_FORMAT_DOUBLE && prop->data != nullptr &&
                    (std::strcmp(prop->name, "time-pos") == 0 || std::strcmp(prop->name, "duration") == 0)) {
                    // mpv time-pos/duration 均为秒（double）。time-pos 在文件加载初期可能
                    // 为负或缺失（属性不存在）；duration 在直播/未知时长时为 0 或负。这里只更新
                    // 对应缓存，再交给 DispatchPositionIfChanged 决定是否派发，避免同值洪泛。
                    const double seconds = *static_cast<double*>(prop->data);
                    if (std::strcmp(prop->name, "time-pos") == 0) {
                        positionSeconds_ = seconds;
                    } else {
                        durationSeconds_ = seconds;
                    }
                    DispatchPositionIfChanged();
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

        // issue #71（DV Profile 5 渲染层迁移，草稿）：vo_gpu_next 由 mpv 自行渲染到 OHOS surface，
        // 无需 libmpv render API。此处把 OHOS Surface id 以运行时属性注入 mpv --wid（WinID），
        // vo_ohos_init 读它建 OHNativeWindow 并绑定 Vulkan surface。随后返回，不再创建
        // mpv_render_context、不再手动 render（下方 SW/GL render 分支为旧 vo_gpu 路径，可删）。
        // 注：wid 需在 VO 创建前（Load/播放前）设置；若 RenderLoop 已晚于 VO 创建，应提前到
        // Attach（surfaceId_ 就绪时）。mpv_set_property 支持运行时。
        int64_t wid = static_cast<int64_t>(id);
        int widRc = mpv_set_property(player_.get(), "wid", MPV_FORMAT_INT64, &wid);
        OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG,
            "vo_gpu_next(ohosvk) window bind: wid=%{public}lld rc=%{public}d (legacy render API skipped)",
            static_cast<long long>(wid), widRc);
        // vo_gpu_next 由 mpv 自行渲染到 OHOS surface：wid rc=0 表示 surface id 已绑定到 mpv
        // --wid（WinID），vo_ohos_init 会在 VO 创建(播放)时据此建 OHNativeWindow + Vulkan surface。
        // 窗口绑定即视为 surface 附着成功，置 rendererReady_ 让 Attach 的 wait_for resolve，
        // 播放时 mpv 才会真正创建 VO 并出帧。rc<0 则标记失败并通知 Attach 返回 SURFACE_UNAVAILABLE。
        {
            std::lock_guard<std::mutex> lock(rendererMutex_);
            if (widRc == 0) {
                rendererReady_ = true;
            } else {
                rendererFailed_ = true;
            }
            rendererReadyCv_.notify_one();
        }
        // vo_gpu_next 自行渲染到 OHOS surface，不再走 libmpv render API。
        // 下方 SW/GL render 分支为旧 vo_gpu 路径，草稿阶段先整体跳过，待真机验证后删除
        // (TryUpgradeToGlRenderer / GlRenderLoop / SwRenderLoop / RenderLoop 内 render context 相关)。
        return;
        // 策略：先创建 SW render context（永远安全），再尝试升级 GL。
        // GL 在模拟器上可能 SIGSEGV，需要安全检测。
        // 第一步：SW context（保证播放能力）
        {
            const char* swApi = MPV_RENDER_API_TYPE_SW;
            mpv_render_param swParams[] = {
                {MPV_RENDER_PARAM_API_TYPE, const_cast<char*>(swApi)},
                {MPV_RENDER_PARAM_INVALID, nullptr}
            };
            int swRc = mpv_render_context_create(&renderer_, player_.get(), swParams);
            if (swRc < 0) {
                OH_LOG_Print(LOG_APP, LOG_ERROR, LOG_DOMAIN, LOG_TAG, "mpv_render_context_create(SW) failed rc=%{public}d", swRc);
                MarkRendererFailed(); return;
            }
        }
        isSwRenderer_ = true;
        OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG, "SW renderer created as baseline");

        // 第二步：如果硬件解码已启用，检测 GL 可用性后尝试升级
        // 安全检测：检查 libEGL_impl.so 是否存在（模拟器上不存在 → GL 不可用）
        // 不使用 fork 方案，因为 HarmonyOS EGL 内部使用 binder IPC，
        // fork 后子进程继承的 binder 连接状态不一致会导致主进程崩溃。
        if (hardwareDecodingRequested_.load()) {
            bool glAvailable = false;
            FILE* eglImpl = fopen("/vendor/lib64/chipsetsdk/libEGL_impl.so", "r");
            if (eglImpl != nullptr) {
                fclose(eglImpl);
                glAvailable = true;
            } else {
                OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG, "GL impl not found, skipping GL upgrade (emulator?)");
            }
            if (glAvailable && TryUpgradeToGlRenderer()) {
                OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG, "Upgraded to GL renderer");
                GlRenderLoop();
                return;
            }
        }

        // SW render loop（恢复 63222bd0 的可靠实现）
        SwRenderLoop();
    }

    // 检测 GL 可用性并升级渲染 context：SW → GL
    // 前提：已确认 libEGL_impl.so 存在（调用方已检查），此函数不再使用 fork。
    bool TryUpgradeToGlRenderer()
    {
        // 先释放已有的 SW renderer
        if (renderer_ != nullptr) {
            mpv_render_context_set_update_callback(renderer_, nullptr, nullptr);
            mpv_render_context_free(renderer_);
            renderer_ = nullptr;
        }

        // 直接在主进程中创建 GL context（调用方已确认 GL impl 存在）
        eglDisplay_ = eglGetDisplay(EGL_DEFAULT_DISPLAY);
        if (eglDisplay_ == EGL_NO_DISPLAY) return false;
        EGLint major = 0, minor = 0;
        if (!eglInitialize(eglDisplay_, &major, &minor)) { eglDisplay_ = EGL_NO_DISPLAY; return false; }
        EGLint configAttribs[] = { EGL_SURFACE_TYPE, EGL_WINDOW_BIT, EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT, EGL_NONE };
        EGLint numConfigs = 0;
        if (!eglChooseConfig(eglDisplay_, configAttribs, &eglConfig_, 1, &numConfigs) || numConfigs < 1) { eglTerminate(eglDisplay_); eglDisplay_ = EGL_NO_DISPLAY; return false; }
        EGLint contextAttribs[] = { EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE };
        eglContext_ = eglCreateContext(eglDisplay_, eglConfig_, EGL_NO_CONTEXT, contextAttribs);
        if (eglContext_ == EGL_NO_CONTEXT) { eglTerminate(eglDisplay_); eglDisplay_ = EGL_NO_DISPLAY; return false; }
        eglSurface_ = eglCreateWindowSurface(eglDisplay_, eglConfig_, reinterpret_cast<EGLNativeWindowType>(window_), nullptr);
        if (eglSurface_ == EGL_NO_SURFACE) { eglDestroyContext(eglDisplay_, eglContext_); eglContext_ = EGL_NO_CONTEXT; eglTerminate(eglDisplay_); eglDisplay_ = EGL_NO_DISPLAY; return false; }
        if (!eglMakeCurrent(eglDisplay_, eglSurface_, eglSurface_, eglContext_)) { eglDestroySurface(eglDisplay_, eglSurface_); eglSurface_ = EGL_NO_SURFACE; eglDestroyContext(eglDisplay_, eglContext_); eglContext_ = EGL_NO_CONTEXT; eglTerminate(eglDisplay_); eglDisplay_ = EGL_NO_DISPLAY; return false; }
        mpv_opengl_init_params glInit{ &MpvGlGetProcAddress, nullptr };
        const char* api = MPV_RENDER_API_TYPE_OPENGL;
        // 诊断：确认渲染后端。render API 只有 OPENGL/SW 两种，OPENGL=vo_gpu，无 gpu-next。
        // Dolby Vision Profile 5 的 dovi RPU→显示 reshape 需 vo_gpu_next，本 render API 不可达。
        OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG,
            "render context api=%{public}s vo=libmpv(vo_gpu): DV dovi reshape 需 vo_gpu_next（render API 不可达）",
            api);
        mpv_render_param params[] = {
            {MPV_RENDER_PARAM_API_TYPE, const_cast<char*>(api)},
            {MPV_RENDER_PARAM_OPENGL_INIT_PARAMS, &glInit},
            {MPV_RENDER_PARAM_INVALID, nullptr}
        };
        int rc = mpv_render_context_create(&renderer_, player_.get(), params);
        if (rc < 0) {
            OH_LOG_Print(LOG_APP, LOG_ERROR, LOG_DOMAIN, LOG_TAG, "GL context create failed rc=%{public}d after child confirmed safe", rc);
            eglMakeCurrent(eglDisplay_, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
            eglDestroySurface(eglDisplay_, eglSurface_); eglSurface_ = EGL_NO_SURFACE;
            eglDestroyContext(eglDisplay_, eglContext_); eglContext_ = EGL_NO_CONTEXT;
            eglTerminate(eglDisplay_); eglDisplay_ = EGL_NO_DISPLAY;
            return false;
        }
        isSwRenderer_ = false;
        return true;
    }

    void GlRenderLoop()
    {
        mpv_render_context_set_update_callback(renderer_, NotifyRender, this);
        { std::lock_guard<std::mutex> lock(rendererMutex_); rendererReady_ = true; rendererReadyCv_.notify_one(); }

        while (true) {
            bool geometryDirty = false;
            { std::unique_lock<std::mutex> lock(rendererMutex_); renderCondition_.wait_for(lock, std::chrono::milliseconds(16), [this] { return stopRenderer_ || renderRequested_ || geometryDirty_; }); if (stopRenderer_) break; renderRequested_ = false; geometryDirty = geometryDirty_.exchange(false); }
            int width = width_; int height = height_;
            if (geometryDirty) {
                eglMakeCurrent(eglDisplay_, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
                eglDestroySurface(eglDisplay_, eglSurface_);
                eglSurface_ = EGL_NO_SURFACE;
                OH_NativeWindow_NativeWindowHandleOpt(window_, SET_BUFFER_GEOMETRY, width, height);
                eglSurface_ = eglCreateWindowSurface(eglDisplay_, eglConfig_, reinterpret_cast<EGLNativeWindowType>(window_), nullptr);
                eglMakeCurrent(eglDisplay_, eglSurface_, eglSurface_, eglContext_);
            }
            uint64_t updateFlags = mpv_render_context_update(renderer_);
            if ((updateFlags & MPV_RENDER_UPDATE_FRAME) == 0) continue;
            if (width <= 0 || height <= 0) continue;
            mpv_opengl_fbo fbo{ 0, width, height, 0 };
            int flipY = 1;
            mpv_render_param frame[] = {
                {MPV_RENDER_PARAM_OPENGL_FBO, &fbo},
                {MPV_RENDER_PARAM_FLIP_Y, &flipY},
                {MPV_RENDER_PARAM_INVALID, nullptr}
            };
            int renderResult = mpv_render_context_render(renderer_, frame);
            if (renderResult < 0) {
                OH_LOG_Print(LOG_APP, LOG_ERROR, LOG_DOMAIN, LOG_TAG, "mpv_render_context_render failed rc=%{public}d", renderResult);
                continue;
            }
            eglSwapBuffers(eglDisplay_, eglSurface_);
            if (!firstFrameSent_.exchange(true)) {
                Dispatch("state", "playing");
            }
        }
        DestroyRenderer();
    }

    // SW 渲染循环：基于 63222bd0 的可靠实现，增加 PixelMap fallback
    // 优先 NativeWindow（SET_FORMAT/SET_USAGE/mmap 回退），连续失败时降级 PixelMap
    void SwRenderLoop()
    {
        OH_LOG_Print(LOG_APP, LOG_INFO, LOG_DOMAIN, LOG_TAG, "Entering SW render loop");
        // mpv 软件渲染输出 RGBA8888（每像素 4 字节），Surface 缓冲区格式必须匹配，
        // 否则显示 HDI 层会拒绝分配缓冲区（"format X can not support"）。
        int32_t format = NATIVEBUFFER_PIXEL_FMT_RGBA_8888;
        OH_NativeWindow_NativeWindowHandleOpt(window_, SET_FORMAT, format);
        OH_NativeWindow_NativeWindowHandleOpt(window_, SET_BUFFER_GEOMETRY, width_.load(), height_.load());
        // 软件渲染需要 CPU 直接写入缓冲区，必须显式声明 CPU 读写 usage，
        // 否则分配到的 BufferHandle::virAddr 为空（仅 GPU 可访问），导致每帧都被丢弃。
        uint64_t usage = NATIVEBUFFER_USAGE_CPU_READ | NATIVEBUFFER_USAGE_CPU_WRITE;
        OH_NativeWindow_NativeWindowHandleOpt(window_, SET_USAGE, usage);

        mpv_render_context_set_update_callback(renderer_, NotifyRender, this);
        { std::lock_guard<std::mutex> lock(rendererMutex_); rendererReady_ = true; rendererReadyCv_.notify_one(); }

        std::vector<uint8_t> pixels;
        bool useNativeWindow = true;
        int nativeWindowFailCount = 0;
        constexpr int MAX_NATIVE_WINDOW_FAILS = 30;

        while (true) {
            bool geometryDirty = false;
            { std::unique_lock<std::mutex> lock(rendererMutex_); renderCondition_.wait_for(lock, std::chrono::milliseconds(16), [this] { return stopRenderer_ || renderRequested_ || geometryDirty_; }); if (stopRenderer_) break; renderRequested_ = false; geometryDirty = geometryDirty_.exchange(false); }
            int width = width_; int height = height_;
            if (geometryDirty && useNativeWindow) OH_NativeWindow_NativeWindowHandleOpt(window_, SET_BUFFER_GEOMETRY, width, height);
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

            if (useNativeWindow) {
                // NativeWindow 直接写入路径（高优先级，大部分设备可用）
                OHNativeWindowBuffer* buffer = nullptr;
                int fence = -1;
                int requestRc = OH_NativeWindow_NativeWindowRequestBuffer(window_, &buffer, &fence);
                if (requestRc != 0 || buffer == nullptr) {
                    nativeWindowFailCount++;
                    if (nativeWindowFailCount >= MAX_NATIVE_WINDOW_FAILS) {
                        OH_LOG_Print(LOG_APP, LOG_WARN, LOG_DOMAIN, LOG_TAG, "NativeWindow failed %d times, switching to PixelMap fallback", nativeWindowFailCount);
                        useNativeWindow = false;
                    }
                    continue;
                }
                nativeWindowFailCount = 0;
                BufferHandle* target = OH_NativeWindow_GetBufferHandleFromNative(buffer);
                void* mappedAddr = nullptr;
                bool ownsMapping = false;
                if (target != nullptr && target->virAddr == nullptr && target->fd >= 0 && target->size > 0) {
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
            } else {
                // PixelMap 回调路径：NativeWindow 不可用时的兜底方案
                // 将帧数据存入内存，ArkTS 通过 getFrameData() 获取并显示
                {
                    std::lock_guard<std::mutex> lock(frameMutex_);
                    if (pendingFrame_.size() != static_cast<size_t>(width * height * 4)) {
                        pendingFrame_.resize(width * height * 4);
                    }
                    memcpy(pendingFrame_.data(), pixels.data(), pendingFrame_.size());
                    frameWidth_ = width;
                    frameHeight_ = height;
                    frameReady_ = true;
                }
            }

            if (!firstFrameSent_.exchange(true)) {
                Dispatch("state", "playing");
            }
        }
        DestroyRenderer();
    }

    public:
    napi_value GetFrameData(napi_env env)
    {
        std::lock_guard<std::mutex> lock(frameMutex_);
        if (!frameReady_ || pendingFrame_.empty()) return nullptr;
        napi_value result = nullptr;
        napi_create_object(env, &result);
        napi_value widthVal = nullptr, heightVal = nullptr;
        napi_create_int32(env, frameWidth_, &widthVal);
        napi_create_int32(env, frameHeight_, &heightVal);
        napi_set_named_property(env, result, "width", widthVal);
        napi_set_named_property(env, result, "height", heightVal);
        napi_value arrayBuffer = nullptr;
        void* data = nullptr;
        napi_create_arraybuffer(env, pendingFrame_.size(), &data, &arrayBuffer);
        memcpy(data, pendingFrame_.data(), pendingFrame_.size());
        napi_set_named_property(env, result, "data", arrayBuffer);
        frameReady_ = false;
        return result;
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
        if (eglDisplay_ != EGL_NO_DISPLAY) {
            eglMakeCurrent(eglDisplay_, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
            if (eglSurface_ != EGL_NO_SURFACE) { eglDestroySurface(eglDisplay_, eglSurface_); eglSurface_ = EGL_NO_SURFACE; }
            if (eglContext_ != EGL_NO_CONTEXT) { eglDestroyContext(eglDisplay_, eglContext_); eglContext_ = EGL_NO_CONTEXT; }
            eglTerminate(eglDisplay_);
            eglDisplay_ = EGL_NO_DISPLAY;
        }
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
    std::atomic<bool> rendererReady_{false};
    std::atomic<bool> rendererFailed_{false};
    std::atomic<bool> released_{false};
    std::string surfaceId_;
    std::atomic<std::uint64_t> generation_{0};
    std::atomic<std::uint64_t> eventEpoch_{0};
    std::atomic<std::uint64_t> eventSequence_{0};
    std::atomic<int> width_{0};
    std::atomic<int> height_{0};
    // videoWidth_/videoHeight_ 只在 EventLoop 所在的事件线程读写，无需原子操作。
    int videoWidth_ = 0;
    int videoHeight_ = 0;
    // video-params 扩展字段缓存（只在 EventLoop 读写，无需原子操作）
    std::string vpPixfmt_;
    std::string vpHwPixfmt_; // mpv video-params "hw-pixelformat"：硬件输出像素格式
    int vpBitDepth_ = 0;
    std::string vpPrimaries_;
    std::string vpTransfer_;
    std::string vpMatrix_;
    std::string vpVideoRange_; // 从 sig-peak 推断：>1.0→HDR，=1.0→SDR，其他→Unknown
    double vpFps_ = 0;
    int vpRotate_ = 0;
    std::string vpAspect_;
    bool vpInterlaced_ = false;
    std::string vpColorLevels_; // mpv video-params "colorlevels"：limited/full
    double vpBitrate_ = 0; // mpv "video-bitrate"：实时视频码率（bps）
    // audio-params 缓存（只在 EventLoop 读写，无需原子操作）
    int apSamplerate_ = 0;
    std::string apChannels_; // 声道布局字符串，如 "stereo"/"5.1"
    int apChannelCount_ = 0;
    std::string apFormat_; // 采样格式，如 "s16"/"float"
    double apBitrate_ = 0; // mpv "audio-bitrate"：实时音频码率（bps）
    // time-pos/duration 缓存（只在 EventLoop 读写，无需原子操作）。单位：秒。
    // time-pos 在播放中可能为负（mpv 初始化阶段）或缺失（无媒体），用 -1.0 表示尚未收到。
    double positionSeconds_ = -1.0;
    double durationSeconds_ = -1.0;
    // 上一次已 Dispatch 的 positionMs/durationMs，用于同值去抖（避免 mpv 重复上报相同值）。
    long long lastPositionMs_ = -1;
    long long lastDurationMs_ = -1;
    // position 派发开关：仅在新文件 FILE_LOADED 后为 true，抑制切源期间旧文件残留
    // 的 time-pos。Load() 与 END_FILE 置 false，FILE_LOADED 置 true。跨线程读写故用原子。
    std::atomic<bool> positionActive_{false};
    std::atomic<bool> firstFrameSent_{false};
    OHNativeWindow* window_ = nullptr;
    mpv_render_context* renderer_ = nullptr;
    bool isSwRenderer_ = false; // true = SW 软件渲染（模拟器/无GL环境），false = GL 渲染（真机）
    std::atomic<bool> hardwareDecodingRequested_{false}; // ArkTS 层是否请求了硬件解码
    // PixelMap fallback（模拟器 SW 渲染路径，NativeWindow 不可用时将帧数据暴露给 ArkTS）
    std::mutex frameMutex_;
    std::vector<uint8_t> pendingFrame_;
    int frameWidth_ = 0;
    int frameHeight_ = 0;
    bool frameReady_ = false;
    // EGL 渲染上下文（GL 渲染路径，支持 ohcodec 硬件解码输出到 GL texture）
    EGLDisplay eglDisplay_ = EGL_NO_DISPLAY;
    EGLSurface eglSurface_ = EGL_NO_SURFACE;
    EGLContext eglContext_ = EGL_NO_CONTEXT;
    EGLConfig eglConfig_ = nullptr;
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
    napi_value args[4] = {nullptr}; size_t argc = 4;
    std::string fontsDir, hwdec, toneMapping, hdrComputePeak;
    if (napi_get_cb_info(env, info, &argc, args, nullptr, nullptr) == napi_ok) {
        if (argc >= 1) ReadString(env, args[0], fontsDir);
        if (argc >= 2) ReadString(env, args[1], hwdec);
        if (argc >= 3) ReadString(env, args[2], toneMapping);
        if (argc >= 4) ReadString(env, args[3], hdrComputePeak);
    }
#if VIDALL_MPV_AVAILABLE
    auto session = std::make_shared<NativeSession>();
    if (!session->Initialize(fontsDir, hwdec, toneMapping, hdrComputePeak)) return CreateResult(env, {false, 0, "NATIVE_PLAYBACK_FAILED"});
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

napi_value SetPropertyString(napi_env env, napi_callback_info info)
{
    napi_value args[3] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; std::string property; std::string value;
    if (!GetArguments(env, info, 3, args, argc) || argc != 3 || !ReadHandle(env, args[0], handle) ||
        !ReadString(env, args[1], property) || !ReadString(env, args[2], value)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->SetPropertyString(property, value, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value SetAudioFilter(napi_env env, napi_callback_info info)
{
    napi_value args[2] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; std::string filter;
    if (!GetArguments(env, info, 2, args, argc) || argc != 2 || !ReadHandle(env, args[0], handle) ||
        !ReadString(env, args[1], filter)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->SetAudioFilter(filter, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value SetVolume(napi_env env, napi_callback_info info)
{
    napi_value args[2] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; double volume = 0;
    if (!GetArguments(env, info, 2, args, argc) || argc != 2 || !ReadHandle(env, args[0], handle) ||
        napi_get_value_double(env, args[1], &volume) != napi_ok) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->SetVolume(volume, handle));
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

napi_value GetFrameData(napi_env env, napi_callback_info info)
{
    napi_value args[1] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0;
    if (!GetArguments(env, info, 1, args, argc) || argc != 1 || !ReadHandle(env, args[0], handle)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle);
    return session ? session->GetFrameData(env) : nullptr;
#else
    return nullptr;
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
        {"setPropertyString", nullptr, SetPropertyString, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setAudioFilter", nullptr, SetAudioFilter, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setVolume", nullptr, SetVolume, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"selectTrack", nullptr, SelectTrack, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"addExternalAudio", nullptr, AddExternalAudio, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"addExternalSubtitle", nullptr, AddExternalSubtitle, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setEventCallback", nullptr, SetEventCallback, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"getFrameData", nullptr, GetFrameData, nullptr, nullptr, nullptr, napi_default, nullptr},
    };
    if (!Check(env, napi_define_properties(env, exports, sizeof(descriptors) / sizeof(descriptors[0]), descriptors), "Failed to define native bridge exports.") ||
        !Check(env, napi_add_env_cleanup_hook(env, CleanupSessions, nullptr), "Failed to register cleanup hook.")) return nullptr;
    return exports;
}
} // namespace

NAPI_MODULE(vidall_player_native, Init)
