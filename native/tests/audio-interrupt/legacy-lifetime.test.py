"""编译真实 legacy 登记/回调函数，确定性阻塞旧回调验证其他 AO 不受牵连。"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[3]
source = (Path(sys.argv[1])/'audio/out/ao_ohaudio.c').read_text()

def function(name):
    match = re.search(r'^static [\w *]+\b'+name+r'\([^;]*?\)\s*\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    return match[0]

binding = source[source.index('struct legacy_binding {'):source.index('struct priv {')]
start = re.search(r'^static pthread_(?:rwlock|mutex)_t legacy_lock',source,re.M)
assert start
registry = source[start.start():source.index('static void reset_timing')]
code = r'''
#include "host_recovery.h"
#include <assert.h>
#include <limits.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
/* BINDING */
struct priv {unsigned long long recovery_generation;struct legacy_binding legacy;};
struct ao {struct priv*priv;unsigned writes,pauses;};
typedef void OH_AudioRenderer;
typedef int OH_AudioInterrupt_ForceType;
typedef int OH_AudioInterrupt_Hint;
enum {AUDIOSTREAM_INTERRUPT_HINT_PAUSE=1,AUDIOSTREAM_INTERRUPT_HINT_STOP=2};
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed=PTHREAD_COND_INITIALIZER;
static bool block_callback,entered,old_unbind_started,old_unbound,fresh_started,fresh_done;
static bool release_write,old_callback_done;
static unsigned callbacks_entered;
static bool interrupt_mode;
static struct ao*blocked_ao;
static void enter_callback(struct ao*a,bool interrupt){
 pthread_mutex_lock(&gate);
 if(a==blocked_ao&&block_callback){entered=true;callbacks_entered++;pthread_cond_broadcast(&changed);while(block_callback&&(interrupt||!release_write))pthread_cond_wait(&changed,&gate);}
 pthread_mutex_unlock(&gate);
}
static int audio_on_write_callback(OH_AudioRenderer*r,void*opaque,void*data,int32_t size){
 (void)r;struct ao*a=opaque;enter_callback(a,false);a->writes++;memset(data,37,size);return 0;
}
static void ao_request_pause(struct ao*a){enter_callback(a,true);a->pauses++;}
/* REGISTRY */
/* CALLBACKS */
static bool wait_flag(bool*flag){
 struct timespec until;clock_gettime(CLOCK_REALTIME,&until);until.tv_sec++;
 pthread_mutex_lock(&gate);int rc=0;
 while(!*flag&&!rc)rc=pthread_cond_timedwait(&changed,&gate,&until);
 bool done=*flag;pthread_mutex_unlock(&gate);return done;
}
static void mark(bool*flag){pthread_mutex_lock(&gate);*flag=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&gate);}
static void*old_callback(void*token){
 unsigned char bytes[16];
 if(interrupt_mode)legacy_interrupt(NULL,token,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
 else legacy_write(NULL,token,bytes,sizeof(bytes));
 mark(&old_callback_done);return NULL;
}
static void*second_callback(void*token){legacy_interrupt(NULL,token,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);return NULL;}
static void*old_unbind(void*opaque){mark(&old_unbind_started);unbind_legacy(((struct ao*)opaque)->priv);mark(&old_unbound);return NULL;}
static void*fresh_session(void*opaque){
 struct ao*a=opaque;mark(&fresh_started);void*token=bind_legacy(a);assert(token);
 unsigned char bytes[16];legacy_write(NULL,token,bytes,sizeof(bytes));
 legacy_interrupt(NULL,token,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
 unbind_legacy(a->priv);mark(&fresh_done);return NULL;
}
static bool token_registered(void*token){
 REGISTRY_LOCK;
 bool present=false;for(struct legacy_binding*b=legacy_bindings;b;b=b->next)if(b->token==(uintptr_t)token)present=true;
 REGISTRY_UNLOCK;
 return present;
}
int main(int argc,char**argv){
 assert(argc==2);const char*mode=argv[1];bool dual=!strcmp(mode,"two-callbacks");
 struct priv old_priv={.recovery_generation=mp_host_generation()},new_priv={.recovery_generation=mp_host_generation()};
 struct ao old={.priv=&old_priv},fresh={.priv=&new_priv};
 void*token=bind_legacy(&old);assert(token);
 if(!strcmp(mode,"overflow")){
#if HAVE_REFS
  REGISTRY_LOCK;old_priv.legacy.in_flight=UINT_MAX;REGISTRY_UNLOCK;
  unsigned char bytes[16];memset(bytes,99,sizeof(bytes));legacy_write(NULL,token,bytes,sizeof(bytes));
  legacy_interrupt(NULL,token,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
  assert(!old.writes&&!old.pauses&&old_priv.legacy.in_flight==UINT_MAX);
  for(unsigned i=0;i<sizeof(bytes);i++)assert(!bytes[i]);
  REGISTRY_LOCK;old_priv.legacy.in_flight=0;REGISTRY_UNLOCK;unbind_legacy(&old_priv);
#else
  assert(!"缺少有界在途引用");
#endif
  return 0;
 }
 interrupt_mode=!strcmp(mode,"interrupt-blocked");block_callback=true;blocked_ao=&old;
 pthread_t callback,closing,other,second;assert(!pthread_create(&callback,NULL,old_callback,token));assert(wait_flag(&entered));
 if(dual){
  assert(!pthread_create(&second,NULL,second_callback,token));
  struct timespec until;clock_gettime(CLOCK_REALTIME,&until);until.tv_sec++;
  pthread_mutex_lock(&gate);int rc=0;while(callbacks_entered<2&&!rc)rc=pthread_cond_timedwait(&changed,&gate,&until);
  assert(callbacks_entered==2);pthread_mutex_unlock(&gate);
 }
 assert(!pthread_create(&closing,NULL,old_unbind,&old));assert(wait_flag(&old_unbind_started));
 assert(!pthread_create(&other,NULL,fresh_session,&fresh));assert(wait_flag(&fresh_started));
 // 旧回调仍明确阻塞：其他 AO 必须完成登记、写回调、中断与注销。
 assert(wait_flag(&fresh_done)&&"旧回调不应阻塞其他 AO 的登记/注销");pthread_join(other,NULL);
 assert(fresh.writes==1&&fresh.pauses==1);
 pthread_mutex_lock(&gate);assert(!old_unbound);pthread_mutex_unlock(&gate);
 // 新 AO 已完成后，允许旧注销线程获得一次调度，再检查它已撤销旧 token。
 for(unsigned i=0;i<1000&&token_registered(token);i++)usleep(1000);
 assert(!token_registered(token));assert(bind_legacy(&old)==NULL);
 unsigned char bytes[16];memset(bytes,99,sizeof(bytes));legacy_write(NULL,token,bytes,sizeof(bytes));
 legacy_interrupt(NULL,token,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);assert(!old.writes&&!old.pauses);
 for(unsigned i=0;i<sizeof(bytes);i++)assert(!bytes[i]);
 if(dual){
  pthread_mutex_lock(&gate);release_write=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&gate);
  assert(wait_flag(&old_callback_done));
  pthread_mutex_lock(&gate);assert(!old_unbound);pthread_mutex_unlock(&gate);
  assert(old.writes==1&&!old.pauses);
 }
 pthread_mutex_lock(&gate);block_callback=false;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&gate);
 pthread_join(callback,NULL);if(dual)pthread_join(second,NULL);pthread_join(closing,NULL);assert(old_unbound);
 assert(old.writes==(interrupt_mode?0:1)&&old.pauses==(interrupt_mode||dual?1:0));
 // 同一 AO 存储重新登记也不能让旧 token 命中新实例。
 void*next=bind_legacy(&old);assert(next&&next!=token);unsigned writes=old.writes,pauses=old.pauses;
 legacy_write(NULL,token,bytes,sizeof(bytes));legacy_interrupt(NULL,token,0,AUDIOSTREAM_INTERRUPT_HINT_PAUSE);
 assert(old.writes==writes&&old.pauses==pauses);unbind_legacy(&old_priv);unbind_legacy(&old_priv);
 assert(legacy_bindings==NULL);
 puts("PASS 旧回调阻塞隔离、注销等待、迟到 token 与地址复用");
}
'''
rw = 'pthread_rwlock_t' in registry
code = code.replace('/* BINDING */',binding).replace('/* REGISTRY */',registry)
code = code.replace('/* CALLBACKS */',function('legacy_write')+'\n'+function('legacy_interrupt'))
code = code.replace('REGISTRY_LOCK','pthread_rwlock_rdlock(&legacy_lock)' if rw else 'pthread_mutex_lock(&legacy_lock)')
code = code.replace('REGISTRY_UNLOCK','pthread_rwlock_unlock(&legacy_lock)' if rw else 'pthread_mutex_unlock(&legacy_lock)')
code = '#define HAVE_REFS '+str(int('in_flight' in binding))+'\n'+code
cases = sys.argv[2:] or ['write-blocked','interrupt-blocked','two-callbacks','overflow']
with tempfile.TemporaryDirectory() as temp:
    path=Path(temp);(path/'test.c').write_text(code)
    subprocess.run(['clang','-std=gnu11','-pthread','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined',
                    '-I'+str(root/'native/mpv'),str(path/'test.c'),str(root/'native/mpv/host_recovery.c'),'-o',str(path/'test')],check=True)
    for case in cases:
        subprocess.run([str(path/'test'),case],check=True,timeout=5)
        print(case,'PASS',flush=True)
