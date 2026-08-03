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

    bool Initialize()
    {
        if (!player_) return false;
        mpv_set_option_string(player_.get(), "terminal", "no");
        mpv_set_option_string(player_.get(), "config", "no");
        mpv_set_option_string(player_.get(), "vo", "libmpv");
        if (mpv_initialize(player_.get()) < 0) return false;
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

    NativeResult Load(const std::string& uri, std::uint64_t handle)
    {
        std::lock_guard<std::mutex> lock(lifecycleMutex_);
        if (released_) return {false, handle, "RELEASED"};
        if (!rendererReady_) return {false, handle, "SURFACE_UNAVAILABLE"};
        if (uri.empty()) return {false, handle, "INPUT_INVALID"};
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
        while (!stopEvents_) {
            mpv_event* event = mpv_wait_event(player, 0.1);
            if (event->event_id == MPV_EVENT_SHUTDOWN) break;
            if (event->event_id == MPV_EVENT_END_FILE) {
                const auto* end = static_cast<mpv_event_end_file*>(event->data);
                if (end != nullptr && end->reason == MPV_END_FILE_REASON_ERROR) Dispatch("error", "libmpv playback failed");
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

napi_value CreateSession(napi_env env, napi_callback_info)
{
#if VIDALL_MPV_AVAILABLE
    auto session = std::make_shared<NativeSession>();
    if (!session->Initialize()) return CreateResult(env, {false, 0, "NATIVE_PLAYBACK_FAILED"});
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
    napi_value args[2] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0; std::string uri;
    if (!GetArguments(env, info, 2, args, argc) || argc != 2 || !ReadHandle(env, args[0], handle) || !ReadString(env, args[1], uri)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle); return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : session->Load(uri, handle));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}

napi_value Control(napi_env env, napi_callback_info info, bool play)
{
    napi_value args[1] = {nullptr}; size_t argc = 0; std::uint64_t handle = 0;
    if (!GetArguments(env, info, 1, args, argc) || argc != 1 || !ReadHandle(env, args[0], handle)) return nullptr;
#if VIDALL_MPV_AVAILABLE
    std::shared_ptr<NativeSession> session = FindSession(handle); return CreateResult(env, session == nullptr ? NativeResult{false, handle, "RELEASED"} : (play ? session->Play(handle) : session->Stop(handle)));
#else
    return CreateResult(env, {false, handle, "FEATURE_UNSUPPORTED"});
#endif
}
napi_value Play(napi_env env, napi_callback_info info) { return Control(env, info, true); }
napi_value Stop(napi_env env, napi_callback_info info) { return Control(env, info, false); }

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
        {"stop", nullptr, Stop, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setEventCallback", nullptr, SetEventCallback, nullptr, nullptr, nullptr, napi_default, nullptr},
    };
    if (!Check(env, napi_define_properties(env, exports, sizeof(descriptors) / sizeof(descriptors[0]), descriptors), "Failed to define native bridge exports.") ||
        !Check(env, napi_add_env_cleanup_hook(env, CleanupSessions, nullptr), "Failed to register cleanup hook.")) return nullptr;
    return exports;
}
} // namespace

NAPI_MODULE(vidall_player_native, Init)
