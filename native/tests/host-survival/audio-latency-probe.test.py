"""真实诊断片段必须从已加载音频库取符号，覆盖局部作用域和接口缺失。"""
from pathlib import Path
import subprocess,tempfile,sys
s=(Path(sys.argv[1])/'audio/out/ao_ohaudio.c').read_text()
start=s.index('    // 仅诊断：API23');end=s.index('    MP_WARN(ao,"AUDIO_START_CALL',start)
code=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
typedef int OH_AudioRenderer;
#define RTLD_DEFAULT ((void*)0)
#define RTLD_NOW 2
#define RTLD_NOLOAD 4
#define MP_WARN(...) ((void)0)
static int handle,renderer,calls,opens,closes;static bool missing;
static int query(OH_AudioRenderer*r,int kind,int32_t*out){assert(r==&renderer);assert(kind==calls%3);calls++;*out=80;return kind==1?-1:0;}
static void*dlopen(const char*name,int flags){assert(strstr(name,"libohaudio.so"));assert(flags&RTLD_NOLOAD);opens++;return &handle;}
static void*dlsym(void*h,const char*name){assert(!strcmp(name,"OH_AudioRenderer_GetLatency"));return h==&handle&&!missing?(void*)query:0;}
static int dlclose(void*h){assert(h==&handle);closes++;return 0;}
struct priv{OH_AudioRenderer*renderer;unsigned long long recovery_token;};
static void probe(struct priv*p){(void)p;
/* BLOCK */
}
int main(){struct priv p={&renderer,257};probe(&p);assert(calls==3&&opens==1&&closes==1);missing=true;probe(&p);assert(calls==3&&opens==2&&closes==2);}
'''.replace('/* BLOCK */',s[start:end])
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(code);subprocess.run(['clang','-std=c11',str(p/'test.c'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
print('PASS 已加载局部音频库查询/接口缺失/查询错误保持诊断性质')
