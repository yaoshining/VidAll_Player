#ifndef MPV_HOST_RECOVERY_API_H
#define MPV_HOST_RECOVERY_API_H
#include <stdint.h>
#ifndef MPV_HOST_OPTIONAL
#define MPV_HOST_OPTIONAL
#endif
#ifdef __cplusplus
extern "C" {
#endif
#define MPV_HOST_RECOVERY_ABI_VERSION 0x00020000u
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL uint32_t mpv_host_recovery_api_version(void);
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL uint64_t mpv_host_recovery_generation(void);
struct mpv_handle;
typedef struct mpv_host_fault_record {
    uint32_t size;
    uint64_t session_id, load_generation; // 两者均非零才可关联；零表示未知。
} mpv_host_fault_record;
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL int mpv_host_loadfile_async(struct mpv_handle *, uint64_t generation, uint64_t session_id, const char **args);
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL int mpv_host_fault_snapshot(mpv_host_fault_record *out);
// 有界快照，不调用平台。非零表示仍不能开始恢复播放。
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL unsigned mpv_host_recovery_audio_pending(void);
// 仅独立恢复线程调用，可能等待平台 Stop；不得从 UI、通知 handler 或 mpv core 调用。
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL void mpv_host_recovery_stop_audio(void);
#ifdef __cplusplus
}
#endif
#endif
