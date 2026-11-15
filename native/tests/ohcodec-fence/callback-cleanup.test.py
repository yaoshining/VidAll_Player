#!/usr/bin/env python3
"""编译真实回调与 owner 消息分支；替身只负责 NAPI 排队及计数。"""
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
source = (ROOT / 'packages/vidall-player/src/main/cpp/napi_init.cpp').read_text()


def extract(signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


methods = '\n'.join(extract(s) for s in [
    'NativeResult SetEventCallback(', 'static void FinalizeCallback(',
    'static void CallCallback(', 'void QueueEventLocked(', 'void Dispatch(',
    'void DispatchCompletion(', 'const char* OperationAdmissionError() const',
    'void CloseCallbackLocked()', 'void CloseIsolatedCallbacks()'])
owner = extract('if (isolation_ && event->event_id == MPV_EVENT_CLIENT_MESSAGE')
code = r'''
#include "session_isolation.h"
#include "environment_lifetime.h"
#include "fault_message.h"
#include "event_mailbox.h"
#include <functional>
#include <atomic>
#include <cassert>
#include <cstring>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <vector>
#define OH_LOG_Print(...) ((void)0)
using napi_env=void*; using napi_value=void*; using napi_valuetype=int;
constexpr int napi_ok=0,napi_pending_exception=10,napi_tsfn_nonblocking=0,napi_tsfn_release=0;
bool pendingException=false,throwNext=false;int clearedExceptions=0;
constexpr int napi_undefined=0,napi_function=1,MPV_EVENT_CLIENT_MESSAGE=16;
struct NativeResult {bool ok; uint64_t handle; const char* code;};
struct mpv_event_client_message {int num_args; const char**args;};
struct mpv_event {int event_id; void* data;};
int calls=0, objects=0, closed=0, reported=0;
constexpr int MPV_END_FILE_REASON_EOF=0,MPV_END_FILE_REASON_ERROR=4;
struct Payload {std::string type,message;uint64_t sequence=0;};
Payload payload;std::vector<Payload> delivered;std::string textValue;uint64_t numberValue;
std::function<void()> onCall;
struct Tsfn {size_t max;void* lifetime;void(*finalize)(napi_env,void*,void*);bool closed=false;};
std::vector<std::unique_ptr<Tsfn>> functions;
struct Pending {Tsfn* fn;void* data;};
std::vector<Pending> queue;
int napi_typeof(napi_env,napi_value,napi_valuetype*t){*t=napi_function;return 0;}
int napi_create_threadsafe_function(napi_env,napi_value,napi_value,napi_value,size_t max,size_t,
 void* lifetime,void(*finalize)(napi_env,void*,void*),void*,void(*)(napi_env,napi_value,void*,void*),void**out){
 assert(max==1);auto fn=std::make_unique<Tsfn>();fn->max=max;fn->lifetime=lifetime;fn->finalize=finalize;
 *out=fn.get();functions.push_back(std::move(fn));return 0;
}
int napi_release_threadsafe_function(void*p,int){closed++;static_cast<Tsfn*>(p)->closed=true;return 0;}
int napi_call_threadsafe_function(void*p,void*event,int){
 auto*fn=static_cast<Tsfn*>(p);size_t count=0;for(auto&q:queue)if(q.fn==fn)count++;
 if(fn->closed||count>=fn->max)return 1;queue.push_back({fn,event});return 0;
}
napi_value CreateString(napi_env,const std::string&s){textValue=s;return nullptr;}
int napi_create_object(napi_env,napi_value*){assert(!pendingException);objects++;payload={};return 0;}
int napi_set_named_property(napi_env,napi_value,const char*key,napi_value){
 if(!strcmp(key,"type"))payload.type=textValue;if(!strcmp(key,"message"))payload.message=textValue;
 if(!strcmp(key,"sequence"))payload.sequence=numberValue;return 0;
}
int napi_create_int64(napi_env,int64_t n,napi_value*){numberValue=n;return 0;}
int napi_call_function(napi_env,napi_value,napi_value,size_t,napi_value*,napi_value*){assert(!pendingException);calls++;delivered.push_back(payload);if(onCall)onCall();if(throwNext){throwNext=false;pendingException=true;return napi_pending_exception;}return 0;}
int napi_get_and_clear_last_exception(napi_env,napi_value*){assert(pendingException);pendingException=false;clearedExceptions++;return 0;}
void finalizeClosed(){for(auto&f:functions)if(f->closed&&f->lifetime){f->finalize(nullptr,f->lifetime,nullptr);f->lifetime=nullptr;}}
namespace vidall::runtime {
bool terminal=false;
void RecordSessionFault(int,unsigned,uint64_t session,uint64_t load){reported++;assert(!session&&!load); }
const char* SessionAdmissionError(uint64_t born,bool compatible){return !terminal||(born==2&&compatible)?nullptr:"PLAYER_TERMINAL";}
}
class NativeSession {
public:
@@EVENT@@;
using CallbackMailbox=vidall::runtime::EventMailbox<Event>;
using CallbackTicket=std::shared_ptr<CallbackMailbox>;
CallbackTicket callbackMailbox_;
std::atomic<bool> eventDeliveryFailed_{false};
const char* RuntimeAdmissionError()const{return vidall::runtime::SessionAdmissionError(runtimeGeneration_,compatible_);}
bool IsRecoverySession()const{return runtimeGeneration_>1&&compatible_;}
uint64_t completionEpoch_=1;
uint64_t runtimeGeneration_=1;bool compatible_=false;
std::shared_ptr<vidall::runtime::EnvironmentLifetime> environment_;
std::shared_ptr<vidall::runtime::SessionIsolation> isolation_;
std::shared_ptr<std::atomic<bool>> callbackOpen_=std::make_shared<std::atomic<bool>>(true);
std::mutex callbackMutex_;
std::atomic<bool> stopEvents_{false},released_{false};
std::atomic<uint64_t> eventEpoch_{1},eventSequence_{0},generation_{1},surfaceSessionHandle_{1};
void* eventTsfn_=nullptr;
NativeSession(uint64_t born=1,bool compatible=false,bool subscribe=true):runtimeGeneration_(born),compatible_(compatible){if(subscribe)assert(SetEventCallback((void*)1,(void*)1,1).ok);}
~NativeSession(){CloseIsolatedCallbacks();}
@@METHODS@@
void receive(mpv_event*event){if(!stopEvents_){do { @@OWNER@@ }while(false);}}
};
void drain(bool nullEnv=false){auto pending=std::move(queue);queue.clear();for(auto p:pending)
 NativeSession::CallCallback(nullEnv?nullptr:(void*)1,(void*)1,nullptr,p.data);}
int main(int argc,char**argv){
 std::string mode=argv[1];
 if(mode=="flood"){
  NativeSession s;
  for(int i=0;i<10000;i++){s.Dispatch("position",std::to_string(i));s.Dispatch("subtitleText",std::to_string(i));}
  s.Dispatch("state","playing");s.Dispatch("error","bad");s.DispatchCompletion(0);
  assert(queue.size()<=1&&"JS 未消费时 NAPI 唤醒票据必须有界");
  drain();assert(calls==5&&delivered[3].type=="error"&&delivered.back().type=="fileEnd");
 }else if(mode=="exception"){
  NativeSession s;s.Dispatch("position","1");s.DispatchCompletion(0);throwNext=true;
  drain();assert(!pendingException&&clearedExceptions==1&&calls==2&&delivered.back().type=="fileEnd");
 }else if(mode=="coalesced-order"){
  NativeSession s;s.Dispatch("position","old");s.Dispatch("state","playing");s.Dispatch("error","bad");
  s.Dispatch("position","new");s.DispatchCompletion(0);drain();
  assert(calls==4&&delivered[0].type=="state"&&delivered[1].type=="error"&&delivered[2].message=="new"&&delivered[3].type=="fileEnd");
  for(size_t i=1;i<delivered.size();i++)assert(delivered[i-1].sequence<delivered[i].sequence);
 }else if(mode=="overflow"||mode=="bytes"||mode=="oversized"){
  NativeSession s;
  if(mode=="overflow")for(int i=0;i<65;i++)s.Dispatch("state","playing");
  if(mode=="bytes")for(int i=0;i<5;i++)s.Dispatch("state",std::string(60000,'x'));
  if(mode=="oversized")s.Dispatch("subtitleText",std::string(1024*1024,'x'));
  assert(s.eventDeliveryFailed_&&std::string(s.OperationAdmissionError())=="PLAYER_EVENT_QUEUE_FULL");
  s.Dispatch("state","playing");s.DispatchCompletion(0);
  auto replaced=s.SetEventCallback((void*)1,(void*)1,1);assert(!replaced.ok&&std::string(replaced.code)=="PLAYER_EVENT_QUEUE_FULL");
  assert(queue.size()==1);drain();assert(calls==1&&delivered[0].type=="error"&&delivered[0].message=="PLAYER_EVENT_QUEUE_FULL");
 }else if(mode=="inflight-overflow"||mode=="inflight-close"||mode=="inflight-bytes"){
  NativeSession s;const int count=mode=="inflight-bytes"?4:64;const std::string message=mode=="inflight-bytes"?std::string(60000,'x'):"state";
  for(int i=0;i<count;i++)s.Dispatch("state",message);
  onCall=[&]{if(calls!=1)return;for(int i=0;i<count;i++)s.Dispatch("state",message);
   assert(queue.size()==1);if(mode=="inflight-close")s.CloseIsolatedCallbacks();else s.Dispatch("state",message);};
  drain();onCall={};assert(calls==(mode=="inflight-close"?1:count));drain();
  if(mode!="inflight-close")assert(calls==count+1&&delivered.back().message=="PLAYER_EVENT_QUEUE_FULL");else assert(calls==1);
 }else if(mode=="replacement-budget"||mode=="release-budget"){
  if(mode=="replacement-budget"){
   NativeSession s;for(int i=0;i<31;i++){s.Dispatch("state","old");assert(s.SetEventCallback((void*)1,(void*)1,1).ok);}
   auto r=s.SetEventCallback((void*)1,(void*)1,1);assert(!r.ok&&std::string(r.code)=="CALLBACK_RESOURCE_LIMIT");
   s.Dispatch("state","kept");assert(queue.size()==32);drain();assert(calls==1&&delivered.back().message=="kept");
  }else{
   for(int i=0;i<32;i++){NativeSession s;s.Dispatch("state","old");}
   NativeSession denied(1,false,false);auto r=denied.SetEventCallback((void*)1,(void*)1,1);assert(!r.ok&&std::string(r.code)=="CALLBACK_RESOURCE_LIMIT");
   // finalize 先于旧票据清理也不能提前归还全局额度。
   finalizeClosed();assert(!denied.SetEventCallback((void*)1,(void*)1,1).ok);
  }
  vidall::runtime::terminal=true;
  std::vector<std::unique_ptr<NativeSession>> recovery;
  for(int i=0;i<8;i++)recovery.push_back(std::make_unique<NativeSession>(2,true));
  NativeSession denied(2,true,false);assert(!denied.SetEventCallback((void*)1,(void*)1,1).ok);
  drain(true);finalizeClosed();vidall::runtime::terminal=false;
  NativeSession fresh;
 }else if(mode=="queued"){
  {NativeSession s;s.Dispatch("position","");s.Dispatch("state","");s.Dispatch("error","");s.CloseIsolatedCallbacks();}
  drain();assert(calls==0&&objects==0&&closed==1&&"清理后排队事件不得访问 JS");
 }else if(mode=="owner"){
  NativeSession s;s.isolation_=vidall::runtime::SessionIsolation::Acquire();s.CloseIsolatedCallbacks();
  char tag[]="vidall-ohcodec-quarantined",stage[]="close",error[]="-4";const char*args[]={tag,stage,error};
  mpv_event_client_message message{3,args};mpv_event event{MPV_EVENT_CLIENT_MESSAGE,&message};
  s.receive(&event);assert(s.isolation_->IsQuarantined()&&"关闭回调后仍须接收 owner 故障");
  assert(queue.empty()&&reported==1);
 }else if(mode=="replace"){
  NativeSession s;s.Dispatch("error","old");assert(s.SetEventCallback((void*)1,(void*)1,1).ok);
  s.Dispatch("state","new");drain();assert(calls==1&&objects==1);
 }else if(mode=="normal"){
  NativeSession s;s.Dispatch("position","");s.Dispatch("state","");s.Dispatch("error","");drain();assert(calls==3);
  s.CloseIsolatedCallbacks();s.Dispatch("error","");assert(queue.empty());
 }else if(mode=="null-env"){
  NativeSession s;s.Dispatch("error","");drain(true);assert(calls==0&&objects==0);
 }else if(mode=="environment"){
  int a,b;NativeSession old,fresh;
  old.environment_=vidall::runtime::EnvironmentLifetime::Open(&a);
  fresh.environment_=vidall::runtime::EnvironmentLifetime::Open(&b);
  old.Dispatch("position","");fresh.Dispatch("position","");
  vidall::runtime::EnvironmentLifetime::Close(old.environment_);drain();assert(calls==1&&objects==1);
  vidall::runtime::EnvironmentLifetime::Close(fresh.environment_);
 }else if(mode=="recovery"){
  NativeSession old;old.Dispatch("position","");old.Dispatch("error","");
  vidall::runtime::terminal=true;drain();assert(calls==0&&objects==0);
  NativeSession fresh(2,true);
  fresh.Dispatch("position","");drain();assert(calls==1&&objects==1);
 }else if(mode=="quarantined"){
  NativeSession s;s.isolation_=vidall::runtime::SessionIsolation::Acquire();
  s.Dispatch("position","");s.Dispatch("error","");s.isolation_->Quarantine();drain();assert(calls==1);
 }
 drain(true);finalizeClosed();
}
'''.replace('@@EVENT@@', extract('struct Event {')).replace('@@METHODS@@', methods).replace('@@OWNER@@', owner)
with tempfile.TemporaryDirectory(prefix='callback-cleanup-') as out:
    path = pathlib.Path(out)
    (path / 'test.cpp').write_text(code)
    subprocess.run(['clang++', '-std=c++17', '-pthread', '-fsanitize=address,undefined',
                    '-I' + str(ROOT / 'native/runtime'), str(path / 'test.cpp'), '-o', str(path / 'test')], check=True, timeout=120)
    results = []
    for case in ['exception','coalesced-order','overflow','bytes','oversized','inflight-overflow','inflight-bytes','inflight-close','replacement-budget','release-budget','flood', 'environment', 'recovery', 'queued', 'owner', 'replace', 'normal', 'null-env', 'quarantined']:
        result = subprocess.run([str(path / 'test'), case], capture_output=True, text=True, timeout=5)
        print(case, result.returncode, result.stderr.strip())
        results.append(result.returncode)
    assert not any(results), '真实回调清理回归失败'
