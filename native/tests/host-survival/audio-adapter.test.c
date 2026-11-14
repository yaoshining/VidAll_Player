// 真实适配器控制线程测试；平台替身不等于TV验收。
#include "../../experimental/audio_output_adapter.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
static atomic_int creates, starts, pauses, stops, flushes, releases, cleared;
static atomic_bool block_stop, stop_entered, block_release, release_entered;
static atomic_bool block_pause, pause_entered;
static atomic_bool clock_fail;
static atomic_bool block_first_release;
static atomic_llong clock_position;
static int fail_flush;
static int64_t now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}
static int create(void **p, const struct vpa_format *f, struct vpa_output *o) {
    (void)f;
    *p = o;
    creates++;
    return 0;
}
static int start(void *p) {
    (void)p;
    starts++;
    return 0;
}
static int pause_stream(void *p) {
    (void)p;
    pauses++;
    pause_entered = true;
    while (block_pause)
        usleep(1000);
    return 0;
}
static int stop(void *p) {
    (void)p;
    stops++;
    stop_entered = true;
    while (block_stop)
        usleep(1000);
    return 0;
}
static int flush(void *p) {
    (void)p;
    flushes++;
    return fail_flush;
}
static int state(void *p) {
    (void)p;
    return 0;
}
static int release(void *p) {
    (void)p;
    int number = ++releases;
    release_entered = true;
    while (block_release || (block_first_release && number == 1))
        usleep(1000);
    return 0;
}
static int clock_sample(void *p, int64_t *a, int64_t *b) {
    (void)p;
    *a = clock_position;
    *b = now();
    return clock_fail ? -1 : 0;
}
static bool retired(uint64_t g) { return g == 99; }
static void done(uint64_t token) {
    assert(token);
    cleared++;
}
static struct vpa_ops ops = {create,  start,        pause_stream, stop, flush, state,
                             release, clock_sample, retired,      done, now};
static struct vpa_format format = {48000, 2, 4, 1, 3};
static void wait_count(atomic_int *p, int n) {
    for (int i = 0; i < 2000 && *p < n; i++)
        usleep(1000);
    assert(*p >= n);
}
static void wait_flag(atomic_bool *p) {
    for (int i = 0; i < 2000 && !*p; i++)
        usleep(1000);
    assert(*p);
}
int main(int argc, char **argv) {
    assert(argc == 2);
    vpa_configure(&ops);
    struct vpa_output *o = vpa_acquire(1, 1, &format, 500);
    assert(o);
    unsigned char data[3840], got[3840];
    memset(data, 0x33, sizeof(data));
    assert(vpa_write(o, 1, data, 960));
    vpa_start(o, 1);
    wait_count(&starts, 1);
    assert(vpa_callback(o, got, sizeof(got)) == 960);
    assert(!memcmp(got, data, sizeof(got)));
    if (!strcmp(argv[1], "pause-clock")) {
        for (int i = 0; i < 4; i++) {
            assert(vpa_write(o, 1, data, 960));
            vpa_callback(o, got, sizeof(got));
        }
        clock_position = 3840;
        usleep(60000);
        assert(vpa_pause(o, 1, true));
        wait_count(&pauses, 1);
        usleep(10000);
        struct vpa_snapshot s;
        vpa_snapshot(o, 1, &s);
        assert(s.delay <= 0.021);
        return 0;
    }
    if (!strcmp(argv[1], "clock")) {
        struct vpa_snapshot s;
        vpa_snapshot(o, 1, &s);
        assert(s.delay >= 0.019);
        clock_position = 480;
        usleep(60000);
        vpa_snapshot(o, 1, &s);
        assert(s.delay < 0.019);
        clock_fail = true;
        usleep(600000);
        vpa_snapshot(o, 1, &s);
        assert(s.delay >= 0.009 && s.delay <= 0.011);
        return 0;
    }
    if (!strcmp(argv[1], "formats")) {
        vpa_detach(o, 1);
        wait_count(&cleared, 1);
        for (uint64_t t = 2; t < 8; t++) {
            struct vpa_format f = format;
            f.rate = 32000 + (int)t * 1000;
            struct vpa_output *next = vpa_acquire(t, 1, &f, 500);
            assert(next);
            vpa_detach(next, t);
            wait_count(&cleared, (int)t);
        }
        assert(releases >= 5);
        return 0;
    }
    if (!strcmp(argv[1], "pending-pause")) {
        assert(vpa_write(o, 1, data, 960));
        block_pause = true;
        assert(vpa_pause(o, 1, true));
        wait_flag(&pause_entered);
        vpa_callback(o, got, sizeof(got));
        for (unsigned i = 0; i < sizeof(got); i++)
            assert(!got[i]);
        block_pause = false;
        return 0;
    }
    if (!strcmp(argv[1], "async-reset") || !strcmp(argv[1], "reset-focus") ||
        !strcmp(argv[1], "reset-detach")) {
        block_stop = true;
        vpa_reset(o, 1);
        wait_flag(&stop_entered);
        assert(flushes == 1); // 先丢弃已排队旧音，再等待Stop完成。
        struct vpa_snapshot state;
        vpa_snapshot(o, 1, &state);
        assert(state.free_frames >= 960);
        memset(data, 0x55, sizeof(data));
        assert(vpa_write(o, 1, data, 960));
        vpa_start(o, 1);
        vpa_callback(o, got, sizeof(got));
        for (unsigned i = 0; i < sizeof(got); i++)
            assert(!got[i]);
        assert(starts == 1);
        bool interrupted = !strcmp(argv[1], "reset-focus");
        bool detached = !strcmp(argv[1], "reset-detach");
        if (interrupted)
            vpa_interrupt(o, true);
        if (detached)
            vpa_detach(o, 1);
        block_stop = false;
        if (detached) {
            wait_count(&cleared, 1);
            assert(starts == 1);
            assert(vpa_callback(o, got, sizeof(got)) == 0);
            assert(vpa_acquire(2, 1, &format, 500));
            return 0;
        }
        if (interrupted) {
            usleep(30000);
            vpa_snapshot(o, 1, &state);
            assert(state.pause_requested && starts == 1);
            assert(vpa_pause(o, 1, false));
        }
        wait_count(&starts, 2);
        assert(vpa_callback(o, got, sizeof(got)) == 960);
        assert(!memcmp(data, got, sizeof(got)));
        return 0;
    }
    if (!strcmp(argv[1], "unknown-stop")) {
        block_stop = true;
        vpa_detach(o, 1);
        wait_flag(&stop_entered);
        int64_t before = now();
        for (int i = 0; i < 10000; i++) {
            struct vpa_snapshot s;
            vpa_snapshot(o, 1, &s);
            assert(!vpa_write(o, 1, data, 960));
        }
        assert(now() - before < 1000000000);
        assert(!vpa_acquire(2, 1, &format, 20));
        assert(!cleared);
        memset(got, 0x33, sizeof(got));
        vpa_callback(o, got, sizeof(got));
        for (unsigned i = 0; i < sizeof(got); i++)
            assert(!got[i]);
        block_stop = false;
        wait_count(&cleared, 1);
        assert(vpa_acquire(2, 1, &format, 500));
        return 0;
    }
    if (!strcmp(argv[1], "flush-error")) {
        fail_flush = -1;
        vpa_detach(o, 1);
        wait_count(&flushes, 1);
        usleep(20000);
        assert(!cleared);
        assert(!vpa_acquire(2, 1, &format, 20));
        return 0;
    }
    if (!strcmp(argv[1], "focus")) {
        vpa_interrupt(o, true);
        struct vpa_snapshot s;
        vpa_snapshot(o, 1, &s);
        assert(s.pause_requested);
        vpa_start(o, 1);
        usleep(30000);
        assert(starts == 1);
        assert(vpa_pause(o, 1, false));
        wait_count(&starts, 2);
        vpa_snapshot(o, 1, &s);
        assert(!s.pause_requested);
        vpa_detach(o, 1);
        wait_count(&cleared, 1);
        assert(vpa_acquire(2, 1, &format, 500) == o);
        vpa_snapshot(o, 2, &s);
        assert(!s.pause_requested);
        assert(!vpa_pause(o, 1, false));
        return 0;
    }
    if (!strcmp(argv[1], "release-hang-formats")) {
        vpa_detach(o, 1);
        wait_count(&cleared, 1);
        block_first_release = true;
        vpa_shutdown_idle();
        wait_flag(&release_entered);
        struct vpa_output *next = vpa_acquire(2, 1, &format, 500);
        assert(next);
        vpa_detach(next, 2);
        wait_count(&cleared, 2);
        // 第一个Release永久停住；后续Release允许返回，仍需能切换格式。
        struct vpa_format different = format;
        different.rate = 44100;
        assert(vpa_acquire(3, 1, &different, 500));
        return 0;
    }
    if (!strcmp(argv[1], "all-slots-held")) {
        vpa_detach(o, 1);
        wait_count(&cleared, 1);
        block_release = true;
        vpa_shutdown_idle();
        wait_flag(&release_entered);
        struct vpa_output *next = vpa_acquire(2, 1, &format, 500);
        assert(next);
        vpa_detach(next, 2);
        wait_count(&cleared, 2);
        vpa_shutdown_idle();
        wait_count(&releases, 2);
        int64_t before = now();
        assert(!vpa_acquire(3, 1, &format, 20));
        assert(now() - before < 200000000);
        assert(creates == 2 && releases == 2);
        return 0; // 明确边界：保持进程存活，但没有安全的第三个输出。
    }
    if (!strcmp(argv[1], "release-hang")) {
        vpa_detach(o, 1);
        wait_count(&cleared, 1);
        block_release = true;
        vpa_shutdown_idle();
        wait_flag(&release_entered);
        struct vpa_output *fresh = vpa_acquire(2, 1, &format, 500);
        assert(fresh && fresh != o);
        for (uint64_t t = 2; t < 23; t++) {
            assert(vpa_write(fresh, t, data, 960));
            vpa_start(fresh, t);
            wait_count(&starts, (int)t);
            assert(vpa_callback(fresh, got, sizeof(got)) == 960);
            assert(!memcmp(data, got, sizeof(got)));
            vpa_detach(fresh, t);
            wait_count(&cleared, (int)t);
            if (t < 22)
                assert(vpa_acquire(t + 1, 1, &format, 500) == fresh);
        }
        assert(creates == 2 && releases == 1);
        block_release = false;
        return 0;
    }
    assert(!strcmp(argv[1], "normal"));
    assert(vpa_pause(o, 1, true));
    wait_count(&pauses, 1);
    usleep(10000);
    struct vpa_snapshot paused_state;
    vpa_snapshot(o, 1, &paused_state);
    assert(paused_state.playing);
    assert(vpa_write(o, 1, data, 960));
    vpa_callback(o, got, sizeof(got));
    for (unsigned i = 0; i < sizeof(got); i++)
        assert(!got[i]);
    assert(vpa_pause(o, 1, false));
    wait_count(&starts, 2);
    assert(vpa_callback(o, got, sizeof(got)) == 960);
    vpa_reset(o, 1);
    wait_count(&stops, 1);
    usleep(20000);
    assert(vpa_write(o, 1, data, 960));
    vpa_detach(o, 1);
    wait_count(&cleared, 1);
    for (uint64_t t = 2; t < 25; t++) {
        assert(vpa_acquire(t, 1, &format, 500) == o);
        assert(!vpa_write(o, t - 1, data, 960));
        assert(vpa_write(o, t, data, 960));
        vpa_start(o, t);
        wait_count(&starts, (int)t + 1);
        assert(vpa_callback(o, got, sizeof(got)) == 960);
        assert(!memcmp(data, got, sizeof(got)));
        vpa_detach(o, t);
        wait_count(&cleared, (int)t);
    }
    assert(creates == 1 && releases == 0);
    vpa_shutdown_idle();
    wait_count(&releases, 1);
    return 0;
}
