#ifndef VIDALL_PROCESS_RUNTIME_H
#define VIDALL_PROCESS_RUNTIME_H
#include <cstdint>
#include <string>
namespace vidall::runtime {
struct Status {
    int state; // 0 未配置，1 配置中，2 就绪，3 配置失败，4 终局
    int platformError;
    unsigned stage;
    std::uint64_t ownerTag;
    std::int64_t firstObservedMs;
    unsigned deadlineMs;
};
const char* Configure(const std::string& filesDir, const std::string& config, unsigned deadlineMs);
Status Snapshot();
void RejectResources();
const char* AdmissionError();
// 仅后台析构/释放链使用；终局后不得让父级释放继续返回。
void ParkIfTerminal();
}
#endif
