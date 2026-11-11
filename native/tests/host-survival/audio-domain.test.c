#include "host_recovery.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <unistd.h>
static int stopped,released;
static atomic_bool block,entered,scan_done;
static int stop(void *p){assert(p);entered=true;while(block)usleep(1000);stopped++;return *(int*)p;}
static int release(void *p){assert(p);released++;return 0;}
static int release_failed(void *p){assert(p);return -1;}
static void *worker(void *p){(void)p;mp_host_stop_retired_audio();scan_done=true;return NULL;}
int main(void){
 unsigned long long old=mp_host_generation();int ok=0,fail=-1;
 unsigned long long a=mp_host_audio_begin(old),b=mp_host_audio_begin(old);
 assert(a&&b);assert(mp_host_audio_publish(a,stop,&ok));
 assert(mp_host_audio_control_lock(a));
 mp_host_retire_all();assert(mp_host_is_retired(old));assert(!mp_host_audio_begin(old));
 // 普通控制调用尚未归还锁：本轮跳过，不能假报停止或丢掉下轮 Stop。
 pthread_t busy;pthread_create(&busy,NULL,worker,NULL);
 for(int i=0;i<1000&&!scan_done;i++)usleep(1000);
 assert(scan_done);pthread_join(busy,NULL);
 assert(!stopped&&mp_host_audio_pending()==2); // a 活动，b 初始化在途。
 mp_host_audio_control_unlock(a);
 assert(!mp_host_audio_control_lock(a));
 assert(mp_host_audio_pending()==2); // BUILDING 不能冒充已经停止。
 block=true;pthread_t t;pthread_create(&t,NULL,worker,NULL);while(!entered)usleep(1000);
 unsigned long long fresh=mp_host_generation(),c=mp_host_audio_begin(fresh);
 assert(c&&mp_host_audio_publish(c,stop,&ok));
 assert(mp_host_audio_control_lock(c));mp_host_audio_control_unlock(c);
 assert(mp_host_audio_pending()==2); // 快照不能等待旧 Stop。
 block=false;pthread_join(t,NULL);assert(stopped==1&&mp_host_audio_pending()==1);
 assert(mp_host_audio_publish(b,stop,&fail));mp_host_stop_retired_audio();assert(mp_host_audio_pending()==1);
 assert(!mp_host_audio_remove(b,release_failed,&fail));assert(mp_host_audio_pending()==1);
 assert(mp_host_audio_remove(b,release,&fail));assert(mp_host_audio_pending()==0);
 // 已确认停止后清理失败仍保留槽，但不得把音频静止事实改回未知。
 assert(!mp_host_audio_remove(a,release_failed,&fail));assert(mp_host_audio_pending()==0);
 assert(mp_host_audio_remove(a,release,&ok));assert(!mp_host_audio_control_lock(a));
 unsigned long long ids[16];int n=0;while(n<16&&(ids[n]=mp_host_audio_begin(fresh)))n++;
 assert(n==15&&!mp_host_audio_begin(fresh));assert(!mp_host_audio_publish(a,stop,&ok));
 for(int i=0;i<n;i++)assert(mp_host_audio_remove(ids[i],release,&ok));
 assert(mp_host_audio_remove(c,release,&ok));
 assert(!mp_host_audio_remove(c,release,&ok));
 assert(mp_host_generation()==fresh);mp_host_retire_all();assert(mp_host_generation()==fresh);
 puts("PASS 音频代隔离、忙控制重试、在途初始化、阻塞停止、失败保留、上限与过期 token");
}
