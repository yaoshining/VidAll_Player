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
#include "host_recovery.h"
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
typedef int OH_AudioStream_State;
typedef int OH_AudioStream_Result;
typedef struct {int state;int starts,pauses,stops,flushes;int failed;} OH_AudioRenderer;
#define AUDIOSTREAM_SUCCESS 0
#define AUDIOSTREAM_STATE_PREPARED 1
#define AUDIOSTREAM_STATE_RUNNING 2
#define AUDIOSTREAM_STATE_PAUSED 3
#define AUDIOSTREAM_STATE_STOPPED 4
#define AUDIOSTREAM_STATE_RELEASED 5
int OH_AudioRenderer_GetCurrentState(OH_AudioRenderer*r,int*s){*s=r->state;return 0;}
int OH_AudioRenderer_Stop(OH_AudioRenderer*r){r->stops++;if(r->failed)return -1;r->state=4;return 0;}
int OH_AudioRenderer_Start(OH_AudioRenderer*r){r->starts++;r->state=2;return 0;}
int OH_AudioRenderer_Pause(OH_AudioRenderer*r){r->pauses++;r->state=3;return 0;}
int OH_AudioRenderer_Flush(OH_AudioRenderer*r){r->flushes++;return 0;}
struct priv {OH_AudioRenderer*renderer;unsigned long long recovery_token;int last_query;};
struct ao {struct priv*priv;};
static void reset_timing(struct priv*p){p->last_query=0;}
/* METHODS */
int main(void){
 OH_AudioRenderer r={.state=1};struct priv p={.renderer=&r};struct ao a={.priv=&p};
 p.recovery_token=mp_host_audio_begin(mp_host_generation());
 assert(mp_host_audio_publish(p.recovery_token,stop_for_recovery,&r));
 start(&a);assert(r.starts==1);set_pause(&a,true);assert(r.pauses==1);
 set_pause(&a,false);assert(r.starts==2);reset(&a);assert(r.flushes==1);
 mp_host_retire_all();start(&a);assert(!set_pause(&a,false));reset(&a);
 assert(r.starts==2&&r.flushes==1);mp_host_stop_retired_audio();
 assert(r.stops==1&&r.state==4&&mp_host_audio_pending()==0);
 OH_AudioRenderer prepared={.state=1};assert(stop_for_recovery(&prepared)==0&&prepared.stops==0);
 OH_AudioRenderer failed={.state=2,.failed=1};assert(stop_for_recovery(&failed)!=0);
}
'''.replace('/* METHODS */','\n'.join(function(n) for n in ['stop_for_recovery','reset','set_pause','start']))
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(code)
 subprocess.run(['cc','-std=c11','-pthread','-Wall','-Werror','-I'+str(root/'native/mpv'),str(p/'test.c'),str(root/'native/mpv/host_recovery.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=5)
print('PASS 实际 OHAudio 停止、禁止旧代启动、正常暂停恢复和失败状态')
