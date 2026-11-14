#include "bounded_capture.h"
#include <cassert>
#include <cstdint>
int main() {
    uint8_t bytes[8]{};
    RawCaptureBuffer b(80, 3);
    assert(b.append(1, 100, 110, bytes, 8));
    assert(b.append(2, 90, 112, bytes, 8)); // 各轨独立；不能按回调抵达次序强排媒体时序。
    assert(!b.append(1, 100, 120, bytes, 8)); // 同轨重复必须使整轮失效。
    assert(b.error() && b.records()==2);
    assert(!b.append(1, 200, 210, bytes, 8));
    RawCaptureBuffer cap(32, 8);
    assert(cap.append(1, 1, 2, bytes, 8));
    assert(!cap.append(2, 2, 3, bytes, 8));
    assert(cap.bytes().size()==32 && cap.records()==1);
    RawCaptureBuffer count(128, 1);
    assert(count.append(1, 1, 2, bytes, 8));
    assert(!count.append(1, 2, 3, bytes, 8));
    for(int type: {0,3}) { RawCaptureBuffer bad(128,8);assert(!bad.append(type,1,2,bytes,8)); }
    RawCaptureBuffer backwards(128,8);
    assert(backwards.append(1,10,20,bytes,8));assert(!backwards.append(1,9,21,bytes,8));
    RawCaptureBuffer invalid(128,8);assert(!invalid.append(1,-1,2,bytes,8));
    RawCaptureBuffer forensic(128,8,false);
    assert(forensic.append(1,10,20,bytes,8));assert(forensic.append(1,10,21,bytes,8));
    assert(forensic.records()==2 && forensic.anomalies()==1); // 保存异常，不等于时间轴通过。
    RawCaptureBuffer empty(128,8);assert(!empty.append(1,1,2,bytes,0));
}
