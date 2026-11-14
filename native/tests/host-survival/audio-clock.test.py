"""编译实际OHAudio回调、时钟线程和关闭函数；不以平台替身代替设备音画验收。"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
src = (Path(sys.argv[1]) / 'audio/out/ao_ohaudio.c').read_text()
def function(name):
    match = re.search(r'^static [\w *]+\b' + name + r'\([^;]*?\)\s*\n\{.*?^\}', src, re.M | re.S)
    assert match, name
    return match[0]
worker = 'static void *timing_worker(' in src
structs = src[src.index('struct legacy_binding {'):src.index('// token 永不复用')]
registry = src[src.index('static pthread_mutex_t legacy_lock'):src.index('static void reset_timing')]
names = ['reset_timing'] + (['timing_worker', 'stop_timing_worker'] if worker else [])
names += ['release_for_recovery', 'uninit', 'audio_on_write_callback', 'legacy_write', 'modern_write']
code = r'''
#include "host_recovery.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <limits.h>
#include <time.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#define MP_TIME_MS_TO_NS(v) ((int64_t)(v)*1000000)
#define MP_TIME_S_TO_NS(v) ((int64_t)(v)*1000000000)
#define MPMIN(a,b) ((a)<(b)?(a):(b))
#define MPCLAMP(v,l,h) MPMIN((v)>(l)?(v):(l),h)
#define AF_FORMAT_U8 1
#define AUDIOSTREAM_SUCCESS 0
#define AUDIO_DATA_CALLBACK_RESULT_VALID 0
typedef int OH_AudioStream_Result;
typedef int OH_AudioStream_State;
#define AUDIOSTREAM_STATE_STOPPED 3
typedef int OH_AudioData_Callback_Result;
typedef int OH_AudioStreamBuilder;
typedef struct { atomic_bool blocked,entered; atomic_int calls,released; atomic_llong pos,stamp; } OH_AudioRenderer;
typedef pthread_mutex_t mp_mutex;
typedef pthread_cond_t mp_cond;
#define mp_mutex_lock pthread_mutex_lock
#define mp_mutex_unlock pthread_mutex_unlock
#define mp_mutex_destroy pthread_mutex_destroy
#define mp_cond_signal pthread_cond_signal
#define mp_cond_broadcast pthread_cond_broadcast
#define mp_cond_destroy pthread_cond_destroy
static int mp_mutex_init(mp_mutex*m){return pthread_mutex_init(m,NULL);}
static int mp_cond_init(mp_cond*c){return pthread_cond_init(c,NULL);}
static int mp_cond_timedwait(mp_cond*c,mp_mutex*m,int64_t ns){
 struct timespec ts;clock_gettime(CLOCK_REALTIME,&ts);ts.tv_nsec+=ns;
 while(ts.tv_nsec>=1000000000){ts.tv_sec++;ts.tv_nsec-=1000000000;}
 return pthread_cond_timedwait(c,m,&ts);
}
/* STRUCTS */
struct ao {struct priv *priv; int format,sstride,samplerate;};
static _Thread_local bool in_write;
static atomic_int callback_queries;
static atomic_llong now_ns=1000000000;
static atomic_llong end_ns;
static atomic_bool callback_done,close_done;
static atomic_int builder_releases;
static int64_t mp_time_ns(void){return now_ns;}
static void mp_sleep_ns(int64_t ns){(void)ns;usleep(1000);}
static int OH_AudioRenderer_GetAudioTimestampInfo(OH_AudioRenderer*r,int64_t*pos,int64_t*stamp){
 if(in_write)callback_queries++;
 r->entered=true;r->calls++;
 while(r->blocked)usleep(1000);
 *pos=r->pos;*stamp=r->stamp;return 0;
}
static int OH_AudioRenderer_GetCurrentState(OH_AudioRenderer*r, int*state){(void)r;*state=2;return 0;}
static int OH_AudioRenderer_Release(OH_AudioRenderer*r){assert(!r->blocked);r->released++;return 0;}
static int OH_AudioStreamBuilder_Destroy(OH_AudioStreamBuilder*b){(void)b;builder_releases++;return 0;}
static void ao_read_data(struct ao*a,void**data,int samples,int64_t end,void*unused,bool pad,bool blocking){
 (void)unused;(void)pad;(void)blocking;end_ns=end;memset(*data,37,samples*a->sstride);
}
/* REGISTRY */
/* FUNCTIONS */
static int stop_stub(void*r){(void)r;return 0;}
static void setup(struct ao*a,struct priv*p,OH_AudioRenderer*r){
 memset(p,0,sizeof(*p));*a=(struct ao){p,0,2,48000};p->renderer=r;
 p->recovery_generation=mp_host_generation();
 p->recovery_token=mp_host_audio_begin(p->recovery_generation);assert(p->recovery_token);
 assert(mp_host_audio_publish(p->recovery_token,stop_stub,r));assert(bind_legacy(a));
#if HAVE_WORKER
 assert(!pthread_mutex_init(&p->timing_lock,NULL));assert(!pthread_cond_init(&p->timing_wakeup,NULL));p->timing_initialized=true;
#endif
 reset_timing(p);
}
static void launch(struct ao*a){
#if HAVE_WORKER
 assert(!pthread_create(&a->priv->timing_thread,NULL,timing_worker,a));a->priv->timing_started=true;
#else
 (void)a;
#endif
}
static void wait_flag(atomic_bool*f){for(int i=0;i<2000&&!atomic_load(f);i++)usleep(1000);assert(atomic_load(f));}
static int sdk;
static void write_one(struct ao*a){
 unsigned char data[960];memset(data,99,sizeof(data));in_write=true;
 if(sdk<20)legacy_write(a->priv->renderer,(void*)a->priv->legacy.token,data,sizeof(data));
 else modern_write(a->priv->renderer,(void*)a->priv->legacy.token,data,sizeof(data));
 in_write=false;for(unsigned i=0;i<sizeof(data);i++)assert(data[i]==37);
 assert(callback_queries==0&&"写回调不能重入平台时间戳接口");
 assert(end_ns>=now_ns);
}
static void*write_thread(void*a){write_one(a);callback_done=true;return NULL;}
static void*close_thread(void*a){uninit(a);close_done=true;return NULL;}
static void wait_sample(struct priv*p,int64_t pos){
#if HAVE_WORKER
 bool ready=false;for(int i=0;i<2000;i++){
  pthread_mutex_lock(&p->timing_lock);ready=p->timestamp_valid&&p->frame_position==pos;pthread_mutex_unlock(&p->timing_lock);
  if(ready)break;usleep(1000);
 }assert(ready);
#else
 (void)p;(void)pos;
#endif
}
int main(int argc,char**argv){
 assert(argc==3);sdk=atoi(argv[1]);const char*mode=argv[2];
 struct priv p;struct ao a;OH_AudioRenderer r={.pos=0,.stamp=999000000};setup(&a,&p,&r);
 if(!strcmp(mode,"callback-contract")){write_one(&a);uninit(&a);return 0;}
#if HAVE_WORKER
 if(!strcmp(mode,"blocked-query")){
  r.blocked=true;launch(&a);wait_flag(&r.entered);
  pthread_t writer,closer;assert(!pthread_create(&writer,NULL,write_thread,&a));wait_flag(&callback_done);pthread_join(writer,NULL);
  void*old_token=(void*)p.legacy.token;
  assert(!pthread_create(&closer,NULL,close_thread,&a));
  bool revoked=false;for(int n=0;n<2000;n++){
   pthread_mutex_lock(&legacy_lock);revoked=legacy_bindings==NULL;pthread_mutex_unlock(&legacy_lock);
   if(revoked)break;usleep(1000);
  }
  assert(revoked&&!close_done&&!r.released&&p.recovery_token);
  unsigned char late[32];memset(late,99,sizeof(late));legacy_write(&r,old_token,late,sizeof(late));
  for(unsigned i=0;i<sizeof(late);i++)assert(!late[i]);
  // 旧查询挂住时另一个槽仍能查询、写数据和释放；不把它误判为系统整体失效。
  struct priv fresh_p;struct ao fresh;OH_AudioRenderer fresh_r={.pos=0,.stamp=999000000};setup(&fresh,&fresh_p,&fresh_r);
  launch(&fresh);wait_sample(&fresh_p,0);write_one(&fresh);uninit(&fresh);assert(fresh_r.released==1);
  r.blocked=false;pthread_join(closer,NULL);assert(close_done&&r.released==1&&!p.recovery_token);return 0;
 }
 if(!strcmp(mode,"clock")){
  launch(&a);wait_sample(&p,0);write_one(&a);
  // 480个采样、48kHz：首缓冲的结束时刻是当前时间之后10ms。
  assert(end_ns==now_ns+10000000);
  write_one(&a);assert(end_ns==now_ns+19000000);
  // 过期快照不能一直按旧播放时刻外推；降级估计仍有上限。
  stop_timing_worker(&p);now_ns+=3000000000LL;write_one(&a);
  assert(!p.timestamp_valid&&end_ns<=now_ns+260000000);
  reset_timing(&p);assert(p.written_frames==0&&!p.timestamp_valid);write_one(&a);
  assert(end_ns==now_ns+10000000);uninit(&a);return 0;
 }
 if(!strcmp(mode,"delayed-query")){
  r.blocked=true;launch(&a);wait_flag(&r.entered);now_ns+=500000000;r.stamp=now_ns-1000000;r.blocked=false;
  wait_sample(&p,0);write_one(&a);assert(end_ns==now_ns+10000000);uninit(&a);return 0;
 }
 if(!strcmp(mode,"route-reset")||!strcmp(mode,"route-reset-invalid")){
  p.written_frames=960;r.pos=480;r.stamp=now_ns;launch(&a);wait_sample(&p,480);
  write_one(&a);assert(end_ns==now_ns+20000000);
  r.pos=0;pthread_mutex_lock(&p.timing_lock);if(!strcmp(mode,"route-reset-invalid"))p.timestamp_valid=false;pthread_cond_signal(&p.timing_wakeup);pthread_mutex_unlock(&p.timing_lock);
  wait_sample(&p,0);write_one(&a);assert(end_ns==now_ns+10000000);
  uninit(&a);return 0;
 }
 if(!strcmp(mode,"retired-query")){
  r.blocked=true;launch(&a);wait_flag(&r.entered);mp_host_retire_all();
  unsigned char bytes[960];memset(bytes,99,sizeof(bytes));
  legacy_write(&r,(void*)p.legacy.token,bytes,sizeof(bytes));for(unsigned i=0;i<sizeof(bytes);i++)assert(!bytes[i]);
  assert(mp_host_audio_pending()==1);r.blocked=false;uninit(&a);assert(!mp_host_audio_pending());return 0;
 }
 if(!strcmp(mode,"budget")){
  uninit(&a);struct priv ps[16];struct ao as[16];OH_AudioRenderer rs[16]={0};
  for(int i=0;i<16;i++){rs[i].blocked=true;rs[i].stamp=999000000;setup(&as[i],&ps[i],&rs[i]);launch(&as[i]);wait_flag(&rs[i].entered);}
  assert(!mp_host_audio_begin(mp_host_generation()));
  // 全部未知查询仍占槽，不能靠重试扩张线程；真实返回后才能回收并复用。
  for(int i=0;i<16;i++){rs[i].blocked=false;uninit(&as[i]);assert(rs[i].released==1);}
  setup(&a,&p,&r);write_one(&a);uninit(&a);return 0;
 }
 if(!strcmp(mode,"repeat")){
  uninit(&a);
  for(int i=0;i<64;i++){OH_AudioRenderer next={.pos=0,.stamp=999000000};setup(&a,&p,&next);launch(&a);wait_sample(&p,0);write_one(&a);uninit(&a);assert(next.released==1);}
  assert(!legacy_bindings);return 0;
 }
#endif
 assert(!"未知模式或缺少采样线程实现");
}
'''
code = '#define HAVE_WORKER '+str(int(worker))+'\n'+code
code = code.replace('/* STRUCTS */', structs).replace('/* REGISTRY */',registry)
code = code.replace('/* FUNCTIONS */','\n'.join(function(n) for n in names))
with tempfile.TemporaryDirectory() as td:
    p=Path(td);(p/'test.c').write_text(code)
    subprocess.run(['clang','-std=gnu11','-pthread','-Wall','-Wextra','-Werror','-Wno-unused-function',
                    '-fsanitize=address,undefined','-I'+str(ROOT/'native/mpv'),str(p/'test.c'),
                    str(ROOT/'native/mpv/host_recovery.c'),'-o',str(p/'test')],check=True)
    for sdk in ['19','24','26']:
        for case in sys.argv[2:] or ['callback-contract','blocked-query','clock','delayed-query','route-reset','route-reset-invalid','retired-query','budget','repeat']:
            subprocess.run([str(p/'test'),sdk,case],check=True,timeout=10)
            print('API'+sdk,case,'PASS',flush=True)
