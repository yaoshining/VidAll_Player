#!/usr/bin/env python3
"""编译生产 SW 循环，验证暂停 resize、缓冲失败和清理；平台函数为替身。"""
import pathlib, subprocess, sys, tempfile
source = pathlib.Path(sys.argv[1]).read_text()
method = source[source.index('    void SwRenderLoop()'):source.index('    public:', source.index('    void SwRenderLoop()'))]
harness = r'''
#include <atomic>
#include <mutex>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
#include <sys/mman.h>
constexpr int LOG_APP=0,LOG_INFO=0,LOG_ERROR=0,LOG_WARN=0,LOG_DOMAIN=0;
const char* LOG_TAG="test";
constexpr int SET_FORMAT=1,SET_BUFFER_GEOMETRY=2,SET_USAGE=3,NATIVEBUFFER_PIXEL_FMT_RGBA_8888=1,NATIVEBUFFER_USAGE_CPU_READ=1,NATIVEBUFFER_USAGE_CPU_WRITE=2;
constexpr int MPV_RENDER_UPDATE_FRAME=1,MPV_RENDER_PARAM_SW_SIZE=1,MPV_RENDER_PARAM_SW_FORMAT=2,MPV_RENDER_PARAM_SW_STRIDE=3,MPV_RENDER_PARAM_SW_POINTER=4,MPV_RENDER_PARAM_INVALID=0;
struct mpv_render_param{int type;void* data;};
struct OHNativeWindowBuffer{};
struct BufferHandle{void* virAddr;int fd,size,stride,height,width;};
struct Region{struct Rect{int x,y;uint32_t w,h;};Rect* rects=nullptr;int rectNumber=0;};
int requests=0,polls=0;bool retry=false;int frames=1,renders=0,errors=0,destroys=0,geometryCalls=0,geometryRc=0;
int renderW=0,renderH=0,flushes=0;
char pixels[96];BufferHandle buffer{pixels,-1,96,16,6,4};OHNativeWindowBuffer nativeBuffer;
bool* stopPtr=nullptr;
void OH_LOG_Print(int,int,int,const char*,const char*,...){}
void mpv_render_context_set_update_callback(void*,void(*)(void*),void*){}
int OH_NativeWindow_NativeWindowHandleOpt(void*,int op,...){if(op==SET_BUFFER_GEOMETRY){++geometryCalls;return geometryCalls>1?geometryRc:0;}return 0;}
int OH_NativeWindow_NativeWindowRequestBuffer(void*,OHNativeWindowBuffer** b,int*){++requests;if(retry&&requests==1)return -1;*b=&nativeBuffer;return 0;}
BufferHandle* OH_NativeWindow_GetBufferHandleFromNative(OHNativeWindowBuffer*){return &buffer;}
int OH_NativeWindow_NativeWindowFlushBuffer(void*,OHNativeWindowBuffer*,int,Region){++flushes;if(retry)*stopPtr=true;return 0;}
uint64_t mpv_render_context_update(void*){if(retry){if(++polls>5)*stopPtr=true;}else if(!frames)*stopPtr=true;return frames;}
int mpv_render_context_render(void*,mpv_render_param* p){auto size=static_cast<int*>(p[0].data);++renders;renderW=size[0];renderH=size[1];if(!retry)*stopPtr=true;return 0;}
class Session{public:
std::mutex rendererMutex_,frameMutex_;std::condition_variable rendererReadyCv_,renderCondition_;
bool rendererReady_=false,stopRenderer_=false,renderRequested_=true,frameReady_=false;
std::atomic<bool> geometryDirty_{true},firstFrameSent_{true};
std::atomic<int> width_{4},height_{6};int frameWidth_=0,frameHeight_=0;
std::vector<uint8_t> pendingFrame_;void* window_=nullptr;void* renderer_=nullptr;
uint64_t generation_=1;std::atomic<uint64_t> surfaceSessionHandle_{9};
static void NotifyRender(void*){}
void Dispatch(const char* kind,const char*){if(std::string(kind)=="error")++errors;}
void MarkRendererFailed(){rendererReady_=false;}
void DestroyRenderer(){++destroys;}
METHOD
};
int main(int argc,char**argv){
std::string name=argv[1];Session s;stopPtr=&s.stopRenderer_;
if(name=="retry"){retry=true;frames=0;}
if(name=="paused-resize"||name=="paused-idle")frames=0;
if(name=="paused-idle")s.geometryDirty_=false;
if(name=="geometry-failed")geometryRc=-1;
s.SwRenderLoop();
bool ok=destroys==1;
if(name=="geometry-failed")ok=ok&&errors==1&&renders==0&&!s.rendererReady_;
else if(name=="retry")ok=ok&&errors==0&&requests==2&&flushes==1;
else if(name=="paused-idle")ok=ok&&errors==0&&renders==0;
else ok=ok&&errors==0&&renders==1&&renderW==4&&renderH==6&&flushes==1;
std::cout<<name<<" "<<(ok?"PASS":"FAIL")<<"\n";return ok?0:1;
}
'''.replace('METHOD',method)
with tempfile.TemporaryDirectory(prefix='vidall-sw-test-') as td:
 p=pathlib.Path(td);(p/'test.cpp').write_text(harness)
 subprocess.run(['c++','-std=c++17','-pthread',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 failed=sum(subprocess.run([str(p/'test'),case],timeout=3).returncode!=0 for case in ['normal','paused-resize','paused-idle','geometry-failed','retry'])
 sys.exit(bool(failed))
