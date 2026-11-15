"""编译实际 OHAudio 控制函数，平台为替身；不冒充真机焦点验收。"""
from pathlib import Path
import re,subprocess,tempfile,sys
root=Path(__file__).resolve().parents[3]
s=(Path(sys.argv[1])/'audio/out/ao_ohaudio.c').read_text()
def function(name):
 m=re.search(r'^static [\w *]+\b'+name+r'\([^;]*?\)\s*\n\{.*?^\}',s,re.M|re.S)
 assert m, name
 return m[0]
code=r'''
#define _POSIX_C_SOURCE 200809L
#include "host_recovery.h"
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
#include <time.h>
#include <errno.h>
typedef int OH_AudioStream_State;
typedef int OH_AudioStream_Result;
typedef struct {
 int state,starts,pauses,flushes,failed;
 atomic_int stops,queries;
 bool stop_sets_state,post_query_failed;
 int stop_state;
} OH_AudioRenderer;
#define AUDIOSTREAM_SUCCESS 0
#define AUDIOSTREAM_ERROR_INVALID_PARAM 1
#define AUDIOSTREAM_ERROR_ILLEGAL_STATE 2
#define AUDIOSTREAM_STATE_PREPARED 1
#define AUDIOSTREAM_STATE_RUNNING 2
#define AUDIOSTREAM_STATE_STOPPED 3
#define AUDIOSTREAM_STATE_RELEASED 4
#define AUDIOSTREAM_STATE_PAUSED 5
static atomic_bool stop_blocked,stop_entered,scan_finished;
static void wait_one_ms(void){
 struct timespec delay={0,1000000};
 while(nanosleep(&delay,&delay)<0)assert(errno==EINTR);
}
int OH_AudioRenderer_GetCurrentState(OH_AudioRenderer*r,int*s){
 int call=atomic_fetch_add(&r->queries,1)+1;
 if(call>1&&r->post_query_failed)return AUDIOSTREAM_ERROR_INVALID_PARAM;
 *s=r->state;return AUDIOSTREAM_SUCCESS;
}
int OH_AudioRenderer_Stop(OH_AudioRenderer*r){
 r->stops++;stop_entered=true;while(stop_blocked)wait_one_ms();
 if(r->stop_sets_state)r->state=r->stop_state;
 else if(!r->failed)r->state=AUDIOSTREAM_STATE_STOPPED;
 return r->failed?AUDIOSTREAM_ERROR_ILLEGAL_STATE:AUDIOSTREAM_SUCCESS;
}
int OH_AudioRenderer_Start(OH_AudioRenderer*r){r->starts++;r->state=AUDIOSTREAM_STATE_RUNNING;return 0;}
int OH_AudioRenderer_Pause(OH_AudioRenderer*r){r->pauses++;r->state=AUDIOSTREAM_STATE_PAUSED;return 0;}
int OH_AudioRenderer_Flush(OH_AudioRenderer*r){r->flushes++;return 0;}
struct priv {bool timestamp_valid;pthread_mutex_t timing_lock;pthread_cond_t timing_wakeup;OH_AudioRenderer*renderer;unsigned long long recovery_token;int last_query;};
struct ao {struct priv*priv;};
static void reset_timing(struct priv*p){p->last_query=0;}
#define mp_mutex_lock pthread_mutex_lock
#define mp_mutex_unlock pthread_mutex_unlock
#define mp_cond_signal pthread_cond_signal
/* METHODS */
static void*scan(void*unused){(void)unused;mp_host_stop_retired_audio();scan_finished=true;return NULL;}
int main(int argc,char**argv){
 assert(argc==2);const char*mode=argv[1];
 if(strcmp(mode,"normal")){
  bool blocked=!strcmp(mode,"stop-blocked");
  bool stopped=!strcmp(mode,"stop-error-stopped")||blocked;
  bool prepared=!strcmp(mode,"stop-error-prepared");
  bool query_failed=!strcmp(mode,"post-query-failed");
  OH_AudioRenderer r={.state=AUDIOSTREAM_STATE_RUNNING,.failed=1,
   .stop_sets_state=stopped||prepared||query_failed,
   .stop_state=prepared?AUDIOSTREAM_STATE_PREPARED:AUDIOSTREAM_STATE_STOPPED,
   .post_query_failed=query_failed};
  unsigned long long token=mp_host_audio_begin(mp_host_generation());
  assert(token&&mp_host_audio_publish(token,stop_for_recovery,&r));
  mp_host_retire_all();
  if(blocked){
   stop_blocked=true;pthread_t worker;assert(!pthread_create(&worker,NULL,scan,NULL));
   for(int i=0;i<2000&&!stop_entered;i++)wait_one_ms();
   assert(stop_entered);
   // Stop 尚未返回：不得提前查询状态、确认静止或结束扫描。
   for(int i=0;i<20;i++){
    assert(r.queries==1&&!scan_finished&&mp_host_audio_pending()==1);
    wait_one_ms();
   }
   stop_blocked=false;assert(!pthread_join(worker,NULL));assert(scan_finished);
  }else mp_host_stop_retired_audio();
  assert(r.stops==1&&r.queries==2);
  assert(mp_host_audio_pending()==(stopped?0u:1u));
  assert(!mp_host_audio_control_lock(token));
  // 返回错误不能触发隐式 Stop 重试，成功确认也不允许重启旧 renderer。
  mp_host_stop_retired_audio();assert(r.stops==1&&r.queries==2);
  return 0;
 }
 OH_AudioRenderer r={.state=AUDIOSTREAM_STATE_PREPARED};struct priv p={.renderer=&r};struct ao a={.priv=&p};
 pthread_mutex_init(&p.timing_lock,NULL);pthread_cond_init(&p.timing_wakeup,NULL);
 p.recovery_token=mp_host_audio_begin(mp_host_generation());
 assert(mp_host_audio_publish(p.recovery_token,stop_for_recovery,&r));
 start(&a);assert(r.starts==1);set_pause(&a,true);assert(r.pauses==1);
 set_pause(&a,false);assert(r.starts==2);reset(&a);assert(r.flushes==1);
 mp_host_retire_all();start(&a);assert(!set_pause(&a,false));reset(&a);
 assert(r.starts==2&&r.flushes==1);mp_host_stop_retired_audio();
 assert(r.stops==1&&r.state==AUDIOSTREAM_STATE_STOPPED&&mp_host_audio_pending()==0);
 OH_AudioRenderer prepared={.state=AUDIOSTREAM_STATE_PREPARED};assert(stop_for_recovery(&prepared)==0&&prepared.stops==0);
 OH_AudioRenderer failed={.state=AUDIOSTREAM_STATE_RUNNING,.failed=1};assert(stop_for_recovery(&failed)!=0);
}
'''.replace('/* METHODS */','\n'.join(function(n) for n in ['stop_for_recovery','reset','set_pause','start']))
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(code)
 subprocess.run(['clang','-std=c11','-pthread','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(root/'native/mpv'),str(p/'test.c'),str(root/'native/mpv/host_recovery.c'),'-o',str(p/'test')],check=True)
 for case in sys.argv[2:] or ['normal','stop-error-stopped','stop-error-running','post-query-failed','stop-error-prepared','stop-blocked']:
  subprocess.run([str(p/'test'),case],check=True,timeout=5);print(case,'PASS',flush=True)
print('PASS 实际 OHAudio 控制、Stop 返回后确认、失败拒绝与未返回边界')
