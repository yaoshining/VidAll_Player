// 独立夹具：正常核心未改，不模拟真实 GPU 故障。
#include <mpv/ohcodec_terminal.h>
#include <chrono>
extern "C" int __real_mpv_ohcodec_terminal_snapshot(mpv_ohcodec_terminal_record*);
extern "C" int __wrap_mpv_ohcodec_terminal_snapshot(mpv_ohcodec_terminal_record* record) {
 static const auto start = std::chrono::steady_clock::now();
 if (std::chrono::steady_clock::now() - start < std::chrono::seconds(5)) return __real_mpv_ohcodec_terminal_snapshot(record);
 record->platform_error = -432; record->stage = MPV_OHCODEC_TERMINAL_DRAIN; record->owner_tag = 32;
 return 1;
}
