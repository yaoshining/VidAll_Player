// S37实验：控制线程与回调仅持有独立输出，不持有mpv/AO指针。
#include "audio_output_adapter.h"
#include <limits.h>
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#define OUTPUTS 2
#define FRAMES 8192
#define STRIDE 64
enum phase { EMPTY, OPENING, READY, RUNNING, PAUSED, CLEARING, BROKEN, DESTROYING };
enum command { NONE, START, PAUSE, RESET, DETACH, DESTROY };
struct vpa_output {
    pthread_mutex_t lock;
    pthread_t worker;
    enum phase phase;
    enum command command;
    uint64_t token, generation, revision;
    bool focus, clean, has_started, restart_after_clear;
    struct vpa_format format;
    void *platform;
    unsigned char pcm[FRAMES * STRIDE];
    int head, queued, capacity;
    atomic_llong submitted;
    atomic_int callback_stride;
    int64_t audio_end, position, timestamp, query_at;
    bool clock_valid;
};
static struct vpa_output outputs[OUTPUTS];
static struct vpa_ops ops;
static pthread_once_t once = PTHREAD_ONCE_INIT;
static pthread_mutex_t pool = PTHREAD_MUTEX_INITIALIZER;
static bool same(const struct vpa_format *a, const struct vpa_format *b) {
    return a->rate == b->rate && a->channels == b->channels && a->stride == b->stride &&
           a->format == b->format && a->layout == b->layout;
}
static void clear_queue(struct vpa_output *o) {
    o->head = o->queued = 0;
    o->clock_valid = false;
}
static void request_clear(struct vpa_output *o, enum command cmd) {
    clear_queue(o);
    o->command = cmd;
    o->restart_after_clear = false;
    if (o->phase != OPENING)
        o->phase = CLEARING;
    o->clean = false;
    o->revision++;
}
static void *worker(void *arg) {
    struct vpa_output *o = arg;
    for (;;) {
        pthread_mutex_lock(&o->lock);
        if (o->token && ops.retired(o->generation) && o->command != DETACH && o->phase != BROKEN)
            request_clear(o, DETACH);
        enum phase phase = o->phase;
        enum command cmd = o->command;
        uint64_t revision = o->revision, token = o->token;
        struct vpa_format f = o->format;
        void *platform = o->platform;
        bool has_started = o->has_started;
        if (cmd == START)
            o->has_started = true;
        pthread_mutex_unlock(&o->lock);
        int result = 0;
        bool action = true;
        if (phase == OPENING)
            result = ops.create(&platform, &f, o);
        else if (cmd == START)
            result = ops.start(platform);
        else if (cmd == PAUSE)
            result = ops.pause(platform);
        else if (cmd == RESET || cmd == DETACH) {
            if (has_started) {
                // 回调已停止送旧PCM；先Flush丢弃排队旧音，避免Stop把旧缓存播完。
                // 即使首次Flush失败仍尝试Stop，但不能伪报清空成功。
                result = ops.flush(platform);
                int stop_result = ops.stop(platform);
                if (!result)
                    result = stop_result;
                if (!result)
                    result = ops.flush(platform);
                if (!result)
                    result = ops.stopped(platform);
            }
        } else if (cmd == DESTROY)
            result = ops.release(platform);
        else
            action = false;
        uint64_t acknowledge = 0;
        pthread_mutex_lock(&o->lock);
        if (phase == OPENING) {
            o->platform = platform;
            if (result) {
                acknowledge = token;
                o->token = 0;
                o->clean = true;
                o->phase = platform ? DESTROYING : EMPTY;
                o->command = platform ? DESTROY : NONE;
            } else {
                o->phase = READY;
                o->clean = true;
                if (o->revision != revision)
                    o->phase = CLEARING;
            }
        } else if (action) {
            if (result) {
                o->phase = BROKEN;
                o->command = NONE;
            } else if (cmd == RESET || cmd == DETACH) {
                // 已停止时重置绝对平台帧域；不会把运行中的位置0当作播放进度。
                o->has_started = false;
                atomic_store(&o->submitted, 0);
                o->audio_end = o->position = o->timestamp = 0;
                o->clock_valid = false;
                if (o->revision == revision) {
                    o->clean = true;
                    o->command = NONE;
                    o->phase = READY;
                    if (cmd == RESET && o->restart_after_clear && !o->focus) {
                        o->command = START;
                        o->clean = false;
                    }
                    if (cmd == DETACH) {
                        acknowledge = token;
                        o->token = 0;
                        o->focus = false;
                    }
                }
            } else if (cmd == DESTROY) {
                o->platform = NULL;
                o->phase = EMPTY;
                o->command = NONE;
            } else if (o->revision == revision) {
                o->phase = cmd == START ? RUNNING : PAUSED;
                o->command = NONE;
            }
        }
        bool sample =
            o->phase == RUNNING && o->command == NONE && ops.now() - o->query_at >= 50000000LL;
        pthread_mutex_unlock(&o->lock);
        if (acknowledge)
            ops.cleared(acknowledge);
        if (sample) {
            int64_t pos = 0, stamp = 0;
            result = ops.clock(platform, &pos, &stamp);
            int64_t now = ops.now();
            pthread_mutex_lock(&o->lock);
            o->query_at = now;
            if (o->revision == revision && o->phase == RUNNING && !result && pos > 0 && stamp > 0 &&
                stamp <= now && now - stamp < 2000000000LL && pos >= o->position) {
                o->position = pos;
                o->timestamp = stamp;
                o->query_at = now;
                o->clock_valid = true;
            }
            pthread_mutex_unlock(&o->lock);
        }
        usleep(5000);
    }
    return NULL;
}
static void initialize(void) {
    for (int i = 0; i < OUTPUTS; i++) {
        pthread_mutex_init(&outputs[i].lock, NULL);
        if (pthread_create(&outputs[i].worker, NULL, worker, &outputs[i])) {
            outputs[i].phase = BROKEN;
            outputs[i].clean = true;
        } else
            pthread_detach(outputs[i].worker);
    }
}
void vpa_configure(const struct vpa_ops *value) {
    pthread_mutex_lock(&pool);
    if (!ops.create) {
        ops = *value;
        pthread_once(&once, initialize);
    }
    pthread_mutex_unlock(&pool);
}
struct vpa_output *vpa_acquire(uint64_t token, uint64_t gen, const struct vpa_format *f,
                               int timeout_ms) {
    if (!token || !gen || !f || f->rate < 8000 || f->rate > 192000 || f->channels < 1 ||
        f->channels > 16 || f->stride < 1 || f->stride > STRIDE || timeout_ms < 0 ||
        timeout_ms > 2000)
        return NULL;
    int64_t deadline = ops.now() + (int64_t)timeout_ms * 1000000;
    struct vpa_output *chosen = NULL;
    do {
        pthread_mutex_lock(&pool);
        bool blocked = false;
        for (int i = 0; i < OUTPUTS; i++) {
            struct vpa_output *o = &outputs[i];
            pthread_mutex_lock(&o->lock);
            if (o->token && o != chosen)
                blocked = true;
            if ((o->phase == BROKEN && !o->clean) || o->phase == CLEARING)
                blocked = true;
            pthread_mutex_unlock(&o->lock);
        }
        if (!blocked && !chosen) {
            // 优先复用同格式健康停止输出；不先消耗第二个空槽。
            for (int pass = 0; pass < 2 && !chosen; pass++)
                for (int i = 0; i < OUTPUTS; i++) {
                    struct vpa_output *o = &outputs[i];
                    pthread_mutex_lock(&o->lock);
                    if (!o->token &&
                        ((pass == 0 && o->phase == READY && o->clean && same(f, &o->format)) ||
                         (pass == 1 && o->phase == EMPTY))) {
                        chosen = o;
                        o->format = *f;
                        atomic_store(&o->callback_stride, f->stride);
                        o->token = token;
                        o->generation = gen;
                        o->revision++;
                        o->focus = false;
                        o->command = NONE;
                        o->capacity = (f->rate / 50) * 2;
                        clear_queue(o);
                        if (o->phase == EMPTY)
                            o->phase = OPENING;
                    }
                    pthread_mutex_unlock(&o->lock);
                    if (chosen)
                        break;
                }
        }
        if (!blocked && !chosen) {
            for (int i = 0; i < OUTPUTS; i++) {
                struct vpa_output *o = &outputs[i];
                pthread_mutex_lock(&o->lock);
                bool evict = !o->token && o->phase == READY && o->clean;
                if (evict) {
                    o->phase = DESTROYING;
                    o->command = DESTROY;
                    o->revision++;
                }
                pthread_mutex_unlock(&o->lock);
                if (evict)
                    break;
            }
        }
        bool ready = false;
        if (chosen) {
            pthread_mutex_lock(&chosen->lock);
            ready = chosen->phase == READY && chosen->token == token && chosen->clean;
            pthread_mutex_unlock(&chosen->lock);
        }
        pthread_mutex_unlock(&pool);
        if (ready)
            return chosen;
        if (ops.now() >= deadline)
            break;
        usleep(1000);
    } while (true);
    if (chosen)
        vpa_detach(chosen, token);
    return NULL;
}
static bool reset_pending(const struct vpa_output *o) {
    return o->phase == CLEARING && o->command == RESET;
}
// reset后的新PCM只暂存在同一有界队列；确认停止前回调仍输出零。
static bool accepts_pcm(const struct vpa_output *o) {
    return o->phase == READY || o->phase == RUNNING || o->phase == PAUSED || reset_pending(o);
}
bool vpa_write(struct vpa_output *o, uint64_t t, const void *data, int n) {
    if (!o || !data || n < 0)
        return false;
    pthread_mutex_lock(&o->lock);
    bool ok = o->token == t && t && !ops.retired(o->generation) && accepts_pcm(o) &&
              n <= o->capacity - o->queued;
    if (ok) {
        for (int i = 0; i < n; i++)
            memcpy(o->pcm + ((o->head + o->queued + i) % FRAMES) * o->format.stride,
                   (const char *)data + i * o->format.stride, o->format.stride);
        o->queued += n;
    }
    pthread_mutex_unlock(&o->lock);
    return ok;
}
int vpa_callback(struct vpa_output *o, void *data, int bytes) {
    if (!o || !data || bytes <= 0)
        return 0;
    memset(data, 0, bytes);
    int stride = atomic_load(&o->callback_stride);
    if (stride <= 0 || bytes % stride)
        return 0;
    int n = bytes / stride;
    int64_t first = atomic_fetch_add(&o->submitted, n);
    int copied = 0;
    if (pthread_mutex_trylock(&o->lock))
        return 0;
    if (o->token && !o->focus && !ops.retired(o->generation) && o->phase != CLEARING &&
        o->phase != BROKEN && o->command != PAUSE && (o->phase == RUNNING || o->command == START)) {
        copied = n < o->queued ? n : o->queued;
        for (int i = 0; i < copied; i++)
            memcpy((char *)data + i * stride, o->pcm + ((o->head + i) % FRAMES) * stride, stride);
        o->head = (o->head + copied) % FRAMES;
        o->queued -= copied;
        if (copied)
            o->audio_end = first + copied;
    }
    pthread_mutex_unlock(&o->lock);
    return copied;
}
void vpa_start(struct vpa_output *o, uint64_t t) {
    if (!o)
        return;
    pthread_mutex_lock(&o->lock);
    if (o->token == t && t && !o->focus && reset_pending(o)) {
        o->restart_after_clear = true;
    } else if (o->token == t && t && !o->focus && o->phase != CLEARING && o->phase != BROKEN) {
        o->command = START;
        o->revision++;
        o->clean = false;
    }
    pthread_mutex_unlock(&o->lock);
}
bool vpa_pause(struct vpa_output *o, uint64_t t, bool pause) {
    if (!o)
        return false;
    pthread_mutex_lock(&o->lock);
    bool ok =
        o->token == t && t && (o->phase != CLEARING || reset_pending(o)) && o->phase != BROKEN;
    if (ok) {
        if (!pause)
            o->focus = false;
        if (reset_pending(o))
            o->restart_after_clear = !pause;
        else {
            o->command = pause ? PAUSE : START;
            o->revision++;
        }
        o->clock_valid = false;
    }
    pthread_mutex_unlock(&o->lock);
    return ok;
}
void vpa_interrupt(struct vpa_output *o, bool pause) {
    if (!o || !pause)
        return;
    pthread_mutex_lock(&o->lock);
    if (o->token && (o->phase != CLEARING || reset_pending(o)) && o->phase != BROKEN) {
        o->focus = true;
        if (reset_pending(o))
            o->restart_after_clear = false;
        else {
            o->command = PAUSE;
            o->revision++;
        }
        o->clock_valid = false;
    }
    pthread_mutex_unlock(&o->lock);
}
void vpa_reset(struct vpa_output *o, uint64_t t) {
    if (!o)
        return;
    pthread_mutex_lock(&o->lock);
    if (o->token == t && t && o->phase != BROKEN && o->command != DETACH)
        request_clear(o, RESET);
    pthread_mutex_unlock(&o->lock);
}
void vpa_detach(struct vpa_output *o, uint64_t t) {
    if (!o)
        return;
    pthread_mutex_lock(&o->lock);
    if (o->token == t && t && o->command != DETACH && o->phase != BROKEN)
        request_clear(o, DETACH);
    pthread_mutex_unlock(&o->lock);
}
void vpa_snapshot(struct vpa_output *o, uint64_t t, struct vpa_snapshot *s) {
    *s = (struct vpa_snapshot){0};
    if (!o) {
        s->failed = true;
        return;
    }
    pthread_mutex_lock(&o->lock);
    if (!t || o->token != t) {
        s->failed = true;
        pthread_mutex_unlock(&o->lock);
        return;
    }
    int64_t played = o->position, now = ops.now(), submitted = atomic_load(&o->submitted);
    if (o->clock_valid && o->phase == RUNNING && o->command != PAUSE && o->timestamp <= now &&
        now - o->timestamp < 500000000LL) {
        played = o->position + (now - o->timestamp) * o->format.rate / 1000000000LL;
        if (played > submitted)
            played = submitted;
    }
    int64_t remaining = o->audio_end > played ? o->audio_end - played : 0;
    s->queued_frames = o->queued;
    s->delay = (o->queued + remaining) / (double)o->format.rate;
    s->free_frames = accepts_pcm(o) ? o->capacity - o->queued : 0;
    s->playing = (o->phase == RUNNING || o->phase == PAUSED || o->command == START ||
                  o->command == PAUSE || (reset_pending(o) && o->restart_after_clear)) &&
                 (o->queued + remaining > 0);
    s->pause_requested = o->focus;
    s->failed = o->phase == BROKEN;
    pthread_mutex_unlock(&o->lock);
}
void vpa_shutdown_idle(void) {
    for (int i = 0; i < OUTPUTS; i++) {
        struct vpa_output *o = &outputs[i];
        pthread_mutex_lock(&o->lock);
        if (!o->token && o->phase == READY && o->clean) {
            o->phase = DESTROYING;
            o->command = DESTROY;
            o->revision++;
        }
        pthread_mutex_unlock(&o->lock);
    }
}

bool vpa_owns_token(uint64_t t) {
    bool found = false;
    for (int i = 0; i < OUTPUTS; i++) {
        pthread_mutex_lock(&outputs[i].lock);
        if (t && outputs[i].token == t)
            found = true;
        pthread_mutex_unlock(&outputs[i].lock);
    }
    return found;
}
void vpa_detach_token(uint64_t t) {
    for (int i = 0; i < OUTPUTS; i++)
        vpa_detach(&outputs[i], t);
}
