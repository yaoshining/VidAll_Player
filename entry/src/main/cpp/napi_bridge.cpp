#include <napi/native_api.h>
#include <hilog/log.h>
#include <ace/xcomponent/native_interface_xcomponent.h>

#include <atomic>
#include <cmath>
#include <cstdint>

constexpr unsigned int VIDALL_LOG_DOMAIN = 0xA04d50;
constexpr const char* VIDALL_LOG_TAG = "VidAllPlayer";
#define MPV_LOG(level, ...) OH_LOG_Print(LOG_APP, level, VIDALL_LOG_DOMAIN, VIDALL_LOG_TAG, __VA_ARGS__)
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <memory>
#include <mutex>
#include <string>
#include <sys/stat.h>
#include <thread>
#include <unordered_map>
#include <vector>

#if VIDALL_MPV_AVAILABLE
#include <chrono>
#include <condition_variable>
#include <csetjmp>
#include <csignal>
#include <dlfcn.h>

#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <native_window/external_window.h>
#include <mpv/client.h>
#include <mpv/render.h>
#include <mpv/render_gl.h>
#endif

namespace {

#if VIDALL_MPV_AVAILABLE
// File-scope sigjmp_buf for GL probe signal handler — must appear before
// PlayerSession because ProbeGlDriver() uses it at line ~264.
static sigjmp_buf gProbeJmpBuf;

// Global NativeWindow obtained from XComponent OnSurfaceCreated callback.
// This is the ONLY correct way to get the NativeWindow — CreateNativeWindowFromSurfaceId
// creates a new BufferQueue producer that conflicts with XComponent's own producer.
static OHNativeWindow* gNativeWindow = nullptr;
static std::mutex gNativeWindowMutex;
static std::condition_variable gNativeWindowCv;

// XComponent native callbacks — obtain NativeWindow directly from XComponent
void OnSurfaceCreated(OH_NativeXComponent* component, void* window)
{
    MPV_LOG(LOG_INFO, "XComponent OnSurfaceCreated: window=%{public}p", window);
    std::lock_guard<std::mutex> lock(gNativeWindowMutex);
    gNativeWindow = static_cast<OHNativeWindow*>(window);
    gNativeWindowCv.notify_one();
}

void OnSurfaceChanged(OH_NativeXComponent* component, void* window)
{
    MPV_LOG(LOG_INFO, "XComponent OnSurfaceChanged: window=%{public}p", window);
    std::lock_guard<std::mutex> lock(gNativeWindowMutex);
    gNativeWindow = static_cast<OHNativeWindow*>(window);
    gNativeWindowCv.notify_one();
}

void OnSurfaceDestroyed(OH_NativeXComponent* component, void* window)
{
    MPV_LOG(LOG_INFO, "XComponent OnSurfaceDestroyed");
    std::lock_guard<std::mutex> lock(gNativeWindowMutex);
    gNativeWindow = nullptr;
}

void DispatchTouchEvent(OH_NativeXComponent* component, void* window)
{
    // No-op for touch events
}
#endif

napi_value CreateString(napi_env env, const std::string& value)
{
    napi_value result = nullptr;
    napi_create_string_utf8(env, value.c_str(), NAPI_AUTO_LENGTH, &result);
    return result;
}

bool ReadString(napi_env env, napi_value value, std::string& result)
{
    size_t length = 0;
    if (value == nullptr || napi_get_value_string_utf8(env, value, nullptr, 0, &length) != napi_ok) {
        return false;
    }
    result.assign(length + 1, '\0');
    if (napi_get_value_string_utf8(env, value, result.data(), result.size(), &length) != napi_ok) {
        return false;
    }
    result.resize(length);
    return true;
}

bool GetStringArgument(napi_env env, napi_callback_info info, size_t index, std::string& result)
{
    size_t argc = 3;
    napi_value args[3] = {nullptr, nullptr, nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
    return argc > index && ReadString(env, args[index], result);
}

bool GetHandleArgument(napi_env env, napi_callback_info info, int64_t& handle)
{
    size_t argc = 3;
    napi_value args[3] = {nullptr, nullptr, nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
    return argc > 0 && napi_get_value_int64(env, args[0], &handle) == napi_ok && handle > 0;
}

bool GetFiniteDoubleArgument(napi_env env, napi_callback_info info, size_t index, double& value)
{
    size_t argc = 3;
    napi_value args[3] = {nullptr, nullptr, nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
    return argc > index && napi_get_value_double(env, args[index], &value) == napi_ok && std::isfinite(value);
}

// 缓冲状态默认快照：模拟器桩路径与无效句柄共用，保证演示层轮询不崩溃。
napi_value DefaultBufferingState(napi_env env)
{
    napi_value result = nullptr;
    napi_create_object(env, &result);
    napi_value falseValue = nullptr;
    napi_get_boolean(env, false, &falseValue);
    napi_set_named_property(env, result, "pausedForCache", falseValue);
    napi_value falseValue2 = nullptr;
    napi_get_boolean(env, false, &falseValue2);
    napi_set_named_property(env, result, "demuxerBuffering", falseValue2);
    napi_value zeroValue = nullptr;
    napi_create_double(env, 0.0, &zeroValue);
    napi_set_named_property(env, result, "cacheDurationSeconds", zeroValue);
    napi_value falseValue3 = nullptr;
    napi_get_boolean(env, false, &falseValue3);
    napi_set_named_property(env, result, "eofReached", falseValue3);
    napi_value trueValue = nullptr;
    napi_get_boolean(env, true, &trueValue);
    napi_set_named_property(env, result, "idleActive", trueValue);
    napi_set_named_property(env, result, "mediaKind", CreateString(env, ""));
    napi_set_named_property(env, result, "proxyLeaseId", CreateString(env, ""));
    napi_set_named_property(env, result, "errorText", CreateString(env, ""));
    return result;
}

#if VIDALL_MPV_AVAILABLE

class PlayerSession {
public:
    struct NativeEvent {
        std::string type;
        std::string message;
        int errorCode = 0;
    };

    PlayerSession()
        : player_(mpv_create(), mpv_terminate_destroy)
    {
    }

    ~PlayerSession()
    {
        Release();
    }

    bool Initialize(std::string& error)
    {
        if (!player_) {
            error = "libmpv 创建失败";
            return false;
        }

        mpv_set_option_string(player_.get(), "terminal", "no");
        mpv_set_option_string(player_.get(), "config", "no");
        mpv_set_option_string(player_.get(), "vo", "libmpv");
        mpv_set_option_string(player_.get(), "hwdec", "auto-safe");
        // 字幕字体：libass 需要能找到字体才渲染。指向 HarmonyOS 系统字体目录。
        mpv_set_option_string(player_.get(), "sub-fonts-dir", "/system/fonts");
        mpv_set_option_string(player_.get(), "sub-font", "HarmonyOS Sans SC");
        // 强制 ASS 字幕用默认样式，避免引用不存在的字体导致空白。
        mpv_set_option_string(player_.get(), "sub-ass-override", "force");
        if (mpv_initialize(player_.get()) < 0) {
            player_.reset();
            error = "libmpv 初始化失败";
            return false;
        }
        if (mpv_request_log_messages(player_.get(), "warn") < 0) {
            MPV_LOG(LOG_WARN, "Initialize: 无法请求 libmpv warn 日志");
        }
        mpv_observe_property(player_.get(), 100, "paused-for-cache", MPV_FORMAT_FLAG);
        mpv_observe_property(player_.get(), 101, "demuxer-cache-state", MPV_FORMAT_NODE);
        mpv_observe_property(player_.get(), 102, "track-list", MPV_FORMAT_NODE);
        // Start mpv event loop thread to drive render callbacks
        eventThread_ = std::thread(&PlayerSession::EventLoop, this);
        return true;
    }

    std::string AttachSurface(const std::string& surfaceId)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (!player_) {
            return "播放器已释放";
        }
        if (renderThread_.joinable()) {
            return renderReady_ ? "XComponent Surface 已绑定" : "图形输出正在初始化…";
        }

        surfaceId_ = surfaceId;
        renderReady_ = false;
        renderError_.clear();
        stopRenderer_ = false;
        renderThread_ = std::thread(&PlayerSession::RenderLoop, this);

        // Wait briefly for the render thread to report init success or failure
        std::unique_lock<std::mutex> renderLock(renderMutex_);
        renderReadyCv_.wait_for(renderLock, std::chrono::seconds(5), [this] {
            return renderReady_ || !renderError_.empty();
        });
        if (!renderError_.empty()) {
            return renderError_;
        }
        return renderReady_ ? "XComponent Surface 已绑定" : "图形输出正在初始化…";
    }

    std::string DetachSurface()
    {
        StopRenderer();
        return "XComponent Surface 已解绑";
    }

    std::string Load(const std::string& url, const std::string& authorization)
    {
        if (!player_ || url.empty()) {
            return player_ ? "请输入有效的视频 URL" : "播放器已释放";
        }
        ClearProxyLease("source-switch");
        // 每次加载媒体时单独设置认证头，避免凭据泄漏到后续请求。
        const int headerResult = mpv_set_property_string(player_.get(), "http-header-fields", authorization.c_str());
        if (headerResult < 0) {
            return "设置网络认证失败";
        }
        const char* command[] = {"loadfile", url.c_str(), "replace", nullptr};
        return mpv_command_async(player_.get(), 1, command) >= 0 ? "已提交加载请求" : "libmpv 拒绝加载请求";
    }

    // 按媒体类型加载（US4）：
    // - hls：主播放列表选择最高码率变体（hls-bitrate=max）；运行期自适应
    //   切换依赖 FFmpeg HLS demuxer 构建，真机效果标记为已构建待验证。
    // - dash：交给 FFmpeg DASH demuxer 默认自适应策略，不额外设置专有选项。
    // - localhostProxy：关联 SMB 代理租约 ID，并尽量强制可跳转；跳转能力最终
    //   取决于业务层代理的 Range 支持，force-seekable 失败不阻断加载。
    // 旧租约在切源时先清理，避免旧代理连接/端口泄漏。
    std::string LoadMedia(const std::string& kind, const std::string& url,
                          const std::string& authorization, const std::string& proxyLeaseId)
    {
        if (!player_ || url.empty()) {
            return player_ ? "请输入有效的视频 URL" : "播放器已释放";
        }
        ClearProxyLease("source-switch");
        const int headerResult = mpv_set_property_string(player_.get(), "http-header-fields", authorization.c_str());
        if (headerResult < 0) {
            return "设置网络认证失败";
        }
        // 切源时复位上一次按类型设置的 mpv 选项，避免 HLS/代理专有选项跨来源残留：
        // hls-bitrate 仅影响 HLS demuxer，force-seekable 会作用到任意可跳转来源，
        // 复位为各自默认值（max / no）后再按本次 kind 覆盖。
        if (mpv_set_property_string(player_.get(), "hls-bitrate", "max") < 0) {
            MPV_LOG(LOG_WARN, "LoadMedia: hls-bitrate 复位失败，保持默认变体选择");
        }
        if (mpv_set_property_string(player_.get(), "force-seekable", "no") < 0) {
            MPV_LOG(LOG_WARN, "LoadMedia: force-seekable 复位失败，跳转按来源默认行为");
        }
        if (kind == "hls") {
            if (mpv_set_property_string(player_.get(), "hls-bitrate", "max") < 0) {
                MPV_LOG(LOG_WARN, "LoadMedia: hls-bitrate 设置失败，退回默认变体选择");
            }
        } else if (kind == "localhostProxy") {
            if (mpv_set_property_string(player_.get(), "force-seekable", "yes") < 0) {
                MPV_LOG(LOG_WARN, "LoadMedia: force-seekable 不可用，跳转取决于代理 Range 支持");
            }
        }
        currentMediaKind_ = kind;
        currentProxyLeaseId_ = proxyLeaseId;
        if (!currentProxyLeaseId_.empty()) {
            // 只记录租约 ID 与类型，不记录 URL/凭据。
            MPV_LOG(LOG_INFO, "LoadMedia: 关联 SMB 代理租约 lease=%{public}s kind=%{public}s",
                    currentProxyLeaseId_.c_str(), currentMediaKind_.c_str());
        }
        const char* command[] = {"loadfile", url.c_str(), "replace", nullptr};
        return mpv_command_async(player_.get(), 1, command) >= 0 ? "已提交加载请求" : "libmpv 拒绝加载请求";
    }

    std::string AddExternalAudio(const std::string& uri)
    {
        if (!player_ || uri.empty()) {
            return player_ ? "音频地址无效" : "播放器已释放";
        }
        // 与外挂字幕一致：同步命令，audio-add 带 "select" 加载后立即选中该音轨。
        const char* command[] = {"audio-add", uri.c_str(), "select", nullptr};
        return mpv_command(player_.get(), command) >= 0 ? "已加载外挂音频" : "外挂音频加载失败";
    }

    // 清理当前 SMB 代理租约关联：日志只含租约 ID 与原因（不含 URL/凭据），
    // 业务层据此关闭代理连接、回收端口。
    void ClearProxyLease(const char* reason)
    {
        currentMediaKind_.clear();
        if (currentProxyLeaseId_.empty()) {
            return;
        }
        MPV_LOG(LOG_INFO, "SMB 代理租约已释放 lease=%{public}s reason=%{public}s",
                currentProxyLeaseId_.c_str(), reason);
        currentProxyLeaseId_.clear();
    }

    std::string SetPause(bool paused)
    {
        if (!player_) {
            return "播放器已释放";
        }
        const char* command[] = {"set", "pause", paused ? "yes" : "no", nullptr};
        return mpv_command_async(player_.get(), 2, command) >= 0 ? (paused ? "已暂停" : "正在播放") : "播放状态切换失败";
    }

    std::string Stop()
    {
        if (!player_) {
            return "播放器已释放";
        }
        ClearProxyLease("stop");
        const char* command[] = {"stop", nullptr};
        return mpv_command_async(player_.get(), 3, command) >= 0 ? "已停止播放" : "停止播放失败";
    }

    std::string Seek(double value, const char* mode)
    {
        if (!player_) {
            return "播放器已释放";
        }
        char position[64] = {0};
        const int written = std::snprintf(position, sizeof(position), "%.17g", value);
        if (written < 0 || static_cast<size_t>(written) >= sizeof(position)) {
            return "跳转参数格式化失败";
        }
        const char* command[] = {"seek", position, mode, nullptr};
        return mpv_command_async(player_.get(), 4, command) >= 0 ? "已提交跳转请求" : "跳转请求失败";
    }

    std::string SetOption(const char* name, double value)
    {
        if (!player_) {
            return "播放器已释放";
        }
        char text[64] = {0};
        const int written = std::snprintf(text, sizeof(text), "%.17g", value);
        if (written < 0 || static_cast<size_t>(written) >= sizeof(text)) {
            return "设置参数格式化失败";
        }
        const char* command[] = {"set", name, text, nullptr};
        return mpv_command_async(player_.get(), 5, command) >= 0 ? "已提交设置请求" : "设置请求失败";
    }

    std::string SetMuted(bool muted)
    {
        if (!player_) {
            return "播放器已释放";
        }
        const char* command[] = {"set", "mute", muted ? "yes" : "no", nullptr};
        return mpv_command_async(player_.get(), 6, command) >= 0 ? "已提交静音设置" : "静音设置失败";
    }

    std::string SelectTrack(const char* property, int64_t id)
    {
        if (!player_) {
            return "播放器已释放";
        }
        int rc = 0;
        if (id < 0) {
            rc = mpv_set_property_string(player_.get(), property, "no");
        } else {
            rc = mpv_set_property(player_.get(), property, MPV_FORMAT_INT64, &id);
        }
        // 选字幕时确保可见性开启，避免之前被关闭后选了也不渲染。
        if (rc >= 0 && std::string(property) == "sid" && id >= 0) {
            mpv_set_property_string(player_.get(), "sub-visibility", "yes");
        }
        return rc >= 0 ? "已切换轨道" : "轨道切换失败";
    }

    std::string AddExternalSubtitle(const std::string& uri)
    {
        if (!player_ || uri.empty()) {
            return player_ ? "字幕地址无效" : "播放器已释放";
        }
        // 使用同步命令而非异步，确保外挂字幕加载完成后才返回。
        // sub-add 带 "select" 标志表示加载后立即选中该字幕轨。
        const char* command[] = {"sub-add", uri.c_str(), "select", nullptr};
        return mpv_command(player_.get(), command) >= 0 ? "已加载外挂字幕" : "外挂字幕加载失败";
    }

    napi_value GetTracks(napi_env env)
    {
        napi_value tracks = nullptr;
        napi_create_array(env, &tracks);
        if (!player_) {
            return tracks;
        }
        mpv_node trackList{};
        if (mpv_get_property(player_.get(), "track-list", MPV_FORMAT_NODE, &trackList) < 0 ||
            trackList.format != MPV_FORMAT_NODE_ARRAY) {
            mpv_free_node_contents(&trackList);
            return tracks;
        }
        // 读取当前选中的音轨/字幕 ID，自行计算 selected 字段。
        // mpv 在某些版本下 track-list/N/selected 不会随 aid/sid 立即更新，
        // 用属性值判断最可靠。
        int64_t currentAid = 0;
        int64_t currentSid = 0;
        mpv_get_property(player_.get(), "aid", MPV_FORMAT_INT64, &currentAid);
        mpv_get_property(player_.get(), "sid", MPV_FORMAT_INT64, &currentSid);
        uint32_t outputIndex = 0;
        for (int index = 0; index < trackList.u.list->num; index++) {
            const mpv_node& item = trackList.u.list->values[index];
            if (item.format != MPV_FORMAT_NODE_MAP) {
                continue;
            }
            napi_value track = nullptr;
            napi_create_object(env, &track);
            int64_t trackId = 0;
            std::string trackType;
            for (int field = 0; field < item.u.list->num; field++) {
                const char* key = item.u.list->keys[field];
                const mpv_node& value = item.u.list->values[field];
                if (key == nullptr) {
                    continue;
                }
                if (std::string(key) == "id" && value.format == MPV_FORMAT_INT64) {
                    trackId = value.u.int64;
                } else if (std::string(key) == "type" && value.format == MPV_FORMAT_STRING && value.u.string != nullptr) {
                    trackType = value.u.string;
                }
                napi_value property = nullptr;
                if (value.format == MPV_FORMAT_INT64) {
                    napi_create_int64(env, value.u.int64, &property);
                } else if (value.format == MPV_FORMAT_FLAG) {
                    napi_get_boolean(env, value.u.flag != 0, &property);
                } else if (value.format == MPV_FORMAT_STRING && value.u.string != nullptr) {
                    property = CreateString(env, value.u.string);
                }
                if (property != nullptr) {
                    napi_set_named_property(env, track, key, property);
                }
            }
            // 用 aid/sid 属性覆盖 selected，确保与实际选择一致。
            bool selected = false;
            if (trackType == "audio" && trackId == currentAid) {
                selected = true;
            } else if (trackType == "sub" && trackId == currentSid) {
                selected = true;
            }
            napi_value selectedValue = nullptr;
            napi_get_boolean(env, selected, &selectedValue);
            napi_set_named_property(env, track, "selected", selectedValue);
            napi_set_element(env, tracks, outputIndex++, track);
        }
        mpv_free_node_contents(&trackList);
        return tracks;
    }

    std::string GetPlayerStatus()
    {
        if (!player_) {
            return "播放器已释放";
        }
        std::string status;
        char sessionInfo[64] = {0};
        std::snprintf(sessionInfo, sizeof(sessionInfo), "session:%p", this);
        status += sessionInfo;
        status += useSwRender_ ? " 渲染:SW" : " 渲染:GL";
        {
            char initInfo[128] = {0};
            std::snprintf(initInfo, sizeof(initInfo), " sw:%d ctx:%p initRc:%d",
                          useSwRender_, renderContext_, lastInitRc_);
            status += initInfo;
        }
        int64_t w = 0, h = 0;
        mpv_get_property(player_.get(), "width", MPV_FORMAT_INT64, &w);
        mpv_get_property(player_.get(), "height", MPV_FORMAT_INT64, &h);
        char dim[64] = {0};
        std::snprintf(dim, sizeof(dim), " 视频:%lldx%lld", (long long)w, (long long)h);
        status += dim;
        char* mediaTitle = mpv_get_property_string(player_.get(), "media-title");
        if (mediaTitle && mediaTitle[0]) {
            status += " 标题:";
            status += mediaTitle;
        }
        if (mediaTitle) mpv_free(mediaTitle);
        char* pauseStr = mpv_get_property_string(player_.get(), "pause");
        status += (pauseStr && std::string(pauseStr) == "yes") ? " 已暂停" : " 播放中";
        if (pauseStr) mpv_free(pauseStr);
        char* eofStr = mpv_get_property_string(player_.get(), "eof-reached");
        if (eofStr && std::string(eofStr) == "yes") {
            status += " 已结束";
        }
        if (eofStr) mpv_free(eofStr);
        char* idleStr = mpv_get_property_string(player_.get(), "idle-active");
        if (idleStr && std::string(idleStr) == "yes") {
            status += " 空闲";
        }
        if (idleStr) mpv_free(idleStr);
        char* demuxer = mpv_get_property_string(player_.get(), "demuxer");
        if (demuxer && demuxer[0]) {
            status += " demuxer:";
            status += demuxer;
        }
        if (demuxer) mpv_free(demuxer);
        int64_t aid = 0, sid = 0;
        mpv_get_property(player_.get(), "aid", MPV_FORMAT_INT64, &aid);
        mpv_get_property(player_.get(), "sid", MPV_FORMAT_INT64, &sid);
        int subVisFlag = 0;
        mpv_get_property(player_.get(), "sub-visibility", MPV_FORMAT_FLAG, &subVisFlag);
        char trackInfo[96] = {0};
        std::snprintf(trackInfo, sizeof(trackInfo), " aid:%lld sid:%lld subvis:%d",
                      (long long)aid, (long long)sid, subVisFlag);
        status += trackInfo;
        char* errorMsg = mpv_get_property_string(player_.get(), "error-text");
        if (errorMsg && errorMsg[0]) {
            status += " 错误:";
            status += errorMsg;
        }
        if (errorMsg) mpv_free(errorMsg);
        // 当前字幕文本，用于诊断字幕是否被解码
        char* subText = mpv_get_property_string(player_.get(), "sub-text");
        if (subText && subText[0]) {
            status += " 字幕文本:";
            std::string st = subText;
            if (st.length() > 50) {
                st = st.substr(0, 50) + "…";
            }
            // 替换换行避免状态栏断行
            for (char& c : st) {
                if (c == '\n' || c == '\r') {
                    c = ' ';
                }
            }
            status += st;
        } else {
            status += " 字幕文本:(空)";
        }
        if (subText) mpv_free(subText);
        double cacheSpeed = 0;
        mpv_get_property(player_.get(), "cache-speed", MPV_FORMAT_DOUBLE, &cacheSpeed);
        char cacheInfo[64] = {0};
        std::snprintf(cacheInfo, sizeof(cacheInfo), " 缓存速度:%.0fB/s", cacheSpeed);
        status += cacheInfo;
        double timePos = 0, duration = 0;
        mpv_get_property(player_.get(), "time-pos", MPV_FORMAT_DOUBLE, &timePos);
        mpv_get_property(player_.get(), "duration", MPV_FORMAT_DOUBLE, &duration);
        char timeInfo[64] = {0};
        std::snprintf(timeInfo, sizeof(timeInfo), " 时间:%.1f/%.1f", timePos, duration);
        status += timeInfo;
        // Frame count for debugging
        char frameInfo[64] = {0};
        std::snprintf(frameInfo, sizeof(frameInfo), " 帧数:%d", framesRendered_);
        status += frameInfo;
        // Audio params
        char* aoDriver = mpv_get_property_string(player_.get(), "current-ao");
        if (aoDriver && aoDriver[0]) {
            status += " ao:";
            status += aoDriver;
        }
        if (aoDriver) mpv_free(aoDriver);
        mpv_node audioParams;
        if (mpv_get_property(player_.get(), "audio-params", MPV_FORMAT_NODE, &audioParams) >= 0 && audioParams.format == MPV_FORMAT_NODE_MAP) {
            for (int i = 0; i < audioParams.u.list->num; i++) {
                if (std::string(audioParams.u.list->keys[i]) == "samplerate" && audioParams.u.list->values[i].format == MPV_FORMAT_INT64) {
                    char sr[32];
                    std::snprintf(sr, sizeof(sr), " sr:%lld", (long long)audioParams.u.list->values[i].u.int64);
                    status += sr;
                }
                if (std::string(audioParams.u.list->keys[i]) == "format" && audioParams.u.list->values[i].format == MPV_FORMAT_STRING) {
                    status += " af:";
                    status += audioParams.u.list->values[i].u.string;
                }
            }
            mpv_free_node_contents(&audioParams);
        }
        return status;
    }

    // 缓冲/缓存状态快照（US4）：演示层轮询后映射为 buffering 事件。
    // pausedForCache 来自 paused-for-cache；demuxerBuffering 与 cacheDurationSeconds
    // 来自 demuxer-cache-state（mpv 0.40 已移除 cache-buffering-state，改读该节点）。
    napi_value GetBufferingState(napi_env env)
    {
        napi_value result = DefaultBufferingState(env);
        if (!player_) {
            return result;
        }
        int pausedFlag = 0;
        if (mpv_get_property(player_.get(), "paused-for-cache", MPV_FORMAT_FLAG, &pausedFlag) >= 0) {
            napi_value pausedValue = nullptr;
            napi_get_boolean(env, pausedFlag != 0, &pausedValue);
            napi_set_named_property(env, result, "pausedForCache", pausedValue);
        }
        mpv_node cacheState{};
        const int cacheResult = mpv_get_property(player_.get(), "demuxer-cache-state", MPV_FORMAT_NODE, &cacheState);
        if (cacheResult >= 0) {
            // 只要 mpv_get_property 成功就需释放 node，避免演示层轮询时按 format
            // 差异遗漏 mpv_free_node_contents 造成原生内存长期增长。
            if (cacheState.format == MPV_FORMAT_NODE_MAP) {
                for (int index = 0; index < cacheState.u.list->num; index++) {
                    const std::string key = cacheState.u.list->keys[index];
                    const mpv_node& value = cacheState.u.list->values[index];
                    if (key == "buffering" && value.format == MPV_FORMAT_FLAG) {
                        napi_value bufferingValue = nullptr;
                        napi_get_boolean(env, value.u.flag != 0, &bufferingValue);
                        napi_set_named_property(env, result, "demuxerBuffering", bufferingValue);
                    } else if (key == "cache-end" && value.format == MPV_FORMAT_DOUBLE) {
                        napi_value cacheEndValue = nullptr;
                        napi_create_double(env, value.u.double_, &cacheEndValue);
                        napi_set_named_property(env, result, "cacheDurationSeconds", cacheEndValue);
                    }
                }
            }
            mpv_free_node_contents(&cacheState);
        }
        int eofFlag = 0;
        if (mpv_get_property(player_.get(), "eof-reached", MPV_FORMAT_FLAG, &eofFlag) >= 0) {
            napi_value eofValue = nullptr;
            napi_get_boolean(env, eofFlag != 0, &eofValue);
            napi_set_named_property(env, result, "eofReached", eofValue);
        }
        int idleFlag = 0;
        if (mpv_get_property(player_.get(), "idle-active", MPV_FORMAT_FLAG, &idleFlag) >= 0) {
            napi_value idleValue = nullptr;
            napi_get_boolean(env, idleFlag != 0, &idleValue);
            napi_set_named_property(env, result, "idleActive", idleValue);
        }
        napi_set_named_property(env, result, "mediaKind", CreateString(env, currentMediaKind_));
        napi_set_named_property(env, result, "proxyLeaseId", CreateString(env, currentProxyLeaseId_));
        char* errorMsg = mpv_get_property_string(player_.get(), "error-text");
        if (errorMsg != nullptr) {
            napi_set_named_property(env, result, "errorText", CreateString(env, errorMsg));
            mpv_free(errorMsg);
        }
        return result;
    }

    std::string SetEventCallback(napi_env env, napi_value callback)
    {
        napi_valuetype type = napi_undefined;
        if (callback == nullptr || napi_typeof(env, callback, &type) != napi_ok || type != napi_function) {
            return "事件回调必须是函数";
        }
        std::lock_guard<std::mutex> lock(eventCallbackMutex_);
        if (eventTsfn_ != nullptr) {
            const napi_status releaseStatus = napi_release_threadsafe_function(eventTsfn_, napi_tsfn_release);
            if (releaseStatus != napi_ok) {
                MPV_LOG(LOG_WARN, "SetEventCallback: 释放旧事件回调失败，状态=%{public}d", releaseStatus);
            }
            eventTsfn_ = nullptr;
        }
        napi_value resourceName = CreateString(env, "VidAllMpvEvent");
        const napi_status status = napi_create_threadsafe_function(
            env, callback, nullptr, resourceName, 0, 1, this, nullptr, this,
            PlayerSession::CallEventCallback, &eventTsfn_);
        return status == napi_ok ? "事件回调已注册" : "注册事件回调失败";
    }

    void Release()
    {
        ClearProxyLease("release");
        StopRenderer();
        stopEventLoop_.store(true);
        if (player_) {
            mpv_wakeup(player_.get());
        }
        if (eventThread_.joinable()) {
            eventThread_.join();
        }
        {
            std::lock_guard<std::mutex> lock(lifecycleMutex_);
            player_.reset();
        }
        {
            std::lock_guard<std::mutex> eventLock(eventCallbackMutex_);
            if (eventTsfn_ != nullptr) {
                const napi_status releaseStatus = napi_release_threadsafe_function(eventTsfn_, napi_tsfn_release);
                if (releaseStatus != napi_ok) {
                    MPV_LOG(LOG_WARN, "Release: 释放事件回调失败，状态=%{public}d", releaseStatus);
                }
                eventTsfn_ = nullptr;
            }
        }
    }

    // MPV event loop thread — required for mpv_render_context_set_update_callback
    // to work. Without this, the render callback is never triggered.
    void EventLoop()
    {
        MPV_LOG(LOG_INFO, "EventLoop: starting");
        while (!stopEventLoop_.load()) {
            mpv_event* event = mpv_wait_event(player_.get(), 0.1);
            if (event->event_id == MPV_EVENT_SHUTDOWN) {
                MPV_LOG(LOG_INFO, "EventLoop: shutdown received");
                break;
            }
            if (event->event_id == MPV_EVENT_END_FILE) {
                const auto* endFile = static_cast<mpv_event_end_file*>(event->data);
                if (endFile != nullptr && endFile->reason == MPV_END_FILE_REASON_ERROR) {
                    DispatchEvent("error", mpv_error_string(endFile->error), endFile->error);
                }
            } else if (event->event_id == MPV_EVENT_LOG_MESSAGE) {
                const auto* log = static_cast<mpv_event_log_message*>(event->data);
                if (log != nullptr && log->text != nullptr) {
                    DispatchEvent("log", log->text);
                }
            } else if (event->event_id == MPV_EVENT_PROPERTY_CHANGE) {
                const auto* property = static_cast<mpv_event_property*>(event->data);
                if (property != nullptr && property->name != nullptr) {
                    if (std::string(property->name) == "track-list") {
                        DispatchEvent("tracks", "track-list changed");
                    } else {
                        DispatchEvent("buffering", "cache state changed");
                    }
                }
            }
        }
        MPV_LOG(LOG_INFO, "EventLoop: exiting");
    }

    // Get frame data for PixelMap rendering (called from ArkTS thread)
    napi_value GetFrameData(napi_env env)
    {
        std::lock_guard<std::mutex> lock(frameMutex_);
        if (!frameReady_ || pendingFrame_.empty()) {
            return nullptr;
        }

        napi_value result = nullptr;
        napi_create_object(env, &result);

        napi_value widthVal = nullptr;
        napi_create_int32(env, frameWidth_, &widthVal);
        napi_set_named_property(env, result, "width", widthVal);

        napi_value heightVal = nullptr;
        napi_create_int32(env, frameHeight_, &heightVal);
        napi_set_named_property(env, result, "height", heightVal);

        // Create ArrayBuffer from the pending frame data
        napi_value arrayBuffer = nullptr;
        void* data = nullptr;
        size_t dataSize = pendingFrame_.size();
        napi_create_arraybuffer(env, dataSize, &data, &arrayBuffer);
        memcpy(data, pendingFrame_.data(), dataSize);
        napi_set_named_property(env, result, "data", arrayBuffer);

        frameReady_ = false; // Mark as consumed
        return result;
    }

private:
    void DispatchEvent(const std::string& type, const char* message, int errorCode = 0)
    {
        std::lock_guard<std::mutex> lock(eventCallbackMutex_);
        if (eventTsfn_ == nullptr) {
            return;
        }
        auto* event = new NativeEvent{type, message == nullptr ? "未知 libmpv 错误" : message, errorCode};
        if (napi_call_threadsafe_function(eventTsfn_, event, napi_tsfn_nonblocking) != napi_ok) {
            delete event;
        }
    }

    static void CallEventCallback(napi_env env, napi_value callback, void*, void* data)
    {
        std::unique_ptr<NativeEvent> event(static_cast<NativeEvent*>(data));
        if (env == nullptr || callback == nullptr || !event) {
            return;
        }
        napi_value payload = nullptr;
        napi_create_object(env, &payload);
        napi_set_named_property(env, payload, "type", CreateString(env, event->type));
        napi_set_named_property(env, payload, "message", CreateString(env, event->message));
        napi_value errorCode = nullptr;
        napi_create_int32(env, event->errorCode, &errorCode);
        napi_set_named_property(env, payload, "errorCode", errorCode);
        napi_value ignored = nullptr;
        napi_call_function(env, nullptr, callback, 1, &payload, &ignored);
    }

    // GetProcAddress callback for mpv_opengl_init_params. Only uses
    // eglGetProcAddress — this is the standard way to resolve GL and EGL
    // extension functions. On devices with a broken GPU driver (e.g.
    // HarmonyOS TV emulator missing libEGL_impl.so), eglGetProcAddress
    // returns NULL for core GL functions. In that case, GetProcAddress
    // returns NULL, and libmpv will detect this and fail gracefully in
    // mpv_render_context_create rather than crashing.
    static void* GetProcAddress(void*, const char* name)
    {
        if (name == nullptr) {
            return nullptr;
        }
        void* proc = reinterpret_cast<void*>(eglGetProcAddress(name));
        if (proc == nullptr) {
            // Log only once to avoid flooding; the InitializeMpvRenderer
            // pre-check will catch this case before libmpv calls us.
            static bool loggedOnce = false;
            if (!loggedOnce) {
                MPV_LOG(LOG_WARN, "GetProcAddress: eglGetProcAddress(\"%{public}s\") returned NULL", name);
                loggedOnce = true;
            }
        }
        return proc;
    }

    static void NotifyRender(void* context)
    {
        auto* session = static_cast<PlayerSession*>(context);
        {
            std::lock_guard<std::mutex> lock(session->renderMutex_);
            session->renderRequested_ = true;
        }
        session->renderCondition_.notify_one();
    }

    bool InitializeEgl()
    {
        // window_ must already be created by RenderLoop before calling this
        if (window_ == nullptr) {
            return false;
        }
        display_ = eglGetDisplay(EGL_DEFAULT_DISPLAY);
        if (display_ == EGL_NO_DISPLAY || !eglInitialize(display_, nullptr, nullptr)) {
            return false;
        }

        const EGLint configAttributes[] = {
            EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
            EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
            EGL_RED_SIZE, 8,
            EGL_GREEN_SIZE, 8,
            EGL_BLUE_SIZE, 8,
            EGL_ALPHA_SIZE, 8,
            EGL_NONE
        };
        EGLint configCount = 0;
        if (!eglChooseConfig(display_, configAttributes, &config_, 1, &configCount) || configCount != 1) {
            return false;
        }
        const EGLint contextAttributes[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE};
        context_ = eglCreateContext(display_, config_, EGL_NO_CONTEXT, contextAttributes);
        if (context_ == EGL_NO_CONTEXT) {
            return false;
        }
        surface_ = eglCreateWindowSurface(display_, config_, reinterpret_cast<EGLNativeWindowType>(window_), nullptr);
        if (surface_ == EGL_NO_SURFACE || !eglMakeCurrent(display_, surface_, surface_, context_)) {
            return false;
        }

        // Probe the GL driver by calling a lightweight function. On some TV
        // emulator images the EGL wrapper "succeeds" (eglInitialize returns
        // true, eglGetProcAddress returns non-NULL) but the underlying GPU
        // driver library (libEGL_impl.so) is missing, so any actual GL call
        // crashes with SIGSEGV. We detect this here by calling glClear with a
        // no-op mask — it must not crash and must not leave an impossible
        // error state. If it does crash, the signal handler below will longjmp
        // back and we clean up EGL gracefully.
        if (!ProbeGlDriver()) {
            eglMakeCurrent(display_, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
            if (surface_ != EGL_NO_SURFACE) { eglDestroySurface(display_, surface_); surface_ = EGL_NO_SURFACE; }
            if (context_ != EGL_NO_CONTEXT) { eglDestroyContext(display_, context_); context_ = EGL_NO_CONTEXT; }
            eglTerminate(display_); display_ = EGL_NO_DISPLAY;
            // Do NOT destroy window_ — it may be reused for SW render
            return false;
        }

        eglSwapInterval(display_, 1);
        return true;
    }

    // File-scope jump buffer for the GL probe signal handler.
    // Defined at file scope (outside the class) to avoid ODR issues.
    // sigjmp_buf gProbeJmpBuf;

    // Probe the GL driver with a lightweight call. Returns false if the
    // driver is broken (SIGSEGV from NULL-dereferencing EGL wrapper stub).
    bool ProbeGlDriver()
    {
        struct sigaction oldAction = {};
        struct sigaction sa = {};
        sa.sa_handler = [](int) { siglongjmp(gProbeJmpBuf, 1); };
        sigemptyset(&sa.sa_mask);
        sa.sa_flags = 0;
        if (sigaction(SIGSEGV, &sa, &oldAction) != 0) {
            MPV_LOG(LOG_ERROR, "ProbeGlDriver: sigaction failed");
            return false;
        }

        if (sigsetjmp(gProbeJmpBuf, 1) != 0) {
            // SIGSEGV was caught during the GL probe — driver is broken.
            sigaction(SIGSEGV, &oldAction, nullptr);
            MPV_LOG(LOG_ERROR, "ProbeGlDriver: SIGSEGV caught — GPU driver is broken");
            return false;
        }

        // Clear with zero mask — a no-op that still exercises the GL dispatch.
        glClear(0);
        // glGetError exercises the driver further; any return proves the
        // dispatch table works. A crash means the driver is broken.
        GLenum err = glGetError();
        MPV_LOG(LOG_INFO, "ProbeGlDriver: glClear+glGetError OK, err=%{public}u — driver OK", err);

        sigaction(SIGSEGV, &oldAction, nullptr);
        return true;
    }

    bool InitializeMpvRenderer()
    {
        MPV_LOG(LOG_INFO, "InitializeMpvRenderer: called, useSwRender_=%{public}d renderContext_=%{public}p",
                useSwRender_, renderContext_);
        // On emulator devices with broken GPU drivers, eglGetProcAddress may
        // return non-NULL stubs that crash when called by libmpv internally.
        // To avoid this, try SW render first (which requires no GPU), and
        // only attempt OpenGL if SW is not available.
        // TODO: On real TV hardware, try OpenGL first for better performance.

        // Try software rendering first — safe on all devices
        const char* swApiType = MPV_RENDER_API_TYPE_SW;
        mpv_render_param swParams[] = {
            {MPV_RENDER_PARAM_API_TYPE, const_cast<char*>(swApiType)},
            {MPV_RENDER_PARAM_INVALID, nullptr}
        };
        int rc = mpv_render_context_create(&renderContext_, player_.get(), swParams);
        MPV_LOG(LOG_INFO, "InitializeMpvRenderer: SW mpv_render_context_create rc=%{public}d renderContext_=%{public}p", rc, renderContext_);
        if (rc >= 0) {
            MPV_LOG(LOG_INFO, "InitializeMpvRenderer: SW render context created OK");
            mpv_render_context_set_update_callback(renderContext_, NotifyRender, this);
            useSwRender_ = true;
            return true;
        }
        MPV_LOG(LOG_WARN, "InitializeMpvRenderer: SW render failed (rc=%{public}d), trying OpenGL", rc);
        lastInitRc_ = rc;

        // Fallback: try OpenGL via EGL
        void* glClearProc = reinterpret_cast<void*>(eglGetProcAddress("glClear"));
        void* glBindTexProc = reinterpret_cast<void*>(eglGetProcAddress("glBindTexture"));
        MPV_LOG(LOG_INFO, "InitializeMpvRenderer: eglGetProcAddress glClear=%{public}p glBindTexture=%{public}p",
                glClearProc, glBindTexProc);
        if (glClearProc == nullptr || glBindTexProc == nullptr) {
            MPV_LOG(LOG_ERROR, "InitializeMpvRenderer: eglGetProcAddress returns NULL for core GL — GPU driver broken");
            return false;
        }

        mpv_opengl_init_params glInit = {GetProcAddress, nullptr};
        const char* apiType = MPV_RENDER_API_TYPE_OPENGL;
        mpv_render_param params[] = {
            {MPV_RENDER_PARAM_API_TYPE, const_cast<char*>(apiType)},
            {MPV_RENDER_PARAM_OPENGL_INIT_PARAMS, &glInit},
            {MPV_RENDER_PARAM_INVALID, nullptr}
        };
        rc = mpv_render_context_create(&renderContext_, player_.get(), params);
        if (rc >= 0) {
            MPV_LOG(LOG_INFO, "InitializeMpvRenderer: OpenGL render context created OK");
            mpv_render_context_set_update_callback(renderContext_, NotifyRender, this);
            useSwRender_ = false;
            return true;
        }
        MPV_LOG(LOG_ERROR, "InitializeMpvRenderer: OpenGL render also failed (rc=%{public}d)", rc);
        return false;
    }

    void RenderLoop()
    {
        MPV_LOG(LOG_INFO, "RenderLoop: starting");

        // Create NativeWindow from surfaceId obtained from XComponentController.
        // This creates an independent producer connection to the BufferQueue,
        // which is the standard approach for video decoder output on HarmonyOS.
        if (surfaceId_.empty()) {
            MPV_LOG(LOG_ERROR, "RenderLoop: no surfaceId provided");
            std::lock_guard<std::mutex> renderLock(renderMutex_);
            renderError_ = "Surface ID 未提供；请确保 XComponent Surface 已创建。";
            renderReadyCv_.notify_one();
            return;
        }

        uint64_t sid = 0;
        try {
            sid = std::stoull(surfaceId_);
        } catch (...) {
            MPV_LOG(LOG_ERROR, "RenderLoop: invalid surfaceId '%{public}s'", surfaceId_.c_str());
            std::lock_guard<std::mutex> renderLock(renderMutex_);
            renderError_ = "Surface ID 格式无效。";
            renderReadyCv_.notify_one();
            return;
        }

        OHNativeWindow* createdWindow = nullptr;
        int32_t createRc = OH_NativeWindow_CreateNativeWindowFromSurfaceId(sid, &createdWindow);
        MPV_LOG(LOG_INFO, "RenderLoop: CreateNativeWindowFromSurfaceId sid=%{public}llu rc=%{public}d window=%{public}p",
                (unsigned long long)sid, createRc, createdWindow);
        if (createRc != 0 || createdWindow == nullptr) {
            MPV_LOG(LOG_ERROR, "RenderLoop: CreateNativeWindowFromSurfaceId failed (rc=%{public}d)", createRc);
            std::lock_guard<std::mutex> renderLock(renderMutex_);
            renderError_ = "无法从 Surface ID 创建 NativeWindow；rc=" + std::to_string(createRc);
            renderReadyCv_.notify_one();
            return;
        }
        window_ = createdWindow;
        ownsWindow_ = true;

        // Strategy: try SW render first (no GPU/EGL needed).
        // Only fall back to EGL+GL if SW render fails.
        // IMPORTANT: Do NOT initialize EGL before trying SW render, because
        // eglCreateWindowSurface claims the NativeWindow's BufferQueue producer,
        // which then conflicts with SW render's RequestBuffer calls (error 50002000).

        // Try SW render first — no GPU required
        if (InitializeMpvRenderer()) {
            // SW render context created successfully
            MPV_LOG(LOG_INFO, "RenderLoop: SW render initialized, entering SwRenderLoop");
        } else {
            // SW render failed — try EGL + OpenGL as fallback
            MPV_LOG(LOG_INFO, "RenderLoop: SW render failed, trying EGL+GL");
            bool eglOk = InitializeEgl();
            if (eglOk) {
                // Re-try InitializeMpvRenderer with EGL context active (GL render path)
                if (!InitializeMpvRenderer()) {
                    MPV_LOG(LOG_ERROR, "RenderLoop: GL render also failed after EGL init");
                    // Clean up EGL
                    eglMakeCurrent(display_, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
                    if (surface_ != EGL_NO_SURFACE) { eglDestroySurface(display_, surface_); surface_ = EGL_NO_SURFACE; }
                    if (context_ != EGL_NO_CONTEXT) { eglDestroyContext(display_, context_); context_ = EGL_NO_CONTEXT; }
                    eglTerminate(display_); display_ = EGL_NO_DISPLAY;
                }
            }
            if (renderContext_ == nullptr) {
                MPV_LOG(LOG_ERROR, "RenderLoop: Both SW and GL render failed");
                std::lock_guard<std::mutex> lock(renderMutex_);
                renderError_ = "渲染上下文创建失败；当前设备不支持视频输出。";
                renderReadyCv_.notify_one();
                return;
            }
        }

        {
            std::lock_guard<std::mutex> lock(renderMutex_);
            renderReady_ = true;
            renderReadyCv_.notify_one();
        }

        if (useSwRender_) {
            SwRenderLoop();
        } else {
            GlRenderLoop();
        }
        DestroyRenderer();
    }

    // Software render loop: read frames from mpv as raw pixels.
    // On real hardware with working NativeWindow BufferQueue, writes frames
    // directly to the XComponent surface. On emulators where BufferQueue is
    // broken (error 50002000), falls back to PixelMap callback path that
    // delivers RGBA pixels to ArkTS via onFrameCallback.
    void SwRenderLoop()
    {
        MPV_LOG(LOG_INFO, "SwRenderLoop: starting");
        bool useNativeWindow = false;
        int nativeWindowFailCount = 0;
        const int MAX_NATIVE_WINDOW_FAILS = 3;

        if (window_ != nullptr) {
            // Try to set up NativeWindow
            int32_t format = 1; // PIXEL_FMT_RGBA_8888
            OH_NativeWindow_NativeWindowHandleOpt(window_, SET_FORMAT, format);
            OH_NativeWindow_NativeWindowHandleOpt(window_, SET_BUFFER_GEOMETRY, 480, 270);

            // Test if NativeWindow BufferQueue works by requesting one buffer
            OHNativeWindowBuffer* testBuf = nullptr;
            int testFence = -1;
            int testRc = OH_NativeWindow_NativeWindowRequestBuffer(window_, &testBuf, &testFence);
            if (testRc == 0 && testBuf != nullptr) {
                // BufferQueue works — flush the test buffer and use NativeWindow path
                Region region = {};
                Region::Rect rect = {0, 0, 480, 270};
                region.rects = &rect;
                region.rectNumber = 1;
                OH_NativeWindow_NativeWindowFlushBuffer(window_, testBuf, testFence, region);
                useNativeWindow = true;
                MPV_LOG(LOG_INFO, "SwRenderLoop: NativeWindow BufferQueue OK, using direct path");
            } else {
                MPV_LOG(LOG_WARN, "SwRenderLoop: NativeWindow BufferQueue failed (rc=%{public}d), using PixelMap callback", testRc);
            }
        } else {
            MPV_LOG(LOG_WARN, "SwRenderLoop: no NativeWindow, using PixelMap callback");
        }

        int lastW = 0, lastH = 0;
        std::vector<uint8_t> frameBuf;

        for (;;) {
            {
                std::unique_lock<std::mutex> lock(renderMutex_);
                renderCondition_.wait_for(lock, std::chrono::milliseconds(16), [this] {
                    return stopRenderer_ || renderRequested_;
                });
                if (stopRenderer_) {
                    break;
                }
                if (!renderRequested_) {
                    continue;
                }
                renderRequested_ = false;
            }

            if ((mpv_render_context_update(renderContext_) & MPV_RENDER_UPDATE_FRAME) == 0) {
                continue;
            }

            int64_t w64 = 0, h64 = 0;
            mpv_get_property(player_.get(), "width", MPV_FORMAT_INT64, &w64);
            mpv_get_property(player_.get(), "height", MPV_FORMAT_INT64, &h64);
            int w = static_cast<int>(w64);
            int h = static_cast<int>(h64);
            if (w <= 0 || h <= 0) {
                continue;
            }

            // Reallocate buffer if dimensions changed
            size_t stride = ((w * 4 + 63) / 64) * 64;
            size_t frameSize = stride * h;
            if (w != lastW || h != lastH) {
                frameBuf.resize(frameSize + 64);
                lastW = w;
                lastH = h;
                if (useNativeWindow) {
                    OH_NativeWindow_NativeWindowHandleOpt(window_, SET_BUFFER_GEOMETRY, w, h);
                }
                MPV_LOG(LOG_INFO, "SwRenderLoop: video dimensions changed to %dx%d", w, h);
            }

            uint8_t* framePtr = frameBuf.data();
            uintptr_t alignOffset = (64 - (reinterpret_cast<uintptr_t>(framePtr) % 64)) % 64;
            framePtr += alignOffset;

            int size[2] = {w, h};
            char* fmt = const_cast<char*>("rgba");
            mpv_render_param renderParams[] = {
                {MPV_RENDER_PARAM_SW_SIZE, size},
                {MPV_RENDER_PARAM_SW_FORMAT, fmt},
                {MPV_RENDER_PARAM_SW_STRIDE, &stride},
                {MPV_RENDER_PARAM_SW_POINTER, framePtr},
                {MPV_RENDER_PARAM_INVALID, nullptr}
            };
            if (mpv_render_context_render(renderContext_, renderParams) < 0) {
                continue;
            }

            framesRendered_++;

            if (useNativeWindow) {
                // Direct NativeWindow path — high performance on real hardware
                OHNativeWindowBuffer* buffer = nullptr;
                int fenceFd = -1;
                int rc = OH_NativeWindow_NativeWindowRequestBuffer(window_, &buffer, &fenceFd);
                if (rc != 0 || buffer == nullptr) {
                    nativeWindowFailCount++;
                    if (nativeWindowFailCount >= MAX_NATIVE_WINDOW_FAILS) {
                        MPV_LOG(LOG_WARN, "SwRenderLoop: NativeWindow failed %d times, switching to PixelMap", nativeWindowFailCount);
                        useNativeWindow = false;
                    }
                    continue;
                }
                nativeWindowFailCount = 0;

                BufferHandle* bufHandle = OH_NativeWindow_GetBufferHandleFromNative(buffer);
                if (bufHandle != nullptr && bufHandle->virAddr != nullptr) {
                    int bufStride = bufHandle->stride;
                    if (bufStride <= 0) {
                        bufStride = w * 4;
                    }
                    size_t copyWidth = std::min(static_cast<size_t>(w * 4), static_cast<size_t>(bufStride));
                    size_t copyLines = std::min(static_cast<size_t>(h), static_cast<size_t>(bufHandle->height > 0 ? bufHandle->height : h));
                    for (size_t y = 0; y < copyLines; y++) {
                        memcpy(static_cast<uint8_t*>(bufHandle->virAddr) + y * bufStride,
                               framePtr + y * stride, copyWidth);
                    }
                }
                Region region = {};
                int flushW = (bufHandle && bufHandle->width > 0) ? bufHandle->width : w;
                int flushH = (bufHandle && bufHandle->height > 0) ? bufHandle->height : h;
                Region::Rect rect = {0, 0, static_cast<uint32_t>(flushW), static_cast<uint32_t>(flushH)};
                region.rects = &rect;
                region.rectNumber = 1;
                OH_NativeWindow_NativeWindowFlushBuffer(window_, buffer, fenceFd, region);
            } else {
                // PixelMap callback path — for emulators with broken BufferQueue
                // Store the latest frame data so ArkTS can read it via getFrameData()
                {
                    std::lock_guard<std::mutex> lock(frameMutex_);
                    // Store tightly packed RGBA data (no stride padding needed for PixelMap)
                    if (pendingFrame_.size() != static_cast<size_t>(w * h * 4)) {
                        pendingFrame_.resize(w * h * 4);
                    }
                    // Copy with stride-to-tight conversion
                    for (int y = 0; y < h; y++) {
                        memcpy(pendingFrame_.data() + y * w * 4,
                               framePtr + y * stride, w * 4);
                    }
                    frameWidth_ = w;
                    frameHeight_ = h;
                    frameReady_ = true;
                }
            }
        }
        MPV_LOG(LOG_INFO, "SwRenderLoop: exiting, rendered %d frames", framesRendered_);
    }

    // OpenGL render loop using EGL + XComponent surface
    void GlRenderLoop()
    {
        MPV_LOG(LOG_INFO, "GlRenderLoop: starting");
        for (;;) {
            {
                std::unique_lock<std::mutex> lock(renderMutex_);
                renderCondition_.wait_for(lock, std::chrono::milliseconds(100), [this] {
                    return stopRenderer_ || renderRequested_;
                });
                if (stopRenderer_) {
                    break;
                }
                renderRequested_ = false;
            }

            if ((mpv_render_context_update(renderContext_) & MPV_RENDER_UPDATE_FRAME) == 0) {
                continue;
            }
            EGLint width = 0;
            EGLint height = 0;
            eglQuerySurface(display_, surface_, EGL_WIDTH, &width);
            eglQuerySurface(display_, surface_, EGL_HEIGHT, &height);
            if (width <= 0 || height <= 0 || !eglMakeCurrent(display_, surface_, surface_, context_)) {
                continue;
            }
            mpv_opengl_fbo fbo = {0, width, height, GL_RGBA8};
            int flipY = 1;
            mpv_render_param params[] = {
                {MPV_RENDER_PARAM_OPENGL_FBO, &fbo},
                {MPV_RENDER_PARAM_FLIP_Y, &flipY},
                {MPV_RENDER_PARAM_INVALID, nullptr}
            };
            if (mpv_render_context_render(renderContext_, params) >= 0) {
                eglSwapBuffers(display_, surface_);
            }
        }
    }

    void StopRenderer()
    {
        std::unique_lock<std::mutex> lifecycleLock(lifecycleMutex_);
        if (!renderThread_.joinable()) {
            return;
        }
        {
            std::lock_guard<std::mutex> renderLock(renderMutex_);
            stopRenderer_ = true;
        }
        renderCondition_.notify_one();
        lifecycleLock.unlock();
        renderThread_.join();
    }

    void DestroyRenderer()
    {
        if (renderContext_ != nullptr) {
            mpv_render_context_set_update_callback(renderContext_, nullptr, nullptr);
            mpv_render_context_free(renderContext_);
            renderContext_ = nullptr;
        }
        if (display_ != EGL_NO_DISPLAY) {
            eglMakeCurrent(display_, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
            if (surface_ != EGL_NO_SURFACE) {
                eglDestroySurface(display_, surface_);
            }
            if (context_ != EGL_NO_CONTEXT) {
                eglDestroyContext(display_, context_);
            }
            eglTerminate(display_);
        }
        if (window_ != nullptr) {
            if (ownsWindow_) {
                // We created this window via CreateNativeWindowFromSurfaceId — must destroy it
                OH_NativeWindow_DestroyNativeWindow(window_);
            }
            window_ = nullptr;
            ownsWindow_ = false;
        }
        display_ = EGL_NO_DISPLAY;
        surface_ = EGL_NO_SURFACE;
        context_ = EGL_NO_CONTEXT;
        config_ = nullptr;
    }

    std::unique_ptr<mpv_handle, decltype(&mpv_terminate_destroy)> player_{nullptr, mpv_terminate_destroy};
    std::mutex lifecycleMutex_;
    std::atomic<bool> stopEventLoop_{false};
    std::mutex eventCallbackMutex_;
    napi_threadsafe_function eventTsfn_ = nullptr;
    std::thread eventThread_;
    std::thread renderThread_;
    std::mutex renderMutex_;
    std::condition_variable renderCondition_;
    std::condition_variable renderReadyCv_;
    bool stopRenderer_ = false;
    bool renderRequested_ = false;
    bool renderReady_ = false;
    std::string renderError_;
    bool useSwRender_ = false;
    int lastInitRc_ = 0;
    OHNativeWindow* window_ = nullptr;
    bool ownsWindow_ = false;
    std::string surfaceId_;
    EGLDisplay display_ = EGL_NO_DISPLAY;
    EGLSurface surface_ = EGL_NO_SURFACE;
    EGLContext context_ = EGL_NO_CONTEXT;
    EGLConfig config_ = nullptr;
    mpv_render_context* renderContext_ = nullptr;
    // PixelMap fallback frame data
    std::mutex frameMutex_;
    std::vector<uint8_t> pendingFrame_;
    int frameWidth_ = 0;
    int frameHeight_ = 0;
    bool frameReady_ = false;
    int framesRendered_ = 0;
    // 当前媒体类型与 SMB 代理租约关联（US4）：切源/停止/释放时清理。
    std::string currentMediaKind_;
    std::string currentProxyLeaseId_;
};

std::mutex g_sessionsMutex;
std::unordered_map<int64_t, std::shared_ptr<PlayerSession>> g_sessions;
int64_t g_nextHandle = 1;

std::shared_ptr<PlayerSession> FindSession(int64_t handle)
{
    std::lock_guard<std::mutex> lock(g_sessionsMutex);
    const auto found = g_sessions.find(handle);
    return found == g_sessions.end() ? nullptr : found->second;
}

#endif

napi_value GetBuildInfo(napi_env env, napi_callback_info info)
{
    (void)info;
    napi_value result = nullptr;
    napi_create_object(env, &result);
    napi_value available = nullptr;
#if VIDALL_MPV_AVAILABLE
    napi_get_boolean(env, true, &available);
    napi_set_named_property(env, result, "mpvVersion", CreateString(env, "0.40.0"));
#else
    napi_get_boolean(env, false, &available);
    napi_set_named_property(env, result, "mpvVersion", CreateString(env, "未随 x86_64 模拟器打包"));
#endif
    napi_set_named_property(env, result, "available", available);
    napi_set_named_property(env, result, "abi", CreateString(env,
#if VIDALL_MPV_AVAILABLE
        "arm64-v8a"
#else
        "x86_64"
#endif
    ));
    napi_set_named_property(env, result, "sourceCommit", CreateString(env, "e07b7cd8b872427e03540502e4a68b23b54da133"));
    return result;
}

napi_value CreatePlayer(napi_env env, napi_callback_info info)
{
    (void)info;
    napi_value result = nullptr;
#if VIDALL_MPV_AVAILABLE
    auto session = std::make_shared<PlayerSession>();
    std::string error;
    if (!session->Initialize(error)) {
        napi_create_int64(env, 0, &result);
        return result;
    }
    int64_t handle = 0;
    {
        std::lock_guard<std::mutex> lock(g_sessionsMutex);
        handle = g_nextHandle++;
        g_sessions.emplace(handle, std::move(session));
    }
    napi_create_int64(env, handle, &result);
#else
    napi_create_int64(env, 0, &result);
#endif
    return result;
}

napi_value AttachSurface(napi_env env, napi_callback_info info)
{
#if VIDALL_MPV_AVAILABLE
    size_t argc = 2;
    napi_value args[2] = {nullptr, nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);

    int64_t handle = 0;
    if (napi_get_value_int64(env, args[0], &handle) != napi_ok || handle <= 0) {
        return CreateString(env, "播放器句柄无效");
    }

    std::string surfaceId;
    if (argc >= 2 && args[1] != nullptr) {
        size_t len = 0;
        napi_get_value_string_utf8(env, args[1], nullptr, 0, &len);
        if (len > 0) {
            surfaceId.resize(len);
            napi_get_value_string_utf8(env, args[1], &surfaceId[0], len + 1, &len);
        }
    }

    auto session = FindSession(handle);
    if (!session) {
        return CreateString(env, "播放器不存在或已释放");
    }
    return CreateString(env, session->AttachSurface(surfaceId));
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value DetachSurface(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    if (!GetHandleArgument(env, info, handle)) {
        return CreateString(env, "播放器句柄无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->DetachSurface() : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value SetEventCallback(napi_env env, napi_callback_info info)
{
    size_t argc = 2;
    napi_value args[2] = {nullptr, nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
    int64_t handle = 0;
    if (argc != 2 || napi_get_value_int64(env, args[0], &handle) != napi_ok || handle <= 0) {
        return CreateString(env, "播放器句柄无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->SetEventCallback(env, args[1]) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value Load(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    std::string url;
    std::string authorization;
    if (!GetHandleArgument(env, info, handle) || !GetStringArgument(env, info, 1, url)) {
        return CreateString(env, "请输入有效的视频 URL");
    }
    GetStringArgument(env, info, 2, authorization);
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->Load(url, authorization) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value LoadMedia(napi_env env, napi_callback_info info)
{
    size_t argc = 5;
    napi_value args[5] = {nullptr, nullptr, nullptr, nullptr, nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
    int64_t handle = 0;
    std::string kind;
    std::string url;
    std::string authorization;
    std::string proxyLeaseId;
    if (argc < 3 || napi_get_value_int64(env, args[0], &handle) != napi_ok || handle <= 0 ||
        !ReadString(env, args[1], kind) || !ReadString(env, args[2], url)) {
        return CreateString(env, "请输入有效的媒体类型与 URL");
    }
    if (argc >= 4) {
        ReadString(env, args[3], authorization);
    }
    if (argc >= 5) {
        ReadString(env, args[4], proxyLeaseId);
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->LoadMedia(kind, url, authorization, proxyLeaseId) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value AddExternalAudio(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    std::string uri;
    if (!GetHandleArgument(env, info, handle) || !GetStringArgument(env, info, 1, uri)) {
        return CreateString(env, "音频地址无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->AddExternalAudio(uri) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value GetBufferingState(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    if (!GetHandleArgument(env, info, handle)) {
        return DefaultBufferingState(env);
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return session ? session->GetBufferingState(env) : DefaultBufferingState(env);
#else
    return DefaultBufferingState(env);
#endif
}

napi_value SetPause(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    size_t argc = 2;
    napi_value args[2] = {nullptr, nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
    bool paused = false;
    if (argc != 2 || napi_get_value_int64(env, args[0], &handle) != napi_ok || napi_get_value_bool(env, args[1], &paused) != napi_ok) {
        return CreateString(env, "播放状态参数无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->SetPause(paused) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value SeekRelative(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    double seconds = 0;
    if (!GetHandleArgument(env, info, handle) || !GetFiniteDoubleArgument(env, info, 1, seconds)) {
        return CreateString(env, "跳转参数无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->Seek(seconds, "relative+exact") : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value SeekPercent(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    double percent = 0;
    if (!GetHandleArgument(env, info, handle) || !GetFiniteDoubleArgument(env, info, 1, percent) || percent < 0 || percent > 100) {
        return CreateString(env, "百分比跳转参数无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->Seek(percent, "absolute-percent+exact") : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value SetSpeed(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    double speed = 0;
    if (!GetHandleArgument(env, info, handle) || !GetFiniteDoubleArgument(env, info, 1, speed) || speed <= 0) {
        return CreateString(env, "播放速度参数无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->SetOption("speed", speed) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value SetVolume(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    double volume = 0;
    if (!GetHandleArgument(env, info, handle) || !GetFiniteDoubleArgument(env, info, 1, volume) || volume < 0 || volume > 100) {
        return CreateString(env, "音量参数无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->SetOption("volume", volume) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value SetMuted(napi_env env, napi_callback_info info)
{
    size_t argc = 2;
    napi_value args[2] = {nullptr, nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
    int64_t handle = 0;
    bool muted = false;
    if (argc != 2 || napi_get_value_int64(env, args[0], &handle) != napi_ok || handle <= 0 ||
        napi_get_value_bool(env, args[1], &muted) != napi_ok) {
        return CreateString(env, "静音参数无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->SetMuted(muted) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value SelectTrack(napi_env env, napi_callback_info info, const char* property)
{
    int64_t handle = 0;
    if (!GetHandleArgument(env, info, handle)) {
        return CreateString(env, "播放器句柄无效");
    }
    size_t argc = 2;
    napi_value args[2] = {nullptr, nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
    int64_t trackId = -1;
    if (argc != 2) {
        return CreateString(env, "轨道参数无效");
    }
    napi_valuetype argumentType = napi_undefined;
    napi_typeof(env, args[1], &argumentType);
    if (argumentType != napi_null &&
        (napi_get_value_int64(env, args[1], &trackId) != napi_ok || trackId < 0)) {
        return CreateString(env, "轨道参数无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->SelectTrack(property, trackId) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value SelectAudioTrack(napi_env env, napi_callback_info info)
{
    return SelectTrack(env, info, "aid");
}

napi_value SelectSubtitleTrack(napi_env env, napi_callback_info info)
{
    return SelectTrack(env, info, "sid");
}

napi_value AddExternalSubtitle(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    std::string uri;
    if (!GetHandleArgument(env, info, handle) || !GetStringArgument(env, info, 1, uri)) {
        return CreateString(env, "字幕地址无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->AddExternalSubtitle(uri) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value SetSubtitleDelay(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    double delaySeconds = 0;
    if (!GetHandleArgument(env, info, handle) || !GetFiniteDoubleArgument(env, info, 1, delaySeconds)) {
        return CreateString(env, "字幕延迟参数无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->SetOption("sub-delay", delaySeconds) : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value Stop(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    if (!GetHandleArgument(env, info, handle)) {
        return CreateString(env, "播放器句柄无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->Stop() : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value ReleasePlayer(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    if (!GetHandleArgument(env, info, handle)) {
        return CreateString(env, "播放器句柄无效");
    }
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<PlayerSession> session;
    {
        std::lock_guard<std::mutex> lock(g_sessionsMutex);
        const auto found = g_sessions.find(handle);
        if (found == g_sessions.end()) {
            return CreateString(env, "播放器已释放");
        }
        session = found->second;
        g_sessions.erase(found);
    }
    session->Release();
    return CreateString(env, "播放器已释放");
#else
    return CreateString(env, "模拟器无原生播放器需要释放");
#endif
}

napi_value GetTracks(napi_env env, napi_callback_info info)
{
#if VIDALL_MPV_AVAILABLE
    int64_t handle = 0;
    if (!GetHandleArgument(env, info, handle)) {
        napi_value tracks = nullptr;
        napi_create_array(env, &tracks);
        return tracks;
    }
    auto session = FindSession(handle);
    if (!session) {
        napi_value tracks = nullptr;
        napi_create_array(env, &tracks);
        return tracks;
    }
    return session->GetTracks(env);
#else
    napi_value tracks = nullptr;
    napi_create_array(env, &tracks);
    return tracks;
#endif
}

napi_value GetPlayerStatus(napi_env env, napi_callback_info info)
{
    int64_t handle = 0;
    if (!GetHandleArgument(env, info, handle)) {
        return CreateString(env, "播放器句柄无效");
    }
#if VIDALL_MPV_AVAILABLE
    auto session = FindSession(handle);
    return CreateString(env, session ? session->GetPlayerStatus() : "播放器不存在或已释放");
#else
    return CreateString(env, "x86_64 模拟器不支持本 ARM64 libmpv 演示");
#endif
}

napi_value GetFrameData(napi_env env, napi_callback_info info)
{
#if VIDALL_MPV_AVAILABLE
    int64_t handle = 0;
    if (!GetHandleArgument(env, info, handle)) {        return nullptr;
    }
    auto session = FindSession(handle);
    return session ? session->GetFrameData(env) : nullptr;
#else
    return nullptr;
#endif
}

// 设置字体搜索目录：fontconfig 内嵌配置指向 XDG_DATA_HOME/fonts，
// 需要在 mpv_initialize 之前设置环境变量并拷贝系统字体到可写目录。
napi_value SetDataDir(napi_env env, napi_callback_info info)
{
    std::string dataDir;
    if (!GetStringArgument(env, info, 0, dataDir) || dataDir.empty()) {
        return CreateString(env, "数据目录参数无效");
    }
    // 确保目录存在
    mkdir(dataDir.c_str(), 0755);
    std::string fontsDir = dataDir + "/fonts";
    mkdir(fontsDir.c_str(), 0755);
    std::string fontconfigDir = dataDir + "/fontconfig";
    mkdir(fontconfigDir.c_str(), 0755);
    // 设置 XDG 环境变量，让 fontconfig 在 <dataDir>/fonts 查找字体
    setenv("XDG_DATA_HOME", dataDir.c_str(), 1);
    setenv("XDG_CACHE_HOME", dataDir.c_str(), 1);
    setenv("HOME", dataDir.c_str(), 1);
    // 生成 fontconfig 配置文件，直接指向系统字体目录，绕过编译时路径
    std::string confPath = fontconfigDir + "/fonts.conf";
    std::ofstream confOut(confPath);
    if (confOut.good()) {
        confOut << "<?xml version=\"1.0\"?>\n"
                << "<!DOCTYPE fontconfig SYSTEM \"fonts.dtd\">\n"
                << "<fontconfig>\n"
                << "  <dir>/system/fonts</dir>\n"
                << "  <dir>" << fontsDir << "</dir>\n"
                << "  <cachedir>" << dataDir << "/font-cache</cachedir>\n"
                << "  <config></config>\n"
                << "</fontconfig>\n";
        confOut.close();
        setenv("FONTCONFIG_FILE", confPath.c_str(), 1);
        MPV_LOG(LOG_INFO, "SetDataDir: FONTCONFIG_FILE=%{public}s", confPath.c_str());
    }
#if VIDALL_MPV_AVAILABLE
    // 从 /system/fonts 拷贝关键字体到可写目录（fontconfig 需要可读的字体文件）
    const std::vector<std::string> fontFiles = {
        "HarmonyOS_Sans_SC.ttf",
        "HarmonyOS_Sans.ttf",
        "NotoSansCJK-Regular.ttc"
    };
    int copied = 0;
    for (const std::string& fontFile : fontFiles) {
        std::string dst = fontsDir + "/" + fontFile;
        // 已存在则跳过
        std::ifstream existTest(dst);
        if (existTest.good()) {
            existTest.close();
            copied++;
            continue;
        }
        existTest.close();
        std::string src = "/system/fonts/" + fontFile;
        std::ifstream in(src, std::ios::binary);
        std::ofstream out(dst, std::ios::binary);
        if (in.good() && out.good()) {
            out << in.rdbuf();
            copied++;
            MPV_LOG(LOG_INFO, "SetDataDir: copied %{public}s", fontFile.c_str());
        }
        in.close();
        out.close();
    }
    MPV_LOG(LOG_INFO, "SetDataDir: dataDir=%{public}s fontsCopied=%{public}d", dataDir.c_str(), copied);
    return CreateString(env, "字体目录已设置，拷贝 " + std::to_string(copied) + " 个字体");
#else
    return CreateString(env, "字体目录已设置（非 ARM64 环境）");
#endif
}

napi_value Init(napi_env env, napi_value exports)
{
    napi_property_descriptor descriptors[] = {
        {"getBuildInfo", nullptr, GetBuildInfo, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setDataDir", nullptr, SetDataDir, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"createPlayer", nullptr, CreatePlayer, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setEventCallback", nullptr, SetEventCallback, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"attachSurface", nullptr, AttachSurface, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"detachSurface", nullptr, DetachSurface, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"load", nullptr, Load, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"loadMedia", nullptr, LoadMedia, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"addExternalAudio", nullptr, AddExternalAudio, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"getBufferingState", nullptr, GetBufferingState, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setPause", nullptr, SetPause, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"seekRelative", nullptr, SeekRelative, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"seekPercent", nullptr, SeekPercent, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setSpeed", nullptr, SetSpeed, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setVolume", nullptr, SetVolume, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setMuted", nullptr, SetMuted, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"selectAudioTrack", nullptr, SelectAudioTrack, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"selectSubtitleTrack", nullptr, SelectSubtitleTrack, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"addExternalSubtitle", nullptr, AddExternalSubtitle, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setSubtitleDelay", nullptr, SetSubtitleDelay, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"getTracks", nullptr, GetTracks, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"stop", nullptr, Stop, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"release", nullptr, ReleasePlayer, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"getPlayerStatus", nullptr, GetPlayerStatus, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"getFrameData", nullptr, GetFrameData, nullptr, nullptr, nullptr, napi_default, nullptr},
    };
    napi_define_properties(env, exports, sizeof(descriptors) / sizeof(descriptors[0]), descriptors);

#if VIDALL_MPV_AVAILABLE
    // Register XComponent surface callbacks to obtain NativeWindow
    napi_value exportInstance = nullptr;
    OH_NativeXComponent* nativeXComponent = nullptr;
    // Use OH_NATIVE_XCOMPONENT_OBJ macro to obtain the native XComponent handle
    napi_get_named_property(env, exports, OH_NATIVE_XCOMPONENT_OBJ, &exportInstance);
    if (exportInstance != nullptr) {
        napi_unwrap(env, exportInstance, reinterpret_cast<void**>(&nativeXComponent));
    }
    if (nativeXComponent != nullptr) {
        static OH_NativeXComponent_Callback callback = {
            .OnSurfaceCreated = OnSurfaceCreated,
            .OnSurfaceChanged = OnSurfaceChanged,
            .OnSurfaceDestroyed = OnSurfaceDestroyed,
            .DispatchTouchEvent = DispatchTouchEvent,
        };
        int32_t ret = OH_NativeXComponent_RegisterCallback(nativeXComponent, &callback);
        MPV_LOG(LOG_INFO, "XComponent RegisterCallback: ret=%{public}d", ret);
    } else {
        MPV_LOG(LOG_WARN, "XComponent: nativeXComponent not found via OH_NATIVE_XCOMPONENT_OBJ");
    }
#endif

    return exports;
}

} // namespace

NAPI_MODULE(entry, Init)
