"""编译 mpv 的故障通知生产函数，验证满队列、首故障保留和 owner 隔离。"""
import argparse, re, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('mpv',type=Path);a=p.parse_args()
s=(a.mpv/'player/client.c').read_text()
def function(name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\n\{.*?^\}',s,re.M|re.S)
 assert m,'缺少可靠故障通知函数 '+name
 return m[0]
functions='\n'.join(function(n) for n in ['mp_client_broadcast_critical','gen_critical_event'])
wait=function('mpv_wait_event')
assert wait.index('gen_critical_event(ctx)')<wait.index('ctx->choked'), '故障必须优先于满队列处理'
assert 'mp_client_broadcast_critical(' in (a.mpv/'video/out/hwdec/hwdec_ohcodec.c').read_text()
program=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
typedef pthread_mutex_t mp_mutex;
#define mp_mutex_lock pthread_mutex_lock
#define mp_mutex_unlock pthread_mutex_unlock
typedef struct mpv_event { int event_id; void *data; } mpv_event;
typedef struct { int num_args; const char **args; } mpv_event_client_message;
struct mpv_handle { mp_mutex lock; mpv_event critical_event; mpv_event *cur_event; int wakes; int max_events, num_events; bool choked; };
struct mp_client_api { mp_mutex lock; struct mpv_handle **clients; int num_clients; };
static void *talloc_steal(void *parent,void *data) { (void)parent; return data; }
static void wakeup_client(struct mpv_handle *c) { c->wakes++; }
static void dup_event_data(mpv_event *e) {
 mpv_event_client_message *s=e->data,*d=calloc(1,sizeof(*d));
 d->num_args=s->num_args;d->args=calloc(d->num_args,sizeof(char*));
 for(int n=0;n<d->num_args;n++) d->args[n]=strdup(s->args[n]);
 e->data=d;
}
/* FUNCTIONS */
static void drop(mpv_event *e) {
 mpv_event_client_message *m=e->data;
 for(int n=0;n<m->num_args;n++) free((void*)m->args[n]);
 free(m->args);free(m);e->data=NULL;
}
int main(void) {
 mpv_event out={0},other={0};
 struct mpv_handle c={.lock=PTHREAD_MUTEX_INITIALIZER,.cur_event=&out,.max_events=1,.num_events=1,.choked=true};
 struct mpv_handle d={.lock=PTHREAD_MUTEX_INITIALIZER,.cur_event=&other};
 struct mpv_handle *list[]={&c};
 struct mp_client_api api={.lock=PTHREAD_MUTEX_INITIALIZER,.clients=list,.num_clients=1};
 char stage[]="3",error[]="-4";const char *args[]={"vidall-ohcodec-quarantined",stage,error};
 mpv_event_client_message msg={3,args};
 mp_client_broadcast_critical(&api,16,&msg);
 stage[0]='9';error[1]='9';
 mp_client_broadcast_critical(&api,16,&msg);
 assert(c.critical_event.event_id==16 && c.wakes>0);
 assert(c.num_events==1 && c.choked);
 assert(!gen_critical_event(&d));
 assert(gen_critical_event(&c));
 mpv_event_client_message *got=out.data;
 assert(out.event_id==16 && !strcmp(got->args[1],"3") && !strcmp(got->args[2],"-4"));
 assert(!gen_critical_event(&c));
 drop(&out);
 pthread_mutex_destroy(&c.lock);pthread_mutex_destroy(&d.lock);pthread_mutex_destroy(&api.lock);
}
'''.replace('/* FUNCTIONS */',functions)
with tempfile.TemporaryDirectory() as td:
 path=Path(td);(path/'test.c').write_text(program)
 subprocess.run(['cc','-std=gnu11','-pthread','-Wall','-Werror','-fsanitize=address,undefined',str(path/'test.c'),'-o',str(path/'test')],check=True)
 subprocess.run([str(path/'test')],check=True,timeout=5)
print('满队列故障投递、首次上下文保留、独立 owner 和消费后清空通过')
