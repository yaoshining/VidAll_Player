#ifndef MPV_HOST_RECOVERY_API_H
#define MPV_HOST_RECOVERY_API_H
#include <stdint.h>
#ifndef MPV_HOST_OPTIONAL
#define MPV_HOST_OPTIONAL
#endif
#ifdef __cplusplus
extern "C" {
#endif
#define MPV_HOST_RECOVERY_ABI_VERSION 0x00010000u
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL uint32_t mpv_host_recovery_api_version(void);
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL uint64_t mpv_host_recovery_generation(void);
// 有界快照，不调用平台。非零表示仍不能开始恢复播放。
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL unsigned mpv_host_recovery_audio_pending(void);
// 仅独立恢复线程调用，可能等待平台 Stop；不得从 UI、通知 handler 或 mpv core 调用。
__attribute__((visibility("default"))) MPV_HOST_OPTIONAL void mpv_host_recovery_stop_audio(void);
#ifdef __cplusplus
}
#endif
#endif
