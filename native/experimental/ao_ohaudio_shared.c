/* S37显式实验AO；尚未满足全部设备门槛，不替换生产ohaudio。 */
#include "ao.h"
#include "audio/format.h"
#include "audio_output_adapter.h"
#include "common/global.h"
#include "common/host_recovery.h"
#include "common/msg.h"
#include "internal.h"
#include "options/m_option.h"
#include <deviceinfo.h>
#include <dlfcn.h>
#include <hilog/log.h>
#include <ohaudio/native_audiorenderer.h>
#include <ohaudio/native_audiostreambuilder.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#define TRACE(fmt, ...) OH_LOG_Print(LOG_APP, LOG_INFO, 0xD001, "VPA", fmt, ##__VA_ARGS__)
struct platform {
    OH_AudioStreamBuilder *builder;
    OH_AudioRenderer *renderer;
    unsigned id;
};
struct priv {
    struct vpa_output *output;
    uint64_t token;
    bool pause_notified, failed_notified;
    int encoding_type;
};
static atomic_uint platform_ids, stop_calls, release_calls, clear_calls;
static atomic_bool inject_release;
// 有界的进程生命周期引用，确保迟到回调及挂起控制线程不会执行已卸载代码。
static pthread_once_t pin_once = PTHREAD_ONCE_INIT;
static void *core_pin;
static void pin_core(void) {
    Dl_info origin = {0};
    if (dladdr((void *)vpa_configure, &origin) && origin.dli_fname)
        core_pin = dlopen(origin.dli_fname, RTLD_NOW | RTLD_LOCAL);
}
void mp_audio_probe_arm(unsigned long long session, unsigned long long gen) {
    (void)session;
    (void)gen;
    atomic_store(&inject_release, true);
}
static int64_t now_ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}
static int32_t write_legacy(OH_AudioRenderer *r, void *user, void *data, int32_t bytes) {
    (void)r;
    vpa_callback(user, data, bytes);
    return 0;
}
static OH_AudioData_Callback_Result write_modern(OH_AudioRenderer *r, void *u, void *d, int32_t n) {
    write_legacy(r, u, d, n);
    return AUDIO_DATA_CALLBACK_RESULT_VALID;
}
static int32_t interrupt_legacy(OH_AudioRenderer *r, void *u, OH_AudioInterrupt_ForceType force,
                                OH_AudioInterrupt_Hint hint) {
    (void)r;
    (void)force;
    if (hint == AUDIOSTREAM_INTERRUPT_HINT_PAUSE || hint == AUDIOSTREAM_INTERRUPT_HINT_STOP)
        vpa_interrupt(u, true);
    return 0;
}
static void interrupt_modern(OH_AudioRenderer *r, void *u, OH_AudioInterrupt_ForceType f,
                             OH_AudioInterrupt_Hint h) {
    interrupt_legacy(r, u, f, h);
}
static int create_platform(void **out, const struct vpa_format *f, struct vpa_output *o) {
    struct platform *p = calloc(1, sizeof(*p));
    if (!p)
        return -1;
    *out = p;
    p->id = atomic_fetch_add(&platform_ids, 1) + 1;
    int rc = OH_AudioStreamBuilder_Create(&p->builder, AUDIOSTREAM_TYPE_RENDERER);
    if (rc)
        return rc;
#define SET(call)                                                                                  \
    do {                                                                                           \
        rc = (call);                                                                               \
        if (rc)                                                                                    \
            return rc;                                                                             \
    } while (0)
    SET(OH_AudioStreamBuilder_SetSamplingRate(p->builder, f->rate));
    SET(OH_AudioStreamBuilder_SetChannelCount(p->builder, f->channels));
    SET(OH_AudioStreamBuilder_SetSampleFormat(p->builder, f->format));
    SET(OH_AudioStreamBuilder_SetEncodingType(p->builder, AUDIOSTREAM_ENCODING_TYPE_RAW));
    SET(OH_AudioStreamBuilder_SetRendererInfo(p->builder, AUDIOSTREAM_USAGE_MOVIE));
    // 仅实验：队列2个20ms周期，拒绝不支持的粒度，不能静默截断原4458帧回调。
    SET(OH_AudioStreamBuilder_SetFrameSizeInCallback(p->builder, f->rate / 50));
    if (OH_GetSdkApiVersion() >= 20) {
        void *h = dlopen("libohaudio.so", RTLD_NOW | RTLD_LOCAL);
        if (!h)
            return -1;
        typedef OH_AudioStream_Result (*set_write)(OH_AudioStreamBuilder *,
                                                   OH_AudioRenderer_OnWriteDataCallback, void *);
        typedef OH_AudioStream_Result (*set_interrupt)(
            OH_AudioStreamBuilder *, OH_AudioRenderer_OnInterruptCallback, void *);
        set_write w = (set_write)dlsym(h, "OH_AudioStreamBuilder_SetRendererWriteDataCallback");
        set_interrupt i =
            (set_interrupt)dlsym(h, "OH_AudioStreamBuilder_SetRendererInterruptCallback");
        rc = w && i ? w(p->builder, write_modern, o) : -1;
        if (!rc)
            rc = i(p->builder, interrupt_modern, o);
        dlclose(h);
        if (rc)
            return rc;
    } else {
        OH_AudioRenderer_Callbacks cb = {.OH_AudioRenderer_OnWriteData = write_legacy,
                                         .OH_AudioRenderer_OnInterruptEvent = interrupt_legacy};
        SET(OH_AudioStreamBuilder_SetRendererCallback(p->builder, cb, o));
    }
    SET(OH_AudioStreamBuilder_GenerateRenderer(p->builder, &p->renderer));
    int32_t frames = 0;
    SET(OH_AudioRenderer_GetFrameSizeInCallback(p->renderer, &frames));
    if (frames <= 0 || frames > 2 * (f->rate / 50))
        return -1;
    TRACE("CREATE id=%{public}u frames=%{public}d rate=%{public}d", p->id, frames, f->rate);
    return 0;
#undef SET
}
static int platform_start(void *v) {
    struct platform *p = v;
    OH_AudioStream_State state;
    int rc = OH_AudioRenderer_GetCurrentState(p->renderer, &state);
    if (!rc && state != AUDIOSTREAM_STATE_RUNNING)
        rc = OH_AudioRenderer_Start(p->renderer);
    TRACE("START id=%{public}u rc=%{public}d", p->id, rc);
    return rc;
}
static int platform_pause(void *v) {
    struct platform *p = v;
    OH_AudioStream_State state;
    int rc = OH_AudioRenderer_GetCurrentState(p->renderer, &state);
    if (!rc && state == AUDIOSTREAM_STATE_RUNNING)
        rc = OH_AudioRenderer_Pause(p->renderer);
    TRACE("PAUSE id=%{public}u rc=%{public}d", p->id, rc);
    return rc;
}
static int platform_stop(void *v) {
    struct platform *p = v;
    OH_AudioStream_State state;
    int rc = OH_AudioRenderer_GetCurrentState(p->renderer, &state);
    unsigned n = atomic_fetch_add(&stop_calls, 1) + 1;
    TRACE("STOP_ENTER id=%{public}u count=%{public}u", p->id, n);
    if (!rc && state != AUDIOSTREAM_STATE_STOPPED)
        rc = OH_AudioRenderer_Stop(p->renderer);
    TRACE("STOP_RETURN id=%{public}u rc=%{public}d", p->id, rc);
    return rc;
}
static int platform_flush(void *v) {
    struct platform *p = v;
    int rc = OH_AudioRenderer_Flush(p->renderer);
    TRACE("FLUSH id=%{public}u rc=%{public}d", p->id, rc);
    return rc;
}
static int platform_stopped(void *v) {
    struct platform *p = v;
    OH_AudioStream_State state = AUDIOSTREAM_STATE_INVALID;
    int rc = OH_AudioRenderer_GetCurrentState(p->renderer, &state);
    TRACE("QUIET id=%{public}u state=%{public}d rc=%{public}d", p->id, state, rc);
    return !rc && state == AUDIOSTREAM_STATE_STOPPED ? 0 : -1;
}
static int platform_release(void *v) {
    struct platform *p = v;
    unsigned n = atomic_fetch_add(&release_calls, 1) + 1;
    TRACE("RELEASE_ENTER id=%{public}u count=%{public}u", p->id, n);
    if (atomic_exchange(&inject_release, false)) {
        TRACE("RELEASE_INJECT_HOLD id=%{public}u count=%{public}u", p->id, n);
        for (;;)
            usleep(100000);
    }
    int rc = 0;
    if (p->renderer)
        rc = OH_AudioRenderer_Release(p->renderer);
    if (rc)
        return rc;
    if (p->builder)
        rc = OH_AudioStreamBuilder_Destroy(p->builder);
    if (rc)
        return rc;
    TRACE("RELEASE_RETURN id=%{public}u", p->id);
    free(p);
    return 0;
}
static int platform_clock(void *v, int64_t *pos, int64_t *stamp) {
    struct platform *p = v;
    return OH_AudioRenderer_GetAudioTimestampInfo(p->renderer, pos, stamp);
}
static int no_release(void *v) {
    (void)v;
    return 0;
}
static void cleared(uint64_t token) {
    bool ok = mp_host_audio_remove(token, no_release, NULL);
    TRACE("LEASE_CLEAR token=%{public}llu ok=%{public}d count=%{public}u",
          (unsigned long long)token, ok, atomic_fetch_add(&clear_calls, 1) + 1);
    if (atomic_load(&inject_release))
        vpa_shutdown_idle();
}
static bool retired(uint64_t gen) { return mp_host_is_retired(gen); }
static const struct vpa_ops ops = {create_platform,  platform_start, platform_pause,
                                   platform_stop,    platform_flush, platform_stopped,
                                   platform_release, platform_clock, retired,
                                   cleared,          now_ns};
static int stop_lease(void *opaque) {
    vpa_detach_token((uintptr_t)opaque);
    return -1;
}
static void uninit(struct ao *ao) {
    struct priv *p = ao->priv;
    if (!p->token)
        return;
    vpa_detach_token(p->token);
    if (!vpa_owns_token(p->token))
        mp_host_audio_remove(p->token, no_release, NULL);
    MP_WARN(ao, "VPA_AO_DETACH token=%llu pending=%u\n", (unsigned long long)p->token,
            mp_host_audio_pending());
    p->output = NULL;
    p->token = 0;
}
static int init(struct ao *ao) {
    struct priv *p = ao->priv;
    if (p->encoding_type != AUDIOSTREAM_ENCODING_TYPE_RAW)
        return -1;
    // 不降混、不换采样率；mpv负责转换样本类型，U8在实验路径明确转S16。
    ao->format = af_fmt_is_int(ao->format)
                     ? (af_fmt_to_bytes(ao->format) > 2 ? AF_FORMAT_S32 : AF_FORMAT_S16)
                     : AF_FORMAT_FLOAT;
    struct vpa_format f = {.rate = ao->samplerate,
                           .channels = ao->channels.num,
                           .stride = af_fmt_to_bytes(ao->format) * ao->channels.num,
                           .format =
                               ao->format == AF_FORMAT_FLOAT
                                   ? AUDIOSTREAM_SAMPLE_F32LE
                                   : (ao->format == AF_FORMAT_S32 ? AUDIOSTREAM_SAMPLE_S32LE
                                                                  : AUDIOSTREAM_SAMPLE_S16LE)};
    // 完整有序布局指纹，避免仅按声道数复用。
    f.layout = 1469598103934665603ULL;
    for (int i = 0; i < ao->channels.num; i++)
        f.layout = (f.layout ^ (unsigned)ao->channels.speaker[i]) * 1099511628211ULL;
    pthread_once(&pin_once, pin_core);
    if (!core_pin)
        return -1;
    vpa_configure(&ops);
    p->token = mp_host_audio_begin(ao->global->host_generation);
    if (!p->token)
        return -1;
    p->output = vpa_acquire(p->token, ao->global->host_generation, &f, 800);
    if (!p->output || !mp_host_audio_publish(p->token, stop_lease, (void *)(uintptr_t)p->token)) {
        uninit(ao);
        return -1;
    }
    ao->per_file = true;
    ao->device_buffer = (f.rate / 50) * 2;
    MP_WARN(ao, "VPA_AO_BIND token=%llu generation=%llu output=%p\n", (unsigned long long)p->token,
            ao->global->host_generation, p->output);
    return 0;
}
static bool audio_write(struct ao *ao, void **data, int n) {
    struct priv *p = ao->priv;
    return vpa_write(p->output, p->token, data[0], n);
}
static void start(struct ao *ao) {
    struct priv *p = ao->priv;
    vpa_start(p->output, p->token);
}
static bool set_pause(struct ao *ao, bool paused) {
    struct priv *p = ao->priv;
    if (!paused)
        p->pause_notified = false;
    return vpa_pause(p->output, p->token, paused);
}
static void reset(struct ao *ao) {
    struct priv *p = ao->priv;
    vpa_reset(p->output, p->token);
}
static void get_state(struct ao *ao, struct mp_pcm_state *s) {
    struct priv *p = ao->priv;
    struct vpa_snapshot snap;
    vpa_snapshot(p->output, p->token, &snap);
    *s = (struct mp_pcm_state){.free_samples = snap.free_frames,
                               .queued_samples = snap.queued_frames,
                               .delay = snap.delay,
                               .playing = snap.playing};
    if (snap.pause_requested && !p->pause_notified) {
        p->pause_notified = true;
        ao_request_pause(ao);
    }
    if (snap.failed && !p->failed_notified) {
        p->failed_notified = true;
        MP_ERR(ao, "VPA_OUTPUT_FAILED token=%llu\n", (unsigned long long)p->token);
        ao_request_pause(ao);
    }
}
#define OPT_BASE_STRUCT struct priv
const struct ao_driver audio_out_ohaudio = {
    .description = "实验独立OHAudio输出",
    .name = "ohaudio",
    .init = init,
    .uninit = uninit,
    .write = audio_write,
    .get_state = get_state,
    .start = start,
    .reset = reset,
    .set_pause = set_pause,
    .priv_size = sizeof(struct priv),
    .priv_defaults = &(const struct priv){.encoding_type = AUDIOSTREAM_ENCODING_TYPE_RAW},
    .options =
        (const struct m_option[]){{"encoding_type", OPT_INT(encoding_type), M_RANGE(0, 2)}, {0}},
    .options_prefix = "ohaudio"};
