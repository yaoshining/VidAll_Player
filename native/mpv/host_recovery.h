#ifndef MP_HOST_RECOVERY_H
#define MP_HOST_RECOVERY_H
#include <stdbool.h>
// 由 mpv 拥有的恢复代与音频控制；不获取 mpv core、VO 或日志锁。
unsigned long long mp_host_generation(void);
bool mp_host_is_retired(unsigned long long generation);
void mp_host_retire_all(void);
unsigned long long mp_host_audio_begin(unsigned long long generation);
bool mp_host_audio_publish(unsigned long long token, int (*stop)(void *), void *opaque);
bool mp_host_audio_control_lock(unsigned long long token);
void mp_host_audio_control_unlock(unsigned long long token);
bool mp_host_audio_remove(unsigned long long token, int (*release)(void *), void *opaque);
// 仅在 remove 的 release 回调持有槽控制锁且 renderer 已释放或从未创建时调用。
// 发布音频静止事实，不归还槽或允许重启旧 renderer。
void mp_host_audio_confirm_quiescent(unsigned long long token);
unsigned mp_host_audio_pending(void);
void mp_host_stop_retired_audio(void);
#endif
