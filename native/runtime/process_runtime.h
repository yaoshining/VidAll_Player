#ifndef VIDALL_PROCESS_RUNTIME_H
#define VIDALL_PROCESS_RUNTIME_H
#include <cstdint>
#include <string>
#include <array>
#include "../mpv/host_recovery_api.h"
namespace vidall::runtime {
enum class TerminalPolicy { ControlledAppExit, PreserveHost };
struct Status {
    int state; // 0 未配置，1 配置中，2 就绪，3 配置失败，4 终局
    int platformError;
    unsigned stage;
    std::uint64_t ownerTag;
    std::int64_t firstObservedMs;
    unsigned deadlineMs;
    int recoveryState; // 0 不支持，1 等待音频停止，2 可创建兼容代，3 超时仍保留
    bool preservesHost;
    std::uint64_t faultSession, faultLoad;
};
struct FaultRecord {
    std::uint64_t sequence, sessionId, loadGeneration;
    int platformError;
    unsigned stage, scope; // 1 会话隔离，2 进程终局。
};
struct FaultHistory { std::array<FaultRecord,16> records{}; unsigned count = 0; };
void RecordSessionFault(int platformError, unsigned stage, std::uint64_t sessionId, std::uint64_t loadGeneration);
FaultHistory Faults();
const char* Configure(const std::string& filesDir, const std::string& config, unsigned deadlineMs, TerminalPolicy policy = TerminalPolicy::ControlledAppExit);
Status Snapshot();
void RejectResources();
const char* AdmissionError(bool recoverySession = false);
// 创建前捕获、实例生命周期内不可变；0 表示目前不能创建实例。
std::uint64_t CaptureGeneration();
const char* SessionAdmissionError(std::uint64_t generation, bool compatible);
// 仅后台析构/释放链使用；终局后不得让父级释放继续返回。
void ParkIfTerminal(bool recoverySession = false);
}
#endif
