// 宿主只替换平台边界。注册、事件合并和播放器消费逻辑由测试从 mpv 原样编译。
#include <assert.h>
#include "host_recovery.h"
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdint.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
typedef void OH_AudioRenderer;
typedef void OH_AudioStreamBuilder;
typedef int OH_AudioStream_Result;
typedef int OH_AudioData_Callback_Result;
enum { AUDIO_DATA_CALLBACK_RESULT_VALID = 0 };
typedef int OH_AudioInterrupt_ForceType;
typedef int OH_AudioInterrupt_Hint;
typedef void (*OH_AudioRenderer_OnInterruptCallback)(OH_AudioRenderer *, void *, int, int);
enum { AO_EVENT_PAUSE = 4, AUDIOSTREAM_INTERRUPT_HINT_RESUME = 1,
       AUDIOSTREAM_INTERRUPT_HINT_PAUSE, AUDIOSTREAM_INTERRUPT_HINT_STOP };
typedef struct {
    int32_t (*OH_AudioRenderer_OnWriteData)(OH_AudioRenderer *, void *, void *, int32_t);
    int32_t (*OH_AudioRenderer_OnInterruptEvent)(OH_AudioRenderer *, void *, int, int);
} OH_AudioRenderer_Callbacks;
/* BINDING */
struct priv { bool timing_initialized; pthread_mutex_t timing_lock; pthread_cond_t timing_wakeup; unsigned long long recovery_token,recovery_generation; OH_AudioStreamBuilder *builder; OH_AudioRenderer *renderer; struct legacy_binding legacy; };
struct ao { struct priv *priv; atomic_uint events_; bool per_file;
            void (*wakeup_cb)(void *); void *wakeup_ctx; };
struct MPOpts { bool pause; int gapless_audio; };
typedef struct {
    void *each_frame;
    int last_frame_count;
} screenshot_ctx;
struct ao_chain { struct ao *ao; };
struct MPContext {
    struct ao_chain *ao_chain;
    screenshot_ctx *screenshot_ctx;
    int shown_vframes;
    bool paused, paused_for_cache, osd_force_update;
    int audio_status, osd_function;
    double time_frame;
    void *video_out;
    struct ao *ao;
    struct MPOpts *opts;
    void *mconfig, *encode_lavc_ctx, *vo_chain;
    int step_frames;
    bool hrseek_active;
};
static int sdk = 19, result, writes, wakes, backups, pauses, modern;
static OH_AudioRenderer_Callbacks callbacks;
static void *user;
static unsigned unloaded;
#define MP_TRACE(...) ((void)0)
enum { AUDIOSTREAM_SUCCESS, AUDIOSTREAM_ERROR_SYSTEM = 3 };
static void reset_timing(struct priv *p) {}
static void stop_timing_worker(struct priv *p) {(void)p;}
#define mp_mutex_destroy pthread_mutex_destroy
#define mp_cond_destroy pthread_cond_destroy
static int OH_AudioRenderer_Release(void *r) {return 0;}
static int OH_AudioStreamBuilder_Destroy(void *b) {return 0;}
#define MP_TIME_MS_TO_NS(v) ((v)*1000000LL)
static void mp_sleep_ns(long long ns) {assert(!"意外进入释放失败保留路径");}
static void uninit_audio_out(struct MPContext *ctx) { unloaded++; ctx->ao=NULL; }

static int OH_GetSdkApiVersion(void) { return sdk; }
static void *expected_write_ao;
static int audio_on_write_callback(OH_AudioRenderer *r, void *u, void *buf, int32_t len)
{ assert(u && len == 16); if (expected_write_ao) assert(u == expected_write_ao); writes++; return 0; }
static int OH_AudioStreamBuilder_SetRendererCallback(void *b, OH_AudioRenderer_Callbacks c, void *u)
{ callbacks = c; user = u; return result; }
static int (*modern_write_cb)(OH_AudioRenderer *, void *, void *, int32_t);
static void *shared_user;
static int OH_AudioStreamBuilder_SetRendererWriteDataCallback(void *b,
    int (*cb)(OH_AudioRenderer *, void *, void *, int32_t), void *u)
{ modern_write_cb = cb; shared_user = u; modern++; return result; }
static void (*modern_interrupt_cb)(OH_AudioRenderer *, void *, int, int);
static void *modern_user;
static int interrupt_result;
static int __attribute__((unused)) OH_AudioStreamBuilder_SetRendererInterruptCallback(void *b,
    void (*cb)(OH_AudioRenderer *, void *, int, int), void *u)
{ modern_interrupt_cb = cb; modern_user = u; shared_user = u; return interrupt_result; }
#define MP_ERR(ao, ...) ((void)(ao))
#define RTLD_DEFAULT ((void *)0)
#define RTLD_NOW 2
#define RTLD_LOCAL 0
static void *audio_library = (void *)0x1234;
static bool interrupt_symbol_available = true;
static bool default_symbol_visible = true, library_openable = true;
static unsigned library_opens, library_closes;
static void *__attribute__((unused)) dlopen(const char *name, int flags)
{ assert(sdk>=20 && !strcmp(name,"libohaudio.so") && flags==(RTLD_NOW|RTLD_LOCAL));
  library_opens++; return library_openable ? audio_library : NULL; }
static int __attribute__((unused)) dlclose(void *handle)
{ assert(handle==audio_library);library_closes++;return 0; }
static void *__attribute__((unused)) dlsym(void *handle, const char *name)
{ assert(sdk>=20 && (handle==RTLD_DEFAULT || handle==audio_library) && !strcmp(name,"OH_AudioStreamBuilder_SetRendererInterruptCallback"));
  return interrupt_symbol_available && (handle==audio_library || default_symbol_visible) ? (void *)OH_AudioStreamBuilder_SetRendererInterruptCallback : NULL; }
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed = PTHREAD_COND_INITIALIZER;
static bool block_wake, entered, retiring, released;
static void wake(void *u) {
    pthread_mutex_lock(&gate);
    wakes++;
    if (block_wake) {
        entered = true;
        pthread_cond_broadcast(&changed);
        while (block_wake) pthread_cond_wait(&changed, &gate);
    }
    pthread_mutex_unlock(&gate);
}
static void m_config_backup_opt(void *m, const char *key)
{ assert(!strcmp(key, "pause")); backups++; }
enum { MPSEEK_FRAMESTEP, MPSEEK_VERY_EXACT };
static void queue_seek(struct MPContext *ctx, int kind, int dir, int precision, int flags) {}
enum { STATUS_EOF = 4 };
static float gain, configured_gain = 0.75f;
static float audio_get_gain(struct MPContext *ctx) { return configured_gain; }
static void ao_set_gain(struct ao *ao, float value) { gain = value; }
static bool audio_paused, video_paused;
static void ao_set_paused(struct ao *ao, bool paused, bool eof) { audio_paused = paused; }
static void vo_set_paused(void *vo, bool paused) { video_paused = paused; }
static void mp_wakeup_core(struct MPContext *ctx) {}
static double get_relative_time(struct MPContext *ctx) { return 0; }
static void update_core_idle_state(struct MPContext *ctx) {}
static void m_config_notify_change_opt_ptr(void *config, bool *option) { pauses++; }

// 两轮空闲调度模拟慢写盘，第二轮结束时截图完成。
struct mp_waiter { int unused; };
#define MP_WAITER_INITIALIZER {0}
static unsigned screenshot_ticks, interrupt_tick;
static void *mp_cmd_clone(void *cmd) { return cmd; }
static void screenshot_fin(void *cmd) {}
static void run_command(struct MPContext *ctx, void *cmd, void *sender, void (*done)(void *), void *args) {}
static bool mp_waiter_poll(struct mp_waiter *wait) { return screenshot_ticks >= 2; }
static void mp_waiter_wait(struct mp_waiter *wait) { assert(screenshot_ticks == 2); }
void ao_request_pause(struct ao *ao);
static void mp_idle(struct MPContext *ctx) {
    screenshot_ticks++;
    if (screenshot_ticks == interrupt_tick)
        ao_request_pause(ctx->ao);
    if (screenshot_ticks > interrupt_tick)
        assert(ctx->opts->pause && audio_paused && video_paused);
}

/* PRODUCTION */

static void *interrupt_thread(void *token) {
    legacy_interrupt(NULL, token, 0, AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
    return NULL;
}
static void *release_thread(void *ao) {
    pthread_mutex_lock(&gate);
    retiring = true;
    pthread_cond_broadcast(&changed);
    pthread_mutex_unlock(&gate);
    uninit(ao);
    pthread_mutex_lock(&gate);
    released = true;
    pthread_mutex_unlock(&gate);
    return NULL;
}

int main(void)
{
    struct priv p = {.recovery_generation=mp_host_generation(),.recovery_token=mp_host_audio_begin(mp_host_generation())};
    struct ao old = {.priv=&p, .wakeup_cb=wake}, next = {.priv=&p, .wakeup_cb=wake};
    struct MPOpts opts = {0};
    struct MPContext ctx = {.ao=&old, .opts=&opts};
    assert(register_callbacks(&old) == 0 && old.per_file && !modern);
    callbacks.OH_AudioRenderer_OnWriteData(NULL, user, NULL, 16);
    assert(writes == 1);
    for (int hint = 0; hint <= 7; hint++) {
        if (hint == AUDIOSTREAM_INTERRUPT_HINT_PAUSE || hint == AUDIOSTREAM_INTERRUPT_HINT_STOP) continue;
        callbacks.OH_AudioRenderer_OnInterruptEvent(NULL, user, 0, hint);
    }
    assert(wakes == 0);
    for (int hint = AUDIOSTREAM_INTERRUPT_HINT_PAUSE; hint <= AUDIOSTREAM_INTERRUPT_HINT_STOP; hint++) {
        callbacks.OH_AudioRenderer_OnInterruptEvent(NULL, user, 0, hint);
        callbacks.OH_AudioRenderer_OnInterruptEvent(NULL, user, 1, hint);
        handle_audio_interrupt(&ctx);
        assert(opts.pause && backups == 1 && pauses == 1);
    }
    callbacks.OH_AudioRenderer_OnInterruptEvent(NULL, user, 1, AUDIOSTREAM_INTERRUPT_HINT_RESUME);
    handle_audio_interrupt(&ctx);
    assert(opts.pause && wakes == 2);
    // 用户恢复先于事件消费；之后到达的新 PAUSE 仍必须生效。
    callbacks.OH_AudioRenderer_OnInterruptEvent(NULL, user, 0, AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
    set_user_pause_option(&ctx, false);
    handle_audio_interrupt(&ctx);
    assert(!opts.pause && pauses == 2);
    callbacks.OH_AudioRenderer_OnInterruptEvent(NULL, user, 0, AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
    handle_audio_interrupt(&ctx);
    assert(opts.pause && pauses == 3);
    opts.pause = false;
    callbacks.OH_AudioRenderer_OnInterruptEvent(NULL, user, 0, AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
    opts.gapless_audio = 1;
    ctx.encode_lavc_ctx = &ctx; unload(&ctx); assert(ctx.ao == &old && !unloaded);
    ctx.encode_lavc_ctx = NULL; unload(&ctx); assert(!ctx.ao && unloaded == 1);
    void *retired = user;
    uninit(&old);
    ctx.ao = &next;
    handle_audio_interrupt(&ctx);
    ctx.ao = NULL;
    handle_audio_interrupt(&ctx);
    assert(!opts.pause && pauses == 3);
    assert(register_callbacks(&next) == 0);
    assert(user != retired);
    callbacks.OH_AudioRenderer_OnInterruptEvent(NULL, retired, 0, AUDIOSTREAM_INTERRUPT_HINT_STOP);
    char buf[16]; memset(buf, 1, sizeof(buf));
    callbacks.OH_AudioRenderer_OnWriteData(NULL, retired, buf, sizeof(buf));
    assert(!memcmp(buf, (char[16]){0}, sizeof(buf)) && writes == 1);
    assert(!atomic_load(&next.events_));
    // 同一个回调已进入 wake 时开始销毁；销毁完成后同一 token 再也不能命中新对象。
    block_wake = true;
    pthread_t interrupt, retire;
    assert(!pthread_create(&interrupt, NULL, interrupt_thread, user));
    pthread_mutex_lock(&gate);
    while (!entered) pthread_cond_wait(&changed, &gate);
    /* CALLBACK_LIFETIME_ASSERT */
    assert(!pthread_create(&retire, NULL, release_thread, &next));
    while (!retiring) pthread_cond_wait(&changed, &gate);
    assert(!released);
    block_wake = false;
    pthread_cond_broadcast(&changed);
    pthread_mutex_unlock(&gate);
    pthread_join(interrupt, NULL);
    pthread_join(retire, NULL);
    assert(released);
    unsigned previous_wakes = wakes;
    legacy_interrupt(NULL, user, 0, AUDIOSTREAM_INTERRUPT_HINT_STOP);
    assert(wakes == previous_wakes);
    next.per_file = false;
    ctx.ao = &next; unload(&ctx); assert(ctx.ao == &next && unloaded == 1);
    opts.gapless_audio = 0; unload(&ctx); assert(!ctx.ao && unloaded == 2);
    struct priv step_priv = {0};
    struct ao step = {.priv=&step_priv, .wakeup_cb=wake};
    ctx.ao = &step;
    ctx.vo_chain = &ctx;
    opts.pause = true;
    ao_request_pause(&step);
    add_step_frame(&ctx, 1, false);
    handle_audio_interrupt(&ctx);
    assert(!opts.pause && ctx.step_frames == 1);
    ao_request_pause(&step);
    handle_audio_interrupt(&ctx);
    assert(opts.pause && !ctx.step_frames);
    // 缓存保持内部暂停时，静音逐帧仍可排队。新的系统打断应取消它并恢复用户增益。
    struct ao_chain chain = {.ao = &step};
    ctx.ao_chain = &chain;
    ctx.paused_for_cache = true;
    update_internal_pause_state(&ctx);
    step_frame_mute(&ctx, true);
    add_step_frame(&ctx, 1, false);
    assert(ctx.paused && !opts.pause && ctx.step_frames == 1 && gain == 0);
    ao_request_pause(&step);
    update_internal_pause_state(&ctx);
    handle_audio_interrupt(&ctx);
    assert(opts.pause && !ctx.step_frames && gain == configured_gain);
    ctx.paused_for_cache = false;
    update_internal_pause_state(&ctx);
    assert(ctx.paused && !ctx.step_frames);
    set_user_pause_option(&ctx, false);
    assert(!ctx.paused && !ctx.step_frames && gain == configured_gain);
    // 长按逐帧可能只有临时静音而没有步数；取消时须尊重用户的音量或静音设置。
    for (int muted = 0; muted <= 1; muted++) {
        configured_gain = muted ? 0 : 0.5f;
        step_frame_mute(&ctx, true);
        set_pause_state(&ctx, false);
        assert(!ctx.step_frames && !gain);
        ao_request_pause(&step);
        handle_audio_interrupt(&ctx);
        assert(opts.pause && gain == configured_gain);
    }
    screenshot_ctx screenshot = {.each_frame = &ctx};
    ctx.screenshot_ctx = &screenshot;
    ctx.video_out = &ctx;
    // 分别在慢写盘中途、写盘完成的最后一次调度中打断。
    for (interrupt_tick = 1; interrupt_tick <= 2; interrupt_tick++) {
        ctx.shown_vframes++;
        screenshot_ticks = 0;
        set_pause_state(&ctx, false);
        assert(!audio_paused && !video_paused);
        handle_each_frame_screenshot(&ctx);
        assert(screenshot_ticks == 2 && audio_paused && video_paused);
    }
    set_pause_state(&ctx, false);
    assert(!audio_paused && !video_paused);
    // 写盘立即完成时，正常播放继续，已到达的打断仍先处理。
    ctx.shown_vframes++;
    handle_each_frame_screenshot(&ctx);
    assert(!audio_paused && !video_paused);
    ao_request_pause(&step);
    ctx.shown_vframes++;
    handle_each_frame_screenshot(&ctx);
    assert(audio_paused && video_paused);
    const int modern_sdks[] = {20,24,26};
    for (unsigned i = 0; i < sizeof(modern_sdks)/sizeof(modern_sdks[0]); i++) {
        sdk = modern_sdks[i];
        modern_interrupt_cb = NULL; modern_user = NULL; modern = 0;
        next.per_file = false; atomic_store(&next.events_,0); ctx.ao = &next;
        set_user_pause_option(&ctx,false);
        assert(register_callbacks(&next) == 0 && modern == 1 && next.per_file);
        assert(modern_interrupt_cb && modern_user && "现代分支必须注册真实中断回调");
        void *token = modern_user;
        char modern_buffer[16]; memset(modern_buffer, 0x7f, sizeof(modern_buffer));
        expected_write_ao = &next; int before_write = writes;
        assert(modern_write_cb(NULL,shared_user,modern_buffer,16) == AUDIO_DATA_CALLBACK_RESULT_VALID);
        assert(writes == before_write + 1); expected_write_ao = NULL;
        modern_interrupt_cb(NULL,token,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
        handle_audio_interrupt(&ctx); assert(opts.pause && audio_paused && video_paused);
        modern_interrupt_cb(NULL,token,0,AUDIOSTREAM_INTERRUPT_HINT_RESUME);
        handle_audio_interrupt(&ctx); assert(opts.pause);
        set_user_pause_option(&ctx,false);assert(!opts.pause && !audio_paused);
        uninit(&next);assert(legacy_bindings == NULL);
        assert(register_callbacks(&next) == 0 && modern_user != token);
        before_write = writes; modern_write_cb(NULL,token,modern_buffer,16);
        assert(writes == before_write);
        for (unsigned j = 0; j < sizeof(modern_buffer); j++) assert(modern_buffer[j] == 0);
        modern_interrupt_cb(NULL,token,0,AUDIOSTREAM_INTERRUPT_HINT_STOP);
        handle_audio_interrupt(&ctx);assert(!opts.pause);
        uninit(&next);
        // 系统库以局部可见方式加载时，RTLD_DEFAULT 不一定能查到公开符号。
        default_symbol_visible = false;
        unsigned old_opens=library_opens, old_closes=library_closes;
        assert(register_callbacks(&next)==0);
        assert(library_opens==old_opens+1 && library_closes==old_closes+1);
        modern_interrupt_cb(NULL,modern_user,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
        handle_audio_interrupt(&ctx);assert(opts.pause);
        uninit(&next);set_user_pause_option(&ctx,false);
        library_openable=false;
        assert(register_callbacks(&next)==AUDIOSTREAM_ERROR_SYSTEM);
        assert(library_closes==old_closes+1);
        uninit(&next);library_openable=true;default_symbol_visible=true;
        result = -1; modern_interrupt_cb = NULL;
        assert(register_callbacks(&next) == result && !modern_interrupt_cb);
        uninit(&next);assert(legacy_bindings == NULL);result = 0;
        interrupt_symbol_available = false;
        old_opens=library_opens;old_closes=library_closes;
        assert(register_callbacks(&next) == AUDIOSTREAM_ERROR_SYSTEM);
        assert(library_opens==old_opens+1 && library_closes==old_closes+1);
        uninit(&next);assert(legacy_bindings == NULL);interrupt_symbol_available = true;
        interrupt_result = -2;default_symbol_visible=false;
        old_opens=library_opens;old_closes=library_closes;
        assert(register_callbacks(&next) == interrupt_result);
        assert(library_opens==old_opens+1 && library_closes==old_closes+1);
        uninit(&next);assert(legacy_bindings == NULL);interrupt_result = 0;default_symbol_visible=true;
    }
    result = -1;
    sdk = 15;
    assert(register_callbacks(&old) == result);
    uninit(&old);
    assert(legacy_bindings == NULL);
    result=0;assert(register_callbacks(&old)==0);
    mp_host_retire_all();previous_wakes=wakes;
    callbacks.OH_AudioRenderer_OnInterruptEvent(NULL,user,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
    assert(wakes==previous_wakes);uninit(&old);assert(legacy_bindings==NULL);
    sdk=24;assert(register_callbacks(&old)==0);previous_wakes=wakes;
    modern_interrupt_cb(NULL,modern_user,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
    assert(wakes==previous_wakes);uninit(&old);assert(legacy_bindings==NULL);
}
