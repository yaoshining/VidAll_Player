"""执行真实 Release：GPU 关闭时观察者仍存活，超时/故障不提前回收。"""
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[3]
s=(root/'packages/vidall-player/src/main/cpp/napi_init.cpp').read_text()
start=s.index('    void Release()');i=s.index('{',start)+1;depth=1
while depth: depth+=(s[i]=='{')-(s[i]=='}');i+=1
method=s[start:i]
code=r'''
#include "session_isolation.h"
#include <cassert>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <functional>
#include <memory>
#include <mutex>
#include <thread>
using namespace std::chrono_literals;
namespace vidall::render { enum class RenderBackend{Vulkan,Software}; }
namespace vidall::runtime {void ParkIfTerminal(bool){} void RecordSessionFault(int,unsigned,uint64_t,uint64_t){} }
#define OH_LOG_Print(...) ((void)0)
struct Session;
struct mpv_handle {Session *owner;};
int mpv_set_property_string(mpv_handle*,const char*,const char*);
void mpv_wakeup(mpv_handle*){}
void destroy(mpv_handle*);
struct Session {
 std::atomic<bool> released_{false},stopEvents_{false};
 std::mutex lifecycleMutex_,callbackMutex_;
 bool mpvInitialized_=true;
 uint64_t surfaceSessionHandle_=1;
 vidall::render::RenderBackend renderBackend_=vidall::render::RenderBackend::Vulkan;
 std::shared_ptr<vidall::runtime::SessionIsolation> executor_=vidall::runtime::SessionIsolation::Acquire();
 std::shared_ptr<vidall::runtime::SessionIsolation> isolation_=executor_;
 std::unique_ptr<mpv_handle,decltype(&destroy)> player_{new mpv_handle{this},destroy};
 std::thread eventThread_;
 std::atomic<bool> audioClosed{false},gpuClosed{false},windowFreed{false},handleFreed{false},callbackClosed{false},faultPublished{false};
 std::atomic<bool> allowLate{false},closeEntered{false};
 int mode=0;
 bool IsRecoverySession()const{return false;}
 void InvalidateCompletion(){}
 void StopRendererLocked(){assert(gpuClosed||renderBackend_==vidall::render::RenderBackend::Software||!mpvInitialized_);windowFreed=true;}
 void CloseCallbackLocked(){callbackClosed=true;}
 void CloseIsolatedCallbacks(){std::lock_guard<std::mutex>l(callbackMutex_);CloseCallbackLocked();}
 /* METHOD */
};
int mpv_set_property_string(mpv_handle*p,const char*key,const char*value){
 assert(!strcmp(value,"null"));auto&s=*p->owner;
 if(!strcmp(key,"ao")){if(s.mode==6)return -8;s.audioClosed=true;return 0;}
 assert(!strcmp(key,"vo")&&s.audioClosed);
 assert(!s.stopEvents_&&!s.windowFreed&&!s.handleFreed);s.closeEntered=true;
 if(s.mode==3)return -7;
 if(s.mode==1||s.mode==2)while(!s.allowLate)std::this_thread::sleep_for(1ms);
 if(s.mode==2){s.faultPublished=true;s.isolation_->Quarantine();for(;;)std::this_thread::sleep_for(1s);}
 s.gpuClosed=true;return 0;
}
void destroy(mpv_handle*p){assert(p->owner->gpuClosed||!p->owner->mpvInitialized_||p->owner->renderBackend_==vidall::render::RenderBackend::Software);p->owner->handleFreed=true;delete p;}
int main(int argc,char**argv){
 auto*s=new Session;s->mode=std::stoi(argv[1]);
 if(s->mode==4)s->mpvInitialized_=false;
 if(s->mode==5)s->renderBackend_=vidall::render::RenderBackend::Software;
 auto result=s->executor_->Run([s]{s->Release();},20ms,true);
 if(s->mode==1||s->mode==2){
  assert(!result&&s->closeEntered&&!s->windowFreed&&!s->handleFreed);
  s->CloseIsolatedCallbacks();assert(!s->stopEvents_);
  s->allowLate=true;
  for(int i=0;i<100&&!s->faultPublished&&!s->handleFreed;i++)std::this_thread::sleep_for(2ms);
  if(s->mode==2)assert(s->faultPublished&&s->isolation_->IsQuarantined()&&!s->windowFreed&&!s->handleFreed);
  else assert(s->handleFreed&&s->windowFreed);
 }else if(s->mode==3||s->mode==6){assert(s->executor_->IsQuarantined()&&!s->windowFreed&&!s->handleFreed);}
 else {assert(result&&s->handleFreed&&s->windowFreed&&s->callbackClosed);s->Release();}
}
'''.replace('/* METHOD */',method)
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++17','-pthread','-I'+str(root/'native/runtime'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 for case in range(7):subprocess.run([str(p/'test'),str(case)],check=True,timeout=5)
print('PASS 真实 Release：关闭观察者、迟到成功、迟到 owner 故障、拒绝关闭、未初始化及软件路径')
