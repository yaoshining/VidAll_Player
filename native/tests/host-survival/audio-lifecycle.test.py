"""编译真实 OHAudio 初始化/释放函数，覆盖退休与平台阻塞竞争；平台为替身。"""
from pathlib import Path
import re, subprocess, sys, tempfile
root=Path(__file__).resolve().parents[3]
source=(Path(sys.argv[1])/'audio/out/ao_ohaudio.c').read_text()
def function(name):
 m=re.search(r'^static [\w *]+\b'+name+r'\([^;]*?\)\s*\n\{.*?^\}',source,re.M|re.S)
 assert m,name
 return m[0]
code=r'''
#include "host_recovery.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
typedef int OH_AudioStream_Result;
typedef int OH_AudioStream_State;
#define AUDIOSTREAM_ERROR_ILLEGAL_STATE 2
typedef struct {int state;} OH_AudioRenderer;
typedef int OH_AudioStreamBuilder;
enum {AUDIOSTREAM_SUCCESS=0,AUDIOSTREAM_TYPE_RENDERER=1,AUDIOSTREAM_USAGE_MOVIE=2,
 AUDIOSTREAM_SAMPLE_U8,AUDIOSTREAM_SAMPLE_S16LE,AUDIOSTREAM_SAMPLE_S32LE,AUDIOSTREAM_SAMPLE_F32LE,
 AF_FORMAT_U8,AF_FORMAT_S16,AF_FORMAT_S32,AF_FORMAT_FLOAT,
 AUDIOSTREAM_STATE_PREPARED,AUDIOSTREAM_STATE_STOPPED,AUDIOSTREAM_STATE_RUNNING,AUDIOSTREAM_STATE_PAUSED};
struct priv {bool timing_initialized,timing_started,timing_stop;pthread_mutex_t timing_lock;pthread_cond_t timing_wakeup;pthread_t timing_thread;OH_AudioRenderer*renderer;OH_AudioStreamBuilder*builder;unsigned long long recovery_generation,recovery_token;int encoding_type;};
struct global {unsigned long long host_generation;};
struct ao {struct priv*priv;struct global*global;struct {int num;} channels;int samplerate,format;};
static const char*mode;static int builder;
static OH_AudioRenderer renderer={AUDIOSTREAM_STATE_PREPARED};
static atomic_bool entered,blocked,parked,finished,stop_finished,destroy_entered,destroy_blocked,state_entered,state_blocked;
static int released,destroyed,stops,unbound;
#define MP_ERR(...) ((void)0)
#define MPCLAMP(v,lo,hi) ((v)<(lo)?(lo):(v)>(hi)?(hi):(v))
#define MP_TIME_MS_TO_NS(v) ((v)*1000000LL)
static int af_fmt_is_int(int f){return f!=AF_FORMAT_FLOAT;}
static int af_fmt_to_bytes(int f){return f==AF_FORMAT_S32?4:2;}
static int af_fmt_from_planar(int f){return f;}
static void reset_timing(struct priv*p){(void)p;}
#define mp_mutex_lock pthread_mutex_lock
#define mp_mutex_unlock pthread_mutex_unlock
#define mp_mutex_destroy pthread_mutex_destroy
#define mp_cond_broadcast pthread_cond_broadcast
#define mp_cond_destroy pthread_cond_destroy
static int mp_mutex_init(pthread_mutex_t*m){return pthread_mutex_init(m,NULL);}
static int mp_cond_init(pthread_cond_t*c){return pthread_cond_init(c,NULL);}
static void*timing_worker(void*p){(void)p;return NULL;}
static void unbind_legacy(struct priv*p){(void)p;unbound++;}
static void mp_sleep_ns(long long ns){(void)ns;parked=true;usleep(1000);}
static void gate(void){entered=true;while(blocked)usleep(1000);}
static int OH_AudioStreamBuilder_Create(OH_AudioStreamBuilder**b,int type){(void)type;if(!strcmp(mode,"create-fail"))return -1;*b=&builder;return 0;}
#define SETTER(name) static int name(OH_AudioStreamBuilder*b,int value){(void)b;(void)value;return 0;}
SETTER(OH_AudioStreamBuilder_SetChannelCount)
SETTER(OH_AudioStreamBuilder_SetSamplingRate)
SETTER(OH_AudioStreamBuilder_SetEncodingType)
SETTER(OH_AudioStreamBuilder_SetRendererInfo)
SETTER(OH_AudioStreamBuilder_SetSampleFormat)
static int register_callbacks(struct ao*a){(void)a;return !strcmp(mode,"callback-fail")?-1:0;}
static int OH_AudioStreamBuilder_GenerateRenderer(OH_AudioStreamBuilder*b,OH_AudioRenderer**r){(void)b;if(!strcmp(mode,"generate-block"))gate();if(!strcmp(mode,"generate-fail"))return -1;*r=&renderer;return 0;}
static int OH_AudioRenderer_GetCurrentState(OH_AudioRenderer*r,int*s){
 state_entered=true;while(state_blocked)usleep(1000);*s=r->state;
 return !strcmp(mode,"quiescent-query-fail")?-1:0;
}
static int OH_AudioRenderer_Stop(OH_AudioRenderer*r){stops++;r->state=AUDIOSTREAM_STATE_STOPPED;return !strcmp(mode,"stop-error-stopped")?AUDIOSTREAM_ERROR_ILLEGAL_STATE:0;}
static int OH_AudioRenderer_Release(OH_AudioRenderer*r){(void)r;released++;if(!strncmp(mode,"quiescent-",10)||!strcmp(mode,"release-block")||!strcmp(mode,"release-destroy-block"))gate();return !strcmp(mode,"release-fail")||!strcmp(mode,"quiescent-release-fail")?-1:0;}
static int OH_AudioStreamBuilder_Destroy(OH_AudioStreamBuilder*b){(void)b;destroyed++;destroy_entered=true;while(destroy_blocked)usleep(1000);return !strcmp(mode,"destroy-fail")?-1:0;}
static int create_timing_thread(pthread_t*t,const pthread_attr_t*attr,void*(*entry)(void*),void*arg){
 if(!strcmp(mode,"timing-thread-fail"))return 11;
 return pthread_create(t,attr,entry,arg);
}
#define pthread_create create_timing_thread
/* FUNCTIONS */
#undef pthread_create
static void*initialize(void*p){assert(init(p)==0);finished=true;return NULL;}
static void*dispose(void*p){uninit(p);finished=true;return NULL;}
static void*stop_retired(void*p){(void)p;mp_host_stop_retired_audio();stop_finished=true;return NULL;}
static int release_empty(void*p){(void)p;return 0;}
static void wait_for(atomic_bool*flag){for(int i=0;i<2000&&!atomic_load(flag);i++)usleep(1000);assert(atomic_load(flag));}
static void check_retained_budget(void){
 unsigned long long fresh[15];
 for(int i=0;i<15;i++){fresh[i]=mp_host_audio_begin(mp_host_generation());assert(fresh[i]);}
 assert(!mp_host_audio_begin(mp_host_generation()));
 for(int i=0;i<15;i++)assert(mp_host_audio_remove(fresh[i],release_empty,NULL));
}
int main(int argc,char**argv){
 assert(argc==2);mode=argv[1];struct priv p={0};struct global g={mp_host_generation()};struct ao a={&p,&g,{2},48000,AF_FORMAT_S16};
 if(!strcmp(mode,"create-fail")||!strcmp(mode,"callback-fail")||!strcmp(mode,"generate-fail")){
  assert(init(&a)==-1);assert(!p.renderer&&!p.builder&&!p.recovery_token);assert(!released);
  assert(destroyed==strcmp(mode,"create-fail")!=0);mp_host_retire_all();assert(mp_host_audio_pending()==0);return 0;
 }
 if(!strcmp(mode,"generate-block")){
  blocked=true;pthread_t t;assert(!pthread_create(&t,NULL,initialize,&a));wait_for(&entered);
  mp_host_retire_all();assert(mp_host_audio_pending()==1);mp_host_stop_retired_audio();assert(mp_host_audio_pending()==1);
  blocked=false;pthread_join(t,NULL);assert(finished&&!mp_host_audio_control_lock(p.recovery_token));
  mp_host_stop_retired_audio();assert(mp_host_audio_pending()==0);uninit(&a);assert(released==1&&destroyed==1);return 0;
 }
 if(!strcmp(mode,"timing-thread-fail")){
  assert(init(&a)==-1);assert(released==1&&destroyed==1&&!p.recovery_token&&!p.timing_initialized&&!p.timing_started);return 0;
 }
 assert(init(&a)==0);assert(p.renderer&&p.builder&&p.recovery_token);
 if(!strncmp(mode,"quiescent-",10)){
  bool safe=!strcmp(mode,"quiescent-stopped")||!strcmp(mode,"quiescent-release-fail")||!strcmp(mode,"quiescent-query-block");
  renderer.state=safe||!strcmp(mode,"quiescent-query-fail")?AUDIOSTREAM_STATE_STOPPED:
   !strcmp(mode,"quiescent-paused")?AUDIOSTREAM_STATE_PAUSED:
   !strcmp(mode,"quiescent-prepared")?AUDIOSTREAM_STATE_PREPARED:AUDIOSTREAM_STATE_RUNNING;
  blocked=true;state_blocked=!strcmp(mode,"quiescent-query-block");
  pthread_t t;assert(!pthread_create(&t,NULL,dispose,&a));
  if(state_blocked){
   wait_for(&state_entered);mp_host_retire_all();assert(mp_host_audio_pending()==1&&!released);
   state_blocked=false;
  }
  wait_for(&entered);mp_host_retire_all();
  assert(mp_host_audio_pending()==(safe?0u:1u)&&!finished);
  // 静止仅放行下一代，仍保留资源上限；扫描不碰在途Release。
  mp_host_stop_retired_audio();assert(!stops);check_retained_budget();
  blocked=false;
  if(!strcmp(mode,"quiescent-release-fail")){
   wait_for(&parked);assert(mp_host_audio_pending()==0&&p.renderer&&p.recovery_token&&!finished);
   check_retained_budget();_Exit(0);
  }
  pthread_join(t,NULL);assert(finished&&!p.recovery_token&&mp_host_audio_pending()==0);
  assert(released==1&&destroyed==1);return 0;
 }

 if(!strcmp(mode,"stop-error-stopped")){
  renderer.state=AUDIOSTREAM_STATE_RUNNING;mp_host_retire_all();
  mp_host_stop_retired_audio();assert(stops==1&&mp_host_audio_pending()==0);
  assert(!mp_host_audio_control_lock(p.recovery_token));
  uninit(&a);assert(released==1&&destroyed==1&&!p.recovery_token);
  assert(!p.renderer&&!p.builder&&mp_host_audio_pending()==0);return 0;
 }
 if(!strcmp(mode,"release-destroy-block")){
  blocked=true;destroy_blocked=true;pthread_t closing,stopping;
  assert(!pthread_create(&closing,NULL,dispose,&a));wait_for(&entered);
  mp_host_retire_all();assert(mp_host_audio_pending()==1);
  // Release 未确认时必须拒绝续播，但恢复扫描不能等旧槽的 control 锁。
  assert(!pthread_create(&stopping,NULL,stop_retired,NULL));wait_for(&stop_finished);pthread_join(stopping,NULL);
  assert(mp_host_audio_pending()==1&&!stops&&!finished);
  blocked=false;wait_for(&destroy_entered);
  // Release 已完成，只有 Builder_Destroy 卡住：音频静止和资源归还分别判断。
  assert(!p.renderer&&p.builder&&p.recovery_token&&!finished&&mp_host_audio_pending()==0);
  stop_finished=false;assert(!pthread_create(&stopping,NULL,stop_retired,NULL));wait_for(&stop_finished);pthread_join(stopping,NULL);
  check_retained_budget();assert(released==1&&!stops&&!finished);
  destroy_blocked=false;pthread_join(closing,NULL);assert(finished&&mp_host_audio_pending()==0);
  assert(!p.renderer&&!p.builder&&!p.recovery_token&&released==1&&destroyed==1);return 0;
 }
 if(!strcmp(mode,"release-fail")||!strcmp(mode,"destroy-fail")||!strcmp(mode,"release-block")||!strcmp(mode,"destroy-block")){
  destroy_blocked=!strcmp(mode,"destroy-block");
  blocked=true;pthread_t t;assert(!pthread_create(&t,NULL,dispose,&a));
  if(!strcmp(mode,"release-block"))wait_for(&entered);
  else if(!strcmp(mode,"destroy-block"))wait_for(&destroy_entered);
  else wait_for(&parked);
  mp_host_retire_all();bool renderer_released=!strcmp(mode,"destroy-fail")||!strcmp(mode,"destroy-block");
  assert(mp_host_audio_pending()==(renderer_released?0u:1u)&&!finished);
  // 静止事实不能归还仍保留的槽、AO 或 Builder；新代使用独立剩余额度。
  check_retained_budget();
  if(!strcmp(mode,"release-block")){blocked=false;pthread_join(t,NULL);assert(finished&&mp_host_audio_pending()==0);return 0;}
  if(!strcmp(mode,"destroy-block")){
   mp_host_stop_retired_audio();assert(mp_host_audio_pending()==0&&!stops);
   destroy_blocked=false;pthread_join(t,NULL);assert(finished&&released==1&&destroyed==1);return 0;
  }
  assert(p.recovery_token&&unbound==1);assert(!strcmp(mode,"release-fail")?p.renderer!=NULL:p.renderer==NULL);
  _Exit(0); // 验证失败保留后结束测试进程，不让仍保留的栈对象被析构。
 }
 uninit(&a);assert(released==1&&destroyed==1&&!p.recovery_token&&!p.renderer&&!p.builder);
 uninit(&a);assert(released==1&&destroyed==1);mp_host_retire_all();assert(mp_host_audio_pending()==0);
}
'''.replace('/* FUNCTIONS */','\n'.join(function(n) for n in ['stop_timing_worker','release_for_recovery','uninit','stop_for_recovery','init']))
# 保留 C 断言括号，避免比较运算结合次序误判期望值。
code=code.replace('destroyed==strcmp(mode,"create-fail")!=0','destroyed==(strcmp(mode,"create-fail")!=0)')
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(code)
 subprocess.run(['clang','-std=gnu11','-pthread','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(root/'native/mpv'),str(p/'test.c'),str(root/'native/mpv/host_recovery.c'),'-o',str(p/'test')],check=True)
 for case in sys.argv[2:] or ['quiescent-stopped','quiescent-release-fail','quiescent-running','quiescent-paused','quiescent-prepared','quiescent-query-fail','quiescent-query-block','normal','timing-thread-fail','create-fail','callback-fail','generate-fail','generate-block','release-block','release-fail','destroy-fail','destroy-block','release-destroy-block','stop-error-stopped']:
  subprocess.run([str(p/'test'),case],check=True,timeout=5);print(case,'PASS',flush=True)
