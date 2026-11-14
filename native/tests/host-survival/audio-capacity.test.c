#define _POSIX_C_SOURCE 200809L
#include "host_recovery.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <errno.h>
struct held { unsigned long long token; atomic_bool entered,allow; bool quiescent; };
static void tick(void) {struct timespec t={0,1000000};while(nanosleep(&t,&t)<0)assert(errno==EINTR);}
static int stop(void*p){(void)p;return 0;}
static int dispose(void*p){(void)p;return 0;}
static int hold(void*p) {
 struct held*s=p;
 if(s->quiescent)mp_host_audio_confirm_quiescent(s->token);
 atomic_store(&s->entered,true);
 while(!atomic_load(&s->allow))tick();
 return 0;
}
static void *release(void*p){struct held*s=p;assert(mp_host_audio_remove(s->token,hold,s));return NULL;}
int main(int argc,char**argv) {
 assert(argc==2);bool safe=!strcmp(argv[1],"quiescent");
 assert(safe||!strcmp(argv[1],"unknown"));
 struct held held[16]={0};pthread_t workers[16];
 unsigned long long old=mp_host_generation();
 for(unsigned i=0;i<16;i++){
  held[i].token=mp_host_audio_begin(old);held[i].quiescent=safe;
  assert(held[i].token&&mp_host_audio_publish(held[i].token,stop,&held[i]));
  assert(!pthread_create(&workers[i],NULL,release,&held[i]));
 }
 for(unsigned i=0;i<16;i++){
  for(unsigned n=0;n<2000&&!atomic_load(&held[i].entered);n++)tick();
  assert(atomic_load(&held[i].entered));
 }
 mp_host_retire_all();unsigned long long fresh=mp_host_generation();
 // 16个永久停留的释放操作：状态快照和容量检查必须可返回；静止不等于预算回收。
 for(unsigned n=0;n<10000;n++){
  assert(mp_host_audio_pending()==(safe?0u:16u));
  assert(!mp_host_audio_begin(fresh));
 }
 mp_host_stop_retired_audio(); // 不等待正在释放的任意槽。
 atomic_store(&held[7].allow,true);assert(!pthread_join(workers[7],NULL));
 unsigned long long replacement=mp_host_audio_begin(fresh);assert(replacement&&replacement!=held[7].token);
 assert(!mp_host_audio_begin(fresh));
 assert(!mp_host_audio_publish(held[7].token,stop,&held[7]));
 assert(!mp_host_audio_remove(held[7].token,dispose,NULL));
 assert(!mp_host_audio_control_lock(held[7].token));
 assert(mp_host_audio_publish(replacement,stop,&held[7]));
 assert(mp_host_audio_control_lock(replacement));mp_host_audio_control_unlock(replacement);
 assert(mp_host_audio_pending()==(safe?0u:15u));
 for(unsigned i=0;i<16;i++)if(i!=7){atomic_store(&held[i].allow,true);assert(!pthread_join(workers[i],NULL));}
 assert(mp_host_audio_pending()==0);
 assert(mp_host_audio_remove(replacement,dispose,NULL));
 unsigned long long tokens[16];
 for(unsigned i=0;i<16;i++){tokens[i]=mp_host_audio_begin(fresh);assert(tokens[i]);}
 assert(!mp_host_audio_begin(fresh));
 for(unsigned i=0;i<16;i++)assert(mp_host_audio_remove(tokens[i],dispose,NULL));
 puts(safe?"PASS 已静止16槽仍保留，迟到释放恰好归还一槽":"PASS 未确认16槽不放行，快照可返回，迟到完成及旧令牌隔离");
}
