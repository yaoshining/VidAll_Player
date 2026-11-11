#include "host_recovery.h"
#include <pthread.h>
#include <stdatomic.h>
#include <limits.h>

#define AUDIO_SLOTS 16
// FAILED 仍占用资源，不自动重试未知状态的平台停止。
enum audio_state { EMPTY, BUILDING, ACTIVE, STOPPING, STOPPED, FAILED };
struct audio_slot {
    pthread_mutex_t control;
    unsigned long long token, generation;
    enum audio_state state;
    bool quiescent;
    int (*stop)(void *);
    void *opaque;
};
static struct audio_slot slots[AUDIO_SLOTS];
static pthread_once_t initialized = PTHREAD_ONCE_INIT;
static pthread_mutex_t registry = PTHREAD_MUTEX_INITIALIZER;
static atomic_ullong generation = 1;
static unsigned long long serial;
static void initialize(void) {
    for (unsigned i = 0; i < AUDIO_SLOTS; ++i)
        pthread_mutex_init(&slots[i].control, NULL);
}
static struct audio_slot *slot_for(unsigned long long token) {
    unsigned index = token & 255;
    if (!token || !index || index > AUDIO_SLOTS) return NULL;
    pthread_once(&initialized, initialize);
    return &slots[index - 1];
}
unsigned long long mp_host_generation(void) { return atomic_load(&generation); }
bool mp_host_is_retired(unsigned long long born) { return born != mp_host_generation(); }
void mp_host_retire_all(void) {
    pthread_mutex_lock(&registry);
    // OHCodec 进程终局只发生一次；迟到终局不能退休已创建的兼容代。
    atomic_store(&generation, 2);
    pthread_mutex_unlock(&registry);
}
unsigned long long mp_host_audio_begin(unsigned long long born) {
    pthread_once(&initialized, initialize);
    pthread_mutex_lock(&registry);
    unsigned long long token = 0;
    if (!mp_host_is_retired(born) && serial < (ULLONG_MAX >> 8)) {
        for (unsigned i = 0; i < AUDIO_SLOTS; ++i) {
            struct audio_slot *s = &slots[i];
            // 不等待另一槽内的平台调用；remove/control 的锁顺序与这里不会互锁。
            if (s->state != EMPTY || pthread_mutex_trylock(&s->control)) continue;
            token = (++serial << 8) | (i + 1);
            s->token = token; s->generation = born; s->state = BUILDING;
            s->quiescent = false;
            s->stop = NULL; s->opaque = NULL;
            pthread_mutex_unlock(&s->control);
            break;
        }
    }
    pthread_mutex_unlock(&registry);
    return token;
}
bool mp_host_audio_publish(unsigned long long token, int (*stop)(void *), void *opaque) {
    struct audio_slot *s = slot_for(token);
    if (!s || !stop) return false;
    pthread_mutex_lock(&s->control);
    pthread_mutex_lock(&registry);
    bool ok = s->token == token && s->state == BUILDING;
    if (ok) { s->stop = stop; s->opaque = opaque; s->state = ACTIVE; }
    pthread_mutex_unlock(&registry);
    pthread_mutex_unlock(&s->control);
    return ok;
}
bool mp_host_audio_control_lock(unsigned long long token) {
    struct audio_slot *s = slot_for(token);
    if (!s) return false;
    pthread_mutex_lock(&s->control);
    pthread_mutex_lock(&registry);
    bool ok = s->token == token && s->state == ACTIVE && !mp_host_is_retired(s->generation);
    pthread_mutex_unlock(&registry);
    if (!ok) pthread_mutex_unlock(&s->control);
    return ok;
}
void mp_host_audio_control_unlock(unsigned long long token) {
    struct audio_slot *s = slot_for(token);
    // 仅匹配成功的 control_lock 调用此函数，期间槽不能被复用。
    if (s) pthread_mutex_unlock(&s->control);
}
bool mp_host_audio_remove(unsigned long long token, int (*release)(void *), void *opaque) {
    struct audio_slot *s = slot_for(token);
    if (!s || !release) return false;
    pthread_mutex_lock(&s->control);
    pthread_mutex_lock(&registry);
    bool ok = s->token == token && s->state != EMPTY;
    pthread_mutex_unlock(&registry);
    if (ok) {
        // 平台释放结束前保持占用；平台阻塞只影响本槽。
        int result = release(opaque);
        pthread_mutex_lock(&registry);
        if (result == 0) {
            s->state = EMPTY; s->token = 0; s->stop = NULL; s->opaque = NULL;
        } else {
            s->state = FAILED;
            ok = false;
        }
        pthread_mutex_unlock(&registry);
    }
    pthread_mutex_unlock(&s->control);
    return ok;
}
void mp_host_audio_confirm_quiescent(unsigned long long token) {
    struct audio_slot *s = slot_for(token);
    if (!s) return;
    // 调用方已持有 control；不能重入该锁，也不能将事实发布当作资源归还。
    pthread_mutex_lock(&registry);
    if (s->token == token && s->state != EMPTY) s->quiescent = true;
    pthread_mutex_unlock(&registry);
}
unsigned mp_host_audio_pending(void) {
    pthread_mutex_lock(&registry);
    unsigned pending = 0;
    for (unsigned i = 0; i < AUDIO_SLOTS; ++i) {
        struct audio_slot *s = &slots[i];
        if (s->state != EMPTY && !s->quiescent && mp_host_is_retired(s->generation)) ++pending;
    }
    pthread_mutex_unlock(&registry);
    return pending;
}
void mp_host_stop_retired_audio(void) {
    pthread_once(&initialized, initialize);
    for (unsigned i = 0; i < AUDIO_SLOTS; ++i) {
        struct audio_slot *s = &slots[i];
        pthread_mutex_lock(&registry);
        unsigned long long token = 0;
        // 正在清理的槽可在 renderer 释放后发布静止事实；扫描不能等其 Builder 清理锁。
        // trylock 失败时保持原状态，由有限的下一轮扫描再尝试。
        if (s->state == ACTIVE && !s->quiescent && mp_host_is_retired(s->generation) &&
            !pthread_mutex_trylock(&s->control)) {
            token = s->token; s->state = STOPPING;
        }
        pthread_mutex_unlock(&registry);
        if (!token) continue;
        pthread_mutex_lock(&registry);
        bool valid = s->token == token && s->state == STOPPING;
        pthread_mutex_unlock(&registry);
        if (valid) {
            int result = s->stop(s->opaque);
            pthread_mutex_lock(&registry);
            s->state = result == 0 ? STOPPED : FAILED;
            if (result == 0) s->quiescent = true;
            pthread_mutex_unlock(&registry);
        }
        pthread_mutex_unlock(&s->control);
    }
}

#include "host_recovery_api.h"
uint32_t mpv_host_recovery_api_version(void) { return MPV_HOST_RECOVERY_ABI_VERSION; }
uint64_t mpv_host_recovery_generation(void) { return mp_host_generation(); }
unsigned mpv_host_recovery_audio_pending(void) { return mp_host_audio_pending(); }
void mpv_host_recovery_stop_audio(void) { mp_host_stop_retired_audio(); }
