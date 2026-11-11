"""逐字执行真实事件循环中的隔离故障分支，覆盖实例回调关闭后仍记录故障。"""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[3]
s=(root/'packages/vidall-player/src/main/cpp/napi_init.cpp').read_text()
start=s.index('            if (isolation_ && event->event_id == MPV_EVENT_CLIENT_MESSAGE')
i=s.index('{',start)+1;depth=1
while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
branch=s[start:i]
code=r'''
#include "fault_message.h"
#include <mpv/client.h>
#include <cstring>
#include <memory>
#include <vector>
#include <cassert>
#define OH_LOG_Print(...) ((void)0)
std::vector<vidall::runtime::FaultRecord> facts;
namespace vidall::runtime {void RecordSessionFault(int error,unsigned stage,uint64_t session,uint64_t load){facts.push_back({0,session,load,error,stage,1});}}
struct Isolation{bool isolated=false;void Quarantine(){isolated=true;}};
class Session {
public:
 std::shared_ptr<Isolation> isolation_=std::make_shared<Isolation>();
 bool closed=false;int callbacks=0;
 void Dispatch(const std::string&,const std::string&){if(!closed)callbacks++;}
 void Handle(mpv_event*event){do { /* BRANCH */ } while(false);}
};
int main(){
 const char*args[]={"vidall-ohcodec-quarantined","2","-7","17","4"};
 mpv_event_client_message message{5,args};mpv_event event{};event.event_id=MPV_EVENT_CLIENT_MESSAGE;event.data=&message;
 Session closed;closed.closed=true;closed.Handle(&event);
 assert(closed.isolation_->isolated&&closed.callbacks==0&&facts.size()==1);
 assert(facts[0].sessionId==17&&facts[0].loadGeneration==4);
 Session open;message.num_args=3;open.Handle(&event);
 assert(open.isolation_->isolated&&open.callbacks==1&&facts.size()==2&&!facts[1].sessionId);
}
'''.replace('/* BRANCH */',branch)
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++17','-Inative/runtime','-Irelease/inputs/004-normal-core/include',str(p/'test.cpp'),'-o',str(p/'test')],cwd=root,check=True)
 subprocess.run([str(p/'test')],check=True,timeout=5)
print('PASS 关闭中的真实隔离分支保留故障归属，旧三字段协议保持未知')
