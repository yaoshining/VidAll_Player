"""编译真实 NAPI runtime 配置和状态入口，验证旧/新签名及恢复状态序列化。"""
from pathlib import Path
import subprocess,tempfile,re,json
root=Path(__file__).resolve().parents[3]
s=(root/'packages/vidall-player/src/main/cpp/napi_init.cpp').read_text()
def extract(signature):
 masked=re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/',lambda m:' '*len(m[0]),s,flags=re.S)
 start=s.index(signature);i=masked.index('{',start)+1;depth=1
 while depth:depth+=(masked[i]=='{')-(masked[i]=='}');i+=1
 return s[start:i]
code=r'''
#include "process_runtime.h"
#include "session_isolation.h"
#define OH_LOG_Print(...) ((void)0)
class NativeSession; struct SessionCreation;
#include <cassert>
#include <cstdio>
#include <functional>
#include <string>
#include <vector>
using napi_value=void*;using napi_env=void*;using napi_callback_info=void*;
constexpr int napi_ok=0;
struct NativeResult{bool ok;uint64_t handle;const char*code;};
NativeResult last;std::string encoded;std::vector<std::string> args;
namespace vidall::runtime{
TerminalPolicy seen=TerminalPolicy::ControlledAppExit;int configs=0;Status current{};FaultHistory history{};
const char* Configure(const std::string&,const std::string&,unsigned,TerminalPolicy p){configs++;seen=p;return nullptr;}
Status Snapshot(){return current;}
FaultHistory Faults(){return history;}
uint64_t CaptureGeneration(){return current.recoveryState==2?2:0;}
}
bool GetArguments(napi_env,napi_callback_info,size_t count,napi_value*out,size_t&argc){argc=args.size();for(size_t i=0;i<count&&i<argc;i++)out[i]=&args[i];return true;}
bool ReadString(napi_env,napi_value p,std::string&out){out=*static_cast<std::string*>(p);return true;}
int napi_get_value_int64(napi_env,napi_value p,int64_t*out){*out=std::stoll(*static_cast<std::string*>(p));return 0;}
napi_value QueueNative(napi_env,uint64_t,std::function<NativeResult()>op,bool admit,bool retire,std::shared_ptr<NativeSession>,bool,std::shared_ptr<SessionCreation>,std::shared_ptr<vidall::runtime::SessionIsolation> executor){assert(!admit&&!retire&&executor);assert(executor->Run([&]{last=op();},std::chrono::seconds(1)));return nullptr;}
napi_value CreateString(napi_env,const std::string&text){encoded=text;return nullptr;}
/* METHODS */
int main(){
 using namespace vidall::runtime;
 args={"/app","config","3000"};ConfigureRuntime(nullptr,nullptr);assert(last.ok&&configs==1&&seen==TerminalPolicy::ControlledAppExit);
 args.push_back("preserve-host");ConfigureRuntime(nullptr,nullptr);assert(last.ok&&configs==2&&seen==TerminalPolicy::PreserveHost);
 args[3]="unknown";ConfigureRuntime(nullptr,nullptr);assert(!last.ok&&configs==2);
 args[3]="preserve-host";args[2]="4294968296";ConfigureRuntime(nullptr,nullptr);assert(!last.ok&&configs==2);
 current.state=4;current.preservesHost=true;current.recoveryState=1;
 GetRuntimeStatus(nullptr,nullptr);assert(encoded.find("\"state\":\"pending\"")!=std::string::npos&&encoded.find("\"generation\":0")!=std::string::npos);
 current.faultSession=17;current.faultLoad=4;GetRuntimeStatus(nullptr,nullptr);
 assert(encoded.find("\"sessionId\":\"17\"")!=std::string::npos&&encoded.find("\"loadGeneration\":\"4\"")!=std::string::npos);
 current.faultSession=0;GetRuntimeStatus(nullptr,nullptr);assert(encoded.find("\"attribution\":{\"state\":\"unknown\"}")!=std::string::npos);
 current.recoveryState=2;GetRuntimeStatus(nullptr,nullptr);assert(encoded.find("\"state\":\"ready\"")!=std::string::npos&&encoded.find("\"generation\":2")!=std::string::npos);
 current.recoveryState=3;GetRuntimeStatus(nullptr,nullptr);assert(encoded.find("\"state\":\"timeout\"")!=std::string::npos);
 current.preservesHost=false;GetRuntimeStatus(nullptr,nullptr);assert(encoded.find("recovery")==std::string::npos);
 history.count=2;history.records[0]={1,17,4,-7,2,1};history.records[1]={2,0,0,-9,3,2};
 GetRuntimeStatus(nullptr,nullptr);puts(encoded.c_str());
}
'''.replace('/* METHODS */',extract('napi_value ConfigureRuntime(')+'\n'+extract('napi_value GetRuntimeStatus('))
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++17','-I'+str(root/'native/runtime'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 result=subprocess.run([str(p/'test')],check=True,timeout=5,capture_output=True,text=True)
 status=json.loads(result.stdout)
 assert status['faults'][0]['kind']=='session-quarantined'
 assert status['faults'][0]['attribution']=={'state':'known','sessionId':'17','loadGeneration':'4'}
 assert status['faults'][1]['kind']=='process-terminal' and status['faults'][1]['attribution']=={'state':'unknown'}
print('PASS NAPI 策略透传、截止边界、旧签名和恢复状态')
