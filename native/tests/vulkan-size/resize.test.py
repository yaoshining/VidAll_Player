#!/usr/bin/env python3
"""编译实际 Resize，验证 Vulkan 通知与错误返回；不代替设备 swapchain 测试。"""
import pathlib, subprocess, sys, tempfile
source = pathlib.Path(sys.argv[1]).read_text()
method = source[source.index('    NativeResult Resize('):source.index('    NativeResult Load(')]
method += source[source.index('    void StopRendererLocked()'):source.index('    void DestroyRenderer()')]
harness = r'''
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <cstdint>
#include <string>
#include <memory>
#include <iostream>
#include <thread>
#include <future>
#include <chrono>
namespace vidall::runtime {
bool terminal = false;
const char* AdmissionError() { return terminal ? "TERMINAL" : nullptr; }
}
namespace vidall::render { enum class RenderBackend { Vulkan, OpenGles, Software }; }
constexpr int MPV_FORMAT_INT64=1;
int mpv_set_property(int*,const char*,int,void*){return 0;}
constexpr int SET_BUFFER_GEOMETRY=1,LOG_APP=0,LOG_INFO=0,LOG_ERROR=0,LOG_DOMAIN=0;
const char* LOG_TAG="test";
int readbacks=0;
int mpv_get_property(int*,const char*,int,void* out){++readbacks;*static_cast<int64_t*>(out)=480;return 0;}
int geometryRc=0,resizeRc=0,geometryCalls=0,propertyCalls=0;
std::mutex propertyMutex;std::condition_variable propertyCv;bool blockProperty=false,propertyEntered=false,allowProperty=false;
int actualW=2800,actualH=1684,rollbackRc=0;
std::string option,value;
int OH_NativeWindow_NativeWindowHandleOpt(void*,int,int w,int h){++geometryCalls;int rc=geometryCalls>1?rollbackRc:geometryRc;if(rc==0){actualW=w;actualH=h;}return rc;}
int mpv_set_property_string(int*,const char* k,const char* v){++propertyCalls;option=k;value=v;{std::unique_lock<std::mutex> l(propertyMutex);propertyEntered=true;propertyCv.notify_all();if(blockProperty)propertyCv.wait(l,[]{return allowProperty;});}return resizeRc;}
void OH_LOG_Print(int,int,int,const char*,const char*,...){}
struct NativeResult{bool ok;std::uint64_t handle;const char* code;};
class Session { public:
std::mutex lifecycleMutex_,rendererMutex_;bool released_=false,rendererReady_=true;
std::uint64_t generation_=1;
vidall::render::RenderBackend renderBackend_=vidall::render::RenderBackend::Vulkan;
void* window_=reinterpret_cast<void*>(1);std::unique_ptr<int> player_{new int(0)};
std::atomic<int> width_{2800},height_{1684};
std::atomic<bool> geometryDirty_{false},renderRequested_{false};
std::condition_variable renderCondition_,rendererReadyCv_;bool rendererFailed_=false;
int destroys=0;bool stopRenderer_=false;std::thread renderThread_;
void DestroyRenderer(){++destroys;window_=nullptr;}
void MarkRendererFailed(){rendererReady_=false;}
METHOD
};
int main(int argc,char**argv){
std::string name=argv[1];Session s;
if(name=="geometry-failed")geometryRc=-1;
if(name=="property-failed"||name=="rollback-failed"||name=="retry")resizeRc=-1;
if(name=="rollback-failed")rollbackRc=-1;
if(name=="no-window")s.window_=nullptr;
if(name=="terminal")vidall::runtime::terminal=true;
if(name=="released")s.released_=true;
if(name=="sw")s.renderBackend_=vidall::render::RenderBackend::Software;
if(name=="not-ready")s.rendererReady_=false;
if(name=="gles")s.renderBackend_=vidall::render::RenderBackend::OpenGles;
if(name=="detach-race"){
 blockProperty=true;
 auto resizing=std::async(std::launch::async,[&]{return s.Resize(1,1840,2644,9);});
 {std::unique_lock<std::mutex> l(propertyMutex);if(!propertyCv.wait_for(l,std::chrono::milliseconds(300),[]{return propertyEntered;})){std::cout<<"detach-race FAIL no resize notification\n";return 1;}}
 std::promise<void> started;auto detach=std::async(std::launch::async,[&]{started.set_value();return s.Detach(1,9);});started.get_future().wait();
 bool waited=detach.wait_for(std::chrono::milliseconds(30))==std::future_status::timeout;
 {std::lock_guard<std::mutex> l(propertyMutex);allowProperty=true;propertyCv.notify_all();}
 bool ok=waited&&resizing.get().ok&&detach.get().ok&&s.generation_==0&&!s.Resize(1,640,480,9).ok;
 std::cout<<name<<" "<<(ok?"PASS":"FAIL")<<"\n";return ok?0:1;
}
auto r=s.Resize(name=="stale"?2:1,name=="zero"?0:1840, name=="negative"?-1:2644,9);
bool ok=false;
if(name=="vulkan")ok=r.ok&&geometryCalls==1&&propertyCalls==1&&option=="ohos-surface-size"&&value=="1840x2644"&&!s.geometryDirty_&&s.width_==1840;
else if((name=="gles"||name=="sw"))ok=r.ok&&geometryCalls==0&&propertyCalls==0&&s.geometryDirty_&&s.renderRequested_;
else if(name=="property-failed"||name=="retry"){
 ok=!r.ok&&s.width_==2800&&actualW==2800&&actualH==1684&&geometryCalls==2&&propertyCalls==1&&s.rendererReady_;
 if(name=="retry"){resizeRc=0;auto next=s.Resize(1,1840,2644,9);ok=ok&&next.ok&&s.width_==1840&&actualW==1840;}
}
else if(name=="rollback-failed")ok=!r.ok&&!s.rendererReady_&&!s.Resize(1,640,480,9).ok;
else if(name=="rotate-repeat"){
 ok=r.ok;
 for(int i=0;i<100;++i){int w=i%2?640:1840,h=i%2?480:2644;ok=ok&&s.Resize(1,w,h,9).ok&&actualW==w&&actualH==h&&s.width_==w&&s.height_==h;}
}
else ok=!r.ok&&s.width_==2800&&propertyCalls==0;
std::cout<<name<<" "<<(ok?"PASS":"FAIL")<<"\n";return ok?0:1;
}
'''.replace('METHOD',method)
with tempfile.TemporaryDirectory(prefix='vidall-vk-test-') as td:
    p=pathlib.Path(td);(p/'test.cpp').write_text(harness)
    subprocess.run(['c++','-std=c++17','-pthread',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    failures=sum(subprocess.run([str(p/'test'),case],timeout=3).returncode != 0 for case in
                 ['vulkan','gles','sw','zero','negative','not-ready','geometry-failed','property-failed','rollback-failed','retry','rotate-repeat','detach-race','no-window','released','stale','terminal'])
    sys.exit(bool(failures))
