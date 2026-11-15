"""真实采样/关闭函数和槽锁的确定性交错；平台替身不代表设备验收。"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
source = (Path(sys.argv[1]) / 'audio/out/ao_ohaudio.c').read_text()
def function(name):
    match = re.search(r'^static [\w *]+\b' + name + r'\([^;]*?\)\s*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0]

names = ['reset_timing', 'timing_worker', 'stop_timing_worker', 'release_for_recovery', 'uninit', 'stop_for_recovery']
functions = {name: function(name) for name in names}
code = r'''
#include "host_recovery.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <stdlib.h>
typedef pthread_mutex_t mp_mutex;
typedef pthread_cond_t mp_cond;
#define mp_mutex_lock pthread_mutex_lock
#define mp_mutex_unlock pthread_mutex_unlock
#define mp_mutex_destroy pthread_mutex_destroy
#define mp_cond_signal pthread_cond_signal
#define mp_cond_broadcast pthread_cond_broadcast
#define mp_cond_destroy pthread_cond_destroy
#define MP_TIME_MS_TO_NS(v) ((int64_t)(v)*1000000)
#define MP_TIME_S_TO_NS(v) ((int64_t)(v)*1000000000)
static int64_t mp_time_ns(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return MP_TIME_S_TO_NS(t.tv_sec) + t.tv_nsec;
}
static int mp_cond_timedwait(mp_cond *c, mp_mutex *m, int64_t ns) {
    struct timespec t; clock_gettime(CLOCK_REALTIME, &t); t.tv_nsec += ns;
    while (t.tv_nsec >= 1000000000) { t.tv_sec++; t.tv_nsec -= 1000000000; }
    return pthread_cond_timedwait(c, m, &t);
}
static void mp_sleep_ns(int64_t ns) { (void)ns; usleep(1000); }
typedef int OH_AudioStream_Result;
typedef int OH_AudioStream_State;
typedef int OH_AudioRenderer;
typedef int OH_AudioStreamBuilder;
enum { AUDIOSTREAM_SUCCESS, AUDIOSTREAM_STATE_PREPARED, AUDIOSTREAM_STATE_STOPPED, AUDIOSTREAM_STATE_RUNNING };
struct priv {
    int64_t last_query, frame_position, frame_timestamp, written_frames, queued_frames;
    bool timestamp_valid, timing_initialized, timing_started, timing_stop;
    mp_mutex timing_lock; mp_cond timing_wakeup; pthread_t timing_thread;
    unsigned long long recovery_token, recovery_generation;
    OH_AudioRenderer *renderer; OH_AudioStreamBuilder *builder;
};
struct ao { struct priv *priv; };
static atomic_bool gate_control, allow_control, control_entered, control_returned;
static atomic_bool join_entered, remove_entered, close_done, stop_entered, stop_blocked;
static atomic_bool query_entered, query_blocked;
static atomic_int released, destroyed, state = AUDIOSTREAM_STATE_RUNNING;
static void wait_flag(atomic_bool *flag) {
    int64_t deadline = mp_time_ns() + MP_TIME_S_TO_NS(2);
    while (!*flag && mp_time_ns() < deadline) usleep(1000);
    assert(*flag);
}
static void unbind_legacy(struct priv *p) { (void)p; }
static int OH_AudioRenderer_GetAudioTimestampInfo(OH_AudioRenderer *r, int64_t *pos, int64_t *stamp) {
    (void)r; query_entered = true;
    while (query_blocked) usleep(1000);
    *pos = 1; *stamp = mp_time_ns(); return 0;
}
static int OH_AudioRenderer_GetCurrentState(OH_AudioRenderer *r, int *s) { (void)r; *s = state; return 0; }
static int OH_AudioRenderer_Stop(OH_AudioRenderer *r) {
    (void)r; stop_entered = true;
    while (stop_blocked) usleep(1000);
    state = AUDIOSTREAM_STATE_STOPPED; return 0;
}
static int OH_AudioRenderer_Release(OH_AudioRenderer *r) {
    (void)r; assert(!query_blocked && !stop_blocked); released++; return 0;
}
static int OH_AudioStreamBuilder_Destroy(OH_AudioStreamBuilder *b) { (void)b; destroyed++; return 0; }
// 只在实际函数调用边界设置调度屏障；不替换槽锁、remove或pthread_join。
static bool observed_control(unsigned long long token) {
    control_entered = true;
    while (gate_control && !allow_control) usleep(1000);
    bool ok = mp_host_audio_control_lock(token);
    control_returned = true; return ok;
}
static int observed_join(pthread_t thread, void **result) {
    join_entered = true; return pthread_join(thread, result);
}
static bool observed_remove(unsigned long long token, int (*release)(void *), void *opaque) {
    remove_entered = true; return mp_host_audio_remove(token, release, opaque);
}
#define mp_host_audio_control_lock observed_control
#define pthread_join observed_join
#define mp_host_audio_remove observed_remove
/* FUNCTIONS */
#undef mp_host_audio_control_lock
#undef pthread_join
#undef mp_host_audio_remove
static void *close_session(void *p) { uninit(p); close_done = true; return NULL; }
static void *stop_retired(void *p) { (void)p; mp_host_stop_retired_audio(); return NULL; }
int main(int argc, char **argv) {
    assert(argc == 2);
    bool retired = !strcmp(argv[1], "retired-control");
    bool query = !strcmp(argv[1], "query-in-flight");
    bool no_worker = !strcmp(argv[1], "no-worker");
    bool cycle = !strcmp(argv[1], "mutant-cycle");
    int renderer = 1, builder = 2;
    struct priv p = { .renderer = &renderer, .builder = &builder };
    struct ao a = { &p };
    p.recovery_generation = mp_host_generation();
    p.recovery_token = mp_host_audio_begin(p.recovery_generation);
    assert(p.recovery_token && mp_host_audio_publish(p.recovery_token, stop_for_recovery, p.renderer));
    assert(!pthread_mutex_init(&p.timing_lock, NULL));
    assert(!pthread_cond_init(&p.timing_wakeup, NULL)); p.timing_initialized = true;
    query_blocked = query; gate_control = !query;
    if (!no_worker) {
        assert(!pthread_create(&p.timing_thread, NULL, timing_worker, &a)); p.timing_started = true;
        wait_flag(query ? &query_entered : &control_entered);
    }
    pthread_t closer, stopping;
    if (retired) {
        mp_host_retire_all(); stop_blocked = true;
        assert(!pthread_create(&stopping, NULL, stop_retired, NULL)); wait_flag(&stop_entered);
    }
    assert(!pthread_create(&closer, NULL, close_session, &a));
    if (!no_worker) {
        wait_flag(&join_entered);
        assert(!released && !destroyed && p.recovery_token);
        if (!cycle) assert(!remove_entered);
        allow_control = true;
        if (retired || query) {
            if (query) mp_host_retire_all();
            assert(mp_host_audio_pending() == 1 && !close_done);
            query_blocked = false; stop_blocked = false;
        }
        if (cycle) {
            assert(remove_entered);
            int64_t deadline = mp_time_ns() + MP_TIME_MS_TO_NS(250);
            while (!close_done && mp_time_ns() < deadline) usleep(1000);
            if (!close_done && !control_returned && !released) {
                fprintf(stderr, "LOCK_ORDER_CYCLE: remove holds control; join waits for worker\n");
                _Exit(73); // 仅结束负例测试进程，保留死锁线程的对象到进程退出。
            }
            assert(!"持锁join负例未形成预期死锁");
        }
    }
    wait_flag(&close_done); assert(!pthread_join(closer, NULL));
    if (retired) assert(!pthread_join(stopping, NULL));
    assert(released == 1 && destroyed == 1 && !p.recovery_token && !p.timing_initialized);
    if (!query) assert(!query_entered); // stop发布后不得新进平台查询。
    uninit(&a); assert(released == 1 && destroyed == 1);
    unsigned long long fresh = mp_host_audio_begin(mp_host_generation()); assert(fresh);
    assert(mp_host_audio_remove(fresh, stop_for_recovery, &renderer));
    return 0;
}
'''

with tempfile.TemporaryDirectory() as td:
    p = Path(td)
    for mutant in [True, False]:
        selected = functions.copy()
        if mutant:
            assert selected['uninit'].count('    stop_timing_worker(p);') == 1
            selected['uninit'] = selected['uninit'].replace('    stop_timing_worker(p);\n', '')
            selected['release_for_recovery'] = selected['release_for_recovery'].replace(
                '    struct priv *p = ao->priv;', '    struct priv *p = ao->priv;\n    stop_timing_worker(p);', 1)
        (p/'test.c').write_text(code.replace('/* FUNCTIONS */', '\n'.join(selected[n] for n in names)))
        subprocess.run(['clang', '-std=gnu11', '-pthread', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-I'+str(ROOT/'native/mpv'), str(p/'test.c'),
                        str(ROOT/'native/mpv/host_recovery.c'), '-o', str(p/'test')], check=True)
        for case in (['mutant-cycle'] if mutant else ['waiting-control', 'retired-control', 'query-in-flight', 'no-worker']):
            result = subprocess.run([str(p/'test'), case], capture_output=True, text=True, timeout=5)
            if mutant:
                assert result.returncode == 73 and 'LOCK_ORDER_CYCLE' in result.stderr, result.stderr
            else:
                assert result.returncode == 0, (case, result.stderr)
            print(case, 'EXPECTED_DEADLOCK' if mutant else 'PASS', flush=True)
