#!/usr/bin/env python3
"""编译实际 GlRenderLoop 的平台替身测试；不将其视为 GPU 真机验收。"""
import pathlib, subprocess, sys, tempfile
source = pathlib.Path(sys.argv[1]).read_text()
start = source.index('    void GlRenderLoop()')
end = source.index('    // SW 渲染循环', start)
method = source[start:end]
harness = r'''
#include <atomic>
#include <mutex>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
using EGLint=int;using EGLSurface=int;constexpr int EGL_NONE=4;
using EGLBoolean=int;
using EGLNativeWindowType=void*;
constexpr int EGL_NO_SURFACE=0,EGL_NO_CONTEXT=0,EGL_WIDTH=1,EGL_HEIGHT=2;
constexpr int SET_BUFFER_GEOMETRY=3,MPV_RENDER_UPDATE_FRAME=1;
constexpr int MPV_RENDER_PARAM_OPENGL_FBO=1,MPV_RENDER_PARAM_FLIP_Y=2,MPV_RENDER_PARAM_INVALID=0;
constexpr int LOG_APP=0,LOG_INFO=0,LOG_ERROR=0,LOG_WARN=0,LOG_DOMAIN=0;
const char* LOG_TAG="test";
struct mpv_opengl_fbo{int fbo,w,h,format;};
struct mpv_render_param{int type;void* data;};
int queries=0,frames=1,renders=0,swaps=0,errors=0,destroys=0,bufferRc=0,createRc=2,bindRc=1,queryRc=1,swapRc=1;
int currentContext=1,cleanupContext=0,parkingCreates=0;bool surfaceless=true,parkingAllowed=true;
int actualW=1840,actualH=2644,renderW=0,renderH=0;
bool* stopPtr=nullptr;
void OH_LOG_Print(int,int,int,const char*,const char*,...){}
void mpv_render_context_set_update_callback(void*,void(*)(void*),void*){}
int eglMakeCurrent(int,int draw,int,int context){if((draw==0&&context==1&&!surfaceless)||(draw==2&&bindRc==0))return 0; currentContext=context;return 1;}
int eglDestroySurface(int,int){return 1;}
int OH_NativeWindow_NativeWindowHandleOpt(void*,int,int,int){return bufferRc;}
int eglCreatePbufferSurface(int,int,const int*){++parkingCreates;return parkingAllowed?3:0;}
int eglCreateWindowSurface(int,int,void*,void*){return createRc;}
int eglGetError(){return 0x300d;}
int eglQuerySurface(int,int,int what,int* value){++queries;*value=what==EGL_WIDTH?actualW:actualH;return queryRc;}
uint64_t mpv_render_context_update(void*){if(!frames)*stopPtr=true;return frames;}
int mpv_render_context_render(void*,mpv_render_param* p){auto f=static_cast<mpv_opengl_fbo*>(p[0].data);++renders;renderW=f->w;renderH=f->h;return 0;}
int eglSwapBuffers(int,int){++swaps;*stopPtr=true;return swapRc;}
class Session {
 public:
 std::mutex rendererMutex_;std::condition_variable rendererReadyCv_,renderCondition_;
 bool rendererReady_=false,stopRenderer_=false,renderRequested_=true;
 std::atomic<bool> geometryDirty_{true},firstFrameSent_{true};
 std::atomic<int> width_{1840},height_{2644};
 uint64_t generation_=1;std::atomic<uint64_t> surfaceSessionHandle_{9};
 int eglDisplay_=1,eglSurface_=1,eglContext_=1,eglConfig_=1;
 void* window_=nullptr;void* renderer_=nullptr;
 static void NotifyRender(void*){}
 void Dispatch(const char* kind,const char*){if(std::string(kind)=="error")++errors;}
 void MarkRendererFailed(){rendererReady_=false;}
 void DestroyRenderer(){++destroys;cleanupContext=currentContext;}
 METHOD
};
int main(int argc,char**argv){
 std::string name=argv[1]; Session s; stopPtr=&s.stopRenderer_;
 if(name=="paused-resize")frames=0;
 if(name=="actual-fbo") {actualW=2800;actualH=1684;}
 if(name=="parking"||name=="parking-failed"||name=="parking-bind-failed")surfaceless=false;
 if(name=="parking-failed")parkingAllowed=false;
 if(name=="parking-bind-failed")bindRc=0;
 if(name=="set-failed")bufferRc=-1;
 if(name=="create-failed")createRc=0;
 if(name=="bind-failed")bindRc=0;
 if(name=="query-failed")queryRc=0;
 if(name=="zero-size")actualW=0;
 if(name=="swap-failed")swapRc=0;
 s.GlRenderLoop();
 bool failure=name.find("failed")!=std::string::npos||name=="zero-size";
 bool ok=destroys==1&&cleanupContext==1&&parkingCreates==(surfaceless?0:1);
 if(failure){ok=ok&&errors==1&&!s.rendererReady_;if(name!="swap-failed")ok=ok&&renders==0;}
 else ok=ok&&errors==0&&renders==1&&swaps==1&&renderW==actualW&&renderH==actualH;
 std::cout<<name<<" renders="<<renders<<" fbo="<<renderW<<"x"<<renderH<<" errors="<<errors<<" "<<(ok?"PASS":"FAIL")<<"\n";
 return ok?0:1;
}
'''.replace(' METHOD',method)
with tempfile.TemporaryDirectory(prefix='vidall-gl-test-') as td:
 p=pathlib.Path(td);(p/'test.cpp').write_text(harness)
 subprocess.run(['c++','-std=c++17','-pthread',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 failed=0
 for name in ['normal','paused-resize','actual-fbo','set-failed','create-failed','bind-failed','query-failed','zero-size','swap-failed','parking','parking-failed','parking-bind-failed']:
  try: failed+=subprocess.run([str(p/'test'),name],timeout=3).returncode!=0
  except subprocess.TimeoutExpired: print(name,'FAIL timeout');failed+=1
 sys.exit(bool(failed))
