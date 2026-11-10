#!/usr/bin/env python3
"""逐字编译真实 NAPI 创建、释放与环境清理入口；平台转换和底层 Session 用计数替身。"""
import pathlib, subprocess, json, sys, hashlib
root=pathlib.Path(__file__).resolve().parents[2]
src=root/'packages/vidall-player/src/main/cpp/napi_init.cpp'
s=src.read_text()
def function(signature):
 start=s.index(signature); b=s.index('{',start); depth=1;i=b+1
 while depth:
  depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[start:i]
out=pathlib.Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-B',str(root/'native/tests/ohcodec-fence/initialize.test.py')],check=True)
subprocess.run([sys.executable,'-B',str(root/'native/tests/ohcodec-fence/callback-cleanup.test.py')],check=True)
functions=s[s.index('struct NativeWork {'):s.index('napi_value ConfigureRuntime(')]+'\n'+'\n'.join(function(x) for x in ['napi_value CreateSession(', 'napi_value ReleaseSession(', 'void CleanupSessions('])
prefix=r'''
#include "session_isolation.h"
#include <memory>
#include <mutex>
#include <unordered_map>
#include <string>
#include <cstdint>
#include <cstdio>
#include <thread>
#include <functional>
#include <vector>
#include <cstdlib>
#define VIDALL_MPV_AVAILABLE 1
#define OH_LOG_Print(...) ((void)0)
using napi_env=void*;using napi_value=void*;using napi_callback_info=void*;using napi_deferred=void*;using napi_status=int;
const int napi_ok=0;
struct NativeResult {bool ok;std::uint64_t handle;const char*code;};
int creates=0,initializes=0,releases=0,destructs=0;bool terminal=false,configured=false,createRace=false,releaseRace=false;
namespace vidall::runtime {struct Status{int state;};Status Snapshot(){return {terminal?4:configured?2:0};}const char*AdmissionError(){return terminal?"PLAYER_TERMINAL":configured?nullptr:"RUNTIME_NOT_READY";}void ParkIfTerminal(){if(terminal){puts("FAIL terminal reached destructor");std::abort();}}}
bool scopedTest=false, slowClose=false;
std::atomic<bool> resumeOld{false}, oldReturned{false};
std::atomic<int> closedCallbacks{0};
struct NativeSession {std::shared_ptr<vidall::runtime::SessionIsolation> isolation;auto Isolation(){return isolation;}void CloseIsolatedCallbacks(){closedCallbacks++;} bool closed=false;NativeSession(){creates++;if(createRace)terminal=true;}~NativeSession(){destructs++;vidall::runtime::ParkIfTerminal();Release();vidall::runtime::ParkIfTerminal();}bool Initialize(const std::string&,const std::string&,const std::string&,const std::string&){initializes++;if(scopedTest)isolation=vidall::runtime::SessionIsolation::Acquire();return true;}void Release(){if(closed)return;closed=true;releases++;if(releaseRace)terminal=true;
 if(scopedTest&&isolation){if(!slowClose)isolation->Quarantine();while(!resumeOld.load())std::this_thread::sleep_for(std::chrono::milliseconds(1));isolation->FinishedRelease();oldReturned=true;}}};
std::mutex gSessionsMutex;std::unordered_map<std::uint64_t,std::shared_ptr<NativeSession>>gSessions;std::uint64_t gNextSessionId=1;
std::shared_ptr<NativeSession> FindSession(std::uint64_t id){std::lock_guard<std::mutex> lock(gSessionsMutex);auto it=gSessions.find(id);return it==gSessions.end()?nullptr:it->second;}
int napi_get_cb_info(napi_env,napi_callback_info,size_t*,napi_value*,void*,void*){return napi_ok;}
bool ReadString(napi_env,napi_value,std::string&){return true;}
bool GetArguments(napi_env,napi_callback_info,size_t,napi_value*,size_t&argc){argc=1;return true;}
bool ReadHandle(napi_env,napi_value,std::uint64_t&h){h=1;return true;}
NativeResult last{false,0,"NONE"};napi_value CreateResult(napi_env,NativeResult r){last=r;return nullptr;}
napi_value CreateString(napi_env,const std::string&){return nullptr;}
struct Job{void(*execute)(napi_env,void*);void(*complete)(napi_env,napi_status,void*);void*data;};using napi_async_work=Job*;std::vector<Job*>jobs;
int napi_create_promise(napi_env,napi_deferred*d,napi_value*p){*d=(void*)1;*p=(void*)1;return 0;}
int napi_resolve_deferred(napi_env,napi_deferred,napi_value){return 0;}
int napi_create_async_work(napi_env,napi_value,napi_value,void(*e)(napi_env,void*),void(*c)(napi_env,napi_status,void*),void*d,Job**w){*w=new Job{e,c,d};return 0;}
int napi_queue_async_work(napi_env,Job*w){jobs.push_back(w);return 0;}
int napi_delete_async_work(napi_env,Job*w){delete w;return 0;}
void run(){auto current=jobs;jobs.clear();for(auto*w:current){std::thread t([=]{w->execute(nullptr,w->data);});t.join();w->complete(nullptr,0,w->data);}}
'''
main=r'''
int main(int argc,char**argv){std::string mode=argv[1];if(mode=="create-unconfigured"){CreateSession(nullptr,nullptr);if(creates||!jobs.empty()) {puts("FAIL created before runtime");return 1;}}
else if(mode=="isolated-release" || mode=="slow-release"){
 configured=true;scopedTest=true;slowClose=mode=="slow-release";
 CreateSession(nullptr,nullptr);run();if(!last.ok||last.handle!=1||!FindSession(1)->Isolation())return 1;
 auto before=std::chrono::steady_clock::now();
 ReleaseSession(nullptr,nullptr);if(releases!=0)return 1;run();
 auto elapsed=std::chrono::steady_clock::now()-before;
 if(slowClose&&(elapsed<std::chrono::milliseconds(4800)||elapsed>std::chrono::milliseconds(6500)))return 1;
 if(!last.ok||FindSession(1)||closedCallbacks!=1||destructs||oldReturned)return 1;
 CreateSession(nullptr,nullptr);run();if(!last.ok||last.handle!=2||!FindSession(2)->Isolation())return 1;
 QueueNative(nullptr,2,[]{return NativeResult{true,2,"SECOND_SESSION"};});run();
 if(!last.ok||std::string(last.code)!="SECOND_SESSION"||terminal)return 1;
 if(vidall::runtime::SessionIsolation::Acquire())return 1;
 resumeOld=true;while(!oldReturned.load())std::this_thread::yield();
 if(bool(vidall::runtime::SessionIsolation::Acquire())!=slowClose)return 1;
 // Test process ends with an intentionally retained generation, as on the device.
 puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="cleanup-isolated"){
 configured=true;scopedTest=true;
 CreateSession(nullptr,nullptr);run();auto retained=FindSession(1);
 retained->Isolation()->Quarantine();
 CleanupSessions(nullptr);
 if(closedCallbacks!=1||!gSessions.empty()||destructs||releases)return 1;
 retained.reset();
 puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="create-ui"){configured=true;CreateSession(nullptr,nullptr);if(creates){puts("FAIL native create executed synchronously on UI");return 1;}run();if(creates!=1||!last.ok)return 1;gSessions.clear();}
else if(mode=="create-terminal-race"){configured=true;createRace=true;CreateSession(nullptr,nullptr);run();if(initializes||destructs||last.ok)return 1;}
else{configured=true;gSessions[1]=std::shared_ptr<NativeSession>(new NativeSession(),DeleteSession);terminal=mode!="normal-release"&&mode!="release-terminal-race";releaseRace=mode=="release-terminal-race";
 if(mode=="cleanup-terminal")CleanupSessions(nullptr);else{ReleaseSession(nullptr,nullptr);run();}
 if(mode=="normal-release"){if(releases!=1||destructs!=1||!gSessions.empty())return 1;}
 else if(mode=="release-terminal-race"){if(releases!=1||destructs||gSessions.empty())return 1;}
 else if(releases||destructs||gSessions.empty()){printf("FAIL parent release=%d destructor=%d retained=%zu\n",releases,destructs,gSessions.size());return 1;}}
puts("PASS");return 0;}
'''
if '--mutant-delete' in sys.argv:
 functions=functions.replace('if (vidall::runtime::Snapshot().state == 4) return;', 'if (false) return;')
(out/'harness.cpp').write_text(prefix+functions+main)
subprocess.run(['clang++','-std=c++17','-pthread','-I'+str(root/'native/runtime'),str(out/'harness.cpp'),'-o',str(out/'test')],check=True)
rows=[]
for c in ['create-unconfigured','create-ui','cleanup-isolated','isolated-release','slow-release','release-terminal','cleanup-terminal','create-terminal-race','release-terminal-race','normal-release']:
 p=subprocess.run([str(out/'test'),c],capture_output=True,text=True,timeout=10 if c=='slow-release' else 3);rows.append({'case':c,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});print(c,p.returncode,p.stdout.strip())
(out/'results.json').write_text(json.dumps({'sourceSHA256':hashlib.sha256(src.read_bytes()).hexdigest(),'method':'actual-entry-slices-platform-and-session-stubs','results':rows},indent=2)+'\n')

passed=all(row['exit']==0 and row['stdout'].strip()=='PASS' and 'FAIL' not in row['stdout']+row['stderr'] for row in rows)
raise SystemExit(0 if passed else 1)
