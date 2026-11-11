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
    'static void CallCallback(', 'void Dispatch(',
    'void CloseCallbackLocked()', 'void CloseIsolatedCallbacks()'])
owner = extract('if (isolation_ && event->event_id == MPV_EVENT_CLIENT_MESSAGE')
code = r'''
#include "session_isolation.h"
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
constexpr int napi_ok=0,napi_tsfn_nonblocking=0,napi_tsfn_release=0;
constexpr int napi_undefined=0,napi_function=1,MPV_EVENT_CLIENT_MESSAGE=16;
struct NativeResult {bool ok; uint64_t handle; const char* code;};
struct mpv_event_client_message {int num_args; char**args;};
struct mpv_event {int event_id; void* data;};
int calls=0, objects=0, closed=0;
std::vector<void*> queue;
int napi_typeof(napi_env,napi_value,napi_valuetype*t){*t=napi_function;return 0;}
template<class... T> int napi_create_threadsafe_function(T...){return 0;}
int napi_release_threadsafe_function(void*,int){closed++;return 0;}
int napi_call_threadsafe_function(void*,void*event,int){queue.push_back(event);return 0;}
napi_value CreateString(napi_env,const std::string&){return nullptr;}
int napi_create_object(napi_env,napi_value*){objects++;return 0;}
int napi_set_named_property(napi_env,napi_value,const char*,napi_value){return 0;}
int napi_create_int64(napi_env,int64_t,napi_value*){return 0;}
int napi_call_function(napi_env,napi_value,napi_value,size_t,napi_value*,napi_value*){calls++;return 0;}
namespace vidall::runtime {
bool terminal=false;
const char* SessionAdmissionError(uint64_t born,bool compatible){return !terminal||(born==2&&compatible)?nullptr:"PLAYER_TERMINAL";}
}
class NativeSession {
public:
@@EVENT@@;
uint64_t runtimeGeneration_=1;bool compatible_=false;
std::shared_ptr<vidall::runtime::SessionIsolation> isolation_;
std::shared_ptr<std::atomic<bool>> callbackOpen_=std::make_shared<std::atomic<bool>>(true);
std::mutex callbackMutex_;
std::atomic<bool> stopEvents_{false},released_{false};
std::atomic<uint64_t> eventEpoch_{1},eventSequence_{0},generation_{1},surfaceSessionHandle_{1};
void* eventTsfn_=this;
@@METHODS@@
void receive(mpv_event*event){if(!stopEvents_){do { @@OWNER@@ }while(false);}}
};
void drain(bool nullEnv=false){auto pending=std::move(queue);queue.clear();for(auto*p:pending)
 NativeSession::CallCallback(nullEnv?nullptr:(void*)1,(void*)1,nullptr,p);}
int main(int argc,char**argv){
 std::string mode=argv[1];
 if(mode=="queued"){
  {NativeSession s;s.Dispatch("position","");s.Dispatch("state","");s.Dispatch("error","");s.CloseIsolatedCallbacks();}
  drain();assert(calls==0&&objects==0&&closed==1&&"清理后排队事件不得访问 JS");
 }else if(mode=="owner"){
  NativeSession s;s.isolation_=vidall::runtime::SessionIsolation::Acquire();s.CloseIsolatedCallbacks();
  char tag[]="vidall-ohcodec-quarantined",stage[]="close",error[]="-4";char*args[]={tag,stage,error};
  mpv_event_client_message message{3,args};mpv_event event{MPV_EVENT_CLIENT_MESSAGE,&message};
  s.receive(&event);assert(s.isolation_->IsQuarantined()&&"关闭回调后仍须接收 owner 故障");
  assert(queue.empty());
 }else if(mode=="replace"){
  NativeSession s;s.Dispatch("error","old");assert(s.SetEventCallback((void*)1,(void*)1,1).ok);
  s.eventTsfn_=&s;s.Dispatch("state","new");drain();assert(calls==1&&objects==1);
 }else if(mode=="normal"){
  NativeSession s;s.Dispatch("position","");s.Dispatch("state","");s.Dispatch("error","");drain();assert(calls==3);
  s.CloseIsolatedCallbacks();s.Dispatch("error","");assert(queue.empty());
 }else if(mode=="null-env"){
  NativeSession s;s.Dispatch("error","");drain(true);assert(calls==0&&objects==0);
 }else if(mode=="recovery"){
  NativeSession old;old.Dispatch("position","");old.Dispatch("error","");
  vidall::runtime::terminal=true;drain();assert(calls==0&&objects==0);
  NativeSession fresh;fresh.runtimeGeneration_=2;fresh.compatible_=true;
  fresh.Dispatch("position","");drain();assert(calls==1&&objects==1);
 }else if(mode=="quarantined"){
  NativeSession s;s.isolation_=vidall::runtime::SessionIsolation::Acquire();
  s.Dispatch("position","");s.Dispatch("error","");s.isolation_->Quarantine();drain();assert(calls==1);
 }
}
'''.replace('@@EVENT@@', extract('struct Event {')).replace('@@METHODS@@', methods).replace('@@OWNER@@', owner)
with tempfile.TemporaryDirectory(prefix='callback-cleanup-') as out:
    path = pathlib.Path(out)
    (path / 'test.cpp').write_text(code)
    subprocess.run(['clang++', '-std=c++17', '-pthread', '-fsanitize=address,undefined',
                    '-I' + str(ROOT / 'native/runtime'), str(path / 'test.cpp'), '-o', str(path / 'test')], check=True, timeout=120)
    results = []
    for case in ['recovery', 'queued', 'owner', 'replace', 'normal', 'null-env', 'quarantined']:
        result = subprocess.run([str(path / 'test'), case], capture_output=True, text=True, timeout=5)
        print(case, result.returncode, result.stderr.strip())
        results.append(result.returncode)
    assert not any(results), '真实回调清理回归失败'
