"""编译真实 OHAudio 数据回调，验证正常音频和退休前后竞争；平台为替身。"""
from pathlib import Path
import re, subprocess, sys, tempfile
root = Path(__file__).resolve().parents[3]
source = (Path(sys.argv[1]) / 'audio/out/ao_ohaudio.c').read_text()
match = re.search(r'^static OH_AudioData_Callback_Result audio_on_write_callback\(.*?^\}', source, re.M | re.S)
assert match
code = r'''
#include "host_recovery.h"
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#define AF_FORMAT_U8 1
#define AUDIO_DATA_CALLBACK_RESULT_VALID 0
#define AUDIOSTREAM_SUCCESS 0
#define MP_TIME_MS_TO_NS(v) ((int64_t)(v)*1000000)
#define MP_TIME_S_TO_NS(v) ((int64_t)(v)*1000000000)
#define MPMIN(a,b) ((a)<(b)?(a):(b))
#define MPCLAMP(v,lo,hi) MPMIN(((v)>(lo)?(v):(lo)),hi)
typedef int OH_AudioData_Callback_Result;
typedef int OH_AudioStream_Result;
typedef int OH_AudioRenderer;
struct priv {unsigned long long recovery_generation;int64_t written_frames,last_query,frame_position,frame_timestamp,queued_frames;bool timestamp_valid;};
struct ao {struct priv*priv;int format,sstride,samplerate;};
static bool retire_read,retire_query;
static int reads,queries;
int64_t mp_time_ns(void){return 1000000000;}
int OH_AudioRenderer_GetAudioTimestampInfo(OH_AudioRenderer*r,int64_t*position,int64_t*stamp){
 (void)r;queries++;*position=0;*stamp=999000000;if(retire_query)mp_host_retire_all();return 0;
}
void ao_read_data(struct ao*a,void**data,int samples,int64_t end,void*unused,bool b,bool c){
 (void)end;(void)unused;(void)b;(void)c;reads++;memset(*data,37,samples*a->sstride);
 if(retire_read)mp_host_retire_all();
}
/* CALLBACK */
int main(int argc,char**argv){
 assert(argc==2);const char*mode=argv[1];
 struct priv p={.recovery_generation=mp_host_generation()};struct ao a={&p,0,2,48000};
 unsigned char bytes[32];memset(bytes,99,sizeof(bytes));
 bool before=!strcmp(mode,"retired")||!strcmp(mode,"retired-u8");
 if(!strcmp(mode,"retired-u8"))a.format=AF_FORMAT_U8;
 if(before)mp_host_retire_all();
 retire_read=!strcmp(mode,"during-read");retire_query=!strcmp(mode,"during-query");
 if(!strcmp(mode,"fresh")){mp_host_retire_all();p.recovery_generation=mp_host_generation();}
 assert(audio_on_write_callback(NULL,&a,bytes,sizeof(bytes))==AUDIO_DATA_CALLBACK_RESULT_VALID);
 bool silence=before||retire_read||retire_query;
 for(unsigned i=0;i<sizeof(bytes);i++)assert(bytes[i]==(silence?(a.format==AF_FORMAT_U8?128:0):37));
 assert(reads==(before||retire_query?0:1));assert(queries==(before?0:1));
 if(silence){int old=reads;audio_on_write_callback(NULL,&a,bytes,sizeof(bytes));assert(reads==old);}
}
'''.replace('/* CALLBACK */', match[0])
with tempfile.TemporaryDirectory() as d:
    path = Path(d)
    (path/'test.c').write_text(code)
    subprocess.run(['clang','-std=c11','-pthread','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-I'+str(root/'native/mpv'),
                    str(path/'test.c'),str(root/'native/mpv/host_recovery.c'),'-o',str(path/'test')],check=True)
    for case in ['normal','retired','retired-u8','during-read','during-query','fresh']:
        subprocess.run([str(path/'test'),case],check=True,timeout=5)
        print(case, 'PASS', flush=True)
