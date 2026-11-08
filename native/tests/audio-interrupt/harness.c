// 宿主只替换平台边界。注册、事件合并和播放器消费逻辑由测试从 mpv 原样编译。
#include <assert.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdint.h>
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
struct priv { OH_AudioStreamBuilder *builder; };
struct ao { struct priv *priv; atomic_uint events_; bool per_file;
            void (*wakeup_cb)(void *); void *wakeup_ctx; };
struct MPOpts { bool pause; };
struct MPContext { struct ao *ao; struct MPOpts *opts; void *mconfig; };
static int sdk = 19, result, writes, wakes, backups, pauses, modern;
static OH_AudioRenderer_Callbacks callbacks;
static void *user;
static int OH_GetSdkApiVersion(void) { return sdk; }
static int audio_on_write_callback(OH_AudioRenderer *r, void *u, void *buf, int32_t len)
{ assert(u == user && len == 16); writes++; return 0; }
static int OH_AudioStreamBuilder_SetRendererCallback(void *b, OH_AudioRenderer_Callbacks c, void *u)
{ callbacks = c; user = u; return result; }
static int OH_AudioStreamBuilder_SetRendererWriteDataCallback(void *b,
    int (*cb)(OH_AudioRenderer *, void *, void *, int32_t), void *u)
{ assert(cb == audio_on_write_callback); modern++; return result; }
static void wake(void *u) { wakes++; }
static void m_config_backup_opt(void *m, const char *key)
{ assert(!strcmp(key, "pause")); backups++; }
static void set_pause_state(struct MPContext *ctx, bool value)
{ ctx->opts->pause = value; pauses++; }

/* PRODUCTION */

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
    opts.pause = false;
    callbacks.OH_AudioRenderer_OnInterruptEvent(NULL, user, 0, AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
    ctx.ao = &next;
    handle_audio_interrupt(&ctx);
    ctx.ao = NULL;
    handle_audio_interrupt(&ctx);
    assert(!opts.pause && pauses == 1);
    sdk = 20;
    assert(register_callbacks(&next) == 0 && modern == 1 && !next.per_file);
    result = -1;
    assert(register_callbacks(&next) == result);
    sdk = 15;
    assert(register_callbacks(&old) == result);
}
