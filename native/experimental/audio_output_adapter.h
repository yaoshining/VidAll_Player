#ifndef VIDALL_AUDIO_OUTPUT_ADAPTER_H
#define VIDALL_AUDIO_OUTPUT_ADAPTER_H
#include <stdbool.h>
#include <stdint.h>
struct vpa_output;
// format为适配层样本格式，layout为完整声道布局，不允许仅比较声道数。
struct vpa_format {
    int rate, channels, stride, format;
    uint64_t layout;
};
struct vpa_ops {
    int (*create)(void **, const struct vpa_format *, struct vpa_output *);
    int (*start)(void *), (*pause)(void *), (*stop)(void *), (*flush)(void *);
    int (*stopped)(void *); // 仅确认STOPPED才返回0。
    int (*release)(void *);
    int (*clock)(void *, int64_t *, int64_t *); // 相邻平台MONOTONIC时间戳。
    bool (*retired)(uint64_t);
    void (*cleared)(uint64_t); // 平台停止/清空后归还原租约；不是输出对象回收。
    int64_t (*now)(void);
};
struct vpa_snapshot {
    int free_frames, queued_frames;
    double delay;
    bool playing, pause_requested, failed;
};
void vpa_configure(const struct vpa_ops *);
struct vpa_output *vpa_acquire(uint64_t token, uint64_t generation, const struct vpa_format *,
                               int timeout_ms);
bool vpa_write(struct vpa_output *, uint64_t, const void *, int frames);
int vpa_callback(struct vpa_output *, void *, int bytes);
void vpa_start(struct vpa_output *, uint64_t);
bool vpa_pause(struct vpa_output *, uint64_t, bool);
void vpa_interrupt(struct vpa_output *, bool pause);
void vpa_reset(struct vpa_output *, uint64_t);
void vpa_detach(struct vpa_output *, uint64_t);
void vpa_snapshot(struct vpa_output *, uint64_t, struct vpa_snapshot *);
void vpa_shutdown_idle(void);
bool vpa_owns_token(uint64_t);
void vpa_detach_token(uint64_t);
#endif
