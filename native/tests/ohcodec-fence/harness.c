// 真 FD 加上可注入错误的 Vulkan 和 Surface 边界。生产代码决定是否归还或销毁。
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

typedef int VkResult;
enum { VK_SUCCESS = 0, NATIVE_ERROR_OK = 0, OHCODEC_DRAIN_NOT_APPLICABLE = 0,
       OHCODEC_DRAIN_SAFE = 1, OHCODEC_DRAIN_SAFE_RELEASE_ERROR = 2, OHCODEC_DRAIN_UNSAFE = 3 };
struct vk_import { bool busy; int release_sem, image; struct vk_import *next; };
struct fake_vk { void (*lock_queue)(struct fake_vk *, int, int);
                 void (*unlock_queue)(struct fake_vk *, int, int); };
struct vk_mapper {
    struct fake_vk *vk;
    struct vk_import *current, *imports;
    void *gpu, *window_buffer;
    int qf, queue, num_imports;
    bool external_release_inflight;
    const char *release_reason;
    VkResult (*wait_idle)(int);
    VkResult (*signal_release)(int, int, int *, int, int *);
};
struct ohcodec_mapper_priv { int terminal_drain_error; struct vk_mapper *priv; void *last_src, *last_token; };
struct ra_hwdec_mapper { struct ohcodec_mapper_priv *priv; void *tex[1]; };
#define MP_INFO(...) ((void)0)
#define MP_ERR(...) ((void)0)
#define pl_vulkan_hold_params(...) 0
static int exported = -1, transferred, destroyed, locks, waits;
static bool held = true;
static int signal_rc, wait_rc, release_rc;
static void lock(struct fake_vk *vk, int qf, int idx) { assert(locks++ == 0); }
static void unlock(struct fake_vk *vk, int qf, int idx) { assert(--locks == 0); }
static int signal_release(int queue, int count, int *sem, int image, int *out)
{
    assert(locks == 1);
    if (signal_rc) return signal_rc;
    int pipefd[2]; assert(pipe(pipefd) == 0);
    close(pipefd[1]);
    *out = exported = pipefd[0];
    return 0;
}
static int wait_idle(int queue) { assert(locks == 1); waits++; return wait_rc; }
static void pl_gpu_finish(void *gpu) {}
static bool pl_vulkan_hold_ex(void *gpu, int params) { return held; }
static int release_window_buffer(struct ra_hwdec_mapper *m, int fd)
{
    assert(!locks && m->priv->priv->window_buffer);
    if (fd >= 0) { assert(fd == exported); assert(close(fd) == 0); }
    transferred++; m->priv->priv->window_buffer = NULL; return release_rc;
}
static void destroy_import(struct ra_hwdec_mapper *m, struct vk_import *e) { destroyed++; }
static void mp_image_unrefp(void **value) { *value = NULL; }
static int diagnostic_result(struct ra_hwdec_mapper *m, const char *stage, int reason, int rc) { return rc; }

// 仅拦截生产函数直接执行的 close，平台替身消费 FD 仍由其自身计数。
static int local_closes;
static int close_local_fd(int fd) {
    assert(fd == exported && local_closes++ == 0);
    return close(fd);
}
#define close(fd) close_local_fd(fd)
/* PRODUCTION */
#undef close

int main(int argc, char **argv)
{
    assert(argc == 2);
    const char *scenario = argv[1];
    struct vk_import image = {.busy = true};
    struct fake_vk vk = {lock, unlock};
    struct vk_mapper v = {.vk = &vk, .gpu = &vk, .current = &image, .imports = &image,
                          .num_imports = 1, .window_buffer = &image,
                          .wait_idle = wait_idle, .signal_release = signal_release};
    struct ohcodec_mapper_priv p = {.priv = &v, .last_src = &image, .last_token = &image};
    struct ra_hwdec_mapper mapper = {.priv = &p, .tex = {&image}};
    if (strstr(scenario, "hold-error")) held = false;
    if (strstr(scenario, "signal-error")) signal_rc = -4;
    if (strstr(scenario, "wait-error") || strstr(scenario, "history-error")) wait_rc = -4;
    if (strstr(scenario, "release-error")) release_rc = -9;
    if (strstr(scenario, "frame-")) {
        mapper_release(&mapper);
        if (held && !signal_rc) {
            assert(transferred == 1 && !v.current && !image.busy && v.external_release_inflight);
        } else {
            assert(transferred == 0 && v.window_buffer && v.current == &image && image.busy);
            int error = 0;
            assert(ohcodec_drain(&mapper, 2, &error) == OHCODEC_DRAIN_UNSAFE);
            assert(error == (signal_rc ? signal_rc : -1) && !waits && !destroyed);
        }
    } else {
        if (strstr(scenario, "history")) {
            v.current = NULL; v.window_buffer = NULL; v.external_release_inflight = true;
        }
        int error = 0;
        int rc = ohcodec_drain(&mapper, 1, &error);
        if (!held || signal_rc || wait_rc) {
            assert(rc == OHCODEC_DRAIN_UNSAFE && error != 0);
            assert(!destroyed && !transferred && v.imports == &image);
        } else {
            assert(rc == (release_rc ? OHCODEC_DRAIN_SAFE_RELEASE_ERROR : OHCODEC_DRAIN_SAFE));
            assert(error == release_rc && destroyed == 1 && transferred == 1 && waits == 1);
        }
    }
    if (exported >= 0) {
        assert(local_closes + transferred == 1);
        errno = 0;
        assert(fcntl(exported, F_GETFD) == -1 && errno == EBADF);
    }
    assert(!locks);
}
