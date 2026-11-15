#include "fault_message.h"
#include <cassert>
int main() {
    const char* message[]={"vidall-ohcodec-quarantined","2","-7","17","4"};
    auto fault=vidall::runtime::ParseQuarantineFault(5,message);
    assert(fault.scope==1&&fault.stage==2&&fault.platformError==-7&&fault.sessionId==17&&fault.loadGeneration==4);
    fault=vidall::runtime::ParseQuarantineFault(3,message);assert(!fault.sessionId&&!fault.loadGeneration);
    for(const char* bad:{"","-1","4oops","18446744073709551616","0",static_cast<const char*>(nullptr)}) {
        message[4]=bad;fault=vidall::runtime::ParseQuarantineFault(5,message);
        assert(!fault.sessionId&&!fault.loadGeneration&&fault.stage==2);
    }
    message[1]="2bad";message[2]="-2147483649";
    fault=vidall::runtime::ParseQuarantineFault(5,message);assert(!fault.stage&&!fault.platformError);
    assert(!vidall::runtime::ParseQuarantineFault(2,message).sessionId);
}
