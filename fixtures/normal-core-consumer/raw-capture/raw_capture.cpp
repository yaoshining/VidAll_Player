#include "bounded_capture.h"
#include <napi/native_api.h>
#include <multimedia/player_framework/native_avscreen_capture.h>
#include <multimedia/player_framework/native_avbuffer.h>
#include <native_buffer/native_buffer.h>
#include <native_buffer/buffer_common.h>
#include <atomic>
#include <chrono>
#include <memory>
#include <mutex>
#include <sstream>
#include <unistd.h>
#include <cerrno>

namespace {
constexpr int W=160,H=90;
// 一次性诊断：即使平台关闭挂起也不复用对象或再建线程/采集器。
struct State {
 std::mutex mutex;std::unique_ptr<RawCaptureBuffer> data;
 OH_AVScreenCapture* capture=nullptr;
 std::atomic<bool> used{false},ending{false},startDone{false};
 std::atomic<int> state{-1},error{0};
 int width=0,height=0,stride=0,format=0;
};
State& S(){static auto* s=new State;return *s;}
int64_t Now(){return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
void StateChanged(OH_AVScreenCapture*,OH_AVScreenCaptureStateCode code,void*){S().state=code;}
void Error(OH_AVScreenCapture*,int32_t code,void*){S().error=code?code:-100;}
void Buffer(OH_AVScreenCapture*,OH_AVBuffer* buffer,OH_AVScreenCaptureBufferType type,int64_t timestamp,void*) {
 auto& s=S();if(s.ending||s.error)return;const auto arrival=Now();
 std::lock_guard<std::mutex> lock(s.mutex);if(s.ending||!s.data)return;
 if(type==OH_SCREEN_CAPTURE_BUFFERTYPE_AUDIO_INNER){
  OH_AVCodecBufferAttr attr{};const int capacity=OH_AVBuffer_GetCapacity(buffer);auto* bytes=OH_AVBuffer_GetAddr(buffer);
  if(OH_AVBuffer_GetBufferAttr(buffer,&attr)!=AV_ERR_OK||!bytes||attr.offset<0||attr.size<=0||
     capacity<attr.offset||attr.size>capacity-attr.offset||attr.size%4||attr.size>1024*1024){s.error=-101;return;}
  if(!s.data->append(2,timestamp,arrival,bytes+attr.offset,attr.size))s.error=-102;
 }else if(type==OH_SCREEN_CAPTURE_BUFFERTYPE_VIDEO){
  OH_NativeBuffer* native=OH_AVBuffer_GetNativeBuffer(buffer);if(!native){s.error=-103;return;}
  OH_NativeBuffer_Config c{};OH_NativeBuffer_GetConfig(native,&c);
  s.width=c.width;s.height=c.height;s.stride=c.stride;s.format=c.format;
  bool valid=c.width>=W&&c.width<=4096&&c.height>=H&&c.height<=4096&&c.stride>=c.width*4&&c.stride<=65536&&
      (c.format==NATIVEBUFFER_PIXEL_FMT_RGBA_8888||c.format==NATIVEBUFFER_PIXEL_FMT_BGRA_8888);
  void* address=nullptr;
  if(!valid||OH_NativeBuffer_Map(native,&address)!=0){s.error=-104;OH_NativeBuffer_Unreference(native);return;}
  uint8_t gray[W*H];auto* pixels=static_cast<uint8_t*>(address);
  if(!address){s.error=-105;}else{
   for(int y=0;y<H;++y)for(int x=0;x<W;++x){
    auto* p=pixels+((2*y+1)*c.height/(2*H))*c.stride+((2*x+1)*c.width/(2*W))*4;
    gray[y*W+x]=(unsigned(p[0])+p[1]+p[2])/3;
   }
   if(!s.data->append(1,timestamp,arrival,gray,sizeof(gray)))s.error=-102;
  }
  if(OH_NativeBuffer_Unmap(native)!=0)s.error=-106;
  OH_NativeBuffer_Unreference(native);
 }else{s.error=-107;} // 不接受麦克风数据。
}
std::string Status(){auto& s=S();std::unique_lock<std::mutex> lock(s.mutex,std::try_to_lock);if(!lock.owns_lock())return "{\"state\":"+std::to_string(s.state.load())+",\"error\":"+std::to_string(s.error.load())+",\"busy\":true}";std::ostringstream o;
 o<<"{\"state\":"<<s.state<<",\"error\":"<<s.error<<",\"records\":"<<(s.data?s.data->records():0)
  <<",\"timestampAnomalies\":"<<(s.data?s.data->anomalies():0)<<",\"bytes\":"<<(s.data?s.data->bytes().size():0)<<",\"width\":"<<s.width<<",\"height\":"<<s.height
  <<",\"stride\":"<<s.stride<<",\"format\":"<<s.format<<",\"physicalAccepted\":false}";return o.str();}
bool Write(int fd,const void* data,size_t size){auto* p=static_cast<const char*>(data);while(size){auto n=write(fd,p,size);if(n<0&&errno==EINTR)continue;if(n<=0)return false;p+=n;size-=n;}return true;}
std::string Start(){auto& s=S();
 try{s.data=std::make_unique<RawCaptureBuffer>(64*1024*1024,12000,false);}catch(...){s.error=-108;return Status();}
 s.capture=OH_AVScreenCapture_Create();if(!s.capture){s.error=-109;return Status();}
 OH_AVScreenCaptureConfig c{};c.captureMode=OH_CAPTURE_HOME_SCREEN;c.dataType=OH_ORIGINAL_STREAM;
 c.audioInfo.innerCapInfo={48000,2,OH_ALL_PLAYBACK};
 c.videoInfo.videoCapInfo.videoFrameWidth=640;c.videoInfo.videoCapInfo.videoFrameHeight=360;
 c.videoInfo.videoCapInfo.videoSource=OH_VIDEO_SOURCE_SURFACE_RGBA;
 int rc=OH_AVScreenCapture_SetStateCallback(s.capture,StateChanged,nullptr);
 if(!rc)rc=OH_AVScreenCapture_SetErrorCallback(s.capture,Error,nullptr);
 if(!rc)rc=OH_AVScreenCapture_SetDataCallback(s.capture,Buffer,nullptr);
 if(!rc)rc=OH_AVScreenCapture_SetMicrophoneEnabled(s.capture,false);
 if(!rc)rc=OH_AVScreenCapture_Init(s.capture,c);
 if(!rc)rc=OH_AVScreenCapture_StartScreenCapture(s.capture);
 if(rc)s.error=rc;return Status();
}
std::string Finish(int fd){auto& s=S();s.ending=true;
 int rc=s.capture?OH_AVScreenCapture_StopScreenCapture(s.capture):0;
 if(rc)s.error=rc;
 // Stop失败时保留采集器，拒绝再次使用；不并发Release。
 if(!rc&&s.capture){rc=OH_AVScreenCapture_Release(s.capture);if(rc)s.error=rc;else s.capture=nullptr;}
 {std::lock_guard<std::mutex> lock(s.mutex);
  if(s.data&&(!Write(fd,"VRAWC001",8)||!Write(fd,s.data->bytes().data(),s.data->bytes().size())))s.error=-110;
 }
 close(fd);return Status();
}
napi_value String(napi_env env,const std::string& text){napi_value value;napi_create_string_utf8(env,text.c_str(),text.size(),&value);return value;}
struct Work{napi_async_work work=nullptr;napi_deferred deferred=nullptr;int fd=-1;bool start;std::string result;};
napi_value Schedule(napi_env env,bool start,int fd){
 auto* w=new Work;w->start=start;w->fd=fd;napi_value promise,name;
 if(napi_create_promise(env,&w->deferred,&promise)!=napi_ok){if(fd>=0)close(fd);delete w;return nullptr;}
 napi_create_string_utf8(env,"rawCaptureDiagnostic",NAPI_AUTO_LENGTH,&name);
 auto execute=[](napi_env,void* data){auto* w=static_cast<Work*>(data);try{w->result=w->start?Start():Finish(w->fd);w->fd=-1;if(w->start)S().startDone=true;}catch(...){S().error=-111;if(w->start)S().startDone=true;w->result=Status();if(w->fd>=0)close(w->fd);w->fd=-1;}};
 auto complete=[](napi_env e,napi_status status,void* data){auto* w=static_cast<Work*>(data);auto value=String(e,w->result);if(status==napi_ok)napi_resolve_deferred(e,w->deferred,value);else napi_reject_deferred(e,w->deferred,value);napi_delete_async_work(e,w->work);delete w;};
 if(napi_create_async_work(env,nullptr,name,execute,complete,w,&w->work)!=napi_ok||napi_queue_async_work(env,w->work)!=napi_ok){if(fd>=0)close(fd);napi_reject_deferred(env,w->deferred,String(env,"RAW_SCHEDULE_FAILED"));if(w->work)napi_delete_async_work(env,w->work);delete w;}
 return promise;
}
napi_value Begin(napi_env env,napi_callback_info){if(S().used.exchange(true)){napi_throw_error(env,nullptr,"RAW_ONE_SHOT");return nullptr;}return Schedule(env,true,-1);}
napi_value End(napi_env env,napi_callback_info info){size_t n=1;napi_value args[1];int32_t fd=-1;napi_get_cb_info(env,info,&n,args,nullptr,nullptr);
 if(n!=1||napi_get_value_int32(env,args[0],&fd)!=napi_ok||fd<0){napi_throw_error(env,nullptr,"RAW_BAD_FD");return nullptr;}
 int copy=dup(fd);if(copy<0){napi_throw_error(env,nullptr,"RAW_DUP_FAILED");return nullptr;}
 if(!S().used||!S().startDone||S().ending.exchange(true)){close(copy);napi_throw_error(env,nullptr,"RAW_END_ONE_SHOT");return nullptr;}
 return Schedule(env,false,copy);
}
napi_value Get(napi_env e,napi_callback_info){return String(e,Status());}
napi_value Init(napi_env env,napi_value exports){napi_property_descriptor p[]={
 {"start",nullptr,Begin,nullptr,nullptr,nullptr,napi_default,nullptr},{"finish",nullptr,End,nullptr,nullptr,nullptr,napi_default,nullptr},{"status",nullptr,Get,nullptr,nullptr,nullptr,napi_default,nullptr}};
 napi_define_properties(env,exports,3,p);return exports;}
napi_module module={1,0,nullptr,Init,"raw_capture",nullptr,{0}};
}
extern "C" __attribute__((constructor)) void RegisterRawCapture(){napi_module_register(&module);}
