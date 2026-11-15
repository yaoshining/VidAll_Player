#pragma once
#include <cstdint>
#include <vector>

// Vulkan枚举可以在两次调用间增长；有限次重试和固定上限防止诊断无界分配。
template<class T> struct EnumerationResult {
    bool ok = false;
    int error = 0;
    std::vector<T> values;
};
template<class T, class Enumerate>
EnumerationResult<T> BoundedEnumerate(Enumerate enumerate, uint32_t limit) {
    EnumerationResult<T> result;
    for (int attempt=0; attempt<3; ++attempt) {
        uint32_t count=0;
        int rc=enumerate(&count,nullptr);
        if (rc!=0) { result.error=rc; return result; }
        if (count>limit) { result.error=-100001; return result; }
        if (!count) { result.ok=true; return result; }
        std::vector<T> values(count);
        uint32_t written=count;
        rc=enumerate(&written,values.data());
        if (written>count) { result.error=-100002; return result; }
        if (rc==5) continue; // VK_INCOMPLETE，不把不完整清单当缺少扩展。
        if (rc!=0) { result.error=rc; return result; }
        values.resize(written);
        result.values=std::move(values); result.ok=true; return result;
    }
    result.error=5; return result;
}
