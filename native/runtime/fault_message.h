#pragma once
#include "process_runtime.h"
#include <charconv>
#include <system_error>
namespace vidall::runtime {
template<class T> bool ParseFaultNumber(const char* text, T& value) {
    if (!text) return false;
    unsigned size = 0;
    while (size <= 20 && text[size]) ++size;
    if (!size || size > 20) return false;
    T parsed{};
    const auto result = std::from_chars(text, text + size, parsed);
    if (result.ec != std::errc() || result.ptr != text + size) return false;
    value = parsed;
    return true;
}
// 老三字段消息保留为未知归属；格式错误不能猜测当前媒体。
inline FaultRecord ParseQuarantineFault(int count, const char** args) {
    FaultRecord fault{};
    fault.scope = 1;
    if (!args || (count != 3 && count != 5)) return fault;
    ParseFaultNumber(args[1], fault.stage);
    ParseFaultNumber(args[2], fault.platformError);
    if (count == 5 && ParseFaultNumber(args[3], fault.sessionId) &&
        ParseFaultNumber(args[4], fault.loadGeneration) && fault.sessionId && fault.loadGeneration)
        return fault;
    fault.sessionId = fault.loadGeneration = 0;
    return fault;
}
}
