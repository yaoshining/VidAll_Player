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
functions=function('std::shared_ptr<NativeSession> FindSession(')+'\n'+s[s.index('struct SessionCreation {'):s.index('napi_value ConfigureRuntime(')]+'\n'+'\n'.join(function(x) for x in ['napi_value ConfigureRuntime(', 'napi_value CreateSession(', 'napi_value ReleaseSession(', 'void CleanupSessions('])
prefix=r'''
#include "session_isolation.h"
#include "session_budget.h"
#include "work_budget.h"
#include "environment_lifetime.h"
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
std::atomic<int> creates{0},initializes{0},releases{0},destructs{0};bool terminal=false,configured=false,createRace=false,releaseRace=false;
bool preserve=false,recoveryReady=false;
std::atomic<bool> blockConfigure{false},configureEntered{false},configureDone{false};
namespace vidall::runtime {
enum class TerminalPolicy {ControlledAppExit,PreserveHost};
const char* Configure(const std::string&,const std::string&,unsigned,TerminalPolicy){configureEntered=true;while(blockConfigure)std::this_thread::yield();configureDone=true;return nullptr;}
struct Status{int state;};Status Snapshot(){return {terminal?4:configured?2:0};}
const char* AdmissionError(bool recovery=false){if(terminal&&preserve&&recovery)return recoveryReady?nullptr:"PLAYER_RECOVERY_PENDING";return terminal?"PLAYER_TERMINAL":configured?nullptr:"RUNTIME_NOT_READY";}
std::uint64_t CaptureGeneration(){return terminal?(preserve&&recoveryReady?2:0):configured?1:0;}
const char* SessionAdmissionError(std::uint64_t born,bool compatible){if(terminal&&born==2&&compatible)return AdmissionError(true);return born==1?AdmissionError():"RUNTIME_NOT_READY";}
void ParkIfTerminal(bool recovery=false){if(terminal&&!(preserve&&recoveryReady&&recovery)){puts("FAIL terminal reached destructor");std::abort();}}}
bool scopedTest=false, slowClose=false;
std::string receivedMode;
std::atomic<bool> resumeOld{false}, oldReturned{false};
std::atomic<int> closedCallbacks{0};
std::atomic<bool> blockDestructor{false}, destructionDone{false},blockInitialize{false},initializeEntered{false};
std::atomic<int> completedDestructs{0};
void waitDestruction(){while(!destructionDone.load())std::this_thread::yield();}
struct NativeSession {struct CompletionMarker {~CompletionMarker(){completedDestructs++;}} completionMarker;std::shared_ptr<vidall::runtime::EnvironmentLifetime> environment=vidall::runtime::EnvironmentLifetime::Current(nullptr);
void SetEnvironment(std::shared_ptr<vidall::runtime::EnvironmentLifetime> value){environment=std::move(value);}
auto Environment()const{return environment;}
const std::uint64_t born=vidall::runtime::CaptureGeneration();bool compatible=false;
std::uint64_t RuntimeGeneration()const{return born;}
const char* RuntimeAdmissionError()const{return vidall::runtime::SessionAdmissionError(born,compatible);}
bool IsRecoverySession()const{return born>1&&compatible;}
std::shared_ptr<vidall::runtime::SessionBudget> budget;void SetBudget(std::shared_ptr<vidall::runtime::SessionBudget> b){budget=std::move(b);}std::shared_ptr<vidall::runtime::SessionIsolation> isolation;std::shared_ptr<vidall::runtime::SessionIsolation> executor;auto Isolation(){return isolation;}auto Executor(){return isolation?isolation:executor;}void SetExecutor(std::shared_ptr<vidall::runtime::SessionIsolation> value){executor=std::move(value);}void CloseIsolatedCallbacks(){closedCallbacks++;} bool closed=false;NativeSession(){creates++;if(createRace)terminal=true;}~NativeSession(){while(blockDestructor.load())std::this_thread::yield();destructs++;vidall::runtime::ParkIfTerminal(IsRecoverySession());Release();vidall::runtime::ParkIfTerminal(IsRecoverySession());destructionDone=true;}bool Initialize(const std::string&,const std::string&,const std::string&,const std::string&,const std::string& mode){receivedMode=mode;compatible=mode=="compatible";initializes++;initializeEntered=true;while(blockInitialize)std::this_thread::yield();if(scopedTest){if(mode=="compatible"){if(!executor)executor=vidall::runtime::SessionIsolation::Acquire(vidall::runtime::SessionIsolation::Pool::Compatible);}else isolation=vidall::runtime::SessionIsolation::Acquire();}return true;}void Release(){if(closed)return;closed=true;releases++;if(releaseRace)terminal=true;
 if(scopedTest&&Executor()){if(!slowClose)Executor()->Quarantine();while(!resumeOld.load())std::this_thread::sleep_for(std::chrono::milliseconds(1));Executor()->FinishedRelease();oldReturned=true;}}};
std::mutex gSessionsMutex;std::unordered_map<std::uint64_t,std::shared_ptr<NativeSession>>gSessions;std::uint64_t gNextSessionId=1;
std::vector<std::string> arguments;
int napi_get_cb_info(napi_env,napi_callback_info,size_t*argc,napi_value*args,void*,void*){
 *argc=std::min(*argc,arguments.size());for(size_t i=0;i<*argc;i++)args[i]=&arguments[i];return napi_ok;
}
int napi_get_value_int64(napi_env,napi_value value,int64_t*out){*out=std::stoll(*static_cast<std::string*>(value));return napi_ok;}
bool ReadString(napi_env,napi_value value,std::string& out){if(!value)return false;out=*static_cast<std::string*>(value);return true;}
bool GetArguments(napi_env env,napi_callback_info info,size_t count,napi_value*out,size_t&argc){if(count==1){argc=1;return true;}argc=count;return napi_get_cb_info(env,info,&argc,out,nullptr,nullptr)==napi_ok;}
std::uint64_t selectedHandle=1;
bool ReadHandle(napi_env,napi_value,std::uint64_t&h){h=selectedHandle;return true;}
NativeResult last{false,0,"NONE"};napi_value CreateResult(napi_env,NativeResult r){last=r;return nullptr;}
napi_value CreateString(napi_env,const std::string&){return nullptr;}
std::atomic<int> asyncWorks{0};
struct Job{napi_env env;void(*execute)(napi_env,void*);void(*complete)(napi_env,napi_status,void*);void*data;};using napi_async_work=Job*;std::vector<Job*>jobs;
int napi_create_promise(napi_env,napi_deferred*d,napi_value*p){*d=(void*)1;*p=(void*)1;return 0;}
int napi_resolve_deferred(napi_env,napi_deferred,napi_value){return 0;}
int napi_create_async_work(napi_env env,napi_value,napi_value,void(*e)(napi_env,void*),void(*c)(napi_env,napi_status,void*),void*d,Job**w){*w=new Job{env,e,c,d};asyncWorks++;return 0;}
int napi_queue_async_work(napi_env,Job*w){jobs.push_back(w);return 0;}
int napi_delete_async_work(napi_env,Job*w){delete w;asyncWorks--;return 0;}
void run(){auto current=jobs;jobs.clear();for(auto*w:current){std::thread t([=]{w->execute(w->env,w->data);});t.join();w->complete(w->env,0,w->data);}}
'''
main=r'''
void CleanupTest(napi_env env){CleanupSessions(new std::shared_ptr<vidall::runtime::EnvironmentLifetime>(vidall::runtime::EnvironmentLifetime::Current(env)));}
int main(int argc,char**argv){vidall::runtime::EnvironmentLifetime::Open(nullptr);std::string mode=argv[1];if(mode=="create-unconfigured"){CreateSession(nullptr,nullptr);if(creates||!jobs.empty()) {puts("FAIL created before runtime");return 1;}}
else if(mode=="isolated-release" || mode=="slow-release" || mode=="compatible-slow-release"){
 configured=true;scopedTest=true;slowClose=mode!="isolated-release";bool compatible=mode=="compatible-slow-release";
 if(compatible)arguments={"","no","","","compatible"};
 CreateSession(nullptr,nullptr);run();if(!last.ok||last.handle!=1||!FindSession(1)->Executor())return 1;
 auto before=std::chrono::steady_clock::now();
 ReleaseSession(nullptr,nullptr);if(releases!=0)return 1;run();
 auto elapsed=std::chrono::steady_clock::now()-before;
 if(slowClose&&(elapsed<std::chrono::milliseconds(4800)||elapsed>std::chrono::milliseconds(6500)))return 1;
 if(!last.ok||FindSession(1)||closedCallbacks!=1||destructs||oldReturned)return 1;
 CreateSession(nullptr,nullptr);run();if(!last.ok||last.handle!=2||!FindSession(2)->Executor())return 1;
 QueueNative(nullptr,2,[]{return NativeResult{true,2,"SECOND_SESSION"};});run();
 if(!last.ok||std::string(last.code)!="SECOND_SESSION"||terminal)return 1;
 auto pool=compatible?vidall::runtime::SessionIsolation::Pool::Compatible:vidall::runtime::SessionIsolation::Pool::Hardware;
 if(vidall::runtime::SessionIsolation::Acquire(pool))return 1;
 resumeOld=true;while(!oldReturned.load())std::this_thread::yield();
 if(bool(vidall::runtime::SessionIsolation::Acquire(pool))!=slowClose)return 1;
 // Test process ends with an intentionally retained generation, as on the device.
 puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="cleanup-isolated"){
 configured=true;scopedTest=true;
 CreateSession(nullptr,nullptr);run();auto retained=FindSession(1);
 retained->Isolation()->Quarantine();
 CleanupTest(nullptr);
 if(closedCallbacks!=1||!gSessions.empty()||destructs||releases)return 1;
 retained.reset();
 puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="cleanup-plain-blocked"){
 configured=true;gSessions[1]=std::shared_ptr<NativeSession>(new NativeSession(),DeleteSession);
 blockDestructor=true;
 std::thread unblock([]{std::this_thread::sleep_for(std::chrono::milliseconds(500));blockDestructor=false;});
 auto start=std::chrono::steady_clock::now();CleanupTest(nullptr);
 auto elapsed=std::chrono::steady_clock::now()-start;
 bool returned=elapsed<std::chrono::milliseconds(200);
 unblock.join();waitDestruction();
 if(!returned){puts("FAIL cleanup waited for GPU destructor");return 1;}
 if(closedCallbacks!=1||!gSessions.empty()||destructs!=1||releases!=1)return 1;
}
else if(mode=="cleanup-plain-retained" || mode=="cleanup-plain-terminal"){
 configured=true;gSessions[1]=std::shared_ptr<NativeSession>(new NativeSession(),DeleteSession);
 auto retained=FindSession(1);terminal=mode=="cleanup-plain-terminal";
 CleanupTest(nullptr);
 if(closedCallbacks!=1){puts("FAIL retained callback still live after cleanup");std::fflush(stdout);std::_Exit(1);}
 if(destructs||releases||gSessions.empty()==terminal)return 1;
 retained.reset();
 if(terminal){puts("PASS");std::fflush(stdout);std::_Exit(0);}
 waitDestruction();if(destructs!=1||releases!=1)return 1;
}
else if(mode=="configure-timeout"){
 arguments={"/app","config","1000","preserve-host"};blockConfigure=true;
 auto before=std::chrono::steady_clock::now();ConfigureRuntime(nullptr,nullptr);run();
 auto elapsed=std::chrono::steady_clock::now()-before;
 if(last.ok||std::string(last.code)!="NATIVE_WORK_TIMEOUT"||!configureEntered||configureDone||
 elapsed<std::chrono::milliseconds(4800)||elapsed>std::chrono::milliseconds(6500))return 1;
 QueueNative(nullptr,0,[]{return NativeResult{true,0,"RESPONSIVE"};},false);run();
 if(!last.ok||std::string(last.code)!="RESPONSIVE")return 1;
 blockConfigure=false;while(!configureDone)std::this_thread::yield();
 ConfigureRuntime(nullptr,nullptr);run();if(!last.ok)return 1;
}
else if(mode=="occupied-compatible-pool"){
 configured=true;preserve=true;arguments={"","no","","","compatible"};
 for(int i=0;i<2;i++){CreateSession(nullptr,nullptr);run();if(!last.ok)return 1;}
 terminal=true;recoveryReady=true;
 for(int i=0;i<2;i++){CreateSession(nullptr,nullptr);run();if(!last.ok)return 1;}
 CreateSession(nullptr,nullptr);run();if(last.ok||creates!=4||std::string(last.code)!="SESSION_RESOURCE_LIMIT")return 1;
 selectedHandle=3;ReleaseSession(nullptr,nullptr);run();
 if(!last.ok||FindSession(3))return 1;
 while(completedDestructs!=1)std::this_thread::yield();
 CreateSession(nullptr,nullptr);run();if(!last.ok||creates!=5)return 1;
 CleanupTest(nullptr);while(completedDestructs!=3)std::this_thread::yield();
 if(gSessions.size()!=2)return 1;
 puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="create-boundary-generation"){
 configured=true;preserve=true;terminal=true;recoveryReady=true;
 arguments={"","no","","","compatible","1"};CreateSession(nullptr,nullptr);run();
 if(creates||!gSessions.empty()||last.ok||std::string(last.code)!="PLAYER_TERMINAL")return 1;
}
else if(mode=="create-cancelled-result"){
 configured=true;CreateSession(nullptr,nullptr);auto job=jobs.back();jobs.clear();
 std::thread execute([&]{job->execute(job->env,job->data);});execute.join();
 if(gSessions.size()!=1)return 1;
 job->complete(job->env,1,job->data);waitDestruction();
 if(!gSessions.empty()||last.ok||asyncWorks||destructs!=1)return 1;
 CreateSession(nullptr,nullptr);run();if(!last.ok||last.handle!=2)return 1;
 CleanupTest(nullptr);puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="create-generation-race"){
 configured=true;preserve=true;arguments={"","no","","","compatible"};CreateSession(nullptr,nullptr);
 terminal=true;recoveryReady=true;run();
 if(creates||!gSessions.empty()||last.ok||std::string(last.code)!="PLAYER_TERMINAL")return 1;
}
else if(mode=="create-timeout"){
 configured=true;blockInitialize=true;CreateSession(nullptr,nullptr);
 auto start=std::chrono::steady_clock::now();run();
 if(std::chrono::steady_clock::now()-start>std::chrono::milliseconds(6500))return 1;
 if(last.ok||std::string(last.code)!="NATIVE_WORK_TIMEOUT"||!gSessions.empty()||!initializeEntered)return 1;
 blockInitialize=false;waitDestruction();
 if(!gSessions.empty()||creates!=1||destructs!=1)return 1;
 CreateSession(nullptr,nullptr);run();if(!last.ok||last.handle!=1)return 1;
 CleanupTest(nullptr);puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="environment-creating"){
 configured=true;blockInitialize=true;CreateSession(nullptr,nullptr);
 std::thread pending(run);while(!initializeEntered)std::this_thread::yield();
 CleanupTest(nullptr);blockInitialize=false;pending.join();waitDestruction();
 if(creates!=1||destructs!=1||!gSessions.empty()||asyncWorks!=0)return 1;
 vidall::runtime::EnvironmentLifetime::Open(nullptr);CreateSession(nullptr,nullptr);run();
 if(!last.ok||last.handle!=1)return 1;
 CleanupTest(nullptr);puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="environment-scope"){
 configured=true;int a,b;vidall::runtime::EnvironmentLifetime::Open(&a);vidall::runtime::EnvironmentLifetime::Open(&b);
 CreateSession(&a,nullptr);run();if(!last.ok)return 1;
 CreateSession(&b,nullptr);run();if(!last.ok)return 1;
 if(!FindSession(1,&a)||FindSession(1,&b)||!FindSession(2,&b))return 1;
 QueueNative(&b,1,[]{std::abort();return NativeResult{};});run();if(last.ok)return 1;
 CleanupTest(&a);waitDestruction();if(FindSession(1,&a)||!FindSession(2,&b)||closedCallbacks!=1||destructs!=1)return 1;
 // 清理前排队但尚未创建的任务不能在清理后发布会话。
 CreateSession(&b,nullptr);CleanupTest(&b);run();
 if(!gSessions.empty()||creates!=2)return 1;
 CreateSession(&b,nullptr);if(last.ok||std::string(last.code)!="RUNTIME_ENV_CLOSED")return 1;
 puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="recovery-reserve"){
 configured=true;preserve=true;
 for(int i=0;i<32;i++)QueueNative(nullptr,0,[]{std::abort();return NativeResult{};});
 terminal=true;recoveryReady=true;arguments={"","no","","","compatible"};
 CreateSession(nullptr,nullptr);if(jobs.size()!=33)return 1;run();if(!last.ok)return 1;
 for(int i=0;i<8;i++)QueueNative(nullptr,1,[]{return NativeResult{true,1,"RECOVERY"};});
 if(jobs.size()!=8)return 1;
 QueueNative(nullptr,1,[]{std::abort();return NativeResult{};});
 if(jobs.size()!=8||last.ok||std::string(last.code)!="NATIVE_WORK_QUEUE_FULL")return 1;
 run();CleanupTest(nullptr);waitDestruction();if(destructs!=1)return 1;
}
else if(mode=="recovery-generation"){
 configured=true;preserve=true;arguments={"","no","","","compatible"};
 CreateSession(nullptr,nullptr);run();if(!last.ok)return 1;
 terminal=true;CreateSession(nullptr,nullptr);run();
 if(last.ok||creates!=1||std::string(last.code)!="PLAYER_RECOVERY_PENDING")return 1;
 recoveryReady=true;arguments[4]="standard";CreateSession(nullptr,nullptr);run();
 if(last.ok||creates!=1)return 1;
 arguments[4]="compatible";CreateSession(nullptr,nullptr);run();
 if(!last.ok||last.handle!=2||creates!=2)return 1;
 QueueNative(nullptr,1,[]{std::abort();return NativeResult{};});run();
 if(last.ok||std::string(last.code)!="PLAYER_TERMINAL")return 1;
 QueueNative(nullptr,2,[]{return NativeResult{true,2,"NEW_SESSION"};});run();
 if(!last.ok||std::string(last.code)!="NEW_SESSION")return 1;
 CleanupTest(nullptr);
 if(gSessions.size()!=1||!gSessions.count(1)||FindSession(1)||FindSession(2)||closedCallbacks!=2)return 1;
 waitDestruction();if(destructs!=1)return 1;
 puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="work-budget"){
 configured=true;
 for(int i=0;i<32;i++)QueueNative(nullptr,0,[]{return NativeResult{true,0,"OK"};});
 if(jobs.size()!=32)return 1;
 QueueNative(nullptr,0,[]{return NativeResult{true,0,"UNEXPECTED"};});
 if(jobs.size()!=32||last.ok||std::string(last.code)!="NATIVE_WORK_QUEUE_FULL")return 1;
 for(int i=0;i<8;i++)QueueNative(nullptr,0,[]{return NativeResult{true,0,"OK"};},true,true);
 if(jobs.size()!=40)return 1;
 QueueNative(nullptr,0,[]{return NativeResult{true,0,"UNEXPECTED"};},true,true);
 if(jobs.size()!=40||last.ok)return 1;
 run();QueueNative(nullptr,0,[]{return NativeResult{true,0,"REUSED"};});run();
 if(!last.ok||std::string(last.code)!="REUSED")return 1;
}
else if(mode=="session-budget"){
 configured=true;
 for(int i=0;i<6;i++){CreateSession(nullptr,nullptr);run();if(!last.ok)return 1;}
 CreateSession(nullptr,nullptr);run();if(last.ok||creates!=6||std::string(last.code)!="SESSION_RESOURCE_LIMIT")return 1;
 arguments={"","no","","","compatible"};
 for(int i=0;i<2;i++){CreateSession(nullptr,nullptr);run();if(!last.ok)return 1;}
 CreateSession(nullptr,nullptr);run();if(last.ok||creates!=8)return 1;
 blockDestructor=true;gSessions.clear();arguments.clear();
 CreateSession(nullptr,nullptr);run();if(last.ok||creates!=8)return 1;
 blockDestructor=false;while(destructs.load()!=8)std::this_thread::yield();
 // 等预算从真正完成的析构归还，不能只等析构入口计数。
 for(int i=0;i<1000;i++){
   CreateSession(nullptr,nullptr);run();if(last.ok)break;
   std::this_thread::sleep_for(std::chrono::milliseconds(1));
 }
 if(!last.ok)return 1;
 gSessions.clear();puts("PASS");std::fflush(stdout);std::_Exit(0);
}
else if(mode=="create-compatible" || mode=="create-invalid-mode" || mode=="create-legacy"){
 configured=true;arguments={"","auto","",""};
 if(mode!="create-legacy")arguments.push_back(mode=="create-compatible"?"compatible":"invalid");
 CreateSession(nullptr,nullptr);if(creates)return 1;run();
 if(mode=="create-invalid-mode"){
   if(last.ok||creates||std::string(last.code)!="INVALID_PLAYBACK_MODE")return 1;
 }else{
   if(!last.ok||receivedMode!=(mode=="create-compatible"?"compatible":"standard"))return 1;
   gSessions.clear();waitDestruction();
 }
}
else if(mode=="create-ui"){configured=true;CreateSession(nullptr,nullptr);if(creates){puts("FAIL native create executed synchronously on UI");return 1;}run();if(creates!=1||!last.ok)return 1;gSessions.clear();waitDestruction();}
else if(mode=="create-terminal-race"){configured=true;createRace=true;CreateSession(nullptr,nullptr);run();if(initializes||destructs||last.ok)return 1;}
else{configured=true;gSessions[1]=std::shared_ptr<NativeSession>(new NativeSession(),DeleteSession);terminal=mode!="normal-release"&&mode!="release-terminal-race";releaseRace=mode=="release-terminal-race";
 if(mode=="cleanup-terminal")CleanupTest(nullptr);else{ReleaseSession(nullptr,nullptr);run();}
 if(mode=="normal-release"){waitDestruction();if(releases!=1||destructs!=1||!gSessions.empty())return 1;}
 else if(mode=="release-terminal-race"){if(releases!=1||destructs||gSessions.empty())return 1;}
 else if(releases||destructs||gSessions.empty()){printf("FAIL parent release=%d destructor=%d retained=%zu\n",releases.load(),destructs.load(),gSessions.size());return 1;}}
puts("PASS");return 0;}
'''
if '--mutant-delete' in sys.argv:
 functions=functions.replace('if (vidall::runtime::Snapshot().state == 4) return;', 'if (false) return;')
(out/'harness.cpp').write_text(prefix+functions+main)
subprocess.run(['clang++','-std=c++17','-pthread','-I'+str(root/'native/runtime'),str(out/'harness.cpp'),'-o',str(out/'test')],check=True)
rows=[]
for c in ['configure-timeout','occupied-compatible-pool','create-boundary-generation','create-cancelled-result','create-generation-race','create-timeout','environment-creating','environment-scope','recovery-reserve','recovery-generation','work-budget','compatible-slow-release','session-budget','create-compatible','create-invalid-mode','create-legacy','create-unconfigured','create-ui','cleanup-isolated','cleanup-plain-blocked','cleanup-plain-retained','cleanup-plain-terminal','isolated-release','slow-release','release-terminal','cleanup-terminal','create-terminal-race','release-terminal-race','normal-release']:
 p=subprocess.run([str(out/'test'),c],capture_output=True,text=True,timeout=10 if c in ['configure-timeout','create-timeout','slow-release','compatible-slow-release'] else 3);rows.append({'case':c,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});print(c,p.returncode,p.stdout.strip())
(out/'results.json').write_text(json.dumps({'sourceSHA256':hashlib.sha256(src.read_bytes()).hexdigest(),'method':'actual-entry-slices-platform-and-session-stubs','results':rows},indent=2)+'\n')

passed=all(row['exit']==0 and row['stdout'].strip()=='PASS' and 'FAIL' not in row['stdout']+row['stderr'] for row in rows)
raise SystemExit(0 if passed else 1)
