#include "process_runtime.h"
#include <mpv/ohcodec_terminal.h>
#include <libavformat/ohcodec_smb_runtime.h>
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
static std::atomic<bool> terminal{false},cleanupObserved{false};
static std::mutex logMutex;
static std::string mode;
static thread_local bool isCleanupThread=false;
static mpv_ohcodec_terminal_config registeredConfig{};
static std::mutex callbackBlockMutex;static std::condition_variable callbackBlockCondition;static std::atomic<bool>callbackWaiting{false},loggerWaiting{false};
static void event(const char* name,bool destroy=false){std::lock_guard<std::mutex>l(logMutex);printf("%s %s after_terminal=%d\n",destroy?"DESTROY":"EVENT",name,int(terminal.load()));fflush(stdout);}
static void terminalNow(){terminal=true;auto status=vidall::runtime::Snapshot();{std::lock_guard<std::mutex>l(logMutex);printf("TERMINAL first_ms=%lld observed_ms=%lld deadline_ms=%u\n",static_cast<long long>(status.firstObservedMs),static_cast<long long>(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count()),status.deadlineMs);fflush(stdout);}event("terminal");}
extern "C" {
uint32_t mpv_ohcodec_terminal_api_version(){return MPV_OHCODEC_TERMINAL_ABI_VERSION;}
int mpv_ohcodec_terminal_register(const mpv_ohcodec_terminal_config*c){registeredConfig=*c;return 0;}
int mpv_ohcodec_terminal_enable(){return 0;}
int mpv_ohcodec_terminal_snapshot(mpv_ohcodec_terminal_record*r){if(isCleanupThread)cleanupObserved=true;if(!terminal)return 0;r->stage=1;r->platform_error=-4;r->owner_tag=7;return 1;}
int ohcodec_smb_runtime_configure_v1(const ohcodec_smb_runtime_v1*){return 0;}
mpv_handle*mpv_create(){event("mpv-create");return reinterpret_cast<mpv_handle*>(1);}
void mpv_terminate_destroy(mpv_handle*){event("mpv-player",true);}
void mpv_wakeup(mpv_handle*){event("mpv-wakeup");}
}
static constexpr int EGL_NO_DISPLAY=0,EGL_NO_SURFACE=0,EGL_NO_CONTEXT=0,napi_tsfn_release=0;
void mpv_render_context_set_update_callback(void*,void*,void*){event("renderer-callback-remove",true);}
void mpv_render_context_free(void*){event("renderer",true);if(mode=="terminal-during-render-free")terminalNow();}
void eglMakeCurrent(int,int,int,int){event("egl-unbind",true);}
void eglDestroySurface(int,int){event("egl-surface",true);}
void eglDestroyContext(int,int){event("egl-context",true);}
void eglTerminate(int){event("egl-display",true);}
void OH_NativeWindow_DestroyNativeWindow(void*){event("window",true);}
void napi_release_threadsafe_function(void*,int){event("callback",true);if(mode=="terminal-callback-close")terminalNow();}
class NativeSession {
public:
 /* EXTRACT NativeSession() */
 /* EXTRACT ~NativeSession() */
 /* EXTRACT void Release() */
 /* EXTRACT void InvalidateCompletion() */
 /* EXTRACT void StopRendererLocked() */
 /* EXTRACT void DestroyRenderer() */
 /* EXTRACT void CloseCallbackLocked() */
 std::unique_ptr<mpv_handle,decltype(&mpv_terminate_destroy)>player_{nullptr,mpv_terminate_destroy};
 std::mutex lifecycleMutex_,rendererMutex_,callbackMutex_,completionMutex_;
 // 与实际InvalidateCompletion读取的成员类型一致，非空初值检验Release真实清理调用。
 std::uint64_t completionEpoch_=7;std::int64_t completionEntry_=17;std::vector<std::int64_t>completionEnded_{11};
 std::condition_variable renderCondition_;
 std::thread eventThread_,renderThread_;
 std::atomic<bool>stopEvents_{false};
 bool released_=false,stopRenderer_=false,rendererReady_=true;
 void *renderer_=reinterpret_cast<void*>(1),*window_=reinterpret_cast<void*>(2),*eventTsfn_=reinterpret_cast<void*>(3);
 int eglDisplay_=1,eglSurface_=1,eglContext_=1;
 void Start(){
  eventThread_=std::thread([this]{while(!stopEvents_)std::this_thread::sleep_for(std::chrono::milliseconds(1));event("event-thread-exit");});
  renderThread_=std::thread([this]{{std::unique_lock<std::mutex>lock(rendererMutex_);renderCondition_.wait(lock,[this]{return stopRenderer_;});}if(mode=="terminal-render-tail")terminalNow();DestroyRenderer();event("render-thread-exit");});
 }
};
/* EXTRACT void DeleteSession(NativeSession* session) */
std::mutex gSessionsMutex;
std::unordered_map<std::uint64_t,std::shared_ptr<NativeSession>>gSessions;
/* EXTRACT void CleanupSessions(void*) */
int main(int argc,char**argv){
 if(argc!=3)return 90;mode=argv[1];mkdir(argv[2],0700);
 if(const char*e=vidall::runtime::Configure(argv[2],"[global]\nclient min protocol = SMB2_02\n",1000)){printf("FAIL configure %s\n",e);return 91;}
 if(mode=="terminal-direct-destructor"){std::unique_ptr<NativeSession>direct(new NativeSession());direct->Start();terminalNow();direct.reset();event("FAIL destructor returned");return 92;}
 auto p=std::shared_ptr<NativeSession>(new NativeSession(),DeleteSession);p->Start();
 if(mode=="terminal-callback-delivery-blocked"){
  std::thread([]{std::unique_lock<std::mutex>lock(callbackBlockMutex);event("callback-wait-enter");callbackWaiting=true;callbackBlockCondition.wait(lock,[]{return false;});event("callback-wait-return");registeredConfig.handler(nullptr,registeredConfig.opaque);}).detach();
  while(!callbackWaiting)std::this_thread::yield();terminalNow();p.reset();
 }
 else if(mode=="terminal-logger-blocked"){
  int fds[2];if(pipe(fds))return 93;fcntl(fds[1],F_SETFL,O_NONBLOCK);char bytes[4096]{};while(write(fds[1],bytes,sizeof(bytes))>0){}char lastByte=0;while(write(fds[1],&lastByte,1)>0){}fcntl(fds[1],F_SETFL,0);
  std::thread([fd=fds[1]]{char byte=1;event("logger-write-enter");loggerWaiting=true;write(fd,&byte,1);event("logger-write-return");}).detach();
  while(!loggerWaiting)std::this_thread::yield();terminalNow();p.reset();
 }
 else if(mode=="terminal-before-last-reference"){terminalNow();p.reset();event("retained-last-reference");}
 else if(mode=="terminal-cleanup-swap"){
  gSessions.emplace(1,p);p.reset();
  std::unique_lock<std::mutex>held(gSessionsMutex);
  std::thread cleanup([]{isCleanupThread=true;CleanupSessions(nullptr);event("cleanup-return");});
  while(!cleanupObserved)std::this_thread::sleep_for(std::chrono::milliseconds(1));
  terminalNow();held.unlock();cleanup.join();
 }else{
  if(mode=="normal-explicit-release"){p->Release();if(p->completionEpoch_!=0||p->completionEntry_!=-1||!p->completionEnded_.empty()){event("FAIL completion invalidation");return 94;}}
  p.reset();event("owner-delete");
 }
 if(mode.rfind("terminal-",0)==0){for(;;)std::this_thread::sleep_for(std::chrono::milliseconds(10));}
 return 0;
}
