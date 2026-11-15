"""编译真实 NAPI Load 入口，覆盖旧签名、显式加载代和数值边界。"""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[3]
s=(root/'packages/vidall-player/src/main/cpp/napi_init.cpp').read_text()
start=s.index('napi_value Load(napi_env');i=s.index('{',start)+1;depth=1
while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
code=r'''
#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <cstdint>
#include <cmath>
#include <cassert>
#define VIDALL_MPV_AVAILABLE 1
using napi_value=void*;using napi_env=void*;using napi_callback_info=void*;
constexpr int napi_ok=0;
struct NativeResult {bool ok;uint64_t handle;const char*code;};
std::vector<std::string> arguments;int calls=0;uint64_t seen=0;NativeResult result;
struct NativeSession {
 NativeResult Load(const std::string&,const std::string&,const std::string&,const std::string&,uint64_t h,uint64_t generation=0){calls++;seen=generation;return {true,h,"OK"};}
};
std::shared_ptr<NativeSession> FindSession(uint64_t,napi_env){static auto session=std::make_shared<NativeSession>();return session;}
bool GetArguments(napi_env,napi_callback_info,size_t requested,napi_value*out,size_t&argc){argc=arguments.size();for(size_t i=0;i<argc&&i<requested;i++)out[i]=&arguments[i];return true;}
bool ReadHandle(napi_env,napi_value v,uint64_t&out){out=std::stoull(*static_cast<std::string*>(v));return true;}
bool ReadString(napi_env,napi_value v,std::string&out){out=*static_cast<std::string*>(v);return true;}
int napi_get_value_double(napi_env,napi_value v,double*out){*out=std::stod(*static_cast<std::string*>(v));return 0;}
int napi_get_value_int64(napi_env,napi_value v,int64_t*out){*out=std::stoll(*static_cast<std::string*>(v));return 0;}
napi_value QueueNative(napi_env,uint64_t,std::function<NativeResult()>op){result=op();return (void*)1;}
/* ENTRY */
int main(){
 arguments={"17","file:///test","","","","5"};assert(Load(nullptr,nullptr));assert(calls==1&&seen==5);
 arguments.pop_back();assert(Load(nullptr,nullptr));assert(calls==2&&seen==0);
 for(const char* value:{"0","-1","1.5","nan","inf","9007199254740992"}){
  arguments={"17","file:///test","","","",value};assert(!Load(nullptr,nullptr));assert(calls==2);
 }
 arguments[5]="9007199254740991";assert(Load(nullptr,nullptr));assert(calls==3&&seen==9007199254740991ULL);
}
'''.replace('/* ENTRY */',s[start:i])
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++17',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=5)
print('PASS NAPI Load 旧签名、显式代、分数/溢出/非数拒绝')
