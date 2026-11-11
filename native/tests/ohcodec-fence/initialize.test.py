"""编译真实 NativeSession::Initialize，验证隔离选项、容量降级和初始化失败。"""
from pathlib import Path
import subprocess,tempfile,os
root=Path(__file__).resolve().parents[3]
s=Path(os.environ.get('NATIVE_INITIALIZE_SOURCE',root/'packages/vidall-player/src/main/cpp/napi_init.cpp')).read_text()
start=s.index('    bool Initialize(');body=s.index('{',start);i=body+1;depth=1
while depth:
 depth+=(s[i]=='{')-(s[i]=='}');i+=1
method=s[start:i]
code=r'''
#include "session_isolation.h"
#include "render_backend_policy.h"
#include <atomic>
#include <cassert>
#include <map>
#include <memory>
#include <string>
#include <unistd.h>
bool gpu=true,fail=false;
std::string failOption;
std::map<std::string,std::string> options;
int fake_access(const char*,int) { return gpu?0:-1; }
#define access fake_access
#define OH_LOG_Print(...) ((void)0)
int mpv_set_option_string(void*,const char *key,const char *value) {
 options[key]=value;
 return (fail&&std::string(key)=="ohcodec-session-isolation") || failOption==key ? -1 : 0;
}
struct Harness {
 bool compatible_=false;
 std::shared_ptr<int> player_=std::make_shared<int>(1);
 std::shared_ptr<vidall::runtime::SessionIsolation> isolation_,executor_;
 vidall::render::RenderBackend renderBackend_;
 std::atomic<bool> hardwareDecodingRequested_{false};
 /* METHOD */
};
int main() {
 { Harness h;h.player_.reset();assert(!h.Initialize("","auto","","")); }
 { Harness h;gpu=false;assert(h.Initialize("","auto","",""));assert(!h.isolation_&&options.at("vo")=="libmpv"); }
 gpu=true;options.clear();
 { Harness h;assert(h.Initialize("","auto","","","compatible"));
   assert(h.renderBackend_==vidall::render::RenderBackend::Software);
   assert(h.executor_&&!h.isolation_&&!h.hardwareDecodingRequested_);
   assert(options.at("hwdec")=="no"&&options.at("vo")=="libmpv"&&options.at("gpu-hwdec-interop")=="no");
   assert(!options.count("gpu-api")&&!options.count("gpu-context")&&!options.count("ohcodec-session-isolation")); }
 { Harness h;assert(!h.Initialize("","auto","","","misspelled")); }
 for (auto key : {"vo", "hwdec", "gpu-hwdec-interop"}) {
   failOption=key; Harness h;assert(!h.Initialize("","auto","","","compatible"));
 }
 failOption.clear();options.clear();
 { Harness h;assert(h.Initialize("","no","",""));assert(!h.isolation_&&options.at("gpu-hwdec-interop")=="no"); }
 { Harness h;fail=true;assert(!h.Initialize("","auto","",""));assert(h.isolation_);h.isolation_->FinishedRelease(); }
 fail=false;options.clear();
 Harness a,b,c;
 assert(a.Initialize("","auto","",""));
 assert(a.isolation_&&a.hardwareDecodingRequested_&&options.at("ohcodec-session-isolation")=="yes"&&options.at("hwdec")=="auto");
 assert(b.Initialize("","auto-safe","",""));assert(b.isolation_);
 options.clear();assert(c.Initialize("","auto","",""));
 assert(!c.isolation_&&!c.hardwareDecodingRequested_&&options.at("hwdec")=="no"&&options.at("gpu-hwdec-interop")=="no");
 assert(!options.count("ohcodec-session-isolation"));
 a.isolation_->FinishedRelease();b.isolation_->FinishedRelease();
}
'''.replace('/* METHOD */',method)
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++17','-pthread','-I'+str(root/'native/runtime'),'-I'+str(root/'native/render'),str(p/'test.cpp'),str(root/'native/render/render_backend_policy.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=5)
print('真实 Initialize 的兼容软件路径、隔离接入、两名额上限和错误分支通过')
