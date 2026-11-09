// 宿主只替换平台边界。注册、事件合并和播放器消费逻辑由测试从 mpv 原样编译。
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdint.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
typedef void OH_AudioRenderer;
typedef void OH_AudioStreamBuilder;
typedef int OH_AudioStream_Result;
typedef int OH_AudioInterrupt_ForceType;
typedef int OH_AudioInterrupt_Hint;
enum { AO_EVENT_PAUSE = 4, AUDIOSTREAM_INTERRUPT_HINT_RESUME = 1,
       AUDIOSTREAM_INTERRUPT_HINT_PAUSE, AUDIOSTREAM_INTERRUPT_HINT_STOP };
typedef struct {
    int32_t (*OH_AudioRenderer_OnWriteData)(OH_AudioRenderer *, void *, void *, int32_t);
    int32_t (*OH_AudioRenderer_OnInterruptEvent)(OH_AudioRenderer *, void *, int, int);
} OH_AudioRenderer_Callbacks;
/* BINDING */
struct priv { OH_AudioStreamBuilder *builder; OH_AudioRenderer *renderer; struct legacy_binding legacy; };
struct ao { struct priv *priv; atomic_uint events_; bool per_file;
            void (*wakeup_cb)(void *); void *wakeup_ctx; };
struct MPOpts { bool pause; int gapless_audio; };
struct MPContext { struct ao *ao; struct MPOpts *opts; void *mconfig; void *encode_lavc_ctx; void *vo_chain; int step_frames; bool hrseek_active; };
static int sdk = 19, result, writes, wakes, backups, pauses, modern;
static OH_AudioRenderer_Callbacks callbacks;
static void *user;
static unsigned unloaded;
#define MP_TRACE(...) ((void)0)
enum { AUDIOSTREAM_SUCCESS, AUDIOSTREAM_ERROR_SYSTEM = 3 };
static void reset_timing(struct priv *p) {}
static int OH_AudioRenderer_GetUnderflowCount(void *r, uint32_t *n) { *n=0; return 0; }
static void OH_AudioRenderer_Release(void *r) {}
static void OH_AudioStreamBuilder_Destroy(void *b) {}
static void uninit_audio_out(struct MPContext *ctx) { unloaded++; ctx->ao=NULL; }

static int OH_GetSdkApiVersion(void) { return sdk; }
static int audio_on_write_callback(OH_AudioRenderer *r, void *u, void *buf, int32_t len)
{ assert(u && len == 16); writes++; return 0; }
static int OH_AudioStreamBuilder_SetRendererCallback(void *b, OH_AudioRenderer_Callbacks c, void *u)
{ callbacks = c; user = u; return result; }
static int OH_AudioStreamBuilder_SetRendererWriteDataCallback(void *b,
    int (*cb)(OH_AudioRenderer *, void *, void *, int32_t), void *u)
{ assert(cb == audio_on_write_callback); modern++; return result; }
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
static void update_internal_pause_state(struct MPContext *ctx)
{ if (ctx->opts->pause) ctx->step_frames = 0; pauses++; }

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
    struct priv p = {0};
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
    assert(pthread_rwlock_trywrlock(&legacy_lock) == EBUSY);
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
    sdk = 20;
    assert(register_callbacks(&next) == 0 && modern == 1 && !next.per_file);
    result = -1;
    assert(register_callbacks(&next) == result);
    sdk = 15;
    assert(register_callbacks(&old) == result);
    uninit(&old);
    assert(legacy_bindings == NULL);
}
