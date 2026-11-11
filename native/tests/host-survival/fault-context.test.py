"""编译实际 mpv 加载与 OHCodec 故障入口；模拟当前 B、保留旧帧 A 的竞争。"""
from pathlib import Path
import re,subprocess,sys,tempfile
root=Path(__file__).resolve().parents[3]
mpv=Path(sys.argv[1])
def function(file,name):
 s=(mpv/file).read_text()
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\n\{.*?^\}',s,re.M|re.S)
 assert m,name
 return m[0]
code=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#include <setjmp.h>
#include <pthread.h>
#include "host_recovery_api.h"
#define MPV_ERROR_INVALID_PARAMETER -4
#define MPV_ERROR_GENERIC -20
#define MPV_EVENT_CLIENT_MESSAGE 16
struct mpv_global {atomic_ullong host_session_id;atomic_ullong host_load_generation;void*client_api;};
struct MPContext {struct mpv_global*global;};
typedef struct mpv_handle {struct MPContext*mpctx;void*log;} mpv_handle;
struct mp_cmd {uint64_t host_load_generation;};
static uint64_t queued_generation;static bool fail_parse;
static struct mp_cmd parsed;
struct mp_cmd*mp_input_parse_cmd_strv(void*log,const char**args){(void)log;(void)args;return fail_parse?NULL:&parsed;}
int run_async_cmd(mpv_handle*ctx,uint64_t ud,struct mp_cmd*cmd){(void)ctx;assert(ud==cmd->host_load_generation);queued_generation=ud;return 0;}
struct mp_image {uint64_t host_session_id,host_load_generation;};
struct ohcodec_priv {bool isolated;};
struct ra_hwdec {struct ohcodec_priv*priv;struct mpv_global*global;};
struct ohcodec_mapper_priv {struct mp_image*last_src;};
struct ra_hwdec_mapper {struct ra_hwdec*owner;struct ohcodec_mapper_priv*priv;struct mp_image*src;};
typedef struct {int num_args;const char**args;} mpv_event_client_message;
static jmp_buf escaped;
static uint64_t observed_session,observed_load;static int observed_scope;
void mp_ohcodec_terminal_enter_context(int error,int stage,uintptr_t owner,uint64_t session,uint64_t load){
 assert(error==-7&&stage==2&&owner);observed_session=session;observed_load=load;observed_scope=2;longjmp(escaped,1);
}
void mp_client_broadcast_critical(void*api,int kind,mpv_event_client_message*event){
 assert(api&&kind==16&&event->num_args==5);assert(!strcmp(event->args[0],"vidall-ohcodec-quarantined"));
 assert(!strcmp(event->args[1],"2")&&!strcmp(event->args[2],"-7"));
 observed_session=strtoull(event->args[3],NULL,10);observed_load=strtoull(event->args[4],NULL,10);observed_scope=1;longjmp(escaped,1);
}
/* FUNCTIONS */
int main(void){
 struct mpv_global global={.client_api=(void*)1};struct MPContext core={&global};mpv_handle client={&core,NULL};
 const char*args[]={"loadfile","private-url","replace",NULL};
 assert(mpv_host_loadfile_async(&client,4,17,args)==0&&queued_generation==4);
 assert(atomic_load(&global.host_session_id)==17);
 assert(mpv_host_loadfile_async(&client,5,18,args)<0&&queued_generation==4);
 assert(mpv_host_loadfile_async(&client,0,17,args)<0);
 fail_parse=true;assert(mpv_host_loadfile_async(&client,5,17,args)<0);fail_parse=false;
 assert(mpv_host_loadfile_async(&client,5,17,args)==0&&queued_generation==5);
 struct mp_image old={17,4},newer={17,5},foreign={99,4};
 struct ohcodec_priv owner={true};struct ra_hwdec hw={&owner,&global};
 struct ohcodec_mapper_priv priv={&old};struct ra_hwdec_mapper mapper={&hw,&priv,&newer};
 atomic_store(&global.host_load_generation,5);
 if(!setjmp(escaped))ohcodec_mapper_fault(&mapper,-7,2);
 assert(observed_scope==1&&observed_session==17&&observed_load==4);
 priv.last_src=NULL;if(!setjmp(escaped))ohcodec_mapper_fault(&mapper,-7,2);
 assert(observed_session==0&&observed_load==0);
 priv.last_src=&foreign;if(!setjmp(escaped))ohcodec_mapper_fault(&mapper,-7,2);
 assert(observed_session==0&&observed_load==0);
 owner.isolated=false;priv.last_src=&old;if(!setjmp(escaped))ohcodec_mapper_fault(&mapper,-7,2);
 assert(observed_scope==2&&observed_session==17&&observed_load==4);
}
'''.replace('/* FUNCTIONS */',function('player/client.c','mpv_host_loadfile_async')+'\n'+function('video/out/hwdec/hwdec_ohcodec.c','ohcodec_mapper_fault'))
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(code)
 subprocess.run(['clang','-std=c11','-pthread','-Wall','-Wextra','-Werror','-I'+str(root/'native/mpv'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=5)
print('PASS 加载命令身份、切集旧帧、候选帧拒绝补猜、跨实例拒绝和全局故障关联')
